import pandas as pd
import numpy as np
import sys
import os
import math
import json
import importlib.util
import argparse
import inspect
import time
VDS_MARGIN_DEFAULT = 0.01  # 20 mV safety margin

def read_json_to_dict(filepath):
    """
    Reads a JSON file and returns it as a dictionary.
    Returns an empty dict {} if the file doesn't exist or is invalid.
    """
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        return {}

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{filepath}'.Check format.")
        return {}
    except Exception as e:
        print(f"Error reading file: {e}")
        return {}
# ==============================================================================
# 1. CONFIGURATION & DEFAULTS
# ==============================================================================
DEFAULT_SPECS_FILE = "specs_5T.json"

class LUTLoader:
    def __init__(self, nmos_path, pmos_path, use_cache=True):
        """ 
        Loads LUTs. Uses a binary cache (.pkl) to speed up subsequent loads.
        """
        self.nmos_db = self._load_with_cache(nmos_path, use_cache)
        self.pmos_db = self._load_with_cache(pmos_path, use_cache)
        
        print(f"? LUTs Ready | NMOS: {len(self.nmos_db)} rows | PMOS: {len(self.pmos_db)} rows")

    def _load_with_cache(self, csv_path, use_cache):
        if not os.path.exists(csv_path):
            print(f"? Error: LUT file not found: {csv_path}")
            sys.exit(1)

        cache_path = os.path.splitext(csv_path)[0] + ".pkl"

        if use_cache and os.path.exists(cache_path):
            csv_mtime = os.path.getmtime(csv_path)
            cache_mtime = os.path.getmtime(cache_path)
            
            if cache_mtime > csv_mtime:
                try:
                    return pd.read_pickle(cache_path)
                except Exception:
                    print("  ? Cache corrupted. Reloading from CSV.")

        print(f"  Parsing CSV (First Run): {csv_path}...")
        df = pd.read_csv(csv_path)
        
        # Optimize & Sort (Critical for binary search: L primary, gmid secondary)
        df = df.sort_values(by=['L', 'gmid']).reset_index(drop=True)
        
        if use_cache:
            try:
                df.to_pickle(cache_path)
                print(f"  ? Cache saved: {cache_path}")
            except Exception as e:
                print(f"  ? Could not save cache: {e}")
                
        return df

    def get_sized_batch(self, dev_type, L_target, gmid_targets, I_drain_targets, optimize=False):
        """
        Vectorized sizing with robust column scaling.
        """
        # 1. Select Database
        df = self.nmos_db if dev_type == 'nmos' else self.pmos_db
        
        # 2. Filter by Length (L)
        subset = df[np.isclose(df['L'], L_target, atol=1e-9)]
        if subset.empty:
             unique_Ls = df['L'].unique()
             closest_L = unique_Ls[np.abs(unique_Ls - L_target).argmin()]
             subset = df[np.isclose(df['L'], closest_L, atol=1e-8)]

        # 3. Lookup for GMID, optionally increasing gm/id until sat condition is met
        gmid_vals = subset['gmid'].values
        target_gmids = np.array(gmid_targets, dtype=float)
        vds_margin = VDS_MARGIN_DEFAULT
        selected_rows = []

        for target_gmid in target_gmids:
            # nearest-neighbor starting point
            idx = np.searchsorted(gmid_vals, target_gmid)
            idx = np.clip(idx, 0, len(gmid_vals) - 1)

            prev_idx = np.clip(idx - 1, 0, len(gmid_vals) - 1)
            err_curr = abs(gmid_vals[idx] - target_gmid)
            err_prev = abs(gmid_vals[prev_idx] - target_gmid)
            pick_idx = prev_idx if err_prev < err_curr else idx

            # if optimize is enabled, walk upward in gm/id until sat condition is met
            if optimize and 'vds' in subset.columns:
                found = False
                for j in range(pick_idx, len(subset)):
                    row = subset.iloc[j]
                    row_vdsat = abs(row['vdsat']) if 'vdsat' in subset.columns else abs(2.0 / row['gmid'])

                    if dev_type == 'nmos':
                        sat_ok = row['vds'] >= (row_vdsat + vds_margin)
                    else:
                        sat_ok = abs(row['vds']) >= (row_vdsat + vds_margin)

                    if sat_ok:
                        pick_idx = j
                        found = True
                        break
                # if nothing found, keep original nearest row

            selected_rows.append(subset.iloc[pick_idx])

            rows = pd.DataFrame(selected_rows).reset_index(drop=True)
        
        # 5. Scale Parameters
        # Calculate Multiplier M (W_needed / W_simulated)
        I_targets = np.array(I_drain_targets, dtype=float)
        id_lut = rows['id'].abs().replace(0, 1e-12).values
        M = np.abs(I_targets) / id_lut
        M = np.where(M < 0.1, 1.0, M)
        # Scale Geometry
        rows['W'] = rows['W'].values * M

        # Scale Currents
        if 'id_raw' in rows.columns:
            rows['id_raw'] = rows['id_raw'].values * M
        
        # Set the final ID to the exact target requested
        rows['id'] = np.abs(I_targets)
        
        # Scale Dependent Parasitics (Multiply by M)
        scale_cols = [
            'gm', 'gds', 'gmb', 'id_raw', 'BETA_effective',
            # External Capacitances
            'cgg', 'cgd', 'cgs', 'cdd', 'cds', 'cbd', 'cbs', 'cbg', 'cdg',
            # Intrinsic Capacitances
            'cgg_int', 'cgd_int', 'cgs_int', 'cbg_int', 'cbd_int', 
            'cbs_int', 'cdg_int', 'cdd_int', 'cds_int'
        ]
        
        for col in scale_cols:
            if col in rows.columns:
                rows[col] = rows[col].values * M

        # Handle Voltages (Pass-through, No Scaling)
        if 'vgs' in rows.columns:
            rows['vgs'] = rows['vgs'].abs().values
        else:
            rows['vgs'] = 0.0

        if 'vdsat' in rows.columns:
            rows['vdsat'] = rows['vdsat'].abs().values
        else:
            # Fallback approximation for strong inversion
            rows['vdsat'] = (2.0 / rows['gmid']).values

        # --- Saturation check using LUT vds vs vdsat (with margin) ---
        # Note: LUT 'vds' must exist and be consistent with how LUT was generated.
        vds_margin = VDS_MARGIN_DEFAULT

        if 'vds' in rows.columns:
            if dev_type == 'nmos':
                # NMOS: vds >= vdsat + margin
                rows['sat_ok'] = rows['vds'].values >= (rows['vdsat'].values + vds_margin)
                rows['sat_margin'] = rows['vds'].values - rows['vdsat'].values
            else:
                # PMOS: abs(vds) >= abs(vdsat) + margin
                rows['sat_ok'] = np.abs(rows['vds'].values) >= (np.abs(rows['vdsat'].values) + vds_margin)
                rows['sat_margin'] = np.abs(rows['vds'].values) - np.abs(rows['vdsat'].values)
        else:
            rows['sat_ok'] = False
            rows['sat_margin'] = np.nan


        return rows.to_dict('records')

