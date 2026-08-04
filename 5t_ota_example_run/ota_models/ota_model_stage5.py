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
        if name in device_params:
            row = device_params[name]
        else:
            row = {}
            lname = name.lower()
            for key, value in device_params.items():
                if str(key).lower() == lname:
                    row = value
                    break
        default = get_default_lut_row()
        merged = default.copy()
        if isinstance(row, dict):
            merged.update(row)
        return merged

    def _val(self, row, key):
        try:
            value = row.get(key, 0.0)
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _log_db(self, value):
        return 20.0 * math.log10(max(abs(value), 1e-18))

    def compute(self, device_params, C_load, Vdd, Vss, **additional_passive_elements):
        eps = 1e-18
        C_load = max(float(C_load), 0.0)
        Vdd = float(Vdd)
        Vss = float(Vss)

        m0 = self._dev(device_params, "m0")
        m1 = self._dev(device_params, "m1")
        m2 = self._dev(device_params, "m2")
        m3 = self._dev(device_params, "m3")
        m4 = self._dev(device_params, "m4")
        m5 = self._dev(device_params, "m5")

        gm_m0 = self._val(m0, "gm")
        gm_m1 = self._val(m1, "gm")
        gm_m2 = self._val(m2, "gm")
        gm_m3 = self._val(m3, "gm")
        gm_m4 = self._val(m4, "gm")
        gm_m5 = self._val(m5, "gm")
        gds_m0 = self._val(m0, "gds")
        gds_m1 = self._val(m1, "gds")
        gds_m2 = self._val(m2, "gds")
        gds_m3 = self._val(m3, "gds")
        gds_m4 = self._val(m4, "gds")
        gds_m5 = self._val(m5, "gds")
        gmb_m0 = self._val(m0, "gmb")
        gmb_m1 = self._val(m1, "gmb")
        gmb_m2 = self._val(m2, "gmb")
        gmb_m3 = self._val(m3, "gmb")
        gmb_m4 = self._val(m4, "gmb")
        gmb_m5 = self._val(m5, "gmb")
        id_m0 = self._val(m0, "id")
        id_m1 = self._val(m1, "id")
        id_m2 = self._val(m2, "id")
        id_m3 = self._val(m3, "id")
        id_m4 = self._val(m4, "id")
        id_m5 = self._val(m5, "id")
        vgs_m0 = self._val(m0, "vgs")
        vgs_m1 = self._val(m1, "vgs")
        vgs_m2 = self._val(m2, "vgs")
        vgs_m3 = self._val(m3, "vgs")
        vgs_m4 = self._val(m4, "vgs")
        vgs_m5 = self._val(m5, "vgs")
        vdsat_m0 = self._val(m0, "vdsat")
        vdsat_m1 = self._val(m1, "vdsat")
        vdsat_m2 = self._val(m2, "vdsat")
        vdsat_m3 = self._val(m3, "vdsat")
        vdsat_m4 = self._val(m4, "vdsat")
        vdsat_m5 = self._val(m5, "vdsat")
        cdd_m0 = self._val(m0, "cdd")
        cdd_m1 = self._val(m1, "cdd")
        cdd_m2 = self._val(m2, "cdd")
        cdd_m3 = self._val(m3, "cdd")
        cdd_m4 = self._val(m4, "cdd")
        cdd_m5 = self._val(m5, "cdd")
        cgd_m0 = self._val(m0, "cgd")
        cgd_m1 = self._val(m1, "cgd")
        cgd_m2 = self._val(m2, "cgd")
        cgd_m3 = self._val(m3, "cgd")
        cgd_m4 = self._val(m4, "cgd")
        cgd_m5 = self._val(m5, "cgd")
        cgg_m0 = self._val(m0, "cgg")
        cgg_m1 = self._val(m1, "cgg")
        cgg_m2 = self._val(m2, "cgg")
        cgg_m3 = self._val(m3, "cgg")
        cgg_m4 = self._val(m4, "cgg")
        cgg_m5 = self._val(m5, "cgg")

        results = {}

        mirror_den = max((gm_m1 + gds_m1 + gds_m0), eps)
        gout = max((gds_m2 + gds_m3), eps)
        gm_eff = (gm_m2 + (gm_m0 * gm_m3 / mirror_den)) / 2.0
        Av = gm_eff / gout
        c_out_miller = C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / mirror_den)))
        c_out_simple = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3
        pole_out = gout / (2.0 * math.pi * max(c_out_miller, eps))

        results["DC_Gain_dB"] = 20 * math.log10(abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))))
        print("DC_Gain_dB", results["DC_Gain_dB"])

        results["Bandwidth_3dB_Hz"] = max((gds_m2 + gds_m3), 1e-18) / (2.0 * math.pi * max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))))), 1e-18))
        print("Bandwidth_3dB_Hz", results["Bandwidth_3dB_Hz"])

        results["UGB_Hz"] = abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))) * (max((gds_m2 + gds_m3), 1e-18) / (2.0 * math.pi * max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))))), 1e-18)))
        print("UGB_Hz", results["UGB_Hz"])

        results["Phase_Margin_deg"] = 180.0 - ((math.atan(abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18)))) + math.atan((abs((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))) * (max((gds_m2 + gds_m3), 1e-18) / max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), 1e-18))) / max(((gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), 1e-18)), 1e-18))) * 180.0 / math.pi)
        print("Phase_Margin_deg", results["Phase_Margin_deg"])

        results["Gain_Margin_dB"] = 360.0
        print("Gain_Margin_dB", results["Gain_Margin_dB"])

        net2_g = gds_m4 + gds_m0 + gds_m2
        net2_gm = gm_m0 + gm_m2 + gmb_m0 + gmb_m2
        icmr_min_corr = max(abs(vdsat_m0), abs(vdsat_m2), 0.0) * max(net2_g, 0.0) / max((net2_g + (net2_gm * max(net2_g, 0.0) / max((net2_gm + net2_g), eps))), eps)
        results["Input_CMR_Min_V"] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + icmr_min_corr
        print("Input_CMR_Min_V", results["Input_CMR_Min_V"])

        results["Input_CMR_Max_V"] = min((Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)), (Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)))
        print("Input_CMR_Max_V", results["Input_CMR_Max_V"])

        results["Output_Swing_Max_V"] = Vdd - max((abs(vdsat_m3) + (max((abs(vgs_m3) - abs(vgs_m1)), 0.0) * max((gm_m3 + gmb_m3), 0.0) / max((gm_m1 + gds_m1 + gds_m0 + gm_m3 + gmb_m3), 1e-18))), 0.0)
        print("Output_Swing_Max_V", results["Output_Swing_Max_V"])

        results["Output_Swing_Min_V"] = Vss + max(abs(vdsat_m2), 0.0)
        print("Output_Swing_Min_V", results["Output_Swing_Min_V"])

        sr_pos_current = abs(id_m3) + (abs(id_m1) * max((gm_m3 + gmb_m3), 0.0) / max((gm_m1 + gds_m1 + gds_m0), eps)) - (abs(id_m2) * max(gds_m2, 0.0) / max((gm_m2 + gds_m2 + gds_m3), eps))
        results["Slew_Rate_Pos_V_us"] = (sr_pos_current / max(c_out_simple, eps)) / 1e6
        print("Slew_Rate_Pos_V_us", results["Slew_Rate_Pos_V_us"])

        results["Slew_Rate_Neg_V_us"] = ((abs(id_m2) + max((abs(id_m4) - abs(id_m0)), 0.0) * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)) / max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), 1e-18)) / 1e6
        print("Slew_Rate_Neg_V_us", results["Slew_Rate_Neg_V_us"])

        psrr_pos_feed = (gds_m3 + ((gm_m3 + gmb_m3) * (gds_m1 + gds_m0) / max((gm_m1 + gds_m1 + gds_m0 + gm_m3 + gmb_m3), eps))) / gout
        results["PSRR_Pos_dB"] = 20 * math.log10(abs(Av / max(psrr_pos_feed, eps)))
        print("PSRR_Pos_dB", results["PSRR_Pos_dB"])

        results["PSRR_Neg_dB"] = 20 * math.log10(abs(((((gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0) / max((gds_m2 + gds_m3), 1e-18))) / max((((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), 1e-18)) * (gds_m2 / max((gds_m2 + gds_m3), 1e-18))), 1e-18)))
        print("PSRR_Neg_dB", results["PSRR_Neg_dB"])

        cm_mismatch = (((abs(gm_m2 - (gm_m0 * gm_m3 / mirror_den)) + gds_m0 + gds_m2) / gout) * max((gds_m1 + gds_m0), 0.0) / mirror_den)
        cm_tail = ((gds_m4 + gds_m0 + gds_m2) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4), eps)) * abs(Av)
        Acm = cm_mismatch + cm_tail
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
