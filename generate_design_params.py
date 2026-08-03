import re
import os
import argparse

# Netlists WITHOUT VB2
LIST_A_NO_VB2 = [
    "cm_ota.sp",
    "5t_ota.sp",
    "2s_ota.sp"
]

# Netlists WITH VB2
LIST_B_HAS_VB2 = [
    "lv_cas_ota.sp",
    "cascode_ota.sp",
]

def get_dut_has_vb2(netlist_path):
    netlist_name = os.path.basename(netlist_path).lower()

    list_a = [x.lower() for x in LIST_A_NO_VB2]
    list_b = [x.lower() for x in LIST_B_HAS_VB2]

    if netlist_name in list_a:
        return 0
    elif netlist_name in list_b:
        return 1
    else:
        raise ValueError(
            f"Netlist '{netlist_name}' is not listed in LIST_A_NO_VB2 or LIST_B_HAS_VB2."
        )

def main():
    parser = argparse.ArgumentParser(description="Update device parameters in SPICE params file.")
    parser.add_argument("--netlist", required=True, help="Path to the DUT netlist")
    parser.add_argument("--params", required=True, help="Path to the design_params.sp file")
    parser.add_argument("--length", required=True, help="Desired length of the devices")
    args = parser.parse_args()

    dut_has_vb2 = get_dut_has_vb2(args.netlist)

    param_pattern = re.compile(r'\b(m\d+_[wl])\b', re.IGNORECASE)

    if not os.path.exists(args.netlist):
        print(f"Error: Netlist '{args.netlist}' not found.")
        return

    with open(args.netlist, 'r') as f:
        netlist_content = f.read()
        found_params = set(param_pattern.findall(netlist_content))

    if not found_params:
        print("No device parameters (mX_w/l) found in the netlist.")
        return

    if not os.path.exists(args.params):
        print(f"Error: Params file '{args.params}' not found.")
        return

    with open(args.params, 'r') as f:
        original_lines = f.readlines()

    final_output = []
    found_section = False
    found_dut_has_vb2 = False

    for line in original_lines:
        if re.match(r'\s*\.param\s+DUT_HAS_VB2\s*=', line, re.IGNORECASE):
            final_output.append(f".param DUT_HAS_VB2 = {dut_has_vb2}\n")
            found_dut_has_vb2 = True
            continue

        final_output.append(line)

        if "* Device parameters" in line:
            found_section = True
            break

    if not found_section:
        print("Error: Could not find the '* Device parameters' header in your params file.")
        return

    if not found_dut_has_vb2:
        print("Error: Could not find '.param DUT_HAS_VB2' in your params file.")
        return

    final_output.append("*******************************************************\n")

    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

    sorted_params = sorted(list(found_params), key=natural_sort_key)

    for p in sorted_params:
        p_lower = p.lower()
        val = f"{args.length}n" if p_lower.endswith('_l') else "1u"
        final_output.append(f".param {p_lower}={val}\n")

    with open(args.params, 'w') as f:
        f.writelines(final_output)

    print(f"Successfully synced {len(sorted_params)} parameters to {args.params}")
    print(f"Set DUT_HAS_VB2 = {dut_has_vb2}")

if __name__ == "__main__":
    main()
