import math

EPS = 1e-18


def get_default_lut_row():
    return {
        'L': 0.0, 'W': 0.0, 'vgs': 0.0, 'vds': 0.0, 'vsb': 0.0,
        'id_raw': 0.0, 'id': 0.0, 'gm': 0.0, 'gds': 0.0, 'gmb': 0.0,
        'gmid': 0.0, 'vth': 0.0, 'vdsat': 0.0, 'cgg_int': 0.0,
        'cgd_int': 0.0, 'cgs_int': 0.0, 'cbg_int': 0.0, 'cbd_int': 0.0,
        'cbs_int': 0.0, 'cdg_int': 0.0, 'cdd_int': 0.0, 'cds_int': 0.0,
        'cgg': 0.0, 'cgd': 0.0, 'cgs': 0.0, 'cdd': 0.0, 'cds': 0.0,
        'cbd': 0.0, 'cb': 0.0
    }


class PerformanceModel:
    def _row(self, device_params, name):
        if not isinstance(device_params, dict):
            return get_default_lut_row()
        row = device_params.get(name, None)
        if row is None:
            return get_default_lut_row()
        base = get_default_lut_row()
        if isinstance(row, dict):
            base.update(row)
        return base

    def _p(self, row, key):
        try:
            value = row.get(key, 0.0)
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError, AttributeError):
            return 0.0

    def _clamp(self, value, low, high):
        return max(low, min(high, value))

    def compute(self, device_params, C_load, Vdd, Vss):
        # SECTION A: Safe Parameter Extraction using exact netlist instance names.
        m0 = self._row(device_params, 'm0')
        m1 = self._row(device_params, 'm1')
        m2 = self._row(device_params, 'm2')
        m3 = self._row(device_params, 'm3')
        m4 = self._row(device_params, 'm4')
        m5 = self._row(device_params, 'm5')

        gm_m0 = self._p(m0, 'gm')
        gm_m1 = self._p(m1, 'gm')
        gm_m2 = self._p(m2, 'gm')
        gm_m3 = self._p(m3, 'gm')
        gm_m4 = self._p(m4, 'gm')
        gm_m5 = self._p(m5, 'gm')

        gds_m0 = self._p(m0, 'gds')
        gds_m1 = self._p(m1, 'gds')
        gds_m2 = self._p(m2, 'gds')
        gds_m3 = self._p(m3, 'gds')
        gds_m4 = self._p(m4, 'gds')
        gds_m5 = self._p(m5, 'gds')

        gmb_m0 = self._p(m0, 'gmb')
        gmb_m1 = self._p(m1, 'gmb')
        gmb_m2 = self._p(m2, 'gmb')
        gmb_m3 = self._p(m3, 'gmb')
        gmb_m4 = self._p(m4, 'gmb')
        gmb_m5 = self._p(m5, 'gmb')

        id_m2 = self._p(m2, 'id')
        id_m3 = self._p(m3, 'id')
        id_m4 = self._p(m4, 'id')

        vgs_m0 = self._p(m0, 'vgs')
        vgs_m1 = self._p(m1, 'vgs')
        vgs_m2 = self._p(m2, 'vgs')
        vgs_m3 = self._p(m3, 'vgs')
        vdsat_m0 = self._p(m0, 'vdsat')
        vdsat_m2 = self._p(m2, 'vdsat')
        vdsat_m3 = self._p(m3, 'vdsat')
        vdsat_m4 = self._p(m4, 'vdsat')

        cdd_m0 = self._p(m0, 'cdd')
        cdd_m1 = self._p(m1, 'cdd')
        cdd_m2 = self._p(m2, 'cdd')
        cdd_m3 = self._p(m3, 'cdd')
        cgd_m0 = self._p(m0, 'cgd')
        cgd_m1 = self._p(m1, 'cgd')
        cgd_m2 = self._p(m2, 'cgd')
        cgd_m3 = self._p(m3, 'cgd')
        cgs_m1 = self._p(m1, 'cgs')
        cgs_m3 = self._p(m3, 'cgs')
        cgg_m1 = self._p(m1, 'cgg')
        cgg_m3 = self._p(m3, 'cgg')

        try:
            C_load_f = float(C_load)
        except (TypeError, ValueError):
            C_load_f = 0.0
        try:
            Vdd_f = float(Vdd)
        except (TypeError, ValueError):
            Vdd_f = 1.0
        try:
            Vss_f = float(Vss)
        except (TypeError, ValueError):
            Vss_f = 0.0

        results = {}

        # SECTION B: Metric calculations in SI units unless the metric name explicitly states dB or V/us.
        mirror_den = max(gm_m1 + gds_m1 + gds_m0, EPS)
        mirror_gain = gm_m3 / mirror_den
        Gm_eff = 0.5 * (gm_m2 + gm_m0 * mirror_gain)
        G_out_total = max(gds_m2 + gds_m3, EPS)
        Av0 = Gm_eff / G_out_total
        results['DC_Gain_dB'] = 20.0 * math.log10(max(abs(Av0), EPS))
        print('DC_Gain_dB:', results['DC_Gain_dB'])

        C_out = max(C_load_f + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3 * (1.0 + abs(mirror_gain)), EPS)
        results['Bandwidth_3dB_Hz'] = G_out_total / (2.0 * math.pi * C_out)
        print('Bandwidth_3dB_Hz:', results['Bandwidth_3dB_Hz'])

        results['UGB_Hz'] = abs(Av0) * results['Bandwidth_3dB_Hz']
        print('UGB_Hz:', results['UGB_Hz'])

        C_net3 = max(cdd_m0 + cdd_m1 + cgd_m0 + cgd_m1 + cgs_m1 + cgs_m3 + cgg_m1 + cgg_m3, EPS)
        f_p2 = max((gm_m1 + gds_m1 + gds_m0) / (2.0 * math.pi * C_net3), EPS)
        phase_lag_deg = (math.atan(results['UGB_Hz'] / max(results['Bandwidth_3dB_Hz'], EPS)) + math.atan(results['UGB_Hz'] / f_p2)) * 180.0 / math.pi
        results['Phase_Margin_deg'] = self._clamp(180.0 - phase_lag_deg, 0.0, 180.0)
        print('Phase_Margin_deg:', results['Phase_Margin_deg'])

        phase_cross_gain = 0.0
        results['Gain_Margin_dB'] = 20.0 * math.log10(abs(1.0 / max(abs(phase_cross_gain), EPS)))
        print('Gain_Margin_dB:', results['Gain_Margin_dB'])

        input_cmr_min = Vss_f + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0)
        results['Input_CMR_Min_V'] = self._clamp(input_cmr_min, Vss_f, Vdd_f)
        print('Input_CMR_Min_V:', results['Input_CMR_Min_V'])

        input_cmr_max_m0 = Vdd_f - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)
        input_cmr_max_m2 = Vdd_f - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)
        results['Input_CMR_Max_V'] = self._clamp(min(input_cmr_max_m0, input_cmr_max_m2), Vss_f, Vdd_f)
        print('Input_CMR_Max_V:', results['Input_CMR_Max_V'])

        output_swing_max = Vdd_f - max(abs(vdsat_m3), 0.0)
        results['Output_Swing_Max_V'] = self._clamp(output_swing_max, Vss_f, Vdd_f)
        print('Output_Swing_Max_V:', results['Output_Swing_Max_V'])

        output_swing_min = Vss_f + max(abs(vdsat_m4), 0.0) + max(abs(vdsat_m2), 0.0)
        results['Output_Swing_Min_V'] = self._clamp(output_swing_min, Vss_f, Vdd_f)
        print('Output_Swing_Min_V:', results['Output_Swing_Min_V'])

        C_slew = max(C_load_f + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3, EPS)
        results['Slew_Rate_Pos_V_us'] = (abs(id_m3) / C_slew) / 1e6
        print('Slew_Rate_Pos_V_us:', results['Slew_Rate_Pos_V_us'])

        results['Slew_Rate_Neg_V_us'] = (min(abs(id_m2), abs(id_m4)) / C_slew) / 1e6
        print('Slew_Rate_Neg_V_us:', results['Slew_Rate_Neg_V_us'])

        A_vdd = (gds_m3 + gm_m3 * gds_m1 / mirror_den) / G_out_total
        results['PSRR_Pos_dB'] = 20.0 * math.log10(max(abs(Av0 / max(abs(A_vdd), EPS)), EPS))
        print('PSRR_Pos_dB:', results['PSRR_Pos_dB'])

        A_vss = (gds_m4 / max(gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4, EPS)) * (gds_m2 / G_out_total)
        results['PSRR_Neg_dB'] = 20.0 * math.log10(max(abs(Av0 / max(abs(A_vss), EPS)), EPS))
        print('PSRR_Neg_dB:', results['PSRR_Neg_dB'])

        Acm_mirror = abs(gm_m2 - gm_m0 * mirror_gain) / G_out_total
        Acm_tail = (gds_m4 / max(gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4, EPS)) * abs(Av0)
        Acm_total = Acm_mirror + Acm_tail
        results['CMRR_dB'] = 20.0 * math.log10(max(abs(Av0 / max(abs(Acm_total), EPS)), EPS))
        print('CMRR_dB:', results['CMRR_dB'])

        return results


if __name__ == '__main__':
    mock_params = {
        'm0': get_default_lut_row(),
        'm1': get_default_lut_row(),
        'm2': get_default_lut_row(),
        'm3': get_default_lut_row(),
        'm4': get_default_lut_row(),
        'm5': get_default_lut_row()
    }

    model = PerformanceModel()
    output = model.compute(device_params=mock_params, C_load=1e-12, Vdd=1.0, Vss=0.0)

    print('\nReadable display:')
    for metric, value in output.items():
        print(f'{metric}: {value}')
