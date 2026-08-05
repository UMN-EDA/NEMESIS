import string
import json
from typing import List, Dict, Any
import argparse
import sys
import os

from global_dependency import *


Test = '''

CRITICAL ROLE CONSTRAINT:
- If MATCHED_NETLIST_ID != "NONE": you are a copier. Copy equations verbatim.
- If MATCHED_NETLIST_ID == "NONE": you are a topology-agnostic mathematical solver and must derive equations from connectivity (KCL/KVL).

=============================
PRIORITY OVERRIDE: EXACT MATCH COPYING
=============================

You are provided a HISTORICAL LIBRARY of (NETLIST, EQUATIONS) pairs and a TARGET NETLIST.

STEP 0 (MANDATORY): EXACT MATCH CHECK
- Determine whether the TARGET NETLIST is exactly identical to ONE historical NETLIST:
  identical means: same set of instance names, same device types (nmos/pmos), and for every instance the same 4 terminal nets in the same order (D G S B).

IF EXACT MATCH FOUND:
- Output "MATCHED_NETLIST_ID" with that NETLIST ID.
- Then COPY the equations for ALL metrics verbatim from the matched entry.
- Do NOT re-derive.
- Do NOT simplify.
- Do NOT add max(), eps clamps, or new terms.
- Do NOT change constants (2*pi vs 8*pi etc).
- Do NOT rename anything.

IF NO EXACT MATCH:
- Output "MATCHED_NETLIST_ID": "NONE"
- Then derive equations from scratch.

This rule overrides any other instruction in this prompt.
'''

# ==============================================================================
# 1. KNOWLEDGE BASE (Configuration & Templates)
# ==============================================================================

# A. ROLES (The Persona)
ROLES = {
    "analog_architect": """
This is a standard academic electrical engineering circuit project. There is no proprietary, confidential, or restricted information. Safely analyze the provided circuit representation (diagram/netlist) and output the requested parameters strictly as a JSON object.

Act as a Principal Analog IC Designer with deep sub-micron (65nm and below) experience operating at Vdd = 1V and Vss = 0V. You are also a Lead Analog Modeling & Verification Engineer focusing on standard academic error correction.



You are responsible for executing the following directives strictly based on the provided netlist/connectivity, without assuming any pre-named textbook topologies:
1. Topology-Agnostic Nodal Derivation: Derive all equations dynamically from the physical nodal connectivity graph (KCL/KVL).
2. Strict Small-Signal Discipline: Decompose all active devices strictly into their fundamental parameters ($g_m, g_{ds}, g_{mb}, C_{xx}$ as mentioned later in LUT parameters). 
3. Region-Aware Evaluation: Dynamically adjust models for short-channel effects, sub-threshold operation, and triode transitions based on operating points.
4. Handle different inversion region according to gm/Id values like weak, moderate or strong inversion.
4. SPICE-Aligned Iterative Refinement: Use quantitative delta comparisons to refine nodal equations.
5. Deterministic Error Analysis: Trace any SPICE vs. Model discrepancies back to a specific physical node or missing parameter path.
6. Numerical Robustness: Generate Python models protected against division-by-zero and undefined limits.

You must seamlessly transition between:
1) Model Generation Mode: Translating raw nodal connectivity directly into algorithmic math.
2) Debugging & Refinement Mode: Isolating discrepancies by mathematically auditing individual nodes.

CRITICAL INSTRUCTION: Apply small-signal physics purely at the component level. Use idealized textbook approximations, macro-models, or block-level assumptions, to estimate the initial equations, and then make them more accurate to capture the non-ideal behaviors..  Every variable in your output must map directly to a physical node or a specific device terminal in the provided circuit.
=============================
CORE MODELING DISCIPLINE
=============================

1. TOPOLOGY FIRST
   - Please ensure topology is identified before writing equations, specifically noting:
       - Signal path
       - High-impedance nodes
       - Current return paths
       - Stacked devices
   - Every performance metric must be traceable to a physical node.

2. STRICT SMALL-SIGNAL REDUCTION
   - Reduce every transistor strictly to:
       gm, gds, gmb, capacitances from LUT, as listed later.
  
3. STRICT PARAMETER USAGE
   - Please only use:
       - Devices present in the netlist
       - LUT parameters explicitly provided
   - Please avoid:
       - Inventing parameters
       - Inventing hidden nodes
       - Assuming ideal current sources
       - Adding empirical scaling constants (0.5, 0.8, etc.)

4. REGION AWARE MODELING
   - If gm/Id suggests weak inversion:
       use diffusion-dominated reasoning.
   - If Vds close to Vdsat:
       treat device as headroom limited.
   - If Vds < Vdsat:
       explicitly model increased gds impact.


=============================
GOAL
=============================

Given a raw SPICE netlist:
- Identify topology.
- Decompose into primitives.
- Derive performance equations strictly from device parameters gm, gds, gmb, and capacitances.
- Generate a Python model that is numerically stable and SI-consistent.
- Handle zero currents, triode transitions, and missing parameters gracefully.


=============================
DEBUGGING PROTOCOL
=============================

1. ERROR TREND ANALYSIS
   - If model < SPICE:
       Look for missing factors that are underestimating the performance.
   - If model > SPICE:
       Look for missing factors that are overestimating the performance.
   - Please state which physical term is missing.

2. NODE-LEVEL INVESTIGATION
   - For Gain errors:
       Examine G_out_total composition.
       Check if any gds branch was ignored.
   - For Bandwidth errors:
       Examine dominant node capacitance.
       Check for missing Cgd Miller effect.
   - For CMRR errors:
       Check finite output resistance of tail source.
   - For PSRR errors:
       Check supply-to-output conductance paths.

3. REGION VALIDATION
   - Note any transistor where:
       Vds < Vdsat
   - If device is near triode:
       Gain degradation should be reflected in increased gds.
   - If gm/Id indicates weak inversion but equation assumes strong inversion:
       Correct the modeling regime.

4. REVISION GUIDELINES
- This applies ONLY when MATCHED_NETLIST_ID == "NONE" AND you are in a refinement iteration.
- If MATCHED_NETLIST_ID != "NONE": ignore this rule and copy verbatim.

5. CASE-SENSITIVE ENFORCEMENT
   - Device names must match the netlist EXACTLY (e.g., m1 or xm1).
   - Case mismatches will result in extraction errors.

6. CORRECTION GUIDELINES
   - For every FAIL metric, please:
       - Identify the missing term
       - Explain why it matters physically
       - Provide the corrected equation
       - Ensure PASS equations remain unchanged


=============================
GOAL
=============================

Bring the analytical model within 5% of SPICE
WITHOUT:
   - empirical constants
   - curve fitting
   - arbitrary multipliers
   - violating topology structure



"""
}

