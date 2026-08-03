#!/usr/bin/env python3
import argparse
import os
import re
import shlex

# ==============================================================================
# Easy-to-edit device rules
# ==============================================================================
# prefix = first letter of device instance name
# M = MOS: name d g s b model params...
# R/C/L = passive: name n1 n2 value
# V/I = source: name n1 n2 source/value tokens
DEVICE_RULES = {
    "m": {
        "kind": "mos",
        "num_nodes": 4,
        "keep_params": ["l", "w", "m", "nf"],   # change to ["l", "w"] if you want exact minimal output
    },
    "r": {
        "kind": "passive",
        "num_nodes": 2,
        "keep_after_nodes": 1,
    },
    "c": {
        "kind": "passive",
        "num_nodes": 2,
        "keep_after_nodes": 1,
    },
    "l": {
        "kind": "passive",
        "num_nodes": 2,
        "keep_after_nodes": 1,
    },
    "v": {
        "kind": "source",
        "num_nodes": 2,
        "keep_after_nodes": 2,
    },
    "i": {
        "kind": "source",
        "num_nodes": 2,
        "keep_after_nodes": 2,
    },
}

def merge_continuation_lines(lines):
    """
    HSPICE continuation lines start with '+'.
    This merges:
        m1 ... 
        + ad=...
    into one logical line.
    """
    merged = []
    current = ""

    for raw in lines:
        line = raw.rstrip("\n")

        if not line.strip():
            continue

        if line.lstrip().startswith("*"):
            continue

        if line.lstrip().startswith("+"):
            current += " " + line.lstrip()[1:].strip()
        else:
            if current:
                merged.append(current)
            current = line.strip()

    if current:
        merged.append(current)

    return merged

def extract_subckt(lines, subckt_name="DUT"):
    """
    Extract only the requested .subckt block.
    """
    out = []
    inside = False

    for line in lines:
        stripped = line.strip()
        low = stripped.lower()

        if low.startswith(".subckt"):
            tokens = stripped.split()
            if len(tokens) >= 2 and tokens[1].lower() == subckt_name.lower():
                inside = True
                out.append(stripped)
            continue

        if inside:
            out.append(stripped)
            if low.startswith(".ends"):
                break

    return out

def spice_tokens(line):
    """
    Tokenize while respecting quoted strings like w='m7_w*1'.
    """
    try:
        return shlex.split(line, posix=False)
    except ValueError:
        return line.split()

def clean_value(value):
    """
    Clean simple HSPICE quoted values:
        'm7_w*1' -> m7_w
    """
    value = value.strip().strip("'").strip('"')

    # Simplify trivial multiply-by-one forms
    value = re.sub(r"\*1(\.0)?$", "", value)
    value = re.sub(r"^1(\.0)?\*", "", value)

    return value

def normalize_mos_model(model_name):
    """
    Convert PDK model names to generic nmos/pmos.
    Examples:
        nch_lvt -> nmos
        pch_lvt -> pmos
    If unknown, keep original model name.
    """
    m = model_name.lower()

    if "pch" in m or "pmos" in m or m.startswith("p"):
        return "pmos"
    if "nch" in m or "nmos" in m or m.startswith("n"):
        return "nmos"

    return model_name

def simplify_mos(tokens, rule):
    """
    MOS format:
        mname drain gate source bulk model param=value param=value ...
    """
    num_nodes = rule["num_nodes"]
    keep_params = [p.lower() for p in rule["keep_params"]]

    if len(tokens) < 1 + num_nodes + 1:
        return " ".join(tokens)

    inst = tokens[0]
    nodes = tokens[1:1 + num_nodes]
    model = tokens[1 + num_nodes]
    params = tokens[2 + num_nodes:]

    param_dict = {}

    for p in params:
        if "=" not in p:
            continue
        key, val = p.split("=", 1)
        key = key.lower().strip()
        val = clean_value(val)
        param_dict[key] = val

    out = [inst] + nodes + [normalize_mos_model(model)]

    for key in keep_params:
        if key in param_dict:
            out.append(f"{key}={param_dict[key]}")

    return " ".join(out)

def simplify_non_mos(tokens, rule):
    """
    Generic passive/source format:
        name n1 n2 value...
    """
    num_nodes = rule["num_nodes"]
    keep_after_nodes = rule.get("keep_after_nodes", 1)

    keep_count = 1 + num_nodes + keep_after_nodes
    return " ".join(tokens[:keep_count])

def simplify_device_line(line):
    low = line.lower().strip()

    if low.startswith(".subckt") or low.startswith(".ends"):
        return line.strip()

    tokens = spice_tokens(line)
    if not tokens:
        return ""

    prefix = tokens[0][0].lower()

    if prefix not in DEVICE_RULES:
        # Unsupported device type: keep line unchanged instead of accidentally breaking it
        return " ".join(tokens)

    rule = DEVICE_RULES[prefix]

    if rule["kind"] == "mos":
        return simplify_mos(tokens, rule)

    return simplify_non_mos(tokens, rule)

def simplify_netlist(input_path, output_path, subckt_name="DUT"):
    with open(input_path, "r") as f:
        raw_lines = f.readlines()

    logical_lines = merge_continuation_lines(raw_lines)
    subckt_lines = extract_subckt(logical_lines, subckt_name=subckt_name)

    if not subckt_lines:
        raise RuntimeError(f"Could not find .subckt {subckt_name} ... .ends block in {input_path}")

    simplified = []

    for line in subckt_lines:
        simplified_line = simplify_device_line(line)
        if simplified_line:
            simplified.append(simplified_line)

    with open(output_path, "w") as f:
        f.write("\n".join(simplified) + "\n")

    print(f"Generated simplified netlist: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Simplify a SPICE netlist to only the DUT subckt and compact device lines.")
    parser.add_argument("--input", required=True, help="Input SPICE netlist")
    parser.add_argument("--output", required=True, help="Output simplified SPICE netlist")
    parser.add_argument("--subckt", default="DUT", help="Subckt name to extract. Default: DUT")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input netlist not found: {args.input}")

    simplify_netlist(args.input, args.output, args.subckt)

if __name__ == "__main__":
    main()
