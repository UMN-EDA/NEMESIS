import json, os, glob, re, argparse

INPUT_FILE = "gemini_output_stage1.json"
OUTPUT_FILE = "equation_history.json"

def get_stage_number(filename):
    match = re.search(r"stage(\d+)", filename)
    return int(match.group(1)) if match else -1

def balance_trailing_braces(equation):
    """
    Balances parentheses in an equation string.

    Behavior:
    1) If there are more ')' than '(', remove only trailing ')' until counts match
       or no trailing ')' remain.
    2) If there are more '(' than ')', append the missing ')' at the end.

    Returns:
      (balanced_equation: str, is_balanced: bool)
    """
    if not isinstance(equation, str) or equation == "N/A":
        return equation, True

    eq = equation.strip()

    # Count parentheses
    open_count = eq.count('(')
    closed_count = eq.count(')')

    # Case A: too many closing parens -> trim only from the end
    while closed_count > open_count and eq.endswith(')'):
        eq = eq[:-1].rstrip()
        closed_count -= 1

    # Recompute after trimming (safer if whitespace changed)
    open_count = eq.count('(')
    closed_count = eq.count(')')

    # Case B: too many opening parens -> append missing closing parens
    if open_count > closed_count:
        eq = eq + (')' * (open_count - closed_count))
        closed_count = open_count

    is_balanced = (open_count == closed_count)
    return eq, is_balanced

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=INPUT_FILE, help="Input Gemini output JSON file")
    parser.add_argument("--mismatch-data", type=str, help="JSON dict: {'Metric': [Truth, Model, Err, Status]}")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="Output equation history JSON file")
    args = parser.parse_args()

    input_file = args.input
    output_file = args.output

    # 1. Load existing history or initialize new
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            try:
                equation_log = json.load(f)
            except json.JSONDecodeError:
                equation_log = {}
    else:
        equation_log = {}

    # 2. Use the given input file
    if not os.path.exists(input_file):
        print(f"[ERROR] Input file not found: {input_file}")
        return

    latest_file = input_file
    stage_num = get_stage_number(latest_file)
    stage_key = f"Stage {stage_num}"
    
    print(f">> Processing input file: {latest_file} ({stage_key})")

    # 3. Extract equations from that specific file
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    metrics_raw = data.get("3_PERFORMANCE_METRICS", {})

    new_stage_content = {}
    for name, details in metrics_raw.items():
        if isinstance(details, dict):
            raw_eq = details.get("equation_math", "N/A")
            
            # Run the specific trailing brace cleaner
            fixed_eq, balanced = balance_trailing_braces(raw_eq)

            if fixed_eq != raw_eq:
                print(f">> [CLEANED] Removed extra trailing braces from: {name}")

            new_stage_content[name] = {
                "equation": fixed_eq,
                "is_balanced": balanced
            }

    # 4. Merge simulation error_pct if provided
    if args.mismatch_data:
        try:
            new_results = json.loads(args.mismatch_data)
            for metric, values in new_results.items():
                if metric in new_stage_content:
                    # Append ONLY error_pct (index 2 of the results list)
                    new_stage_content[metric]["error_pct"] = values[2]
            print(f">> Merged error_pct into {stage_key}")
        except Exception as e:
            print(f"[ERROR] Failed to parse mismatch-data: {e}")

    # 5. Update the log with the new stage and write back
    equation_log[stage_key] = new_stage_content
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(equation_log, f, indent=4)
    
    print(f">> [SUCCESS] {output_file} updated with {stage_key}.")

if __name__ == "__main__":
    main()
