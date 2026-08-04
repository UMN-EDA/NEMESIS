import math


def get_default_lut_row():
    return {
        "L": 0.0, "W": 0.0, "vgs": 0.0, "vds": 0.0, "vsb": 0.0,
        "id_raw": 0.0, "id": 0.0, "gm": 0.0, "gds": 0.0, "gmb": 0.0,
        "gmid": 0.0, "vth": 0.0, "vdsat": 0.0, "cgg_int": 0.0,
        "cgd_int": 0.0, "cgs_int": 0.0, "cbg_int": 0.0, "cbd_int": 0.0,
        "cbs_int": 0.0, "cdg_int": 0.0, "cdd_int": 0.0, "cds_int": 0.0,
        "cgg": 0.0, "cgd": 0.0, "cgs": 0.0, "cdd": 0.0, "cds": 0.0,
        "cbd": 0.0, "cb": 0.0
    }


class PerformanceModel:
    def compute(self, device_params, C_load, Vdd, Vss, **kwargs):
        eps = 1e-18

        def row(name):
            if name in device_params:
                return device_params[name]
            for key, value in device_params.items():
                if str(key).lower() == name.lower():
                    return value
            return get_default_lut_row()

        def val(name, param):
            try:
                return float(row(name).get(param, 0.0))
            except (TypeError, ValueError, AttributeError):
                return 0.0

        vgs_m0 = val("m0", "vgs")
        id_m0 = val("m0", "id")
        gm_m0 = val("m0", "gm")
        gds_m0 = val("m0", "gds")
        gmb_m0 = val("m0", "gmb")
        vdsat_m0 = val("m0", "vdsat")
        cdd_m0 = val("m0", "cdd")

        vgs_m1 = val("m1", "vgs")
        id_m1 = val("m1", "id")
        gm_m1 = val("m1", "gm")
        gds_m1 = val("m1", "gds")
        cgg_m1 = val("m1", "cgg")
        cdd_m1 = val("m1", "cdd")

        vgs_m2 = val("m2", "vgs")
        id_m2 = val("m2", "id")
        gm_m2 = val("m2", "gm")
        gds_m2 = val("m2", "gds")
        gmb_m2 = val("m2", "gmb")
        vdsat_m2 = val("m2", "vdsat")
        cdd_m2 = val("m2", "cdd")
        cgd_m2 = val("m2", "cgd")

        vgs_m3 = val("m3", "vgs")
        id_m3 = val("m3", "id")
        gm_m3 = val("m3", "gm")
        gds_m3 = val("m3", "gds")
        gmb_m3 = val("m3", "gmb")
        vth_m3 = val("m3", "vth")
        vdsat_m3 = val("m3", "vdsat")
        cgg_m3 = val("m3", "cgg")
        cdd_m3 = val("m3", "cdd")
        cgd_m3 = val("m3", "cgd")

        id_m4 = val("m4", "id")
        gm_m4 = val("m4", "gm")
        gds_m4 = val("m4", "gds")
        gmb_m4 = val("m4", "gmb")
        vdsat_m4 = val("m4", "vdsat")

        results = {
            "DC_Gain_dB": 0.0,
            "Bandwidth_3dB_Hz": 0.0,
            "UGB_Hz": 0.0,
            "Phase_Margin_deg": 0.0,
            "Gain_Margin_dB": 0.0,
            "Input_CMR_Min_V": 0.0,
            "Input_CMR_Max_V": 0.0,
            "Output_Swing_Max_V": 0.0,
            "Output_Swing_Min_V": 0.0,
            "Slew_Rate_Pos_V_us": 0.0,
            "Slew_Rate_Neg_V_us": 0.0,
            "PSRR_Pos_dB": 0.0,
            "PSRR_Neg_dB": 0.0,
            "CMRR_dB": 0.0
        }

        mirror_den = max((gm_m1 + gds_m1 + gds_m0), eps)
        mirror_gm = gm_m0 * gm_m3 / mirror_den
        gm_eff = (gm_m2 + mirror_gm) / 2.0
        gout = max((gds_m2 + gds_m3), eps)
        Av = gm_eff / gout
        C_out_miller = max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / mirror_den)))), eps)
        C_out_large = max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), eps)
        p_out_hz = gout / (2.0 * math.pi * C_out_miller)

        results["DC_Gain_dB"] = 20 * math.log10(abs(Av)) if abs(Av) > eps else -360.0
        print("DC_Gain_dB", results["DC_Gain_dB"])

        results["Bandwidth_3dB_Hz"] = p_out_hz
        print("Bandwidth_3dB_Hz", results["Bandwidth_3dB_Hz"])

        results["UGB_Hz"] = abs(Av) * p_out_hz
        print("UGB_Hz", results["UGB_Hz"])

        mirror_pole = max(((gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), eps)), eps)
        phase_term_1 = math.atan(abs(Av))
        phase_term_2 = math.atan((abs(Av) * (gout / max(C_out_large, eps))) / mirror_pole)
        results["Phase_Margin_deg"] = 180.0 - ((phase_term_1 + phase_term_2) * 180.0 / math.pi)
        print("Phase_Margin_deg", results["Phase_Margin_deg"])

        results["Gain_Margin_dB"] = 360.0
        print("Gain_Margin_dB", results["Gain_Margin_dB"])

        source_gm = gm_m0 + gm_m2 + gmb_m0 + gmb_m2
        source_g = gds_m4 + gds_m0 + gds_m2
        source_corr = source_gm * max(source_g, 0.0) / max((source_gm + source_g), eps)
        results["Input_CMR_Min_V"] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + (max(abs(vdsat_m0), abs(vdsat_m2), 0.0) * max(source_g, 0.0) / max((source_g + source_corr), eps))
        print("Input_CMR_Min_V", results["Input_CMR_Min_V"])

        icmr_max_left = Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)
        icmr_max_right = Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)
        results["Input_CMR_Max_V"] = min(icmr_max_left, icmr_max_right)
        print("Input_CMR_Max_V", results["Input_CMR_Max_V"])

        results["Output_Swing_Max_V"] = Vdd - max((abs(vdsat_m3) + abs(vdsat_m2)), 0.0)
        print("Output_Swing_Max_V", results["Output_Swing_Max_V"])

        results["Output_Swing_Min_V"] = Vss + max(abs(vdsat_m2), 0.0)
        print("Output_Swing_Min_V", results["Output_Swing_Min_V"])

        i_pos = max(((abs(id_m3) + (abs(id_m1) * max(gm_m3, 0.0) / mirror_den)) - abs(id_m2)), 0.0)
        results["Slew_Rate_Pos_V_us"] = (i_pos / C_out_large) / 1e6
        print("Slew_Rate_Pos_V_us", results["Slew_Rate_Pos_V_us"])

        i_neg = abs(id_m2) + max((abs(id_m4) - abs(id_m0)), 0.0) * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), eps)
        results["Slew_Rate_Neg_V_us"] = (i_neg / C_out_large) / 1e6
        print("Slew_Rate_Neg_V_us", results["Slew_Rate_Neg_V_us"])

        psrr_pos_feed = (gds_m3 + ((gm_m3 + gmb_m3) * (gds_m1 + gds_m0 + gds_m3) / max((gm_m1 + gds_m1 + gds_m0 + gm_m3 + gmb_m3 + gds_m3), eps))) / gout
        results["PSRR_Pos_dB"] = 20 * math.log10(abs(Av / max(psrr_pos_feed, eps)))
        print("PSRR_Pos_dB", results["PSRR_Pos_dB"])

        psrr_neg_feed = ((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), eps)) * (gds_m2 / gout)
        results["PSRR_Neg_dB"] = 20 * math.log10(abs(Av / max(psrr_neg_feed, eps)))
        print("PSRR_Neg_dB", results["PSRR_Neg_dB"])

        cm_mirror_err = ((abs(gm_m2 - mirror_gm) / gout) * max((gds_m1 + gds_m0), 0.0) / mirror_den)
        cm_tail_err = (gds_m4 / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4), eps)) * abs(Av)
        tail_gain = (gm_m0 + gm_m2 + gmb_m0 + gmb_m2) / max((gds_m4 + gds_m0 + gds_m2), eps)
        Acm = (cm_mirror_err + cm_tail_err) / max(tail_gain, eps)
        results["CMRR_dB"] = 20 * math.log10(abs(Av / max(Acm, eps)))
        print("CMRR_dB", results["CMRR_dB"])

        return results


if __name__ == "__main__":
    mock_params = {
        "m0": get_default_lut_row(),
        "m1": get_default_lut_row(),
        "m2": get_default_lut_row(),
        "m3": get_default_lut_row(),
        "m4": get_default_lut_row(),
        "m5": get_default_lut_row()
    }
    model = PerformanceModel()
    output = model.compute(device_params=mock_params, C_load=1e-12, Vdd=1.0, Vss=0.0)
    for metric, value in output.items():
        print(f"{metric}: {value}")
