import json
import os
import sys
import argparse
import prompt_manager as pmt
import copy
# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
from global_dependency import *



def metric_pass_fail(eq_key: str, spice_val: float, model_val: float):
    spec = TOLERANCE_SPEC.get(eq_key, DEFAULT_TOL)
    mode = spec["mode"]
    tol  = float(spec["tol"])
    unit = spec["unit"]

    diff = model_val - spice_val

    if mode == "abs":
        err = abs(diff)
        status = "PASS" if err <= tol else "FAIL"
        # signed error for reporting direction
        signed_err = err if diff >= 0 else -err
        return status, signed_err, f"{signed_err:.4g}{unit}"

    elif mode == "pct":
        ref = abs(spice_val) if abs(spice_val) > 1e-12 else 1e-12
        err_pct = (abs(diff) / ref) * 100.0
        status = "PASS" if err_pct <= tol else "FAIL"
        signed_err_pct = err_pct if diff >= 0 else -err_pct
        return status, signed_err_pct, f"{signed_err_pct:.2f}%"

    else:
        # fallback to pct
        ref = abs(spice_val) if abs(spice_val) > 1e-12 else 1e-12
        err_pct = (abs(diff) / ref) * 100.0
        status = "PASS" if err_pct <= tol else "FAIL"
        signed_err_pct = err_pct if diff >= 0 else -err_pct
        return status, signed_err_pct, f"{signed_err_pct:.2f}%"



# ==============================================================================
# 2. UTILITY FUNCTIONS
# ==============================================================================

def load_json_file(filepath):
    if not os.path.exists(filepath):
        print(f"[ERROR] JSON file not found: {filepath}")
        return None
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load JSON {filepath}: {e}")
        return None

def save_json_file(data, filepath):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"[INFO] Updated history saved to: {filepath}")
    except Exception as e:
        print(f"[ERROR] Failed to save JSON {filepath}: {e}")

def update_equation_history_with_errors(history_data, mismatch_results):
    """
    Injects error percentages back into the history JSON for ONLY the latest stage.
    mismatch_results format: { "Metric_Name": (spice_val, model_val, err_pct, status) }
    """
    if not history_data:
        return history_data

    updated_history = copy.deepcopy(history_data)

    # 1. Identify the latest stage
    # Assuming keys are 'Stage 1', 'Stage 2', etc., we sort them to find the max
    try:
        # Sort keys based on the integer found in the string "Stage X"
        stages = sorted(updated_history.keys(), key=lambda x: int(x.split()[1]) if len(x.split()) > 1 else 0)
        latest_stage_name = stages[-1]
    except (ValueError, IndexError):
        # Fallback if naming convention is different: just take the last key inserted
        latest_stage_name = list(updated_history.keys())[-1]

    content = updated_history[latest_stage_name]

    if not isinstance(content, dict):
        return updated_history

    # 2. Update only the latest stage content
    # Note: Depending on your JSON structure, metrics might be under 
    # a sub-key like "Performance_Equations"
    target_dict = content.get("Performance_Equations", content)

    for metric_key, result_tuple in mismatch_results.items():
        if metric_key in target_dict:
            _, _, err_pct, status = result_tuple
            
            # If the entry is already a dict, inject the error
            if isinstance(target_dict[metric_key], dict):
                target_dict[metric_key]["error_pct"] = round(err_pct, 2)
            
            # If it's a string, transform it into a dict to store the error
            else:
                eq_str = target_dict[metric_key]
                target_dict[metric_key] = {
                    "equation": eq_str,
                    "error_pct": round(err_pct, 2)
                }
                    
    return updated_history

