import sys
import os
import re
import shutil
import argparse

def generate_new_hspice_deck(source_netlist, base_testbench, output_file):
    """
    1. Reads source_netlist for MOSFETs.
    2. Creates a NEW file: 'sim_' + base_testbench.
    3. Appends the .print commands and a final .end.
    """
    
    if not os.path.exists(source_netlist) or not os.path.exists(base_testbench):
        print(f"Error: Ensure both '{source_netlist}' and '{base_testbench}' exist.")
        return

    # Create the output filename
    # output_file is now passed as argument
    
    # 1. Extract Device Names (Preserving Case)
    devices = []
    in_subckt = False
    
    with open(source_netlist, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            if not stripped: continue
            
            if stripped.lower().startswith(".subckt"):
                in_subckt = True
                continue
            if stripped.lower().startswith(".ends"):
                in_subckt = False
                continue

            if in_subckt and not stripped.startswith('*'):
                match = re.match(r'^\s*([mM]\S+)', stripped)
                if match:
                    devices.append(match.group(1))

    if not devices:
        print("No MOSFETs found in subcircuit.")
        return

    # 2. Create the Copy and Append
    print(f"Creating copy: {output_file}")
    shutil.copy2(base_testbench, output_file)

    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n\n* --- AUTOMATED DIAGNOSTIC PRINTS ---\n")
        
        for dev in devices:
            dev_path = f"XU1.XCORE.{dev}"

            template = f"""
* --- Device {dev} ---
.print dc
+ lv1({dev_path}) lv2({dev_path}) lx2({dev_path})  lx3({dev_path})  par('abs(lx1({dev_path}))') 
+ i({dev_path})    par('abs(i({dev_path}))') lx7({dev_path}) lx8({dev_path}) lx9({dev_path}) 
+ par('lx7({dev_path})/max(abs(i({dev_path})),1e-15)')
+ lv9({dev_path})  lv10({dev_path}) lv13({dev_path}) lv22({dev_path}) lv21({dev_path})
+ lx18({dev_path}) lx19({dev_path}) lx20({dev_path}) lx21({dev_path}) lx22({dev_path}) 
+ lx23({dev_path}) lx32({dev_path}) lx33({dev_path}) lx34({dev_path})
+ lx82({dev_path}) lx83({dev_path}) lx84({dev_path}) lx85({dev_path}) lx86({dev_path}) 
+ lx89({dev_path}) lx90({dev_path}) lx287({dev_path})
"""
            f.write(template)

        # 3. Add the final .end
        f.write("\n.end\n")

    print(f"Success! New simulation deck generated: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a new HSPICE simulation deck by copying a base testbench and appending diagnostic .print statements."
    )
    parser.add_argument(
        "--netlist",
        required=True,
        help="Path to the DUT netlist (.sp) containing the .subckt with MOSFET instances."
    )
    parser.add_argument(
        "--testbench",
        required=True,
        help="Path to the base testbench (.sp) to copy and append prints into."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output simulation deck filename."
    )

    args = parser.parse_args()

    generate_new_hspice_deck(args.netlist, args.testbench, args.output)