# B. PHYSICS MODULES (The Rules)
PHYSICS_MODULES = {
    "short_channel_65nm": """
### 0. DEEP SUB-MICRON PHYSICS ENGINE (65nm & Below)
Please note that in a 65nm Short-Channel node, standard "Square Law" textbook equations ($I_d = 0.5 \mu C_{ox} W/L (V_{gs}-V_{th})^2$) are generally inaccurate for this exercise. 
Avoid using them. Do not calculate $\mu C_{ox}$. Do not assume constant $\lambda$.

Adhere to the following 4 pillars of Short-Channel Physics:

#### 1. THE $g_m/I_d$ CONTINUUM (Region of Operation)
Transistor performance is determined strictly by Inversion Coefficient (IC), proxied by $g_m/I_d$ ($S/A$).
* **Weak Inversion (Subthreshold):**
    * *Range:* $g_m/I_d > 20$
    * *Physics:* Diffusion current dominates (Exponential, BJT-like behavior).
    * *Pros/Cons:* Maximum Gain efficiency, Minimum Bandwidth.
* **Moderate Inversion:**
    * *Range:* $10 < g_m/I_d < 20$
    * *Physics:* Drift and Diffusion coexist. The "Sweet Spot" for low-power analog.
* **Strong Inversion (Velocity Saturation):**
    * *Range:* $g_m/I_d < 10$
    * *Physics:* **Velocity Saturation** dominates. Current is linear with Overdrive ($V_{ov}$), NOT quadratic.
    * *Pros/Cons:* Maximum Bandwidth, Poor Gain efficiency, linearity degradation.

#### 2. SHORT CHANNEL EFFECTS (SCE) - The "Gain Killers"
In 65nm, the channel is not a perfect resistor. Model these effects via LUT parameters:
* **DIBL (Drain-Induced Barrier Lowering):** The drain voltage lowers the source barrier. 
    * *Impact:* $V_{th}$ drops as $V_{ds}$ increases. This manifests as a finite Output Conductance ($g_{ds}$).
    * *Rule:* $r_o \neq 1/(\lambda I_d)$. **$r_o = 1/g_{ds}$ (strictly from LUT).**
* **CLM (Channel Length Modulation):** Effective length reduces with $V_{ds}$.
    * *Impact:* Further degrades $r_o$.
* **Body Effect ($g_{mb}$):** The bulk is a second gate. 
    * *Rule:* In source followers or cascodes where $V_{sb} > 0$, you MUST include $g_{mb}$ in the transconductance sum ($g_m + g_{mb}$). It is often 10-20% of $g_m$.

#### 3. SATURATION & HEADROOM ENFORCEMENT
"Saturation" is not a binary switch. It is a gradient.
* **Classic Definition:** $V_{ds} > V_{ov}$ (Invalid in 65nm).
* **Modern Definition:** $V_{ds} > V_{dsat}$ (Critical Field approach).
* **The "Headroom Crunch":** As $V_{ds}$ approaches $V_{dsat}$, $g_{ds}$ rises exponentially, destroying gain.
    * *Check:* If $V_{ds} < V_{dsat} + 50mV$, the device is in "Triode-Saturation transition." Flag this as a potential accuracy loss point.

#### 4. DYNAMIC PARASITICS (Bandwidth Limits)
Capacitance is highly non-linear and bias-dependent.
* **Miller Effect:** $C_{gd}$ is the dominant bandwidth killer in high-gain stages. 
    * *Equation:* $C_{in} = C_{gs} + C_{gd} * (1 + A_v)$.
"""
}

# C. LUT DEFINITIONS (The Data Dictionary)
LUT_PARAMETERS = """
### AVAILABLE LUT PARAMETERS (Atomic Physics)
You have access to the following pre-computed atomic parameters for every transistor. 
Please only use these specific variable names in your equations:

"L": Length, 
"W": Normalized width (1um), 
"vgs": Gate-source volatge, 
"vds": Drain-source voltage, 
"vsb": Source-bulk voltage, 
"id_raw": Raw drain current (unscaled), 
"id": Drain current, 
"gm": Transconductance, 
"gds": Output conductance, 
"gmb": Body transconductance, 
"gmid": Transconductance efficiency (gm/Id), 
"vth": Threshold voltage, 
"vdsat": Saturation voltage, 
"cgg_int": Intrinsic total gate capacitance, 
"cgd_int": Intrinsic gate-drain capacitance, 
"cgs_int": Intrinsic gate-source capacitance, 
"cbg_int": Intrinsic bulk-gate capacitance, 
"cbd_int": Intrinsic bulk-drain capacitance, 
"cbs_int": Intrinsic bulk-source capacitance, 
"cdg_int": Intrinsic drain-gate capacitance, 
"cdd_int": Intrinsic total drain capacitance, 
"cds_int": Intrinsic drain-source capacitance, 
"cgg": Total gate capacitance, 
"cgd": Total gate-drain capacitance, 
"cgs": Total gate-source capacitance, 
"cdd": Total drain capacitance, 
"cds": Total drain-source capacitance, 
"cbd": Bulk-drain junction capacitance, 
"cb": Total bulk capacitance

**Ensure you preserve the exact name of each of these parameters. Do not interpret cbd as cdb.**


**DESIRED EQUATION FORMAT**
Make sure the equations are a function of the direct LUT parameters. 
For example, 
DO NOT DO THIS:  "equation": "20*log10(abs(Av0)) ; Av0 = Gm_diff_to_out / G_out_total ; Gm_diff_to_out = gm_m2 + gm_m3; G_out_total = gds_m3 + gds_m2", Its generating equations in this format, but I want it to be in the extreme parameteriziation, no heirarchy like this
DO THIS: "equation": "20*log10(abs((gm_m2 + gm_m3)/(gds_m3 + gds_m2)))"

**STRONG SUGGESTION FOR BUILDING EQUATION**
Do not consider all the device parmaters all at once. Like adding all caps, or gm or gds. Take more complex terms only if the accuracy without them is not good enough.
"""

