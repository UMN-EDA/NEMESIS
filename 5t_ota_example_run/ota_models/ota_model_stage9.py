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
            base = get_default_lut_row()
            base.update(device_params.get(name, {}))
            return base
        lname = name.lower()
        for key, value in device_params.items():
            if str(key).lower() == lname:
                base = get_default_lut_row()
                base.update(value)
                return base
        return get_default_lut_row()

    def _f(self, row, key):
        try:
            return float(row.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _log_db(self, value):
        return 20.0 * math.log10(max(abs(float(value)), 1e-18))

    def compute(self, device_params, C_load, Vdd, Vss, **kwargs):
        C_load = float(C_load or 0.0)
        Vdd = float(Vdd or 0.0)
        Vss = float(Vss or 0.0)

        m0 = self._row(device_params, "m0")
        m1 = self._row(device_params, "m1")
        m2 = self._row(device_params, "m2")
        m3 = self._row(device_params, "m3")
        m4 = self._row(device_params, "m4")
        m5 = self._row(device_params, "m5")

        vgs_m0 = self._f(m0, "vgs"); vdsat_m0 = self._f(m0, "vdsat")
        id_m0 = self._f(m0, "id"); gm_m0 = self._f(m0, "gm"); gds_m0 = self._f(m0, "gds"); gmb_m0 = self._f(m0, "gmb")
        cdd_m0 = self._f(m0, "cdd")

        vgs_m1 = self._f(m1, "vgs"); id_m1 = self._f(m1, "id")
        gm_m1 = self._f(m1, "gm"); gds_m1 = self._f(m1, "gds")
        cdd_m1 = self._f(m1, "cdd"); cgg_m1 = self._f(m1, "cgg")

        vgs_m2 = self._f(m2, "vgs"); vdsat_m2 = self._f(m2, "vdsat")
        id_m2 = self._f(m2, "id"); gm_m2 = self._f(m2, "gm"); gds_m2 = self._f(m2, "gds"); gmb_m2 = self._f(m2, "gmb")
        cdd_m2 = self._f(m2, "cdd"); cgd_m2 = self._f(m2, "cgd")

        vgs_m3 = self._f(m3, "vgs"); vdsat_m3 = self._f(m3, "vdsat")
        id_m3 = self._f(m3, "id"); gm_m3 = self._f(m3, "gm"); gds_m3 = self._f(m3, "gds"); gmb_m3 = self._f(m3, "gmb")
        cdd_m3 = self._f(m3, "cdd"); cgd_m3 = self._f(m3, "cgd"); cgg_m3 = self._f(m3, "cgg")

        vdsat_m4 = self._f(m4, "vdsat")
        id_m4 = self._f(m4, "id"); gm_m4 = self._f(m4, "gm"); gds_m4 = self._f(m4, "gds"); gmb_m4 = self._f(m4, "gmb")

        results = {}

        mirror_den = max((gm_m1 + gds_m1 + gds_m0), 1e-18)
        gout = max((gds_m2 + gds_m3), 1e-18)
        gm_eff = (gm_m2 + (gm_m0 * gm_m3 / mirror_den)) / 2.0
        Av = gm_eff / gout
        cout_miller = C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / mirror_den)))
        cout_plain = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3
        bw = gout / (2.0 * math.pi * max(cout_miller, 1e-18))

        results["DC_Gain_dB"] = self._log_db(Av)
        print("DC_Gain_dB", results["DC_Gain_dB"])

        results["Bandwidth_3dB_Hz"] = bw
        print("Bandwidth_3dB_Hz", results["Bandwidth_3dB_Hz"])

        results["UGB_Hz"] = abs(Av) * bw
        print("UGB_Hz", results["UGB_Hz"])

        internal_pole = (gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), 1e-18)
        phase_lag = math.atan(abs(Av)) + math.atan((abs(Av) * (gout / max(cout_plain, 1e-18))) / max(internal_pole, 1e-18))
        results["Phase_Margin_deg"] = 180.0 - (phase_lag * 180.0 / math.pi)
        print("Phase_Margin_deg", results["Phase_Margin_deg"])

        results["Gain_Margin_dB"] = 360.0
        print("Gain_Margin_dB", results["Gain_Margin_dB"])

        source_g = gds_m4 + gds_m0 + gds_m2
        source_g_pos = max(source_g, 0.0)
        input_pair_gm_sum = gm_m0 + gm_m2 + gmb_m0 + gmb_m2
        icmr_min_extra = max(abs(vdsat_m0), abs(vdsat_m2), 0.0) * source_g_pos / max((source_g + (input_pair_gm_sum * source_g_pos / max((input_pair_gm_sum + source_g), 1e-18))), 1e-18)
        results["Input_CMR_Min_V"] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + icmr_min_extra
        print("Input_CMR_Min_V", results["Input_CMR_Min_V"])

        results["Input_CMR_Max_V"] = min((Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)), (Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)))
        print("Input_CMR_Max_V", results["Input_CMR_Max_V"])

        results["Output_Swing_Max_V"] = Vdd - max((abs(vdsat_m3) + abs(vdsat_m2)), 0.0)
        print("Output_Swing_Max_V", results["Output_Swing_Max_V"])

        results["Output_Swing_Min_V"] = Vss + max(abs(vdsat_m2), 0.0)
        print("Output_Swing_Min_V", results["Output_Swing_Min_V"])

        sr_pos_charge = abs(id_m3) + (abs(id_m1) * max(gm_m3, 0.0) / mirror_den)
        sr_pos_oppose = abs(id_m2) * max(gds_m2, 0.0) / gout * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)
        results["Slew_Rate_Pos_V_us"] = (max((sr_pos_charge - sr_pos_oppose), 0.0) / max(cout_plain, 1e-18)) / 1e6
        print("Slew_Rate_Pos_V_us", results["Slew_Rate_Pos_V_us"])

        sr_neg_current = abs(id_m2) + max((abs(id_m4) - abs(id_m0)), 0.0) * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)
        results["Slew_Rate_Neg_V_us"] = (sr_neg_current / max(cout_plain, 1e-18)) / 1e6
        print("Slew_Rate_Neg_V_us", results["Slew_Rate_Neg_V_us"])

        psrr_pos_feed = (gds_m3 + ((gm_m3 + gmb_m3) * (gds_m1 + gds_m0 + gds_m3) / max((gm_m1 + gds_m1 + gds_m0 + gm_m3 + gmb_m3 + gds_m3), 1e-18))) / gout
        results["PSRR_Pos_dB"] = self._log_db(Av / max(psrr_pos_feed, 1e-18))
        print("PSRR_Pos_dB", results["PSRR_Pos_dB"])

        psrr_neg_feed = ((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), 1e-18)) * (gds_m2 / gout)
        results["PSRR_Neg_dB"] = self._log_db(Av / max(psrr_neg_feed, 1e-18))
        print("PSRR_Neg_dB", results["PSRR_Neg_dB"])

        cm_path_mirror = (abs(gm_m2 - (gm_m0 * gm_m3 / mirror_den)) / gout) * max((gds_m1 + gds_m0), 0.0) / mirror_den
        m4_body_term = gmb_m4 * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)
        cm_path_tail = ((gds_m4 + m4_body_term) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + m4_body_term), 1e-18)) * abs(Av)
        tail_rejection = max(((gm_m0 + gm_m2 + gmb_m0 + gmb_m2) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)), 1e-18)
        Acm = (cm_path_mirror + cm_path_tail) / tail_rejection
        results["CMRR_dB"] = self._log_db(Av / max(Acm, 1e-18))
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
