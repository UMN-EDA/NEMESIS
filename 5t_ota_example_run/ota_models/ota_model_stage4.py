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
    def _row(self, device_params, name):
        if name in device_params:
            row = device_params[name]
        else:
            row = device_params.get(name.lower(), device_params.get(name.upper(), {}))
        base = get_default_lut_row()
        base.update(row if isinstance(row, dict) else {})
        return base

    def _val(self, row, key):
        try:
            value = float(row.get(key, 0.0))
            if math.isfinite(value):
                return value
            return 0.0
        except (TypeError, ValueError):
            return 0.0

    def compute(self, device_params, C_load, Vdd, Vss):
        eps = 1e-18
        C_load = max(float(C_load), 0.0)
        Vdd = float(Vdd)
        Vss = float(Vss)

        m0 = self._row(device_params, "m0")
        m1 = self._row(device_params, "m1")
        m2 = self._row(device_params, "m2")
        m3 = self._row(device_params, "m3")
        m4 = self._row(device_params, "m4")
        m5 = self._row(device_params, "m5")

        vgs_m0 = self._val(m0, "vgs")
        vgs_m1 = self._val(m1, "vgs")
        vgs_m2 = self._val(m2, "vgs")
        vgs_m3 = self._val(m3, "vgs")
        vdsat_m0 = self._val(m0, "vdsat")
        vdsat_m2 = self._val(m2, "vdsat")
        vdsat_m3 = self._val(m3, "vdsat")
        vdsat_m4 = self._val(m4, "vdsat")
        id_m0 = self._val(m0, "id")
        id_m1 = self._val(m1, "id")
        id_m2 = self._val(m2, "id")
        id_m3 = self._val(m3, "id")
        id_m4 = self._val(m4, "id")
        gm_m0 = self._val(m0, "gm")
        gm_m1 = self._val(m1, "gm")
        gm_m2 = self._val(m2, "gm")
        gm_m3 = self._val(m3, "gm")
        gm_m4 = self._val(m4, "gm")
        gds_m0 = self._val(m0, "gds")
        gds_m1 = self._val(m1, "gds")
        gds_m2 = self._val(m2, "gds")
        gds_m3 = self._val(m3, "gds")
        gds_m4 = self._val(m4, "gds")
        gmb_m0 = self._val(m0, "gmb")
        gmb_m2 = self._val(m2, "gmb")
        gmb_m4 = self._val(m4, "gmb")
        cdd_m0 = self._val(m0, "cdd")
        cdd_m1 = self._val(m1, "cdd")
        cdd_m2 = self._val(m2, "cdd")
        cdd_m3 = self._val(m3, "cdd")
        cgg_m1 = self._val(m1, "cgg")
        cgg_m3 = self._val(m3, "cgg")
        cgd_m2 = self._val(m2, "cgd")
        cgd_m3 = self._val(m3, "cgd")

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
        gm_mirror = gm_m0 * gm_m3 / mirror_den
        gm_eff = (gm_m2 + gm_mirror) / 2.0
        gout = max((gds_m2 + gds_m3), eps)
        Av = gm_eff / gout
        print("Av_linear:", Av)

        C_out_miller = C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / mirror_den)))
        C_out_simple = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3
        C_net3 = cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3
        C_slew = max(C_out_simple, eps)
        pole_out = gout / (2.0 * math.pi * max(C_out_miller, eps))
        pole_net3_rad = (gm_m1 + gds_m1 + gds_m0) / max(C_net3, eps)

        results["DC_Gain_dB"] = 20 * math.log10(abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))))
        print("DC_Gain_dB:", results["DC_Gain_dB"])

        results["Bandwidth_3dB_Hz"] = max((gds_m2 + gds_m3), 1e-18) / (2.0 * math.pi * max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))))), 1e-18))
        print("Bandwidth_3dB_Hz:", results["Bandwidth_3dB_Hz"])

        results["UGB_Hz"] = abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))) * (max((gds_m2 + gds_m3), 1e-18) / (2.0 * math.pi * max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))))), 1e-18)))
        print("UGB_Hz:", results["UGB_Hz"])

        results["Phase_Margin_deg"] = 180.0 - ((math.atan(abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18)))) + math.atan((abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))) * (max((gds_m2 + gds_m3), 1e-18) / max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), 1e-18))) / max(((gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), 1e-18)), 1e-18))) * 180.0 / math.pi)
        print("Phase_Margin_deg:", results["Phase_Margin_deg"])

        results["Gain_Margin_dB"] = 360.0
        print("Gain_Margin_dB:", results["Gain_Margin_dB"])

        results["Input_CMR_Min_V"] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + (max(abs(vdsat_m0), abs(vdsat_m2), 0.0) * max((gds_m4 + gds_m0 + gds_m2), 0.0) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gds_m0 + gds_m2), 1e-18))
        print("Input_CMR_Min_V:", results["Input_CMR_Min_V"])

        results["Input_CMR_Max_V"] = min((Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)), (Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)))
        print("Input_CMR_Max_V:", results["Input_CMR_Max_V"])

        results["Output_Swing_Max_V"] = Vdd - max((abs(vdsat_m3) + (max((abs(vgs_m3) - abs(vgs_m1)), 0.0) * max(gm_m3, 0.0) / max((gm_m1 + gds_m1 + gds_m0), 1e-18))), 0.0)
        print("Output_Swing_Max_V:", results["Output_Swing_Max_V"])

        results["Output_Swing_Min_V"] = Vss + max(abs(vdsat_m2), 0.0)
        print("Output_Swing_Min_V:", results["Output_Swing_Min_V"])

        sr_pos_current = max((abs(id_m3) + (abs(id_m1) * max(gm_m3, 0.0) / max((gm_m1 + gds_m1 + gds_m0), 1e-18)) - (abs(id_m2) * max(gds_m2, 0.0) / max((gds_m2 + gds_m3), 1e-18))), 0.0)
        results["Slew_Rate_Pos_V_us"] = (sr_pos_current / max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), 1e-18)) / 1e6
        print("Slew_Rate_Pos_V_us:", results["Slew_Rate_Pos_V_us"])

        sr_neg_current = abs(id_m2) + max((abs(id_m4) - abs(id_m0)), 0.0) * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)
        results["Slew_Rate_Neg_V_us"] = (sr_neg_current / max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), 1e-18)) / 1e6
        print("Slew_Rate_Neg_V_us:", results["Slew_Rate_Neg_V_us"])

        psrrp_feed = (gds_m3 + (gm_m3 * (gds_m1 + gds_m0) / max((gm_m1 + gds_m1 + gds_m0 + gds_m3), 1e-18))) / max((gds_m2 + gds_m3), 1e-18)
        results["PSRR_Pos_dB"] = 20 * math.log10(abs(Av / max(psrrp_feed, eps)))
        print("PSRR_Pos_dB:", results["PSRR_Pos_dB"])

        results["PSRR_Neg_dB"] = 20 * math.log10(abs(((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))) / max((((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), 1e-18)) * (gds_m2 / max((gds_m2 + gds_m3), 1e-18))), 1e-18)))
        print("PSRR_Neg_dB:", results["PSRR_Neg_dB"])

        cm_mirror = (abs(gm_m2 - gm_mirror) / gout) * max((gds_m1 + gds_m0), 0.0) / max((gm_m1 + gds_m1 + gds_m0), eps)
        cm_tail = (gds_m4 / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4), eps)) * abs(Av)
        source_rejection = max(((gm_m0 + gm_m2 + gmb_m0 + gmb_m2) / max((gds_m4 + gds_m0 + gds_m2), eps)), eps)
        Acm = (cm_mirror + cm_tail) / source_rejection
        results["CMRR_dB"] = 20 * math.log10(abs(Av / max(Acm, eps)))
        print("CMRR_dB:", results["CMRR_dB"])

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