def extract_current_equations(json_data):
    equation_library = {}
    if not json_data or not isinstance(json_data, dict):
        return "(No equation data found)", {}

    lines = []

    # Sort Stage keys by the number inside "Stage X"
    def stage_key(k: str) -> int:
        try:
            digits = "".join(ch for ch in str(k) if ch.isdigit())
            return int(digits) if digits else 0
        except Exception:
            return 0

    sorted_keys = sorted(list(json_data.keys()), key=stage_key)

    for stage_name in sorted_keys:
        stage_content = json_data.get(stage_name, {})
        if not isinstance(stage_content, dict):
            continue

        equation_library[stage_name] = {"Derived_Parameters": {}, "Performance_Equations": {}}
        lines.append(f"\n# {stage_name}")

        # Case 1: Explicit sub-keys exist
        if isinstance(stage_content.get("Performance_Equations"), dict) or isinstance(stage_content.get("Derived_Parameters"), dict):
            derived = stage_content.get("Derived_Parameters", {}) if isinstance(stage_content.get("Derived_Parameters"), dict) else {}
            metrics  = stage_content.get("Performance_Equations", {}) if isinstance(stage_content.get("Performance_Equations"), dict) else {}

            # Copy into library + add to lines
            for k, v in derived.items():
                equation_library[stage_name]["Derived_Parameters"][k] = v
                lines.append(f"- {k}: `{v}`")

            for k, v in metrics.items():
                # v can be str OR dict containing equation/error_pct
                if isinstance(v, dict) and "equation" in v:
                    eq = v.get("equation", "")
                    err = v.get("error_pct", None)
                    equation_library[stage_name]["Performance_Equations"][k] = v  # keep dict
                    if err is None:
                        lines.append(f"- {k}: `{eq}`")
                    else:
                        lines.append(f"- {k}: `{eq}`  (error_pct={err})")
                else:
                    equation_library[stage_name]["Performance_Equations"][k] = v
                    lines.append(f"- {k}: `{v}`")

        # Case 2: Flat metrics directly under Stage (your JSON)
        else:
            for key, value in stage_content.items():
                # Metric dict: {"equation": "...", "error_pct": ...}
                if isinstance(value, dict) and "equation" in value:
                    eq = value.get("equation", "")
                    err = value.get("error_pct", None)

                    # Keep full dict (equation + error) in library
                    equation_library[stage_name]["Performance_Equations"][key] = value

                    if err is None:
                        lines.append(f"- {key}: `{eq}`")
                    else:
                        lines.append(f"- {key}: `{eq}`  (error_pct={err})")

                # Derived parameter as a string
                elif isinstance(value, str):
                    equation_library[stage_name]["Derived_Parameters"][key] = value
                    lines.append(f"- {key}: `{value}`")

                # Anything else: store as-is under Derived_Parameters so it is not silently dropped
                else:
                    equation_library[stage_name]["Derived_Parameters"][key] = value
                    lines.append(f"- {key}: `{value}`")

    return "\n".join(lines).strip(), equation_library

# ==============================================================================
# 3. COMPARATOR LOGIC
# ==============================================================================

def analyze_mismatch(hspice_data, model_data):
    report_lines = []
    mismatch_data = {}
    report_lines.append("| Metric | HSPICE (Truth) | Model (Eq) | Error | Status |")
    report_lines.append("| :--- | :--- | :--- | :--- | :--- |")
    
    issues = []

    for spice_key, eq_key in KEY_MAP.items():
        spice_val = hspice_data.get(spice_key, "FAILED")
        model_val = model_data.get(eq_key, "N/A")

        if spice_val in ["FAILED", "None", "inf"]:
            report_lines.append(f"| {spice_key} | FAILED | {model_val} | N/A | SKIP |")
            continue
        
        if model_val in ["N/A", "inf", None]:
            report_lines.append(f"| {spice_key} | {spice_val} | N/A | N/A | MODEL_FAIL |")
            issues.append((spice_key, spice_val, "MODEL_FAIL", 0))
            continue

        try:
            val_s = float(spice_val)

            # Your model_val parsing (keep your existing handling)
            if isinstance(model_val, dict):
                # NOTE: your current code tries to float(equation_math) which is not numeric.
                # So just treat dict as MODEL_FAIL unless you store numeric results there.
                report_lines.append(f"| {spice_key} | {val_s:.4g} | dict | N/A | MODEL_FAIL |")
                issues.append((spice_key, val_s, "MODEL_FAIL", 0))
                continue
            else:
                val_m = float(model_val)

            # optional Hz scaling block (keep if you really need it)
            val_m_norm = val_m

            eq_key_name = eq_key  # this is the internal key like "DC_Gain_dB"
            status, signed_err, err_str = metric_pass_fail(eq_key_name, val_s, val_m_norm)

            report_lines.append(f"| {spice_key} | {val_s:.4g} | {val_m_norm:.4g} | {err_str} | {status} |")

            if status == "FAIL":
                issues.append((spice_key, val_s, val_m_norm, signed_err))

            mismatch_data[eq_key_name] = (val_s, val_m_norm, signed_err, status)
        except Exception:
             report_lines.append(f"| {spice_key} | {spice_val} | {model_val} | ERR | CALC_ERR |")
            

    return "\n".join(report_lines), issues, mismatch_data

