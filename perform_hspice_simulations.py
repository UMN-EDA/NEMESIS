import os
import re
import subprocess
import csv
import glob
import concurrent.futures
import threading
import time
import datetime
import json
import argparse
import shlex
# ==============================================================================
# 1. GLOBAL CONFIGURATION & DEFAULTS
# ==============================================================================

# Default placeholders (will be overwritten by argparse in main)
HSPICE_CMD = "hspice"
HSPICE_FLAGS = []
MAX_PARALLEL_TESTS = 4
PARAMS_FILE = "Testbenches/design_params.sp"
DUT_FILE = "Testbenches/cm_ota.sp"
DELETE_TEMP_FILES = False
CSV_LOG_FILE = "design_sweep_log.csv"
DUT_WRAPPER_FILE = "Testbenches/dut_wrapper.sp"
RUN_DIR = "."
# Global Parameters (Base Defaults)
GLOBAL_PARAMS = {

}

print_lock = threading.Lock()
def safe_print(msg):
    with print_lock:
        print(msg)

def configure_testbench_paths(testbench_dir):
    for test_config in TEST_PLAN.values():
        test_config["file"] = os.path.join(
            testbench_dir,
            os.path.basename(test_config["file"])
        )

def update_dut_wrapper(testbench_dir):
    wrapper_file = os.path.join(testbench_dir, "dut_wrapper.sp")

    with open(wrapper_file, "r") as f:
        content = f.read()

    content = re.sub(
        r'\.include\s+["\']?[^"\'\s]+["\']?',
        f'.include "{DUT_FILE}"',
        content,
        flags=re.IGNORECASE,
        count=1
    )

    with open(wrapper_file, "w") as f:
        f.write(content)
# ==============================================================================
# 2. TEST PLAN
# ==============================================================================

TEST_PLAN = {
    
    "icmr": {
        "file": "Testbenches/tb_icmr.sp",
        "local_params": { "VCM_START": 0, "VCM_STOP": "'VDD'", "VCM_STEP": "10m", "VDS_SAFETY": 0.02 },
        "link_params": {},
        "extract_map": { "icmr_min": "ICMR Min (V)", "icmr_max": "ICMR Max (V)" },
        "defaults": { "icmr_min": 0.3, "icmr_max": 0.9 }
    },
    "ocmr": {
        "file": "Testbenches/tb_ocmr.sp",
        "local_params": { "VDS_SAFETY": 0.02, "VDIFF_RANGE": 0.05, "VDIFF_STEP": "50u" },
        "link_params": { "VCM_MID": "icmr_mid" },
        "extract_map": { "ocmr_min": "Output Swing Min (V)", "ocmr_max": "Output Swing Max (V)" }
    },
    "ac": {
        "file": "Testbenches/tb_ac.sp",
        "local_params": { "FMIN": "1", "FMAX": "100G" },
        "link_params": { "VCM": "icmr_mid" },
        "extract_map": { "a0_db": "DC Gain (dB)", "ugf": "UGF (Hz)", "pm": "Phase Margin (deg)", "gm_db": "Gain Margin (dB)", "bw_3db": "Bandwidth 3dB (Hz)" }
    },
    "op":{
        "file": "Testbenches/tb_op_temp.sp",
        "link_params": { "VCM": "icmr_mid" }
    },
    "power": {
        "file": "Testbenches/tb_power.sp",
        "local_params": {},
        "link_params": { "VCM": "icmr_mid" },
        "extract_map": {
            "p_total_w": "Power (Watts)"
        }
    },
    "noise": {
        "file": "Testbenches/tb_noise.sp",
        "local_params": {},
        "link_params": { "VCM_MID": "icmr_mid" },
        "extract_map": { "dens_10hz": "Input Noise @ 10Hz (V/sqrtHz)", "dens_1mhz": "Input Noise @ 1MHz (V/sqrtHz)", "rms_total": "Total Integrated Noise (Vrms)" }
    },
    "cmrr": {
        "file": "Testbenches/tb_cmrr.sp",
        "local_params": { "FMIN": "1", "FMAX": "100G", "V_OFFSET": "1m" },
        "link_params": { "VCM": "icmr_mid", "A0_DIFF_DB": "a0_db" },
        "extract_map": { "cmrr_db": "CMRR (dB)" }
    },
    "psrr_p": {
        "file": "Testbenches/tb_psrrp.sp",
        "local_params": { "FMIN": "1", "FMAX": "100G", "VOFF": "1m" },
        "link_params": { "VCM": "icmr_mid", "ADC_GAIN_DB": "a0_db" },
        "extract_map": { "psrr_plus_db": "PSRR+ (dB)" }
    },
    "psrr_n": {
        "file": "Testbenches/tb_psrrn.sp",
        "local_params": { "FMIN": "1", "FMAX": "100G", "VOFF": "1m" },
        "link_params": { "VCM": "icmr_mid", "ADC_GAIN_DB": "a0_db" },
        "extract_map": { "psrr_minus_db": "PSRR- (dB)" }
    },
    "slew": {
        "file": "Testbenches/tb_sr.sp",
        "local_params": { "VSTEP": "0.2" },
        "link_params": { "UGF_EST": "ugf_raw", "VCM": "icmr_mid" , "VICMR_MAX": "icmr_max", "VICMR_MIN": "icmr_min"},
        "extract_map": { "sr_pos_vus": "Slew Rate (+) (V/us)", "sr_neg_vus": "Slew Rate (-) (V/us)", "i_max_p": "Peak Output Current (A)" }
    }
}

