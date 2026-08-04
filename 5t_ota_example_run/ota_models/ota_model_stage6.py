import math

class PerformanceModel:
    def compute(self, device_params, C_load, Vdd, Vss, **kwargs):
        def row(name):
            if name in device_params:
                return device_params[name]
            lname = name.lower()
            for key, value in device_params.items():
                if str(key).lower() == lname:
                    return value
            return get_default_lut_row()

        def val(dev, key):
            try:
                return float(row(dev).get(key, 0.0))
            except Exception:
                return 0.0

        gm_m0 = val('m0', 'gm'); gds_m0 = val('m0', 'gds'); gmb_m0 = val('m0', 'gmb'); vgs_m0 = val('m0', 'vgs'); vdsat_m0 = val('m0', 'vdsat'); cdd_m0 = val('m0', 'cdd')
        gm_m1 = val('m1', 'gm'); gds_m1 = val('m1', 'gds'); gmb_m1 = val('m1', 'gmb'); vgs_m1 = val('m1', 'vgs'); cdd_m1 = val('m1', 'cdd'); cgg_m1 = val('m1', 'cgg'); id_m1 = val('m1', 'id')
        gm_m2 = val('m2', 'gm'); gds_m2 = val('m2', 'gds'); gmb_m2 = val('m2', 'gmb'); vgs_m2 = val('m2', 'vgs'); vdsat_m2 = val('m2', 'vdsat'); cdd_m2 = val('m2', 'cdd'); cgd_m2 = val('m2', 'cgd'); id_m2 = val('m2', 'id')
        gm_m3 = val('m3', 'gm'); gds_m3 = val('m3', 'gds'); gmb_m3 = val('m3', 'gmb'); vgs_m3 = val('m3', 'vgs'); vth_m3 = val('m3', 'vth'); vdsat_m3 = val('m3', 'vdsat'); cdd_m3 = val('m3', 'cdd'); cgd_m3 = val('m3', 'cgd'); cgg_m3 = val('m3', 'cgg'); id_m3 = val('m3', 'id')
        gm_m4 = val('m4', 'gm'); gds_m4 = val('m4', 'gds'); gmb_m4 = val('m4', 'gmb'); vdsat_m4 = val('m4', 'vdsat'); id_m4 = val('m4', 'id')
        id_m0 = val('m0', 'id')

        results = {}
        gain_num = (gm_m2 + (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / 2.0
        gout = max((gds_m2 + gds_m3), 1e-18)
        av = gain_num / gout
        c_out_miller = C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + abs(gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))))
        c_out_static = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3

        results['DC_Gain_dB'] = 20 * math.log10(abs(av)) if abs(av) > 0.0 else -360.0
        print('DC_Gain_dB', results['DC_Gain_dB'])

        results['Bandwidth_3dB_Hz'] = gout / (2.0 * math.pi * max(c_out_miller, 1e-18))
        print('Bandwidth_3dB_Hz', results['Bandwidth_3dB_Hz'])

        results['UGB_Hz'] = abs(av) * results['Bandwidth_3dB_Hz']
        print('UGB_Hz', results['UGB_Hz'])

        mirror_pole = max(((gm_m1 + gds_m1 + gds_m0) / max((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), 1e-18)), 1e-18)
        phase_lag = math.atan(abs(av)) + math.atan((abs(av) * (gout / max(c_out_static, 1e-18))) / mirror_pole)
        results['Phase_Margin_deg'] = 180.0 - (phase_lag * 180.0 / math.pi)
        print('Phase_Margin_deg', results['Phase_Margin_deg'])

        results['Gain_Margin_dB'] = 360.0
        print('Gain_Margin_dB', results['Gain_Margin_dB'])

        icmr_min_num = max(abs(vdsat_m0), abs(vdsat_m2), 0.0) * max((gds_m4 + gds_m0 + gds_m2), 0.0)
        icmr_min_den_inner = ((gm_m0 + gm_m2 + gmb_m0 + gmb_m2) * max((gds_m4 + gds_m0 + gds_m2), 0.0) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gds_m0 + gds_m2), 1e-18))
        results['Input_CMR_Min_V'] = Vss + max(abs(vdsat_m4), 0.0) + max(vgs_m0, vgs_m2, 0.0) + (icmr_min_num / max((gds_m4 + gds_m0 + gds_m2 + icmr_min_den_inner), 1e-18))
        print('Input_CMR_Min_V', results['Input_CMR_Min_V'])

        results['Input_CMR_Max_V'] = min((Vdd - abs(vgs_m1) + max(vgs_m0, 0.0) - max(abs(vdsat_m0), 0.0)), (Vdd - abs(vgs_m3) + max(vgs_m2, 0.0) - max(abs(vdsat_m2), 0.0)))
        print('Input_CMR_Max_V', results['Input_CMR_Max_V'])

        results['Output_Swing_Max_V'] = Vdd - max(abs(vdsat_m3), max((abs(vgs_m3) - abs(vth_m3)), 0.0), 0.0)
        print('Output_Swing_Max_V', results['Output_Swing_Max_V'])

        results['Output_Swing_Min_V'] = Vss + max(abs(vdsat_m2), 0.0)
        print('Output_Swing_Min_V', results['Output_Swing_Min_V'])

        sr_pos_current = abs(id_m3) + (abs(id_m1) * max(gm_m3, 0.0) / max((gm_m1 + gds_m1 + gds_m0), 1e-18))
        results['Slew_Rate_Pos_V_us'] = (sr_pos_current / max(c_out_miller, 1e-18)) / 1e6
        print('Slew_Rate_Pos_V_us', results['Slew_Rate_Pos_V_us'])

        sr_neg_current = abs(id_m2) + max((abs(id_m4) - abs(id_m0)), 0.0) * max(gds_m4, 0.0) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)
        results['Slew_Rate_Neg_V_us'] = (sr_neg_current / max(c_out_static, 1e-18)) / 1e6
        print('Slew_Rate_Neg_V_us', results['Slew_Rate_Neg_V_us'])

        psrr_pos_feed = (gds_m3 + ((gm_m3 + gmb_m3) * (gds_m1 + gds_m0 + gds_m3) / max((gm_m1 + gds_m1 + gds_m0 + gm_m3 + gmb_m3 + gds_m3), 1e-18))) / gout
        results['PSRR_Pos_dB'] = 20 * math.log10(abs(av / max(psrr_pos_feed, 1e-18))) if abs(av) > 0.0 else -360.0
        print('PSRR_Pos_dB', results['PSRR_Pos_dB'])

        psrr_neg_feed = ((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), 1e-18)) * (gds_m2 / gout)
        results['PSRR_Neg_dB'] = 20 * math.log10(abs(av / max(psrr_neg_feed, 1e-18))) if abs(av) > 0.0 else -360.0
        print('PSRR_Neg_dB', results['PSRR_Neg_dB'])

        mirror_mismatch = (abs(gm_m2 - (gm_m0 * gm_m3 / max((gm_m1 + gds_m1 + gds_m0), 1e-18))) / gout) * max((gds_m1 + gds_m0), 0.0) / max((gm_m1 + gds_m1 + gds_m0), 1e-18)
        tail_cm = ((gds_m4 + gmb_m4) / max((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), 1e-18)) * abs(av)
        source_rejection = max(((gm_m0 + gm_m2 + gmb_m0 + gmb_m2) / max((gds_m4 + gds_m0 + gds_m2), 1e-18)), 1e-18)
        acm = (mirror_mismatch + tail_cm) / source_rejection
        results['CMRR_dB'] = 20 * math.log10(abs(av / max(acm, 1e-18))) if abs(av) > 0.0 else -360.0
        print('CMRR_dB', results['CMRR_dB'])

        return results

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
    for metric, value in output.items():
        print(f'{metric}: {value}')
