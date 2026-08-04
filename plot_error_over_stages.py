#!/usr/bin/env python3
"""
plot_stage_errors.py

Reads a multi-stage equation history JSON like:

{
  "Stage 1": { "DC_Gain_dB": {"error_pct": 0.54, ...}, ... },
  "Stage 2": { ... },
  ...
}

Generates one PNG per metric group.

Examples
--------
Use built-in default groups:
    python plot_stage_errors.py --json equation_history.json --outdir plots

Override with arbitrary groups:
    python plot_stage_errors.py --json equation_history.json --outdir plots \
        --group freq=DC_Gain_dB,Bandwidth_3dB_Hz,UGB_Hz,Phase_Margin_deg \
        --group robustness=CMRR_dB,PSRR_dB \
        --group large_signal=Output_Swing_V,ICMR_V,OCMR_V,Slew_Rate_V_per_us

Optionally collect all unassigned metrics into one extra group:
    python plot_stage_errors.py --json equation_history.json --outdir plots --include-remaining
"""

import argparse
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams.update({
    "axes.titlesize": 20,
    "axes.labelsize": 18,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 16,
})
mpl.rcParams["font.family"] = "serif"
mpl.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]

_STAGE_NUM_RE = re.compile(r"(\d+)")

# =========================================================
# Default groups
# You can edit these permanently if you want
# =========================================================



DEFAULT_METRIC_GROUPS = {
    "Relatively_stable_metrics": [
        "Input_CMR_Min_V",
        "Input_CMR_Max_V",
        "Output_Swing_Max_V",
        "Output_Swing_Min_V",
        "DC_Gain_dB",
        "Phase_Margin_deg",
        "Slew_Rate_Pos_V_us",
        "Slew_Rate_Neg_V_us",
        "PSRR_Pos_dB",
        "PSRR_Neg_dB",
        "CMRR_dB"  
    ],
    "Sensitive_metrics": [
        "Bandwidth_3dB_Hz",
        "UGB_Hz"
    ]
}
METRIC_DISPLAY_NAMES = {
    "Input_CMR_Min_V": r"ICMR$_{min}$",
    "Input_CMR_Max_V": r"ICMR$_{max}$",
    "Output_Swing_Max_V": r"OCMR$_{min}$",
    "Output_Swing_Min_V": r"OCMR$_{max}$",
    "DC_Gain_dB": r"A$_{DC}$",
    "Phase_Margin_deg": r"PM",
    "Bandwidth_3dB_Hz": r"BW$_{3dB}$",
    "UGB_Hz": r"UGF",
    "Slew_Rate_Pos_V_us": r"SR$^{+}$/SR$^{-}$",
    "Slew_Rate_Neg_V_us": r"SR$^{+}$/SR$^{-}$",
    "PSRR_Pos_dB": r"PSRR$^{+}$",
    "PSRR_Neg_dB": r"PSRR$^{-}$",
    "CMRR_dB": r"CMRR",
}


def get_metric_display_name(metric: str) -> str:
    return METRIC_DISPLAY_NAMES.get(metric, metric)


def build_metric_color_map(metric_groups: Dict[str, List[str]]) -> Dict[str, Any]:
    ordered_metrics = []
    seen = set()

    for metrics in metric_groups.values():
        for metric in metrics:
            if metric not in seen:
                seen.add(metric)
                ordered_metrics.append(metric)

    dark_palette = [
        "#1f77b4",  # blue
        "#d62728",  # red
        "#2ca02c",  # green
        "#9467bd",  # purple
        "#ff7f0e",  # orange
        "#8c564b",  # brown
        "#e377c2",  # pink
        "#17becf",  # cyan
        "#bcbd22",  # olive
        "#7f7f7f",  # gray
        "#003f5c",
        "#7a5195",
        "#ef5675",
        "#ffa600",
        "#2f4b7c",
        "#a05195",
        "#665191",
        "#d45087",
        "#f95d6a",
        "#006400",
    ]

    color_map = {}
    for i, metric in enumerate(ordered_metrics):
        color_map[metric] = dark_palette[i % len(dark_palette)]

    return color_map
def append_dummy_tail(stage_nums: List[int],
                      metric_to_abs_errs: Dict[str, List[float]],
                      repeat: int = 5) -> Tuple[List[int], Dict[str, List[float]]]:
    """
    Append dummy points by repeating the final stage value `repeat` times
    for every metric. Stage indices become N+1..N+repeat.
    """
    if not stage_nums:
        return stage_nums, metric_to_abs_errs

    last_stage = stage_nums[-1]
    new_stage_nums = stage_nums + [last_stage + i for i in range(1, repeat + 1)]

    new_metric_map: Dict[str, List[float]] = {}
    for metric, ys in metric_to_abs_errs.items():
        if not ys:
            new_metric_map[metric] = ys
            continue
        last_val = ys[-1]
        new_metric_map[metric] = ys + [last_val] * repeat

    return new_stage_nums, new_metric_map


