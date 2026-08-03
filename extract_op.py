import re
import json
import os
import sys
import argparse

def parse_hspice_blocks_to_json(lis_file_path, output_json_path):
    """
    Parses an HSPICE .lis file with 'x ... y' data blocks.
    Maps extracted HSPICE parameters to user-friendly names using mapping_dict.
    """
    
    mapping_dict = {
        'lv1': 'L',
        'lv2': 'W',
        'lx2': 'vgs',
        'abslx2' : 'vgs', #PMOS only
        'lx3': 'vds',
        'abslx3': 'vds', #PMOS only
        'abslx1': 'vsb',
        'current': 'id',
        'absi': 'id', 
        'paramabsim1': 'id',   
        'lx7': 'gm',
        'lx8': 'gds',
        'lx9': 'gmb',
        'lx7maxabsi1e15': 'gmid',
        'lv9': 'vth',
        'paramabslv9': 'vth', #PMOS only
        'lv10': 'vdsat',
        'paramabslv10' : 'vdsat', #PMOS only
        'lx18': 'cgg_int',
        'lx19': 'cgd_int',
        'lx20': 'cgs_int',
        'lx21': 'cbg_int',
        'lx22': 'cbd_int',
        'lx23': 'cbs_int',
        'lx32': 'cdg_int',
        'lx33': 'cdd_int',
        'lx34': 'cds_int',
        'lx82': 'cgg',
        'lx83': 'cgd',
        'lx84': 'cgs',
        'lx85': 'cdd',
        'lx86': 'cds',
        'lx89': 'cbd',
        'lx90': 'cbs',
        'lx287': 'Tox',
        'lv22': 'GAMMA_effective',
        'lv21': 'BETA_effective',
        'lv13': 'rds'
    }

    if not os.path.exists(lis_file_path):
        print(f"Error: File '{lis_file_path}' not found.")
        return

    print(f"Reading {lis_file_path}...")
    results = {}
    device_finder = re.compile(r'\((.*?)\)')

    with open(lis_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line == 'x':
            i += 1
            while i < len(lines) and not lines[i].strip(): i += 1 
            main_headers = lines[i].strip().split()
            
            i += 1
            while i < len(lines) and not lines[i].strip(): i += 1 
            sub_headers = lines[i].strip().split()
            
            i += 1
            while i < len(lines) and not lines[i].strip(): i += 1 
            values = lines[i].strip().split()

            if len(main_headers) > 0 and (main_headers[0] in ['dummy_var', 'time']):
                current_mains = main_headers[1:]
                current_vals = values[1:]
                current_subs = sub_headers 
            else:
                current_mains = main_headers
                current_vals = values
                current_subs = sub_headers

            if len(current_mains) == len(current_vals) == len(current_subs):
                for k in range(len(current_mains)):
                    p_name_top = current_mains[k] 
                    p_name_sub = current_subs[k]  
                    val_str = current_vals[k]

                    device_name = "unknown"
                    final_param_name = p_name_top

                    if p_name_top.startswith("lx") or p_name_top.startswith("lv") or p_name_top == "current":
                        device_name = p_name_sub 
                        final_param_name = p_name_top
                    elif p_name_top == "param":
                        match = device_finder.search(p_name_sub)
                        if match:
                            parts = re.split(r'[\(\)]', p_name_sub)
                            for part in parts:
                                if "xu1" in part.lower(): 
                                    device_name = part
                                    break
                            if device_name == "unknown" and match:
                                device_name = match.group(1)
                        final_param_name = p_name_sub 

                    device_name = device_name.strip()
                    
                    clean_dev_id = device_name.lower().replace('xu1.', '')
                    lookup_key = (final_param_name.lower().replace(' ', ''))
                    
                    #print(f"Device name {device_name}")
                    final_param_name = re.sub(r'[^a-zA-Z0-9]', '', final_param_name).lower().replace('xu1', '').replace(device_name.split('.')[-1], '')
                    
                    mapped_name = mapping_dict.get(final_param_name, final_param_name)
                    #print(f"Name for {lookup_key} with {final_param_name} is {mapped_name}")
                    device_name = device_name.split('.')[-1]
                    if device_name not in results:
                        results[device_name] = {}
                    
                    try:
                        results[device_name][mapped_name] = float(val_str)
                    except ValueError:
                        results[device_name][mapped_name] = val_str
        i += 1

    with open(output_json_path, 'w') as json_file:
        json.dump(results, json_file, indent=4)
    
    print(f"Success! Parsed {len(results)} devices with mapping applied.")
    print(f"JSON saved to: {output_json_path}")


# --- Run with arguments ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse HSPICE .lis file to JSON")

    parser.add_argument(
        "--input",
        required=True,
        help="Path to input .lis file"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSON file"
    )

    args = parser.parse_args()

    parse_hspice_blocks_to_json(args.input, args.output)