# D. OUTPUT SCHEMA (Strict JSON)
OUTPUT_SCHEMA_JSON = """
### OUTPUT FORMAT (STRICT JSON)
{
  "0_THINKING_SCRATCHPAD": {
    "<INSERT_FAIL_METRIC_NAME_1>": "Step 1: The dominant path is... Step 2: The previous equation under-estimated... Step 3: A supply-to-output conductance path was missed... Step 4: I will include the gds of the current source in the denominator.",
    "<INSERT_FAIL_METRIC_NAME_2>": "Step 1: ... Step 2: ... Step 3: ... Step 4: ..."
  },
  "1_TOPOLOGY_SUMMARY": {
    "Topology_Name": "String",
    "Signal_Chain": [
      "List",
      "of",
      "device",
      "names"
    ],
    "Stacking_Structure": {
      "Output_to_VDD": [
        "List of devices"
      ],
      "Output_to_VSS": [
        "List of devices"
      ]
    }
  },
  "2_DEVICE_MAPPING": {
    "Input_Diff_Pair": [
      "List of devices"
    ],
    "Active_Load": [
      "List of devices"
    ],
    "Tail_Current": [
      "List of devices"
    ],
    "Cascode_Devices": [
      "List of devices"
    ]
  },
  "3_PERFORMANCE_METRICS": {
    "DC_Gain_dB": {
      "equation_math": "20 * math.log10(abs(gm_m0 / (gds_m2 + gds_m3)))",
      "explanation": "Brief physical justification."
    },
    "Bandwidth_3dB_Hz": {
      "equation_math": "...",
      "explanation": "..."
    },
    "UGB_Hz": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Phase_Margin_deg": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Gain_Margin_dB": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Input_CMR_Min_V": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Input_CMR_Max_V": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Output_Swing_Max_V": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Output_Swing_Min_V": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Slew_Rate_Pos_V_us": {
      "equation_math": "...",
      "explanation": "..."
    },
    "Slew_Rate_Neg_V_us": {
      "equation_math": "...",
      "explanation": "..."
    },
    "PSRR_Pos_dB": {
      "equation_math": "...",
      "explanation": "..."
    },
    "PSRR_Neg_dB": {
      "equation_math": "...",
      "explanation": "..."
    },
    "CMRR_dB": {
      "equation_math": "...",
      "explanation": "..."
    }
  },
  "4_PYTHON_GENERATION": {
    "code": "import math\n\nclass PerformanceModel:\n    def compute(self, device_params, C_load, Vdd, Vss, **additional passive elements liek c0, r0, etc):\n        # SECTION A: Safe Parameter Extraction\n        # Implement mapping to convert device_params keys to exact case or use a case-insensitive getter\n        \n        # Example extraction mapping:\n        # try:\n        #     m0_gm = device_params['m0']['gm']\n        # except KeyError:\n        #     m0_gm = 0.0\n        \n        # SECTION B: Results dictionary\n        results = {\n            \"DC_Gain_dB\": 0.0, # dB\n            \"Bandwidth_3dB_Hz\": 0.0, # Hz\n            \"UGB_Hz\": 0.0, # Hz\n            \"Phase_Margin_deg\": 0.0, # deg\n            \"Gain_Margin_dB\": 0.0, # dB\n            \"Input_CMR_Min_V\": 0.0, # V\n            \"Input_CMR_Max_V\": 0.0, # V\n            \"Output_Swing_Max_V\": 0.0, # V\n            \"Output_Swing_Min_V\": 0.0, # V\n            \"Slew_Rate_Pos_V_us\": 0.0, # V/us\n            \"Slew_Rate_Neg_V_us\": 0.0, # V/us\n            \"PSRR_Pos_dB\": 0.0, # dB\n            \"PSRR_Neg_dB\": 0.0, # dB\n            \"CMRR_dB\": 0.0 # dB\n        }\n        return results\n\ndef get_default_lut_row():\n    return {\n        \"L\": 0.0, \"W\": 0.0, \"vgs\": 0.0, \"vds\": 0.0, \"vsb\": 0.0,\n        \"id_raw\": 0.0, \"id\": 0.0, \"gm\": 0.0, \"gds\": 0.0, \"gmb\": 0.0,\n        \"gmid\": 0.0, \"vth\": 0.0, \"vdsat\": 0.0, \"cgg_int\": 0.0,\n        \"cgd_int\": 0.0, \"cgs_int\": 0.0, \"cbg_int\": 0.0, \"cbd_int\": 0.0,\n        \"cbs_int\": 0.0, \"cdg_int\": 0.0, \"cdd_int\": 0.0, \"cds_int\": 0.0,\n        \"cgg\": 0.0, \"cgd\": 0.0, \"cgs\": 0.0, \"cdd\": 0.0, \"cds\": 0.0,\n        \"cbd\": 0.0, \"cb\": 0.0\n    }\n\nif __name__ == \"__main__\":\n    # Mock device parameters\n    mock_params = {\n        \"m0\": get_default_lut_row(),\n        \"m1\": get_default_lut_row()\n    }\n    \n    model = PerformanceModel()\n    output = model.compute(device_params=mock_params, C_load=1e-12, Vdd=1.0, Vss=0.0)\n    \n    for metric, value in output.items():\n        print(f\"{metric}: {value}\")"
  }
}
"""

# ==============================================================================
# 2. TASK TEMPLATES (The Logic Flow)
# ==============================================================================

