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
    def _dev(self, device_params, name):
        default = get_default_lut_row()
        row = device_params.get(name, None)
        if row is None:
            lower_map = {str(k).lower(): v for k, v in device_params.items()}
            row = lower_map.get(name.lower(), {})
        merged = default.copy()
        if isinstance(row, dict):
            merged.update(row)
        return merged

    def _p(self, row, key):
        try:
            return float(row.get(key, 0.0))
        except (TypeError, ValueError):
            return 0.0

    def compute(self, device_params, C_load, Vdd, Vss, **kwargs):
        eps = 1e-18
        try:
            C_load = float(C_load)
        except (TypeError, ValueError):
            C_load = 0.0
        try:
            Vdd = float(Vdd)
        except (TypeError, ValueError):
            Vdd = 1.0
        try:
            Vss = float(Vss)
        except (TypeError, ValueError):
            Vss = 0.0

        m0 = self._dev(device_params, "m0")
        m1 = self._dev(device_params, "m1")
        m2 = self._dev(device_params, "m2")
        m3 = self._dev(device_params, "m3")
        m4 = self._dev(device_params, "m4")
        m5 = self._dev(device_params, "m5")

        gm_m0 = self._p(m0, "gm")
        gds_m0 = self._p(m0, "gds")
        gmb_m0 = self._p(m0, "gmb")
        vgs_m0 = self._p(m0, "vgs")
        vdsat_m0 = self._p(m0, "vdsat")
        id_m0 = self._p(m0, "id")
        cdd_m0 = self._p(m0, "cdd")

        gm_m1 = self._p(m1, "gm")
        gds_m1 = self._p(m1, "gds")
        gmb_m1 = self._p(m1, "gmb")
        vgs_m1 = self._p(m1, "vgs")
        vdsat_m1 = self._p(m1, "vdsat")
        id_m1 = self._p(m1, "id")
        cdd_m1 = self._p(m1, "cdd")
        cgg_m1 = self._p(m1, "cgg")

        gm_m2 = self._p(m2, "gm")
        gds_m2 = self._p(m2, "gds")
        gmb_m2 = self._p(m2, "gmb")
        vgs_m2 = self._p(m2, "vgs")
        vdsat_m2 = self._p(m2, "vdsat")
        id_m2 = self._p(m2, "id")
        cdd_m2 = self._p(m2, "cdd")
        cgd_m2 = self._p(m2, "cgd")

        gm_m3 = self._p(m3, "gm")
        gds_m3 = self._p(m3, "gds")
        gmb_m3 = self._p(m3, "gmb")
        vgs_m3 = self._p(m3, "vgs")
        vdsat_m3 = self._p(m3, "vdsat")
        id_m3 = self._p(m3, "id")
        cdd_m3 = self._p(m3, "cdd")
        cgd_m3 = self._p(m3, "cgd")
        cgg_m3 = self._p(m3, "cgg")

        gm_m4 = self._p(m4, "gm")
        gds_m4 = self._p(m4, "gds")
        gmb_m4 = self._p(m4, "gmb")
        vdsat_m4 = self._p(m4, "vdsat")
        id_m4 = self._p(m4, "id")

        gm_m5 = self._p(m5, "gm")
        gds_m5 = self._p(m5, "gds")
        gmb_m5 = self._p(m5, "gmb")
        id_m5 = self._p(m5, "id")

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
        gout = max((gds_m2 + gds_m3), eps)
        gm_eff = (gm_m2 + (gm_m0 * gm_m3 / mirror_den)) / 2.0
        Av = gm_eff / gout
        c_out_miller = C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / mirror_den)))
        c_out_simple = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3

        results["DC_Gain_dB"] = 20 * math.log10(abs(Av)) if abs(Av) > eps else -360.0
        print("DC_Gain_dB", results["DC_Gain_dB"])

        results["Bandwidth_3dB_Hz"] = gout / (2.0 * math.pi * max(c_out_miller, eps))
        print("Bandwidth_3dB_Hz", results["Bandwidth_3dB_Hz"])

        results["UGB_Hz"] = abs(Av) * results["Bandwidth_3dB_Hz"]
        print("UGB_Hz", results["UGB_Hz"])

        p2 = (gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), eps)
        phase_term = math.atan(abs(Av)) + math.atan((abs(Av) * (gout / max(c_out_simple, eps))) / max(p2, eps))
        results["Phase_Margin_deg"] = 180.0 - (phase_term * 180.0 / math.pi)
        print("Phase_Margin_deg", results["Phase_Margin_deg"])

        results["Gain_Margin_dB"] = 360.0
        print("Gain_Margin_dB", results["Gain_Margin_dB"])

        input_pair_headroom = max(abs(vdsat_m0), abs(vdsat_m2), 0.0)
        tail_degen = input_pair_headroom * max(gds_m4, 0.0) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4), eps)
        results["Input_CMR_Min_V"] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + tail_degen
        print("Input_CMR_Min_V", results["Input_CMR_Min_V"])

        icmr_max_0 = Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)
        icmr_max_2 = Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)
        results["Input_CMR_Max_V"] = min(icmr_max_0, icmr_max_2)
        print("Input_CMR_Max_V", results["Input_CMR_Max_V"])

        results["Output_Swing_Max_V"] = Vdd - max((abs(vdsat_m3) + max((abs(vgs_m3) - abs(vgs_m1)), 0.0)), 0.0)
        print("Output_Swing_Max_V", results["Output_Swing_Max_V"])

        results["Output_Swing_Min_V"] = Vss + max(abs(vdsat_m2), 0.0)
        print("Output_Swing_Min_V", results["Output_Swing_Min_V"])

        sr_cap = max(c_out_simple, eps)
        sr_pos_current = abs(id_m3) + (abs(id_m1) * max(gm_m3, 0.0) / mirror_den)
        results["Slew_Rate_Pos_V_us"] = (sr_pos_current / sr_cap) / 1e6
        print("Slew_Rate_Pos_V_us", results["Slew_Rate_Pos_V_us"])

        sr_neg_current = min(abs(id_m2), abs(id_m4))
        results["Slew_Rate_Neg_V_us"] = (sr_neg_current / sr_cap) / 1e6
        print("Slew_Rate_Neg_V_us", results["Slew_Rate_Neg_V_us"])

        psrp_feed = (gds_m3 + (gm_m3 * (gds_m1 + gds_m0) / max((gm_m1 + gmb_m3 + gds_m1 + gds_m0), eps))) / gout
        psrp_ratio = Av / max(psrp_feed, eps)
        results["PSRR_Pos_dB"] = 20 * math.log10(abs(psrp_ratio)) if abs(psrp_ratio) > eps else -360.0
        print("PSRR_Pos_dB", results["PSRR_Pos_dB"])

        psrn_feed = ((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), eps)) * (gds_m2 / gout)
        psrn_ratio = Av / max(psrn_feed, eps)
        results["PSRR_Neg_dB"] = 20 * math.log10(abs(psrn_ratio)) if abs(psrn_ratio) > eps else -360.0
        print("PSRR_Neg_dB", results["PSRR_Neg_dB"])

        cm_mirror = abs(gm_m2 - (gm_m0 * gm_m3 / mirror_den)) / gout
        cm_tail = (gds_m4 / max((gm_m0 + gm_m2 + gds_m4), eps)) * abs(Av)
        cm_source_gain = (gm_m0 + gm_m2) / max((gds_m4 + gds_m0 + gds_m2), eps)
        Acm = (cm_mirror + cm_tail) / max(cm_source_gain, eps)
        cmrr_ratio = Av / max(Acm, eps)
        results["CMRR_dB"] = 20 * math.log10(abs(cmrr_ratio)) if abs(cmrr_ratio) > eps else -360.0
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
