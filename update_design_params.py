import json
import re
import argparse
import sys

def update_spice_netlist(json_path, sp_path, output_path):
    """
    Reads a JSON spec file and a SPICE .sp file.
    Updates the .param mX_l and mX_w values in the .sp file 
    using the W/L values from the JSON.
    """
    
    # 1. Load the JSON Data
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            # Handle different JSON structures: check for 'devices' key or use root
            devices = data.get('devices', data)
    except FileNotFoundError:
        print(f"Error: JSON file '{json_path}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{json_path}'.")
        return

    # 2. Read the SPICE file content
    try:
        with open(sp_path, 'r') as f:
            sp_content = f.read()
    except FileNotFoundError:
        print(f"Error: SPICE file '{sp_path}' not found.")
        return

    print(f"--- Updating Netlist: {sp_path} ---")

    # 3. Iterate through devices in JSON (m0, m1, etc.)
    # We iterate over keys in 'devices' dictionary
    for dev_name, params in devices.items():
        if not isinstance(params, dict):
            continue

        # Update Length (L)
        if 'L' in params:
            new_val = params['L']
            # Regex Explanation:
            # (\.param\s+)  -> Group 1: Matches ".param "
            # ({dev_name}_l)-> Matches the device name + "_l" (e.g., m0_l)
            # (\s*=\s*)     -> Matches the equals sign with optional spaces
            # ([\w\.\-\+]+) -> Matches the old value (numbers, letters, dots, signs)
            # We look for lines like: .param m0_l = 1u
            pattern_l = r"(\.param\s+" + re.escape(dev_name) + r"_l\s*=\s*)([\w\.\-\+]+)"
            
            if re.search(pattern_l, sp_content, re.IGNORECASE):
                # Replace the old value (Group 2) with new_val, keeping Group 1 intact
                sp_content = re.sub(pattern_l, f"\\g<1>{new_val}", sp_content, flags=re.IGNORECASE)
                print(f"  Updated {dev_name}_l -> {new_val}")

        # Update Width (W)
        if 'W' in params:
            new_val = params['W']
            # Look for lines like: .param m0_w = 5u
            pattern_w = r"(\.param\s+" + re.escape(dev_name) + r"_w\s*=\s*)([\w\.\-\+]+)"
            
            if re.search(pattern_w, sp_content, re.IGNORECASE):
                sp_content = re.sub(pattern_w, f"\\g<1>{new_val}", sp_content, flags=re.IGNORECASE)
                print(f"  Updated {dev_name}_w -> {new_val}")

    # 4. Save the new SPICE file
    try:
        with open(output_path, 'w') as f:
            f.write(sp_content)
        print(f"--- Success! Saved updated netlist to: {output_path} ---")
    except Exception as e:
        print(f"Error writing to output file '{output_path}': {e}")

# ==========================================
# Main Execution
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update SPICE netlist parameters from a JSON file.")
    
    # Define arguments
    parser.add_argument("--json_file", help="Path to the input JSON file (Equation based estimation) containing device parameters.")
    parser.add_argument("--sp_file", help="Path to the input DEISGN PARAMS template file .")
    parser.add_argument("--out_file", help="Path where the updated DESIGN PARAMS SPICE will be saved.")

    # Parse arguments
    args = parser.parse_args()

    # Run the function with parsed arguments
    update_spice_netlist(args.json_file, args.sp_file, args.out_file)