def _stage_sort_key(stage_name: str) -> int:
    m = _STAGE_NUM_RE.search(str(stage_name))
    return int(m.group(1)) if m else 0


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if math.isnan(float(x)) or math.isinf(float(x)):
            return None
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if not s or s.lower() in {"nan", "none", "failed", "n/a", "na", "inf", "-inf"}:
            return None
        try:
            v = float(s)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None
    return None


def extract_stage_metric_abs_errors(
    data: Dict[str, Any]
) -> Tuple[List[str], List[int], Dict[str, List[Optional[float]]]]:
    """
    Returns:
      stage_names_sorted: ["Stage 1", "Stage 2", ...]
      stage_nums_sorted:  [1, 2, ...]
      metric_to_abs_errs: metric -> list aligned with stages
    """
    stage_names = [k for k in data.keys() if isinstance(data.get(k), dict)]
    stage_names_sorted = sorted(stage_names, key=_stage_sort_key)
    stage_nums_sorted = [_stage_sort_key(s) for s in stage_names_sorted]

    all_metrics = set()
    for st in stage_names_sorted:
        st_dict = data.get(st, {})
        if isinstance(st_dict, dict):
            all_metrics.update(st_dict.keys())

    all_metrics.discard("Gain_Margin_dB")

    metric_to_abs_errs: Dict[str, List[Optional[float]]] = {
        m: [] for m in sorted(all_metrics)
    }

    for st in stage_names_sorted:
        st_dict = data.get(st, {})
        for metric in metric_to_abs_errs.keys():
            v = None
            if isinstance(st_dict, dict) and metric in st_dict:
                entry = st_dict.get(metric)
                if isinstance(entry, dict):
                    v = safe_float(entry.get("error_pct", None))

            abs_err = 100.0 if v is None else abs(v)
            metric_to_abs_errs[metric].append(abs_err)

    return stage_names_sorted, stage_nums_sorted, metric_to_abs_errs


def _style_axes(ax) -> None:
    ax.grid(False)

    # only left and bottom axes
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.2)
    ax.spines["bottom"].set_linewidth(1.2)

    ax.tick_params(axis="both", which="both", direction="out", width=1.0)


def sanitize_filename(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_\-]", "", s)
    return s or "plot"


def plot_grouped_subplots(stage_nums: List[int],
                          metric_to_abs_errs: Dict[str, List[Optional[float]]],
                          metric_groups: Dict[str, List[str]],
                          metric_color_map: Dict[str, Any],
                          out_path: str,
                          title_prefix: str = "",
                          logy: bool = False,
                          conv_stage: Optional[int] = None,
                          y_max: float = 500.0) -> None:
    group_items = list(metric_groups.items())
    nplots = len(group_items)

    if nplots == 0:
        print("[WARN] No metric groups found.")
        return

    fig, axes = plt.subplots(1, nplots, figsize=(6.2 * nplots, 7.8))

    if nplots == 1:
        axes = [axes]

    legend_handles = {}
    threshold_handle = None
    conv_handle = None

    #for ax, (group_name, metrics) in zip(axes, group_items):
    for idx, (ax, (group_name, metrics)) in enumerate(zip(axes, group_items)):
        metrics_present = [m for m in metrics if m in metric_to_abs_errs]
        if not metrics_present:
            ax.set_visible(False)
            continue

        for metric in metrics_present:
            ys_raw = metric_to_abs_errs[metric]
            ys = [v if v is not None else float("nan") for v in ys_raw]

            display_name = get_metric_display_name(metric)

            line, = ax.plot(
                stage_nums,
                ys,
                #marker="o",
                #markersize=4.5,
                linewidth=2.5,
                label=display_name,
                color=metric_color_map[metric]
            )

            if metric not in legend_handles:
                legend_handles[metric] = line

        ax.set_box_aspect(1)
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Error % (log scale)" if logy else "Error %")
        ax.set_title(group_name.replace("_", " "), pad=10, fontweight="bold")
        subplot_tag = f"({chr(97 + idx)})"
        ax.text(
            0.5, -0.16, subplot_tag,
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=24
        )
        _style_axes(ax)

        if logy:
            ax.set_yscale("log")
        else:
            ax.set_ylim(-10, y_max)

        th = ax.axhline(5.0, linestyle=":", linewidth=2.0, color="red", label="5% threshold")
        if threshold_handle is None:
            threshold_handle = th

        #if conv_stage is not None:
            #cv = ax.axvline(conv_stage, linestyle=":", linewidth=2.2, color="green", alpha=0.9,
            #                label="Convergence")
            #if conv_handle is None:
            #    conv_handle = cv

    #legend_list = list(legend_handles.items())
    legend_list = [(get_metric_display_name(metric), handle) for metric, handle in legend_handles.items()]

    if threshold_handle is not None:
        legend_list.append(("15% threshold", threshold_handle))
    if conv_handle is not None:
        legend_list.append(("Convergence", conv_handle))

    legend_labels = [k for k, _ in legend_list]
    legend_handles_final = [h for _, h in legend_list]

    if title_prefix.strip():
        fig.suptitle(title_prefix.strip(), y=0.98, fontweight="bold")

    fig.legend(
        legend_handles_final,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(0.8, 0.5),
        frameon=False,
        ncol=1,
        borderaxespad=0.0
    )

    fig.subplots_adjust(left=0.08, right=0.80, top=0.88, bottom=0.14, wspace=0.2)
    #fig.subplots_adjust(bottom=0.30, top=0.88, wspace=0.2)
    #fig.subplots_adjust(bottom=0.16, top=0.88, wspace=0.10)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def parse_group_specs(group_specs: List[str]) -> Dict[str, List[str]]:
    """
    Parse repeated CLI entries like:
        --group freq=DC_Gain_dB,UGB_Hz,Phase_Margin_deg
        --group swing=Output_Swing_V,ICMR_V,OCMR_V
    """
    groups: Dict[str, List[str]] = {}

    for spec in group_specs:
        if "=" not in spec:
            raise ValueError(
                f"Invalid --group format: '{spec}'. Expected name=metric1,metric2,..."
            )

        name, metrics_csv = spec.split("=", 1)
        name = name.strip()
        metrics = [m.strip() for m in metrics_csv.split(",") if m.strip()]

        if not name:
            raise ValueError(f"Invalid --group name in '{spec}'")
        if not metrics:
            raise ValueError(f"No metrics provided in '{spec}'")

        groups[name] = metrics

    return groups