class CircuitSizer:
    def __init__(self, lut_loader):
        self.loader = lut_loader

    def check_headroom(self, name, params, voltages):
        """ Checks Vds margin against Vdsat """
        if not voltages: return "N/A"
        Vd, Vs = voltages.get('Vd'), voltages.get('Vs')
        if Vd is None or Vs is None: return "Unknown"
        
        margin = abs(Vd - Vs) - params['vdsat']
        if margin < 0: return f"? SAT VIOLATION ({margin*1000:.0f}mV)"
        elif margin < 0.05: return f"? Low Margin ({margin*1000:.0f}mV)"
        return f"? {margin*1000:.0f}mV"

    def size_topology(self, device_specs, optimize=False):
        """
        Smart Sizer: Detects if input is Scalar (Legacy) or List (Sweep).
        """
        # 1. Detect Mode
        is_sweep = False
        sweep_len = 1
        
        for s in device_specs.values():
            if isinstance(s.get('gmid'), list) or isinstance(s.get('I'), list):
                is_sweep = True
                curr_len = len(s['gmid']) if isinstance(s.get('gmid'), list) else 1
                sweep_len = max(sweep_len, curr_len)

        # 2. Prepare Data Structure
        results = [{} for _ in range(sweep_len)]

        if not is_sweep:
            print(f"\n{'Device':<10} | {'gm/id':<6} | {'W (um)':<8} | {'Vgs':<8} | {'Vdsat':<8} | {'Headroom'}")
            print("-" * 80)

        # 3. Iterate Devices
        for name, spec in device_specs.items():
            # Broadcast scalars to match sweep length
            gmid_in = spec['gmid'] if isinstance(spec.get('gmid'), list) else [spec['gmid']]
            I_in    = spec['I']    if isinstance(spec.get('I'), list)    else [spec['I']]

            if len(gmid_in) < sweep_len: gmid_in = gmid_in * (sweep_len // len(gmid_in)) + gmid_in[:sweep_len % len(gmid_in)]
            if len(I_in) < sweep_len:    I_in = I_in * (sweep_len // len(I_in)) + I_in[:sweep_len % len(I_in)]

            # CALL BATCH SIZER
            #sized_batch = self.loader.get_sized_batch(spec['type'], spec['L'], gmid_in, I_in)
            sized_batch = self.loader.get_sized_batch(spec['type'], spec['L'], gmid_in, I_in, optimize=optimize)
            # Distribute results
            for i in range(sweep_len):
                results[i][name] = sized_batch[i]
                
            # Legacy Print
            if not is_sweep:
                p = sized_batch[0]
                hr = self.check_headroom(name, p, spec.get('_terminals'))
                #print(f"{name:<10} | {p['gmid']:<6.1f} | {p['W']*1e6:<8.2f} | {p['vgs']:<8.3f} | {p['vdsat']:<8.3f} | {hr}")
                print(f"{name:<10} | {p['gmid']:<6.1f} | {p['W']*1e6:<8.2f} | {p['vgs']:<8.3f} | {p['vdsat']:<8.3f} | {hr} | sat_ok={p.get('sat_ok','?')}")
        #for k,v in results[0].items():
        #    print("\n\n",k,v)       
        #print(f"CHECK THE FINAL results {results}")
        if is_sweep:
            print(f"? Batch Sizing Complete: {sweep_len} configurations generated.")
            return results 
        else:
            return results[0]
        

# ==============================================================================
# 2. DYNAMIC MODEL LOADING
# ==============================================================================
def load_performance_model(module_path):
    """
    Loads the performance model from a file, ignoring the JSON class name.
    It automatically looks for 'PerformanceModel' or the first valid class with a 'compute' method.
    """
    if not module_path or not os.path.exists(module_path):
        print(f"? Warning: Model file not found or not specified: {module_path}")
        return None

    # 1. Load the module dynamically
    spec = importlib.util.spec_from_file_location("dynamic_model", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dynamic_model"] = module
    spec.loader.exec_module(module)

    # 2. HARD FORCE: Look specifically for 'PerformanceModel'
    if hasattr(module, "PerformanceModel"):
        print(f"? Loaded class 'PerformanceModel' from {module_path}")
        return getattr(module, "PerformanceModel")()

    # 3. FALLBACK: detailed search (if you renamed it to something else)
    # This finds ANY class in the file that has a 'compute' method
    import inspect
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ == "dynamic_model" and hasattr(obj, 'compute'):
            print(f"?? 'PerformanceModel' not found. Using detected class '{name}' instead.")
            return obj()

    print(f"? Error: No valid model class found in {module_path}. (Looking for 'PerformanceModel')")
    return None

# ==============================================================================
# 3. MAIN FLOW
# ==============================================================================
def run_general_flow(args, verify = False):
    # --- SETUP ---
    NMOS_FILE = "Testbenches/nmos_lut.csv"
    PMOS_FILE = "Testbenches/pmos_lut.csv"
    
    if not os.path.exists(args.specs):
        print(f"? Error: Specs file '{args.specs}' not found.")
        sys.exit(1)

    with open(args.specs, 'r') as f: specs = json.load(f)

    loader = LUTLoader(NMOS_FILE, PMOS_FILE)
    sizer = CircuitSizer(loader)

    #print(f"? Sizing Topology: {specs['meta']['topology_name']}")
    
    if verify == False:   
        # --- SIZING ---
        # Smart function: Returns Dict (if scalar) or List[Dict] (if sweep)
        #sized_data = sizer.size_topology(specs['devices'])
        sized_data = sizer.size_topology(specs['devices'], optimize=args.optimize)

        # Standardize to list for simulation loop
        is_sweep = isinstance(sized_data, list)
        configs = sized_data if is_sweep else [sized_data]

    else:
        configs = read_json_to_dict(args.opjson)
        is_sweep = False
        configs = [configs] 
    #print(configs)    

 
    # --- SIMULATION ---
    # 1. Get model file path
    model_file = args.model if args.model else specs['meta'].get('model_file')
    
    # 2. Load Model (Robust Method)
    model = load_performance_model(model_file)

    final_output = []
    
    # Define fields to export
    export_fields = [
        'W', 'L', 'id', 'vgs', 'vds', 'vsb', 'vth', 'vdsat', 'gmid',
        'gm', 'gds', 'rds', 'gmb', 'Tox', 'GAMMA_effective', 'BETA_effective',
        'cgg', 'cgd', 'cgs', 'cdd', 'cds', 'cbd', 'cbs', 'cbg', 'cdg',
        'cgg_int', 'cgd_int', 'cgs_int', 'cbg_int', 'cbd_int', 
        'cbs_int', 'cdg_int', 'cdd_int', 'cds_int', 'id_raw', 'sat_ok', 'sat_margin'
    ]
 



    for i, config in enumerate(configs):
        # Format for Export
        # Extract only the fields that actually exist in your LUT data
        dev_out = {
            device_name: {k: v[k] for k in export_fields if k in v} 
            for device_name, v in config.items()
        }
        
        perf_out = {}
        if model:
            # Load testbench specs with safe defaults
            tb = specs.get('testbench', {})
            C_load = tb.get('C_load', 500e-15)
            Vdd = tb.get('Vdd', 1.0)
            Vss = tb.get('Vss', 0.0)
            Cc = tb.get('c0', 200e-15)
            Rc = tb.get('r0', 2500)
            print(f"Running equation based simulator with Cload = {C_load}, Vdd = {Vdd}, Vss = {Vss}, Cc={Cc}, Rc = {Rc}")
            try:
                # Call compute with all required arguments
                start_time = time.time()
                res = model.compute(config, C_load=C_load, Vdd=Vdd, Vss=Vss, c0=Cc, r0 = Rc)
                print(f'Finished evaluation in {time.time() - start_time}')
                # Clean NaNs/Infs for JSON compatibility
                perf_out = {k: (str(v) if isinstance(v, float) and (math.isinf(v) or math.isnan(v)) else v) for k,v in res.items()}
            #except Exception as e:
            #    perf_out = {"error": str(e)}
            #    print(f"?? Simulation error in config {i}: {e}")
            
            except Exception as e:
                print(f"Simulation error in config {i}: {e}", flush=True)
                import sys
                sys.exit(1)  

        # Structure calculation results
        if is_sweep:
            final_output.append({"config_id": i, "devices": dev_out, "performance": perf_out})
        else:
            final_output.append({"devices": dev_out, "performance": perf_out})

    # --- EXPORT (PRESERVE ORIGINAL STRUCTURE) ---
    if not is_sweep:
        # SINGLE MODE: Exact match to original structure
        export_data = {
            "meta": specs['meta'],
            "devices": final_output[0]['devices'],
            "performance": final_output[0]['performance']
        }
    else:
        # SWEEP MODE: New structure for lists
        export_data = {
            "meta": specs['meta'],
            "sweep_results": final_output
        }

    # Save Main Output
    out_file = args.out if args.out else "output.json"
    with open(out_file, 'w') as f:
        json.dump(export_data, f, indent=4)
    print(f"? Done. Saved to {out_file}")

    # Save Model Predictions (For Feedback Loop)
    if args.dump_model_preds:
        # If sweep, we might need a different feedback strategy, but for now dump matching structure
        pred_data = {"performance": export_data.get('performance', export_data.get('sweep_results'))}
        with open(args.dump_model_preds, 'w') as f:
            json.dump(pred_data, f, indent=4)
        print(f"? Model predictions saved to {args.dump_model_preds}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--specs", default=DEFAULT_SPECS_FILE)
    parser.add_argument("--model")
    parser.add_argument("--out")
    parser.add_argument("--dump_model_preds")
    parser.add_argument('--verify', action='store_true', help='Enable verification mode')
    parser.add_argument('--opjson', default='op_results.json', help='Path to the extracted op parameters json')
    parser.add_argument('--optimize', action='store_true', help='Increase gm/id from requested value until LUT row satisfies vds > vdsat + margin')
    args = parser.parse_args()
    
    run_general_flow(args, verify = args.verify)