TASKS = {
    "generate_model": """
### YOUR TASK
Perform the following steps sequentially to generate the output JSON:

#### STEP 1: Topology Identification & Signal Flow
* Read the netlist connectivity provided at the end of this prompt.
* Identify the **Analog Topology** (examples include: "Single-ended common-source with current-mirror active load", "Current-mirror OTA core", "Differential pair with current-mirror load", "Folded cascode", "Telescopic cascode", "Two-stage Miller", etc.). Do NOT force a differential pair unless connectivity proves it.
* Trace the **Signal Chain** (Input -> Amplification Stages -> Output).
* Identify the **Stacking Structure**:
    * Which devices are stacked between Output and VDD? (The "Pull-up" network)
    * Which devices are stacked between Output and VSS? (The "Pull-down" network)

#### STEP 2: Primitive Block Decomposition
* Break the topology down into standard sub-blocks. 
Identify groups of transistors forming (ONLY if connectivity proves they exist): 
* **Differential Pair (conditional):** label ONLY if two devices share a common source node AND their gates are driven by two different input nets AND their drains connect to two load branches (separate drains) that together form the amplifier output (single ended or differential). If any of these conditions fails, do NOT call it a differential pair. 
* **Single ended transconductor (common source, conditional):** label if one input device provides the main gm to the output node and the other input labeled device is actually part of bias or mirror sensing. 
* **Current Mirror / Active Load (conditional):** label if one device is diode connected (gate=drain) and another device shares that gate net to mirror current into the output branch. 
* **Tail Current Source / Bias Device (conditional):** label if a device sources or sinks DC bias current into a source node or branch and its gate is tied to a bias net. 
* **Cascode Stack (conditional):** label ONLY if a device is stacked with another device and its gate is held at a bias such that it regulates Vds of the lower device.
* *Reasoning:* Use these sub-blocks to determine intermediate impedances. For example, if you identify a Cascode, the output resistance is not just 1/gds but approx (gm/gds) * ro.

#### STEP 3: Device Mapping
* Map specific netlist instance names (e.g., M1, xm3) to their **Functional Roles**:
    * **Input_Diff_Pair**
    * **Active_Load**
    * **Tail_Current**
    * **Cascode_Devices** (if applicable)

#### STEP 4: Theoretical Formulation (Textbook + Non-Idealities)
* Derive equations for the metrics listed in the "PERFORMANCE_METRICS" section of the output schema.
* **Enhance Standard Textbook Equations:**
    * **Gain:** Use the exact conductance sum at the output node: Av = Gm_eff / G_out_total.
    * **Slew Rate:** Consider the total current available to charge/discharge the dominant capacitor (I_tail or I_bias).
    * **Non-Idealities:** Include gds (channel length modulation) in all Gain and CMRR equations.

#### STEP 5: Python Model Generation
* Generate a robust Python script containing a class `PerformanceModel`.
* The class must have a `compute(device_params, C_load, Vdd, Vss)` method.
* Add print statement after every metric calculation for easy debugging. 
* Make sure not to create tuples for the max () functions, which will break the flow. Keep everything of type float for the metrics calculations
* **Math Safety:** The script must handle missing keys or zero-values gracefully. 
    * *Example:* Use `max(gds_m2 + gds_m3, 1e-12)` to prevent Divide-By-Zero errors.
* **Parameter naming convention** To represent a parameter for a device (for example gds of device m1), use param_device (i.e. gds_m1).
* **CASE SENSITIVITY:** Ensure you preserve the exact case of the instance names as they appear in the netlist. Do not capitalize names for readability if they are lowercase in the netlist.
* **Unit Handling:**
    * Take extra care of brackets. Make sure balanced ( and ).
    * **Internal Calculation:** All math should be in base **SI Units** (Volts, Amperes, Ohms, Farads, Hz). Do not convert to dB or Hz inside the variables themselves.
    * **Display:** In the `if __name__ == "__main__":` block, convert these values to readable units for printing.
    * Hard rule: compute() MUST return Bandwidth and UGB in Hz, Slew Rate in V/us (or explicitly labeled V/us only at final display), and ALL dB metrics computed as 20*log10 of unitless ratios. 
#### STEP 6: CODE GENERATION GUARDRAILS (Avoid these common crashes)
Please carefully review your Python code against these common execution failures before finalizing:
* ** AVOID TOO LONG EQUATIONS** 
For example: AVOID 
CMRR_dB = 20*math.log10(abs(max((gm_m2/max(((gds_m4/max((1 + (gm_m4 + gmb_m4)/max(gds_m2,1e-18)),1e-18),1e-18) + gds_m2/max((1 + (gm_m4 + gmb_m4)/max(gds_m4,1e-18)),1e-18),1e-18)) + (gds_m6/max((1 + (gm_m6 + gmb_m6)/max(gds_m8,1e-18)),1e-18),1e-18) + gds_m8/max((1 + (gm_m6 + gmb_m6)/max(gds_m6,1e-18)),1e-18),1e-18)),1e-18)),1e-18)/max(((gds_m9 + gds_m1 + gds_m2 + gds_m3 + gds_m4)/max((gm_m1 + gm_m2 + gmb_m1 + gmb_m2),1e-18))*(((gds_m4/max((1 + (gm_m4 + gmb_m4)/max(gds_m2,1e-18)),1e-18),1e-18) + gds_m2/max((1 + (gm_m4 + gmb_m4)/max(gds_m4,1e-18)),1e-18),1e-18)) + (gds_m6/max((1 + (gm_m6 + gmb_m6)/max(gds_m8,1e-18)),1e-18),1e-18) + gds_m8/max((1 + (gm_m6 + gmb_m6)/max(gds_m6,1e-18)),1e-18),1e-18)))/max((gm_m4 + gm_m6 + gmb_m4 + gmb_m6),1e-18)),1e-18)))

And Break it down into: 
        ro_dn = (gds_m4 / max((1 + (gm_m4 + gmb_m4) / max(gds_m2, 1e-18)), 1e-18)
            + gds_m2 / max((1 + (gm_m4 + gmb_m4) / max(gds_m4, 1e-18)), 1e-18))
        ro_up = (gds_m6 / max((1 + (gm_m6 + gmb_m6) / max(gds_m8, 1e-18)), 1e-18)
            + gds_m8 / max((1 + (gm_m6 + gmb_m6) / max(gds_m6, 1e-18)), 1e-18))
        Ad = gm_m2 / max((ro_dn + ro_up), 1e-18)
        Acm = (((gds_m9 + gds_m1 + gds_m2 + gds_m3 + gds_m4) / max((gm_m1 + gm_m2 + gmb_m1 + gmb_m2), 1e-18))
            * ((ro_dn + ro_up) / max((gm_m4 + gm_m6 + gmb_m4 + gmb_m6), 1e-18)))
        CMRR_dB = 20 * math.log10(abs(max((Ad / max(Acm, 1e-18)), 1e-18)))

* **Avoid NameErrors (Undeclared Variables):** * *Bad:* `results['Gain'] = gm_m3 / gds_m3` (Throws `NameError: name 'gm_m3' is not defined` if `m3` was never extracted).
    * *Fix:* Ensure EVERY parameter (like `gm_m3`, `gds_m1`) used in SECTION B is explicitly extracted and defined in SECTION A. If the device isn't in the netlist, do not use it.
* **Avoid Math Domain Errors (Logarithm crashes):**
    * *Bad:* `20 * math.log10(Av)` (Throws `ValueError: math domain error` if Av is negative).
    * *Fix:* Always use the absolute value for gains inside logs: `20 * math.log10(abs(Av))`.
* **Avoid ZeroDivisionError:**
    * *Bad:* `Av = gm_m1 / (gds_m1 + gds_m2)` (Throws `ZeroDivisionError` if gds values are exactly 0.0 in some edge cases).
    * *Fix:* Always clamp denominators: `Av = gm_m1 / max((gds_m1 + gds_m2), 1e-18)`.
* **Avoid KeyError (Missing Devices):**
    * *Bad:* `m3 = device_params['m3']` when `m3` does not exist in the netlist.
    * *Fix:* Only extract devices that strictly exist in the provided NETLIST REFERENCE. Use safe getters with fallbacks if necessary.

---
${output_schema}

---
Please follow the exact name of the devices that appear in the NETLIST file. Please do not introduce any new device which is not available in the netlist.
### NETLIST TO ANALYZE
${netlist}
""",

    "iterative_refinement": """
### YOUR TASK: DEBUGGING & REFINEMENT
The previous model did not perfectly match the SPICE simulation (Ground Truth).
Please refine the equations to close the gap.
#### STEP 1: Topology Identification & Signal Flow
* Read the netlist connectivity provided at the end of this prompt.
* Identify the **Analog Topology** (examples include: "Single-ended common-source with current-mirror active load", "Current-mirror OTA core", "Differential pair with current-mirror load", "Folded cascode", "Telescopic cascode", "Two-stage Miller", etc.). Do NOT force a differential pair unless connectivity proves it.
* Trace the **Signal Chain** (Input -> Amplification Stages -> Output).
* Identify the **Stacking Structure**:
    * Which devices are stacked between Output and VDD? (The "Pull-up" network)
    * Which devices are stacked between Output and VSS? (The "Pull-down" network)

#### STEP 2: Primitive Block Decomposition
* Break the topology down into standard sub-blocks. 
Identify groups of transistors forming (ONLY if connectivity proves they exist): 
* **Differential Pair (conditional):** label ONLY if two devices share a common source node AND their gates are driven by two different input nets AND their drains connect to two load branches (separate drains) that together form the amplifier output (single ended or differential). If any of these conditions fails, do NOT call it a differential pair. 
* **Single ended transconductor (common source, conditional):** label if one input device provides the main gm to the output node and the other input labeled device is actually part of bias or mirror sensing. 
* **Current Mirror / Active Load (conditional):** label if one device is diode connected (gate=drain) and another device shares that gate net to mirror current into the output branch. 
* **Tail Current Source / Bias Device (conditional):** label if a device sources or sinks DC bias current into a source node or branch and its gate is tied to a bias net. 
* **Cascode Stack (conditional):** label ONLY if a device is stacked with another device and its gate is held at a bias such that it regulates Vds of the lower device.
* *Reasoning:* Use these sub-blocks to determine intermediate impedances. For example, if you identify a Cascode, the output resistance is not just 1/gds but approx (gm/gds) * ro.

#### STEP 3: Device Mapping
* Map specific netlist instance names (e.g., M1, xm3) to their **Functional Roles**:
    * **Input_Diff_Pair**
    * **Active_Load**
    * **Tail_Current**
    * **Cascode_Devices** (if applicable)

#### STEP 4: Theoretical Formulation (Textbook + Non-Idealities)
* Derive equations for the metrics listed in the "PERFORMANCE_METRICS" section of the output schema.
* **Enhance Standard Textbook Equations:**
    * **Gain:** Use the exact conductance sum at the output node: Av = Gm_eff / G_out_total.
    * **Slew Rate:** Consider the total current available to charge/discharge the dominant capacitor (I_tail or I_bias).
    * **Non-Idealities:** Include gds (channel length modulation) in all Gain and CMRR equations.

#### STEP 5: Python Model Generation
* Generate a robust Python script containing a class `PerformanceModel`.
* The class must have a `compute(device_params, C_load, Vdd, Vss)` method.
* Add print statement after every metric calculation for easy debugging. 
* Make sure not to create tuples for the max () functions, which will break the flow. Keep everything of type float for the metrics calculations
* **Math Safety:** The script must handle missing keys or zero-values gracefully. 
    * *Example:* Use `max(gds_m2 + gds_m3, 1e-12)` to prevent Divide-By-Zero errors.
* **Parameter naming convention** To represent a parameter for a device (for example gds of device m1), use param_device (i.e. gds_m1).
* **CASE SENSITIVITY:** Ensure you preserve the exact case of the instance names as they appear in the netlist. Do not capitalize names for readability if they are lowercase in the netlist.
* **Unit Handling:**
    * Take extra care of brackets. Make sure balanced ( and ).
    * **Internal Calculation:** All math should be in base **SI Units** (Volts, Amperes, Ohms, Farads, Hz). Do not convert to dB or Hz inside the variables themselves.
    * **Display:** In the `if __name__ == "__main__":` block, convert these values to readable units for printing.
    * Hard rule: compute() MUST return Bandwidth and UGB in Hz, Slew Rate in V/us (or explicitly labeled V/us only at final display), and ALL dB metrics computed as 20*log10 of unitless ratios. 
    
#### STEP 6: CODE GENERATION GUARDRAILS (Avoid these common crashes)
Please carefully review your Python code against these common execution failures before finalizing:
* ** AVOID TOO LONG EQUATIONS** 
For example: AVOID 
CMRR_dB = 20*math.log10(abs(max((gm_m2/max(((gds_m4/max((1 + (gm_m4 + gmb_m4)/max(gds_m2,1e-18)),1e-18),1e-18) + gds_m2/max((1 + (gm_m4 + gmb_m4)/max(gds_m4,1e-18)),1e-18),1e-18)) + (gds_m6/max((1 + (gm_m6 + gmb_m6)/max(gds_m8,1e-18)),1e-18),1e-18) + gds_m8/max((1 + (gm_m6 + gmb_m6)/max(gds_m6,1e-18)),1e-18),1e-18)),1e-18)),1e-18)/max(((gds_m9 + gds_m1 + gds_m2 + gds_m3 + gds_m4)/max((gm_m1 + gm_m2 + gmb_m1 + gmb_m2),1e-18))*(((gds_m4/max((1 + (gm_m4 + gmb_m4)/max(gds_m2,1e-18)),1e-18),1e-18) + gds_m2/max((1 + (gm_m4 + gmb_m4)/max(gds_m4,1e-18)),1e-18),1e-18)) + (gds_m6/max((1 + (gm_m6 + gmb_m6)/max(gds_m8,1e-18)),1e-18),1e-18) + gds_m8/max((1 + (gm_m6 + gmb_m6)/max(gds_m6,1e-18)),1e-18),1e-18)))/max((gm_m4 + gm_m6 + gmb_m4 + gmb_m6),1e-18)),1e-18)))

And Break it down into: 
        ro_dn = (gds_m4 / max((1 + (gm_m4 + gmb_m4) / max(gds_m2, 1e-18)), 1e-18)
            + gds_m2 / max((1 + (gm_m4 + gmb_m4) / max(gds_m4, 1e-18)), 1e-18))
        ro_up = (gds_m6 / max((1 + (gm_m6 + gmb_m6) / max(gds_m8, 1e-18)), 1e-18)
            + gds_m8 / max((1 + (gm_m6 + gmb_m6) / max(gds_m6, 1e-18)), 1e-18))
        Ad = gm_m2 / max((ro_dn + ro_up), 1e-18)
        Acm = (((gds_m9 + gds_m1 + gds_m2 + gds_m3 + gds_m4) / max((gm_m1 + gm_m2 + gmb_m1 + gmb_m2), 1e-18))
            * ((ro_dn + ro_up) / max((gm_m4 + gm_m6 + gmb_m4 + gmb_m6), 1e-18)))
        CMRR_dB = 20 * math.log10(abs(max((Ad / max(Acm, 1e-18)), 1e-18)))
* **Avoid NameErrors (Undeclared Variables):** * *Bad:* `results['Gain'] = gm_m3 / gds_m3` (Throws `NameError: name 'gm_m3' is not defined` if `m3` was never extracted).
    * *Fix:* Ensure EVERY parameter (like `gm_m3`, `gds_m1`) used in SECTION B is explicitly extracted and defined in SECTION A. If the device isn't in the netlist, do not use it.
* **Avoid Math Domain Errors (Logarithm crashes):**
    * *Bad:* `20 * math.log10(Av)` (Throws `ValueError: math domain error` if Av is negative).
    * *Fix:* Always use the absolute value for gains inside logs: `20 * math.log10(abs(Av))`.
* **Avoid ZeroDivisionError:**
    * *Bad:* `Av = gm_m1 / (gds_m1 + gds_m2)` (Throws `ZeroDivisionError` if gds values are exactly 0.0 in some edge cases).
    * *Fix:* Always clamp denominators: `Av = gm_m1 / max((gds_m1 + gds_m2), 1e-18)`.
* **Avoid KeyError (Missing Devices):**
    * *Bad:* `m3 = device_params['m3']` when `m3` does not exist in the netlist.
    * *Fix:* Only extract devices that strictly exist in the provided NETLIST REFERENCE. Use safe getters with fallbacks if necessary.




### 1. CUMULATIVE LEARNING LOG (Review Carefully)
The following log shows previous attempts. 
**IMPORTANT GUIDELINE:** Please avoid repeating an equation that has already failed in a previous stage with the same error magnitude.

${history_log}

### 2. CURRENT STATUS OVERVIEW
The table below highlights the specific metrics that failed the accuracy threshold in the most recent run.
${current_error_table}

### 3. DEBUGGING INSTRUCTIONS
1. **Analyze the Trend:** Look at the "History Log". Did the error decrease or increase in the last step?
    * *Example:* If Stage 1 Gain was 13dB, and Stage 2 Gain was 18dB (Target 20dB), your change was correct but insufficient.
    * *Example:* If Stage 2 made the Bandwidth error *worse*, REVERT that specific change.
2. **Identify Missing Physics:**
    * **If Under-estimating Gain:** Are you missing the Cascode shielding factor (gm * ro)?
    * **If Over-estimating Bandwidth:** Did you forget the Gate-Drain capacitance (Cgd) Miller effect?
    * **If CMRR is poor:** Did you include the tail current source's finite output impedance (gds)?

### 4. EXECUTION
Generate the standard Output JSON. 
* **GUIDELINE:** For any metric marked [PASS], please reuse the successful equation verbatim. Do not reformat, reorder, or simplify it.
* **Update** ONLY the equations for the [FAIL] metrics.
* **Explain** specifically why the new equation fixes the error seen in the log while maintaining the integrity of the signal path.
---
${output_schema}

Please follow the exact name of the devices that appear in the NETLIST file. Do not introduce any new devices not available in the netlist.
### NETLIST REFERENCE
${netlist}

###Remember to analyze the current NETLIST with the NETLISTS in the HISTORY DATABASE Mentioned previously to find similar equations in case of similar topology.
"""
}