STAGES = [
    ["icmr"],
    ["op", "ac", "ocmr", "power"], # "noise"
    ["cmrr", "psrr_p", "psrr_n", "slew"]
]

# ==============================================================================
# 3. HELPER FUNCTIONS
# ==============================================================================

def convert_spice_value(val_str):
    if not val_str or val_str.lower() == "failed": return "FAILED"
    suffixes = {
        't': 1e12, 'g': 1e9, 'meg': 1e6, 'x': 1e6,
        'k': 1e3, 'mil': 25.4e-6, 'm': 1e-3,
        'u': 1e-6, 'n': 1e-9, 'p': 1e-12,
        'f': 1e-15, 'a': 1e-18
    }
    try:
        val_str = val_str.strip().lower()
        for suffix, multiplier in sorted(suffixes.items(), key=lambda x: -len(x[0])):
            if val_str.endswith(suffix):
                try:
                    return float(val_str[:-len(suffix)]) * multiplier
                except ValueError:
                    continue
        return float(val_str)
    except ValueError:
        return val_str

def parse_lis_results(run_base_name):
    """
    Parses .lis file using string splitting.
    """
    results = {}
    lis_file = f"{run_base_name}.lis"
    
    # Wait briefly for file system sync
    time.sleep(0.1)
    
    if not os.path.exists(lis_file):
        return {}
    
    try:
        with open(lis_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            # Skip empty lines or standard comments
            if not line or line.startswith('*') or line.startswith('$'):
                continue
            
            if '=' in line:
                parts = line.split('=')
                # We need a Left side and a Right side
                if len(parts) >= 2:
                    # Get the Right-Hand Side (Value)
                    rhs = parts[1].strip()
                    
                    # SAFETY CHECK: If the right side is empty, skip this line.
                    if not rhs:
                        continue
                        
                    rhs_tokens = rhs.split()
                    if not rhs_tokens:
                        continue
                        
                    # Now it is safe to access [0]
                    val_part = rhs_tokens[0]
                    
                    # Get the Left-Hand Side (Key)
                    lhs_tokens = parts[0].strip().split()
                    if not lhs_tokens:
                        continue
                    key_part = lhs_tokens[-1] # Last word before '='
                    
                    # Validate key is alphanumeric/underscore (filters out weird text lines)
                    if re.match(r'^[a-zA-Z0-9_]+$', key_part):

                        clean_val = convert_spice_value(val_part)
                        #print(f"For {val_part} printing {clean_val}")
                        results[key_part.lower()] = clean_val

    except Exception as e:
        safe_print(f"      [ERR] Error reading .lis file: {e}")
        
    return results

# ==============================================================================
# 4. ENGINE
# ==============================================================================

def run_testbench(test_id, result_cache_snapshot):
    # Access global variables (which will be set by args in main)
    global DUT_FILE, PARAMS_FILE, DUT_WRAPPER_FILE, RUN_DIR
    
    test_config = TEST_PLAN[test_id]
    tb_file = test_config["file"]
    
    safe_print(f"[START] {test_id}...")
    
    if not os.path.exists(tb_file):
        safe_print(f"   [ERR] File {tb_file} not found. Skipping.")
        return {}, {}
    
    with open(tb_file, 'r') as f:
        original_lines = f.readlines()

    # 1. MERGE PARAMS
    params_to_set = {}
    for k, v in GLOBAL_PARAMS.items(): params_to_set[k] = v
    for k, v in test_config.get("local_params", {}).items(): params_to_set[k] = v
    for spice_param, cache_key in test_config.get("link_params", {}).items():
        if cache_key in result_cache_snapshot and result_cache_snapshot[cache_key] not in ["FAILED", "None"]:
            val = result_cache_snapshot[cache_key]
            if isinstance(val, float): val = f"{val:.6e}"
            params_to_set[spice_param] = val

    # 2. LINE REPLACEMENT
    new_lines = []
    updated_keys = set()
    for line in original_lines:
        if line.strip().lower().startswith(".param"):
            for k, v in params_to_set.items():
                regex = re.compile(r'\b(' + re.escape(k) + r')\s*=\s*(\'[^\']*\'|"[^"]*"|[^\s]+)', re.IGNORECASE)
                if regex.search(line):
                    line = regex.sub(f"{k}={v}", line)
                    updated_keys.add(k)
        new_lines.append(line)

    # 3. APPEND MISSING
    missing_params = []
    for k, v in params_to_set.items():
        if k not in updated_keys: missing_params.append(f".param {k}={v}")
            
    final_content = "".join(new_lines)
    if missing_params:
        block_str = "\n* --- PYTHON INJECTED PARAMS ---\n" + "\n".join(missing_params) + "\n"
        if ".end" in final_content.lower():
            final_content = re.sub(r'(\.end)', block_str + r'\1', final_content, flags=re.IGNORECASE, count=1)
        else:
            final_content += block_str

    # 4. INCLUDE & RUN

    def include_replacer(match):
        original_include = match.group(0)
        filename = match.group(1)
        base = os.path.basename(filename).lower()

        if "param" in base:
            return f'.include "{PARAMS_FILE}"'

        elif base == "dut_wrapper.sp":
            return f'.include "{DUT_WRAPPER_FILE}"'

        else:
            return original_include

    # Replaces using the smart function above
    #final_content = re.sub(r'\.include\s+["\'](.*?)["\']', include_replacer, final_content, flags=re.IGNORECASE)

    final_content = re.sub(
        r'\.include\s+["\']?([^"\'\s]+)["\']?',
        include_replacer,
        final_content,
        flags=re.IGNORECASE
    )
    # Write the dynamically generated testbench
    run_filename = os.path.join(RUN_DIR, f"run_{test_id}.sp")
    with open(run_filename, 'w') as f:
        f.write(final_content)

    outfile_base = os.path.join(RUN_DIR, f"run_{test_id}")
    cmd = [HSPICE_CMD] + [run_filename, "-o", outfile_base] + HSPICE_FLAGS
    safe_print(f"   [CMD] {shlex.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except Exception as e:
        safe_print(f"   [ERR] {test_id} HSPICE Failed: {e}")

    raw_results = parse_lis_results(outfile_base)
    
    if DELETE_TEMP_FILES:
        try:
            if os.path.exists(run_filename): os.remove(run_filename)
            for f in glob.glob(f"{outfile_base}.*"): os.remove(f)
        except OSError: pass
    
    local_report = {}
    defaults = test_config.get("defaults", {})
    extract_map = test_config.get("extract_map", {})

    for key, clean_name in extract_map.items():
        val = raw_results.get(key, "None")
        if val == "None" and key in defaults: val = defaults[key]
        if key in ["ugf", "bw_3db"] and isinstance(val, (int, float)): val = val
        local_report[clean_name] = val
        if val == "None": safe_print(f"        [FAIL] {test_id}: {clean_name} = None")

    safe_print(f"[DONE] {test_id}")
    return raw_results, local_report

# ==============================================================================
# 5. MAIN
# ==============================================================================

def main(args):
    # Update Globals from CLI Arguments
    configure_testbench_paths(args.testbench_dir)
    global DUT_FILE, CSV_LOG_FILE, HSPICE_CMD, PARAMS_FILE, DUT_WRAPPER_FILE, RUN_DIR
    DUT_FILE = os.path.abspath(args.dut)
    PARAMS_FILE = os.path.abspath(args.params)
    CSV_LOG_FILE = os.path.abspath(args.csv)
    HSPICE_CMD = args.cmd
    DUT_WRAPPER_FILE = os.path.abspath(args.wrapper)
    RUN_DIR = os.path.abspath(args.run_dir)
    os.makedirs(RUN_DIR, exist_ok=True)
    
    update_dut_wrapper(args.testbench_dir)
    print("=======================================================")
    print("      HSPICE PARALLEL CHARACTERIZATION SUITE")
    print("=======================================================")
    print(f"DUT: {DUT_FILE}")
    
    if not os.path.exists(DUT_FILE):
        print(f"CRITICAL: DUT file '{DUT_FILE}' not found.")
        return

    row_data = { "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") }
    row_data.update(GLOBAL_PARAMS)
    result_cache = {}
    start_time = time.time()

    for stage_idx, stage_tests in enumerate(STAGES):
        print(f"\n--- STAGE {stage_idx+1} START: {', '.join(stage_tests)} ---")
        
        # PRE-STAGE CHECKS
        if stage_idx == 1:
            if "icmr_mid" not in result_cache:
                v_min = result_cache.get("icmr_min")
                v_max = result_cache.get("icmr_max")
                if isinstance(v_min, (int, float)) and isinstance(v_max, (int, float)):
                    mid = (v_min + v_max) / 2.0
                    result_cache["icmr_mid"] = mid
                    print(f"   [RECOVERY] Calculated icmr_mid = {mid}")
                else:
                    result_cache["icmr_mid"] = 0.4
                    print(f"   [RECOVERY] Default icmr_mid = 0.4")

        cache_snapshot = result_cache.copy()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_TESTS) as executor:
            future_to_test = { executor.submit(run_testbench, tid, cache_snapshot): tid for tid in stage_tests }
            for future in concurrent.futures.as_completed(future_to_test):
                tid = future_to_test[future]
                try:
                    raw, report = future.result()
                    result_cache.update(raw)
                    row_data.update(report)
                except Exception as exc:
                    print(f"[CRASH] {tid}: {exc}")

        # POST-STAGE CALCS
        if "icmr" in stage_tests:
            v_min = result_cache.get("icmr_min", 0.3)
            v_max = result_cache.get("icmr_max", 0.9)
            if isinstance(v_min, (int,float)) and isinstance(v_max, (int,float)):
                mid = (v_min + v_max) / 2.0
                result_cache["icmr_mid"] = mid
                row_data["ICMR Mid (V)"] = mid
                print(f"   [CALC] ICMR Mid: {mid:.4f} V")

        if "ac" in stage_tests:
            if "ugf" in result_cache: result_cache["ugf_raw"] = result_cache["ugf"]

    print(f"\nDone in {time.time() - start_time:.2f}s.")
    
    # CSV WRITE
    csv_headers = ["Timestamp"] + list(GLOBAL_PARAMS.keys())
    for stage_tests in STAGES:
        for tid in stage_tests:
            if tid in TEST_PLAN:
                if "extract_map" in TEST_PLAN[tid]:
                    for cname in TEST_PLAN[tid]["extract_map"].values():
                        if cname not in csv_headers: csv_headers.append(cname)
        if "icmr" in stage_tests and "ICMR Mid (V)" not in csv_headers:
            csv_headers.append("ICMR Mid (V)")

    try:
        file_exists = os.path.exists(CSV_LOG_FILE)
        with open(CSV_LOG_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_headers, extrasaction='ignore')
            if not file_exists: writer.writeheader()
            writer.writerow(row_data)
        print(f"Results appended to {CSV_LOG_FILE}")
    except IOError as e:
        print(f"CSV Error: {e}")

    # ==========================================================================
    # JSON REPORT GENERATION
    # ==========================================================================
    json_report_file = args.report
    
    # Structure the data neatly for JSON
    json_output = {
        "timestamp": row_data.get("Timestamp", "N/A"),
        "global_parameters": {},
        "extracted_metrics": {}
    }

    # Separate globals and metrics
    global_keys = set(GLOBAL_PARAMS.keys())
    
    for key, val in row_data.items():
        if key == "Timestamp":
            continue
        if key in global_keys:
            json_output["global_parameters"][key] = val
        else:
            if isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf')):
                json_output["extracted_metrics"][key] = str(val)
            else:
                json_output["extracted_metrics"][key] = val

    try:
        with open(json_report_file, 'w') as f:
            json.dump(json_output, f, indent=4)
        print(f"JSON report saved to {json_report_file}")
    except IOError as e:
        print(f"JSON Report Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HSPICE Parallel Characterization Suite")
    
    # Argument definitions
    parser.add_argument("--dut", default="Testbenches/5t_ota.sp", help="Path to DUT SPICE file")
    parser.add_argument("--params", default="Testbenches/design_params.sp", help="Path to Design Params SPICE file")
    parser.add_argument("--csv", default="design_sweep_log.csv", help="Path to Output CSV Log")
    parser.add_argument("--report", default="hspice_simulation_report.json", help="Path to Output JSON Report")
    parser.add_argument("--cmd", default="hspice", help="HSPICE Command")
    parser.add_argument("--testbench-dir", default="Universal", help="Directory containing all TEST_PLAN testbench files")
    parser.add_argument("--wrapper", default="dut_wrapper.sp", help="Path to DUT wrapper SPICE file")
    parser.add_argument("--run-dir", default=".", help="Directory to store generated run_*.sp and HSPICE output files")
    args = parser.parse_args()
    
    main(args)