def add_remaining_group(groups: Dict[str, List[str]],
                        all_metrics: List[str],
                        remaining_group_name: str = "remaining") -> Dict[str, List[str]]:
    used = set()
    for metrics in groups.values():
        used.update(metrics)

    remaining = [m for m in all_metrics if m not in used]
    if remaining:
        groups[remaining_group_name] = remaining
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="Path to multi-stage equation history JSON")
    ap.add_argument("--outdir", default="plots", help="Directory to store output PNGs")
    ap.add_argument("--title-prefix", default="", help="Optional prefix for every plot title")
    ap.add_argument("--group", action="append", default=[],
                    help="Repeated metric group spec: name=metric1,metric2,...")
    ap.add_argument("--include-remaining", action="store_true",
                    help="Put all unassigned metrics into an extra group called 'remaining'")
    ap.add_argument("--logy", action="store_true", help="Use log scale on y-axis")
    ap.add_argument("--ymax", type=float, default=500.0, help="Upper y-limit for linear scale")
    ap.add_argument("--tail-repeat", type=int, default=5,
                    help="Repeat last stage value N times as dummy tail")
    args = ap.parse_args()

    data = load_json(args.json)
    stage_names, stage_nums, metric_to_abs_errs = extract_stage_metric_abs_errors(data)

    if not stage_nums:
        raise SystemExit("No stages found in JSON. Expected keys like Stage 1, Stage 2, ...")

    orig_last_stage = stage_nums[-1]
    stage_nums, metric_to_abs_errs = append_dummy_tail(
        stage_nums, metric_to_abs_errs, repeat=args.tail_repeat
    )

    all_metrics = list(metric_to_abs_errs.keys())

    if args.group:
        metric_groups = parse_group_specs(args.group)
    else:
        metric_groups = dict(DEFAULT_METRIC_GROUPS)

    if args.include_remaining:
        metric_groups = add_remaining_group(metric_groups, all_metrics)

    metric_color_map = build_metric_color_map(metric_groups)
    os.makedirs(args.outdir, exist_ok=True)

    print(f"[INFO] Stages found: {stage_names}")
    print(f"[INFO] Output dir  : {args.outdir}")
    print(f"[INFO] Groups      : {list(metric_groups.keys())}")

    out_path = os.path.join(args.outdir, "combined_subplots.png")

    plot_grouped_subplots(
        stage_nums=stage_nums,
        metric_to_abs_errs=metric_to_abs_errs,
        metric_groups=metric_groups,
        metric_color_map=metric_color_map,
        out_path=out_path,
        title_prefix=args.title_prefix,
        logy=args.logy,
        conv_stage=orig_last_stage,
        y_max=args.ymax,
    )

    print(f"[INFO] Wrote: {out_path}")
    for group_name, metrics in metric_groups.items():
        print(f"       {group_name}: {metrics}")


if __name__ == "__main__":
    main()