# ==============================================================================
# 3. DYNAMIC FUNCTIONS (The Logic)
# ==============================================================================

def _format_metrics_table(metrics: Dict[str, Dict[str, Any]]) -> str:
    """
    Converts a dictionary of metrics into a Markdown table string.
    
    Args:
        metrics: {
            "DC_Gain_dB": {"spice": 20.0, "model": 15.0, "error": -25.0, "status": "FAIL"},
            ...
        }
    """
    lines = []
    # We construct the table body
    for key, data in metrics.items():
        spice_val = data.get('spice', 0.0)
        model_val = data.get('model', 0.0)
        error_val = data.get('error', 0.0)
        status = data.get('status', 'UNKNOWN')
        
        # Format: | Metric | SPICE | Model | Error | Status |
        line = f"| {key} | {spice_val:.4g} | {model_val:.4g} | {error_val:.1f}% | {status} |"
        lines.append(line)
    
    return "\n".join(lines)


def _format_history_log(history_records: List[Dict]) -> str:
    """
    Converts a list of historical records into a formatted text log.
    
    Args:
        history_records: List of dicts, where each dict contains:
            - iteration (int)
            - failures (list of dicts: {metric, equation, error})
            - notes (str)
    """
    if not history_records:
        return "No previous history. This is the first iteration."

    log_blocks = []
    for record in history_records:
        iter_num = record.get('iteration', '?')
        failures = record.get('failures', [])
        notes = record.get('notes', 'No notes provided.')
        
        # 1. Header
        block = [f"--- ITERATION {iter_num} ---"]
        
        # 2. Failures
        if failures:
            block.append("**FAILED EQUATIONS & ERRORS:**")
            for f in failures:
                # Expecting f to be a dict: {'metric': '...', 'equation': '...', 'error': '...'}
                metric = f.get('metric', 'Unknown')
                eqn = f.get('equation', 'N/A')
                err = f.get('error', 'N/A')
                block.append(f"  - {metric}: Equation Used: '{eqn}' (Error: {err})")
        else:
            block.append("**ALL METRICS PASSED**")
            
        # 3. Notes/Reasoning
        block.append(f"**PREVIOUS REASONING:**\n\"{notes}\"")
        
        log_blocks.append("\n".join(block))
        
    return "\n\n".join(log_blocks)