# ==============================================================================
# 4. PROMPT GENERATION
# ==============================================================================

def generate_correction_prompt(base_prompt_content, table_str, issues, current_equations_str):
    diag_lines = []
    if issues:
        for key, s_val, m_val, err in issues:
            if m_val == "MODEL_FAIL":
                diag_lines.append(f"- **{key}**: Model failed to compute.")
            else:
                direction = "OVER-ESTIMATING" if m_val > s_val else "UNDER-ESTIMATING"
                diag_lines.append(f"- **{key}**: Error {err:.1f}%. Model is {direction} (Truth: {s_val:.4g} vs Model: {m_val:.4g}).")
    else:
        diag_lines.append("No numerical mismatches found.")

    diag_text = "\n".join(diag_lines)

    appendix = f"""
---
# SYSTEM FEEDBACK: STAGE UPDATE

## 1. ACCURACY REPORT
{table_str}

## 2. METRICS REQUIRING CORRECTION
{diag_text}

## 3. DEBUGGING CONTEXT (Previous Performance Equations)
{current_equations_str}

## 4. TASK
1. Analyze failing metrics.
2. Modify only failing equations using atomic variables.
3. Do NOT change PASS equations.
"""
    return base_prompt_content + appendix

# ==============================================================================
# 5. MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hspice-performance", required=True)
    parser.add_argument("--equation-performance", required=True)
    parser.add_argument("--output-prompt", required=True)
    parser.add_argument("--error-threshold", type=float, default=15.0)
    parser.add_argument("--netlist-path", default="Testbenches/5t_ota_simple.sp")
    parser.add_argument("--past-equations", default="equation_history.json")
    parser.add_argument("--region-verify", action="store_true", help="Only for region specific check, no update of equation_library")
    args = parser.parse_args()

    hspice_full = load_json_file(args.hspice_performance)
    model_full = load_json_file(args.equation_performance)
    current_gen_json = load_json_file(args.past_equations) 

    if not (hspice_full and model_full and current_gen_json):
        sys.exit(1)

    hspice_metrics = hspice_full.get("extracted_metrics", hspice_full)
    equation_metrics = model_full.get("performance", model_full)
    if "Stage 1" in equation_metrics:
        equation_metrics = equation_metrics["Stage 1"]

    #table_output, issue_list, mismatch_data = analyze_mismatch(hspice_metrics, equation_metrics, args.error_threshold)
    table_output, issue_list, mismatch_data = analyze_mismatch(hspice_metrics, equation_metrics)
    print(f"Generating mismatch report")
    print(table_output)
    #sys.exit()
    # --- NEW: Update the history JSON with the calculated errors ---

    #print(current_gen_json, mismatch_data)
    updated_history = update_equation_history_with_errors(current_gen_json, mismatch_data)
    if args.region_verify == False:
        save_json_file(updated_history, args.past_equations)

    if not issue_list:
        print("OUTPUT: All generated equations are accurate.")
        sys.exit(0) 

    current_eq_str, equation_library = extract_current_equations(current_gen_json)

    final_prompt = pmt.generate_prompt(
        role="analog_architect", 
        task_type="iterative_refinement", 
        netlist=args.netlist_path, 
        metrics=mismatch_data, 
        history=equation_library, 
        table=table_output,
        error_th = args.error_threshold
    )
    
    with open(args.output_prompt, "w", encoding="utf-8") as f:
        f.write(final_prompt)
    
    print(f"\n[INFO] Feedback prompt generated: {args.output_prompt}")

if __name__ == "__main__":
    main()
