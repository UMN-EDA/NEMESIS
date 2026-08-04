KEY_MAP = {
    "ICMR Min (V)": "Input_CMR_Min_V",
    "ICMR Max (V)": "Input_CMR_Max_V",
    "DC Gain (dB)": "DC_Gain_dB",
    "UGF (Hz)": "UGB_Hz",
    "Phase Margin (deg)": "Phase_Margin_deg",
    "Bandwidth 3dB (Hz)": "Bandwidth_3dB_Hz",
    "Gain Margin (dB)":"Gain_Margin_dB",
    "Output Swing Min (V)": "Output_Swing_Min_V",
    "Output Swing Max (V)": "Output_Swing_Max_V",
    "Slew Rate (+) (V/us)": "Slew_Rate_Pos_V_us",
    "Slew Rate (-) (V/us)":"Slew_Rate_Neg_V_us",
    "PSRR+ (dB)": "PSRR_Pos_dB",
    "PSRR- (dB)": "PSRR_Neg_dB",
    "CMRR (dB)": "CMRR_dB"
}

TOLERANCE_SPEC = {
    # dB metrics: absolute dB error
    #"DC_Gain_dB":        {"mode": "abs", "tol": 2.0,  "unit": "dB"},
    #"CMRR_dB":           {"mode": "abs", "tol": 5.0,  "unit": "dB"},
    #"PSRR_Pos_dB":       {"mode": "abs", "tol": 5.0,  "unit": "dB"},
    #"PSRR_Neg_dB":       {"mode": "abs", "tol": 5.0,  "unit": "dB"},
    #"Gain_Margin_dB":    {"mode": "abs", "tol": 4.0,  "unit": "dB"},

    # phase: absolute deg error
    #"Phase_Margin_deg":  {"mode": "abs", "tol": 5.0,  "unit": "deg"},

    # voltages: absolute V error
    #"Input_CMR_Min_V":   {"mode": "abs", "tol": 1, "unit": "V"},
    #"Input_CMR_Max_V":   {"mode": "abs", "tol": 0.05, "unit": "V"},
    #"Output_Swing_Min_V":{"mode": "abs", "tol": 1, "unit": "V"},
    #"Output_Swing_Max_V":{"mode": "abs", "tol": 1, "unit": "V"}

    # slew: percentage or abs depending on what you prefer
    #"Slew_Rate_Pos_V_us":{"mode": "pct", "tol": 15.0, "unit": "%"},
    #"Slew_Rate_Neg_V_us":{"mode": "pct", "tol": 15.0, "unit": "%"},

    # frequency: percentage
    #"Bandwidth_3dB_Hz":  {"mode": "pct", "tol": 15.0, "unit": "%"},
    #"UGB_Hz":            {"mode": "pct", "tol": 15.0, "unit": "%"},
}
DEFAULT_TOL = {"mode": "pct", "tol": 5.0, "unit": "%"}  # fallback