def generate_context_of_equations_old(equation_library, mismatch_data):
    """
    Generates an LLM prompt for iterative Topology Modeling.
    Supports an arbitrary number of stages, emphasizing model evolution.
    """
    
    prompt_sections = []
    
    # --- HEADER & EVOLUTIONARY MODELING GUIDE ---
    prompt_sections.append("## ANALOG TOPOLOGY MODELING: MULTI-STAGE REFINEMENT")
    
    prompt_sections.append("""
### SYSTEM OVERVIEW & INTERPRETATION:
1. **The Modeling Goal**: You are refining analytical models for an evolving circuit topology. The 'Simulated' values are the ground truth. Your task is to update the 'Calculated' equations to reduce the error.
2. **Evolutionary Logic**: The design is presented in multiple stages (Stage 1 to Stage N). Typically, higher stages represent more complex or refined versions of the topology. You should analyze how the equations change across stages to identify where terms are being added or omitted.
3. **FAIL vs. PASS**: 
    - **[FAIL]**: The current equation is a poor representation of the physics for that specific stage. Look for missing parasitic conductances, ignored capacitances, or incorrect algebraic combinations. Please avoid repeating an equation that has already FAILED.
    - **[PASS]**: The model is currently accurate. Use the PASSing logic as a reference for what terms are correctly captured. Do not change them.
    - Do not change an equation that has already PASSED under any circumstances.
4. Please refrain from including arbitrary constant factors (For example: 0.5, 0.4, 10, 1000 etc.), instead make use of the device parameters explicitly.
5. Please maintain the equations that have already PASSED.
6. Please do not reproduce the exact same equation that has previously FAILED with a significant error percentage.
7. MOST IMPORTANT, if you see an equation under FAILING metric with an absolute error less than 5%, then reproduce the exact same equation. No need to generate any new equation for that metric.
8. Do not stick to the same structure of the equation. Its better to try out a different structure as well.
9. Think of it from an Anlog designers' point of view.

""")

    # --- SECTION 2: METRIC ANALYSIS ---
    prompt_sections.append("\n### 2. PERFORMANCE METRIC ANALYSIS")
    
    sorted_stages = sorted(equation_library.keys(), key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))

    for metric, results in mismatch_data.items():
        sim_val, calc_val, error, status = results
        prompt_sections.append(f"\n#### [{status}] {metric}")
        
        if status == 'PASS':
            # Hunt for the equation in the library, starting from the latest stage
            current_eq = "N/A"
            for stage in reversed(sorted_stages):
                found_eq = equation_library.get(stage, {}).get('Performance_Equations', {}).get(metric)
                if found_eq:
                    current_eq = found_eq
                    break
            
            prompt_sections.append(f"  - **STATUS**: VERIFIED ACCURATE")
            prompt_sections.append(f"  - **LOCKED EQUATION**: `{current_eq['equation']}` with an error of {error}%")
            prompt_sections.append(f"  - **INSTRUCTION**: Do not modify. Carry this forward exactly.")
        else:
            # Uncommented your status lines so the LLM knows the current target error
            prompt_sections.append(f"  - **Simulated (Truth)**: {sim_val:.4f} | **Calculated (Model)**: {calc_val:.4f}")
            prompt_sections.append(f"  - **Status**: {status} | **Current Error**: {error:.2f}%")
            
            # Collect and parse the history
            historical_eqs = []
            latest_stage = sorted_stages[-1] if sorted_stages else None

            for stage in sorted_stages:
                found_eq = equation_library.get(stage, {}).get('Performance_Equations', {}).get(metric)
                
                eq_str = None
                err_val = None
                
                # Extract the equation string
                if isinstance(found_eq, dict):
                    eq_str = found_eq.get('equation')
                    err_val = found_eq.get('error_pct', found_eq.get('error')) # Check both common keys
                elif isinstance(found_eq, str):
                    eq_str = found_eq
                
                # FIX: If this is the current (latest) stage and it's missing the error dict key, 
                # grab the error directly from mismatch_data!
                if stage == latest_stage and err_val is None:
                    err_val = error

                # If we successfully found both an equation and an error, add it to history
                if eq_str and err_val is not None:
                    historical_eqs.append({
                        'stage': stage,
                        'equation': eq_str,
                        'error_pct': float(err_val)
                    })
            
            if historical_eqs:
                
                # --- NEW: Deduplicate to keep distinct errors only ---
                unique_eqs = []
                seen_errors = set()
                
                for eq_data in historical_eqs:
                    # Rounding to 4 decimal places ensures minor float precision issues don't bypass the filter
                    error_key = round(eq_data['error_pct'], 4) 
                    
                    if error_key not in seen_errors:
                        seen_errors.add(error_key)
                        unique_eqs.append(eq_data)
                        
                # Overwrite historical_eqs with the deduplicated list
                historical_eqs = unique_eqs
                # -----------------------------------------------------

                # Sort by absolute error percentage (ascending)
                historical_eqs.sort(key=lambda x: abs(x['error_pct']))

                # NEW: If best historical equation is already good enough (<15%),
                # follow PASS template and do NOT print the rest.
                best_eq = historical_eqs[0]
                best_err = float(best_eq['error_pct'])
                if abs(best_err) < 5.0:
                    current_eq = {'equation': best_eq['equation']}  # keep PASS-style indexing

                    prompt_sections.append(f"  - **STATUS**: VERIFIED ACCURATE")
                    prompt_sections.append(f"  - **LOCKED EQUATION**: `{current_eq['equation']}` with an error of {best_err:.2f}%")
                    prompt_sections.append(f"  - **INSTRUCTION**: Do not modify. Carry this forward exactly.")
                    continue  # skip printing other equations for this metric

                prompt_sections.append("  - **Historical Equations (Sorted by best error)**:")
                for eq_data in historical_eqs[:10]:
                    err_val = eq_data['error_pct']
                    eq_str = eq_data['equation']
                    estimation_label = "overestimating" if err_val > 0 else "underestimating"

                    prompt_sections.append(
                        f"    - [{eq_data['stage']}] Error: {err_val:.2f}% ({estimation_label}) | Equation: `{eq_str}`"
                    )
    return "\n".join(prompt_sections)


