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
        base = get_default_lut_row()
        row = device_params.get(name, {}) if isinstance(device_params, dict) else {}
        if not row and isinstance(device_params, dict):
            for key, value in device_params.items():
                if str(key).lower() == name.lower():
                    row = value
                    break
        if isinstance(row, dict):
            base.update(row)
        return base

    def _p(self, row, key):
        try:
            value = float(row.get(key, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return value

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

        m0 = self._row(device_params, "m0")
        m1 = self._row(device_params, "m1")
        m2 = self._row(device_params, "m2")
        m3 = self._row(device_params, "m3")
        m4 = self._row(device_params, "m4")
        m5 = self._row(device_params, "m5")

        gm_m0 = self._p(m0, "gm"); gds_m0 = self._p(m0, "gds"); gmb_m0 = self._p(m0, "gmb"); id_m0 = self._p(m0, "id"); vgs_m0 = self._p(m0, "vgs"); vdsat_m0 = self._p(m0, "vdsat"); cdd_m0 = self._p(m0, "cdd")
        gm_m1 = self._p(m1, "gm"); gds_m1 = self._p(m1, "gds"); gmb_m1 = self._p(m1, "gmb"); id_m1 = self._p(m1, "id"); vgs_m1 = self._p(m1, "vgs"); vdsat_m1 = self._p(m1, "vdsat"); cdd_m1 = self._p(m1, "cdd"); cgg_m1 = self._p(m1, "cgg")
        gm_m2 = self._p(m2, "gm"); gds_m2 = self._p(m2, "gds"); gmb_m2 = self._p(m2, "gmb"); id_m2 = self._p(m2, "id"); vgs_m2 = self._p(m2, "vgs"); vdsat_m2 = self._p(m2, "vdsat"); cdd_m2 = self._p(m2, "cdd"); cgd_m2 = self._p(m2, "cgd")
        gm_m3 = self._p(m3, "gm"); gds_m3 = self._p(m3, "gds"); gmb_m3 = self._p(m3, "gmb"); id_m3 = self._p(m3, "id"); vgs_m3 = self._p(m3, "vgs"); vdsat_m3 = self._p(m3, "vdsat"); cdd_m3 = self._p(m3, "cdd"); cgd_m3 = self._p(m3, "cgd"); cgg_m3 = self._p(m3, "cgg")
        gm_m4 = self._p(m4, "gm"); gds_m4 = self._p(m4, "gds"); gmb_m4 = self._p(m4, "gmb"); id_m4 = self._p(m4, "id"); vgs_m4 = self._p(m4, "vgs"); vdsat_m4 = self._p(m4, "vdsat")
        gm_m5 = self._p(m5, "gm"); gds_m5 = self._p(m5, "gds"); gmb_m5 = self._p(m5, "gmb"); id_m5 = self._p(m5, "id")

        results = {}

        dc_gain_linear = (((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), eps))) / 2.0) / max((gds_m2 + gds_m3), eps))
        results["DC_Gain_dB"] = 20 * math.log10(abs(max(abs(dc_gain_linear), eps)))
        print("DC_Gain_dB", results["DC_Gain_dB"])

        c_out_bw = C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / max((gm_m1 + gds_m1 + gds_m0), eps))))
        results["Bandwidth_3dB_Hz"] = max((gds_m2 + gds_m3), eps) / (2.0 * math.pi * max(c_out_bw, eps))
        print("Bandwidth_3dB_Hz", results["Bandwidth_3dB_Hz"])

        results["UGB_Hz"] = abs(dc_gain_linear) * results["Bandwidth_3dB_Hz"]
        print("UGB_Hz", results["UGB_Hz"])

        c_out_pm = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3
        p2 = (gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), eps)
        results["Phase_Margin_deg"] = 180.0 - ((math.atan(abs(dc_gain_linear)) + math.atan((abs(dc_gain_linear) * (max((gds_m2 + gds_m3), eps) / max(c_out_pm, eps))) / max(p2, eps))) * 180.0 / math.pi)
        print("Phase_Margin_deg", results["Phase_Margin_deg"])

        results["Gain_Margin_dB"] = 360.0
        print("Gain_Margin_dB", results["Gain_Margin_dB"])

        results["Input_CMR_Min_V"] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + (max(abs(vdsat_m0), abs(vdsat_m2), 0.0) * max((gds_m4 + gds_m0 + gds_m2), 0.0) / max((gds_m4 + gds_m0 + gds_m2 + ((gm_m0 + gm_m2 + gmb_m0 + gmb_m2) * max((gds_m4 + gds_m0 + gds_m2), 0.0) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gds_m0 + gds_m2), eps))), eps))
        print("Input_CMR_Min_V", results["Input_CMR_Min_V"])

        results["Input_CMR_Max_V"] = min((Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)), (Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)))
        print("Input_CMR_Max_V", results["Input_CMR_Max_V"])

        results["Output_Swing_Max_V"] = Vdd - max((abs(vdsat_m3) + abs(vdsat_m2)), 0.0)
        print("Output_Swing_Max_V", results["Output_Swing_Max_V"])

        results["Output_Swing_Min_V"] = Vss + max(abs(vdsat_m2), 0.0)
        print("Output_Swing_Min_V", results["Output_Swing_Min_V"])

        c_slew = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3
        i_pos = max(((abs(id_m3) + (abs(id_m1) * max(gm_m3, 0.0) / max((gm_m1 + gds_m1 + gds_m0), eps))) - (abs(id_m2) * max(gds_m2, 0.0) / max((gds_m2 + gds_m3), eps))), 0.0)
        results["Slew_Rate_Pos_V_us"] = (i_pos / max(c_slew, eps)) / 1e6
        print("Slew_Rate_Pos_V_us", results["Slew_Rate_Pos_V_us"])

        i_neg = abs(id_m2) + max((abs(id_m4) - abs(id_m0)), 0.0) * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), eps)
        results["Slew_Rate_Neg_V_us"] = (i_neg / max(c_slew, eps)) / 1e6
        print("Slew_Rate_Neg_V_us", results["Slew_Rate_Neg_V_us"])

        psrr_pos_feed = (gds_m3 + ((gm_m3 + gmb_m3) * (gds_m1 + gds_m0 + gds_m3) / max((gm_m1 + gds_m1 + gds_m0 + gm_m3 + gmb_m3 + gds_m3), eps))) / max((gds_m2 + gds_m3), eps)
        results["PSRR_Pos_dB"] = 20 * math.log10(abs(max((dc_gain_linear / max(psrr_pos_feed, eps)), eps)))
        print("PSRR_Pos_dB", results["PSRR_Pos_dB"])

        psrr_neg_feed = ((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), eps)) * (gds_m2 / max((gds_m2 + gds_m3), eps))
        results["PSRR_Neg_dB"] = 20 * math.log10(abs(max((dc_gain_linear / max(psrr_neg_feed, eps)), eps)))
        print("PSRR_Neg_dB", results["PSRR_Neg_dB"])

        mirror_mismatch_acm = ((abs(gm_m2 - (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), eps))) / max((gds_m2 + gds_m3), eps)) * max((gds_m1 + gds_m0), 0.0) / max((gm_m1 + gds_m1 + gds_m0), eps))
        gmb_m4_weighted = gmb_m4 * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), eps)
        tail_acm = ((gds_m4 + gmb_m4_weighted) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4_weighted), eps)) * abs(dc_gain_linear)
        source_rejection = (gm_m0 + gm_m2 + gmb_m0 + gmb_m2) / max((gds_m4 + gds_m0 + gds_m2), eps)
        acm = (mirror_mismatch_acm + tail_acm) / max(source_rejection, eps)
        results["CMRR_dB"] = 20 * math.log10(abs(max((dc_gain_linear / max(acm, eps)), eps)))
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
