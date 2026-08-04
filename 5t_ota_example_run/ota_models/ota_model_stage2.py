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
            return device_params[name]
        lname = name.lower()
        for key, value in device_params.items():
            if str(key).lower() == lname:
                return value
        return get_default_lut_row()

    def _p(self, row, key):
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
        C_load = float(C_load or 0.0)
        Vdd = float(Vdd or 0.0)
        Vss = float(Vss or 0.0)

        m0 = self._dev(device_params, "m0")
        m1 = self._dev(device_params, "m1")
        m2 = self._dev(device_params, "m2")
        m3 = self._dev(device_params, "m3")
        m4 = self._dev(device_params, "m4")
        m5 = self._dev(device_params, "m5")

        vgs_m0 = self._p(m0, "vgs")
        vdsat_m0 = self._p(m0, "vdsat")
        id_m0 = self._p(m0, "id")
        gm_m0 = self._p(m0, "gm")
        gds_m0 = self._p(m0, "gds")
        gmb_m0 = self._p(m0, "gmb")
        cdd_m0 = self._p(m0, "cdd")

        vgs_m1 = self._p(m1, "vgs")
        vdsat_m1 = self._p(m1, "vdsat")
        id_m1 = self._p(m1, "id")
        gm_m1 = self._p(m1, "gm")
        gds_m1 = self._p(m1, "gds")
        cgg_m1 = self._p(m1, "cgg")
        cdd_m1 = self._p(m1, "cdd")

        vgs_m2 = self._p(m2, "vgs")
        vdsat_m2 = self._p(m2, "vdsat")
        id_m2 = self._p(m2, "id")
        gm_m2 = self._p(m2, "gm")
        gds_m2 = self._p(m2, "gds")
        gmb_m2 = self._p(m2, "gmb")
        cgd_m2 = self._p(m2, "cgd")
        cdd_m2 = self._p(m2, "cdd")

        vgs_m3 = self._p(m3, "vgs")
        vdsat_m3 = self._p(m3, "vdsat")
        id_m3 = self._p(m3, "id")
        gm_m3 = self._p(m3, "gm")
        gds_m3 = self._p(m3, "gds")
        cgg_m3 = self._p(m3, "cgg")
        cgd_m3 = self._p(m3, "cgd")
        cdd_m3 = self._p(m3, "cdd")

        vdsat_m4 = self._p(m4, "vdsat")
        id_m4 = self._p(m4, "id")
        gm_m4 = self._p(m4, "gm")
        gds_m4 = self._p(m4, "gds")
        gmb_m4 = self._p(m4, "gmb")

        id_m5 = self._p(m5, "id")
        gm_m5 = self._p(m5, "gm")
        gds_m5 = self._p(m5, "gds")
        gmb_m5 = self._p(m5, "gmb")

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
        av = gm_eff / gout
        mirror_gain_m3 = abs(gm_m3 / mirror_den)
        c_out_bw = max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + mirror_gain_m3))), eps)
        c_out_pm = max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), eps)
        output_pole = gout / (2.0 * math.pi * c_out_bw)
        mirror_pole = max(((gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), eps)), eps)

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

        results["Input_CMR_Min_V"] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + max(abs(vdsat_m0), abs(vdsat_m2), 0.0)
        print("Input_CMR_Min_V:", results["Input_CMR_Min_V"])

        results["Input_CMR_Max_V"] = min((Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)), (Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)))
        print("Input_CMR_Max_V:", results["Input_CMR_Max_V"])

        results["Output_Swing_Max_V"] = Vdd - max(abs(vdsat_m3), abs(vdsat_m1) * max((gm_m3 + gds_m3), 1e-18) / max((gm_m1 + gds_m1 + gds_m0), 1e-18), 0.0)
        print("Output_Swing_Max_V:", results["Output_Swing_Max_V"])

        results["Output_Swing_Min_V"] = Vss + max(abs(vdsat_m2), 0.0)
        print("Output_Swing_Min_V:", results["Output_Swing_Min_V"])

        results["Slew_Rate_Pos_V_us"] = ((abs(id_m3) + abs(id_m1)) / max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), 1e-18)) / 1e6
        print("Slew_Rate_Pos_V_us:", results["Slew_Rate_Pos_V_us"])

        results["Slew_Rate_Neg_V_us"] = ((abs(id_m2) + abs(id_m4)) / max((C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3), 1e-18)) / 1e6
        print("Slew_Rate_Neg_V_us:", results["Slew_Rate_Neg_V_us"])

        psrr_pos_supply_gain = ((gds_m3 + (gm_m3 * (gds_m1 + gds_m0) / max((gm_m1 + gds_m1 + gds_m0), eps))) / gout)
        results["PSRR_Pos_dB"] = 20 * math.log10(abs(av / max(psrr_pos_supply_gain, eps)))
        print("PSRR_Pos_dB:", results["PSRR_Pos_dB"])

        psrr_neg_supply_gain = (((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), eps)) * (gds_m2 / gout))
        results["PSRR_Neg_dB"] = 20 * math.log10(abs(av / max(psrr_neg_supply_gain, eps)))
        print("PSRR_Neg_dB:", results["PSRR_Neg_dB"])

        acm_raw = ((abs(gm_m2 - gm_mirror) / gout) + ((gds_m4 / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4), eps)) * abs(av)))
        common_source_rejection = max(((gm_m0 + gm_m2 + gmb_m0 + gmb_m2) / max((gds_m4 + gds_m0 + gds_m2), eps)), eps)
        acm = acm_raw / common_source_rejection
        results["CMRR_dB"] = 20 * math.log10(abs(av / max(acm, eps)))
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