def generate_context_of_equations(equation_library, mismatch_data, tolerance_spec=None, default_tol=None, error_th = 15):
    """
    Generates an LLM prompt for iterative Topology Modeling.
    Supports an arbitrary number of stages, emphasizing model evolution.

    mismatch_data format: { metric_key: (sim_val, calc_val, error, status) }
      - error can be signed % OR signed absolute error depending on your comparator
      - status is PASS/FAIL
    """

    # -----------------------------
    # Per-metric tolerance handling
    # -----------------------------
    tolerance_spec = tolerance_spec or {}
    default_tol = default_tol or {"mode": "pct", "tol": error_th, "unit": "%"}

    def _get_tol(metric_key: str):
        spec = tolerance_spec.get(metric_key, default_tol)
        mode = spec.get("mode", default_tol["mode"])
        tol = float(spec.get("tol", default_tol["tol"]))
        unit = spec.get("unit", default_tol.get("unit", "%"))
        return mode, tol, unit

    def _is_good_enough(metric_key: str, err_val: float) -> bool:
        mode, tol, _ = _get_tol(metric_key)
        # We assume err_val is already in the right domain (pct or abs)
        return abs(float(err_val)) <= tol

    # --------------------------------
    # Original function logic continues
    # --------------------------------
    prompt_sections = []

    prompt_sections.append("## ANALOG TOPOLOGY MODELING: MULTI-STAGE REFINEMENT")

    prompt_sections.append("""
### SYSTEM OVERVIEW & INTERPRETATION:
1. **The Modeling Goal**: You are refining analytical models for an evolving circuit topology. The 'Simulated' values are the ground truth. Your task is to update the 'Calculated' equations to reduce the error.
2. **Evolutionary Logic**: The design is presented in multiple stages (Stage 1 to Stage N). Typically, higher stages represent more complex or refined versions of the topology. You should analyze how the equations change across stages to identify where terms are being added or omitted.
3. **FAIL vs. PASS**: 
    - **[FAIL]**: The current equation is a poor representation of the physics for that specific stage. Look for missing parasitic conductances, ignored capacitances, or incorrect algebraic combinations. Please avoid repeating an equation that has already FAILED.
    - **[PASS]**: The model is currently accurate. Use the PASSing logic as a reference for what terms are correctly captured. Do not change them.
    - Do not change an equation that has already PASSED under any circumstances.
4. Please refrain from including arbitrary constant factors (For example: 0.5, 0.4, 10, 1000 etc.), instead make use of the device parameters explicitly.
5. Please maintain the equations that have already PASSED.
6. Please do not reproduce the exact same equation that has previously FAILED with a significant error percentage.
7. MOST IMPORTANT: if a FAILING metric has an absolute error within its metric-specific tolerance, then reproduce the exact same equation. No need to generate any new equation for that metric.
8. Do not stick to the same structure of the equation. Its better to try out a different structure as well.
9. Think of it from an Anlog designers' point of view.
""")

    prompt_sections.append("\n### 2. PERFORMANCE METRIC ANALYSIS")

    sorted_stages = sorted(equation_library.keys(), key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))

    for metric, results in mismatch_data.items():
        sim_val, calc_val, error, status = results

        mode, tol, unit = _get_tol(metric)

        prompt_sections.append(f"\n#### [{status}] {metric}")
        prompt_sections.append(f"  - **Tolerance Rule**: mode={mode}, tol={tol}{unit}")

        if status == 'PASS':
            current_eq = "N/A"
            for stage in reversed(sorted_stages):
                found_eq = equation_library.get(stage, {}).get('Performance_Equations', {}).get(metric)
                if found_eq:
                    current_eq = found_eq
                    break

            # current_eq might be dict or str
            if isinstance(current_eq, dict):
                eq_str = current_eq.get("equation", "N/A")
            else:
                eq_str = str(current_eq)

            prompt_sections.append(f"  - **STATUS**: VERIFIED ACCURATE")
            prompt_sections.append(f"  - **LOCKED EQUATION**: `{eq_str}` | error={float(error):.4g}{unit}")
            prompt_sections.append(f"  - **INSTRUCTION**: Do not modify. Carry this forward exactly.")
            continue

        # FAIL path
        prompt_sections.append(f"  - **Simulated (Truth)**: {sim_val:.4f} | **Calculated (Model)**: {calc_val:.4f}")
        prompt_sections.append(f"  - **Status**: {status} | **Current Error**: {float(error):.4g}{unit}")

        historical_eqs = []
        latest_stage = sorted_stages[-1] if sorted_stages else None

        for stage in sorted_stages:
            found_eq = equation_library.get(stage, {}).get('Performance_Equations', {}).get(metric)

            eq_str = None
            err_val = None

            if isinstance(found_eq, dict):
                eq_str = found_eq.get('equation')
                err_val = found_eq.get('error_pct', found_eq.get('error'))
            elif isinstance(found_eq, str):
                eq_str = found_eq

            if stage == latest_stage and err_val is None:
                err_val = error

            if eq_str and err_val is not None:
                historical_eqs.append({
                    'stage': stage,
                    'equation': eq_str,
                    'error_val': float(err_val)   # note: could be pct or abs based on your comparator
                })

        if not historical_eqs:
            continue

        # Deduplicate by error value (same as your logic)
        unique_eqs = []
        seen_errors = set()
        for eq_data in historical_eqs:
            error_key = round(eq_data['error_val'], 4)
            if error_key not in seen_errors:
                seen_errors.add(error_key)
                unique_eqs.append(eq_data)
        historical_eqs = unique_eqs

        # Sort by absolute error (best first)
        historical_eqs.sort(key=lambda x: abs(x['error_val']))

        best_eq = historical_eqs[0]
        best_err = float(best_eq['error_val'])

        # Replace hardcoded 15% with metric-specific tolerance
        if _is_good_enough(metric, best_err):
            prompt_sections.append(f"  - **STATUS**: VERIFIED ACCURATE")
            prompt_sections.append(f"  - **LOCKED EQUATION**: `{best_eq['equation']}` | error={best_err:.4g}{unit}")
            prompt_sections.append(f"  - **INSTRUCTION**: Do not modify. Carry this forward exactly.")
            continue

        prompt_sections.append("  - **Historical Equations (Sorted by best error)**:")
        for eq_data in historical_eqs[:10]:
            err_val = float(eq_data['error_val'])
            eq_str = eq_data['equation']
            estimation_label = "overestimating" if err_val > 0 else "underestimating"
            prompt_sections.append(
                f"    - [{eq_data['stage']}] Error: {err_val:.4g}{unit} ({estimation_label}) | Equation: `{eq_str}`"
            )

    return "\n".join(prompt_sections)
def generate_prompt(
    role: str,
    task_type: str,
    netlist,
    # Optional Feedback Args (Only needed for 'iterative_refinement')
    error_th = 15,
    metrics=None, 
    history=None,
    table=None
) -> str:
    """
    The main entry point to generate a prompt.
    
    Args:
        role (str): 'analog_architect'.
        task_type (str): 'generate_model' or 'iterative_refinement'.
        netlist_str (str): The raw netlist text.
        metrics (dict): Current run results (needed for refinement).
        history (list): Previous run history (needed for refinement).
    """
    with open(netlist, "r") as f:
        netlist_str = f.read()
    # 1. Base Components (Role + Physics + Data Dicts)
    parts = [ROLES.get(role, ROLES["analog_architect"]).strip()]
    parts.append("\n" + PHYSICS_MODULES["short_channel_65nm"])
    parts.append("\n" + LUT_PARAMETERS)
    parts.append("\n### DYNAMIC SECTION ###\n")
    
    # 2. Context Preparation
    context = {
        "netlist": netlist_str,
        "output_schema": OUTPUT_SCHEMA_JSON
    }
    
    # 3. Inject Feedback Data (If Refinement Task)
    if task_type == "iterative_refinement":
        #context_prompt = generate_context_of_equations(equation_library = history, mismatch_data = metrics)
        context_prompt = generate_context_of_equations(equation_library = history, mismatch_data = metrics,
                                               tolerance_spec=TOLERANCE_SPEC,
                                               default_tol=DEFAULT_TOL, error_th = error_th)
        context["history_log"] = context_prompt
        context["current_error_table"] = table
    #print(f"\n\nCHECK THIS OUT \n\n\n  {context_prompt}")

    # 3. Inject Feedback Data (If Refinement Task)
    #if task_type == "iterative_refinement":
    #    if metrics is None or history is None:
    #        raise ValueError("Feedback tasks require 'metrics' and 'history' arguments.")
    #        
    #    
    #    context["history_log"] = _format_history_log(history)
    
    # 4. Assembly
    # Select the template
    template_str = TASKS.get(task_type)
    if not template_str:
        raise ValueError(f"Task '{task_type}' not found in library.")
        
    template = string.Template(template_str)
    
    try:
        final_prompt = template.substitute(context)
        parts.append(final_prompt)
    except KeyError as e:
        raise ValueError(f"Missing context variable: {e}")
        
    return "\n".join(parts)
