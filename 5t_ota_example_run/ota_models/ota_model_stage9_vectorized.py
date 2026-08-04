import argparse
import contextlib
import importlib.util
import json
import math
import os
import sys

import numpy as np


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


def _safe_float(value):
    try:
        if value is None:
            return 0.0
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read().strip()
    if not text:
        return None
    return json.loads(text)


def normalize_op_json(op_data):
    device_params = {}
    if isinstance(op_data, dict):
        for name, value in op_data.items():
            if isinstance(value, dict):
                row = get_default_lut_row()
                row.update(value)
                device_params[str(name)] = row
    return device_params


def normalize_candidate_json(candidate_data):
    if not isinstance(candidate_data, dict):
        return None
    normalized = {}
    for key, value in candidate_data.items():
        if isinstance(value, (list, tuple)):
            normalized[str(key)] = _safe_float(value[0]) if value else 0.0
        else:
            normalized[str(key)] = _safe_float(value)
    return normalized


def scalar_device_params_to_batch(device_params):
    batch = {}
    for device_name, row in device_params.items():
        out_row = {}
        if isinstance(row, dict):
            for param_name, value in row.items():
                out_row[str(param_name)] = np.asarray([_safe_float(value)], dtype=float)
        batch[str(device_name)] = out_row
    return batch


def scalar_candidates_to_batch(candidates):
    if candidates is None:
        return None
    return {str(key): np.asarray([_safe_float(value)], dtype=float) for key, value in candidates.items()}


class VectorizedPerformanceModel:
    def _infer_n(self, device_params_batch, candidates_batch):
        if isinstance(device_params_batch, dict):
            for row in device_params_batch.values():
                if isinstance(row, dict):
                    for value in row.values():
                        arr = np.asarray(value)
                        if arr.ndim > 0:
                            return int(arr.shape[0])
        if isinstance(candidates_batch, dict):
            for value in candidates_batch.values():
                arr = np.asarray(value)
                if arr.ndim > 0:
                    return int(arr.shape[0])
        return 1

    def _row(self, device_params_batch, name, n):
        if isinstance(device_params_batch, dict):
            if name in device_params_batch and isinstance(device_params_batch[name], dict):
                return device_params_batch[name]
            lname = name.lower()
            for key, value in device_params_batch.items():
                if str(key).lower() == lname and isinstance(value, dict):
                    return value
        return {}

    def _f(self, row, key, n):
        if not isinstance(row, dict) or key not in row:
            return np.zeros(n, dtype=float)
        value = row.get(key, 0.0)
        if value is None:
            return np.zeros(n, dtype=float)
        try:
            arr = np.asarray(value, dtype=float)
        except (TypeError, ValueError):
            return np.zeros(n, dtype=float)
        if arr.ndim == 0:
            return np.full(n, float(arr), dtype=float)
        arr = arr.reshape(-1)
        if arr.shape[0] == n:
            return arr.astype(float, copy=False)
        if arr.shape[0] == 1:
            return np.full(n, float(arr[0]), dtype=float)
        raise ValueError(f"Parameter {key!r} has shape {arr.shape}, expected ({n},)")

    def _scalar_arg(self, value, n):
        try:
            scalar = float(value or 0.0)
        except (TypeError, ValueError):
            scalar = 0.0
        return np.full(n, scalar, dtype=float)

    def _log_db(self, value):
        return 20.0 * np.log10(np.maximum(np.abs(value.astype(float, copy=False)), 1e-18))

    def compute_batch(
        self,
        device_params_batch,
        candidates_batch=None,
        C_load=1e-12,
        Vdd=1.0,
        Vss=0.0,
    ):
        '''
        device_params_batch:
            dict[device_name][param_name] -> np.ndarray shape (N,)

        candidates_batch:
            dict[param_name] -> np.ndarray shape (N,)

        returns:
            dict[metric_name] -> np.ndarray shape (N,)
        '''
        n = self._infer_n(device_params_batch, candidates_batch)
        C_load = self._scalar_arg(C_load, n)
        Vdd = self._scalar_arg(Vdd, n)
        Vss = self._scalar_arg(Vss, n)

        m0 = self._row(device_params_batch, "m0", n)
        m1 = self._row(device_params_batch, "m1", n)
        m2 = self._row(device_params_batch, "m2", n)
        m3 = self._row(device_params_batch, "m3", n)
        m4 = self._row(device_params_batch, "m4", n)
        m5 = self._row(device_params_batch, "m5", n)
        _ = m5

        vgs_m0 = self._f(m0, "vgs", n); vdsat_m0 = self._f(m0, "vdsat", n)
        id_m0 = self._f(m0, "id", n); gm_m0 = self._f(m0, "gm", n); gds_m0 = self._f(m0, "gds", n); gmb_m0 = self._f(m0, "gmb", n)
        cdd_m0 = self._f(m0, "cdd", n)

        vgs_m1 = self._f(m1, "vgs", n); id_m1 = self._f(m1, "id", n)
        gm_m1 = self._f(m1, "gm", n); gds_m1 = self._f(m1, "gds", n)
        cdd_m1 = self._f(m1, "cdd", n); cgg_m1 = self._f(m1, "cgg", n)
        _ = vgs_m1

        vgs_m2 = self._f(m2, "vgs", n); vdsat_m2 = self._f(m2, "vdsat", n)
        id_m2 = self._f(m2, "id", n); gm_m2 = self._f(m2, "gm", n); gds_m2 = self._f(m2, "gds", n); gmb_m2 = self._f(m2, "gmb", n)
        cdd_m2 = self._f(m2, "cdd", n); cgd_m2 = self._f(m2, "cgd", n)

        vgs_m3 = self._f(m3, "vgs", n); vdsat_m3 = self._f(m3, "vdsat", n)
        id_m3 = self._f(m3, "id", n); gm_m3 = self._f(m3, "gm", n); gds_m3 = self._f(m3, "gds", n); gmb_m3 = self._f(m3, "gmb", n)
        cdd_m3 = self._f(m3, "cdd", n); cgd_m3 = self._f(m3, "cgd", n); cgg_m3 = self._f(m3, "cgg", n)

        vdsat_m4 = self._f(m4, "vdsat", n)
        id_m4 = self._f(m4, "id", n); gm_m4 = self._f(m4, "gm", n); gds_m4 = self._f(m4, "gds", n); gmb_m4 = self._f(m4, "gmb", n)
        _ = gm_m4

        results = {}

        mirror_den = np.maximum((gm_m1 + gds_m1 + gds_m0), 1e-18)
        gout = np.maximum((gds_m2 + gds_m3), 1e-18)
        gm_eff = (gm_m2 + (gm_m0 * gm_m3 / mirror_den)) / 2.0
        Av = gm_eff / gout
        cout_miller = C_load + cdd_m2 + cdd_m3 + cgd_m2 + (cgd_m3 * (1.0 + np.abs(gm_m3 / mirror_den)))
        cout_plain = C_load + cdd_m2 + cdd_m3 + cgd_m2 + cgd_m3
        bw = gout / (2.0 * math.pi * np.maximum(cout_miller, 1e-18))

        results["DC_Gain_dB"] = self._log_db(Av)
        results["Bandwidth_3dB_Hz"] = bw
        results["UGB_Hz"] = np.abs(Av) * bw

        internal_pole = (gm_m1 + gds_m1 + gds_m0) / np.maximum((cdd_m0 + cdd_m1 + cgg_m1 + cgg_m3), 1e-18)
        phase_lag = np.arctan(np.abs(Av)) + np.arctan((np.abs(Av) * (gout / np.maximum(cout_plain, 1e-18))) / np.maximum(internal_pole, 1e-18))
        results["Phase_Margin_deg"] = 180.0 - (phase_lag * 180.0 / math.pi)

        results["Gain_Margin_dB"] = np.full(n, 360.0, dtype=float)

        source_g = gds_m4 + gds_m0 + gds_m2
        source_g_pos = np.maximum(source_g, 0.0)
        input_pair_gm_sum = gm_m0 + gm_m2 + gmb_m0 + gmb_m2
        icmr_min_extra = np.maximum.reduce([np.abs(vdsat_m0), np.abs(vdsat_m2), np.zeros(n, dtype=float)]) * source_g_pos / np.maximum((source_g + (input_pair_gm_sum * source_g_pos / np.maximum((input_pair_gm_sum + source_g), 1e-18))), 1e-18)
        results["Input_CMR_Min_V"] = Vss + np.maximum(np.abs(vdsat_m4), 0.0) + np.maximum.reduce([vgs_m0, vgs_m2, np.zeros(n, dtype=float)]) + icmr_min_extra

        results["Input_CMR_Max_V"] = np.minimum((Vdd - np.abs(vgs_m1) + np.maximum(vgs_m0, 0.0) - np.maximum(np.abs(vdsat_m0), 0.0)), (Vdd - np.abs(vgs_m3) + np.maximum(vgs_m2, 0.0) - np.maximum(np.abs(vdsat_m2), 0.0)))

        results["Output_Swing_Max_V"] = Vdd - np.maximum((np.abs(vdsat_m3) + np.abs(vdsat_m2)), 0.0)
        results["Output_Swing_Min_V"] = Vss + np.maximum(np.abs(vdsat_m2), 0.0)

        sr_pos_charge = np.abs(id_m3) + (np.abs(id_m1) * np.maximum(gm_m3, 0.0) / mirror_den)
        sr_pos_oppose = np.abs(id_m2) * np.maximum(gds_m2, 0.0) / gout * np.maximum(gds_m4, 0.0) / np.maximum((gds_m4 + gds_m0 + gds_m2), 1e-18)
        results["Slew_Rate_Pos_V_us"] = (np.maximum((sr_pos_charge - sr_pos_oppose), 0.0) / np.maximum(cout_plain, 1e-18)) / 1e6

        sr_neg_current = np.abs(id_m2) + np.maximum((np.abs(id_m4) - np.abs(id_m0)), 0.0) * np.maximum(gds_m4, 0.0) / np.maximum((gds_m4 + gds_m0 + gds_m2), 1e-18)
        results["Slew_Rate_Neg_V_us"] = (sr_neg_current / np.maximum(cout_plain, 1e-18)) / 1e6

        psrr_pos_feed = (gds_m3 + ((gm_m3 + gmb_m3) * (gds_m1 + gds_m0 + gds_m3) / np.maximum((gm_m1 + gds_m1 + gds_m0 + gm_m3 + gmb_m3 + gds_m3), 1e-18))) / gout
        results["PSRR_Pos_dB"] = self._log_db(Av / np.maximum(psrr_pos_feed, 1e-18))

        psrr_neg_feed = ((gds_m4 + gmb_m4) / np.maximum((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + gmb_m4), 1e-18)) * (gds_m2 / gout)
        results["PSRR_Neg_dB"] = self._log_db(Av / np.maximum(psrr_neg_feed, 1e-18))

        cm_path_mirror = (np.abs(gm_m2 - (gm_m0 * gm_m3 / mirror_den)) / gout) * np.maximum((gds_m1 + gds_m0), 0.0) / mirror_den
        m4_body_term = gmb_m4 * np.maximum(gds_m4, 0.0) / np.maximum((gds_m4 + gds_m0 + gds_m2), 1e-18)
        cm_path_tail = ((gds_m4 + m4_body_term) / np.maximum((gm_m0 + gm_m2 + gmb_m0 + gmb_m2 + gds_m4 + m4_body_term), 1e-18)) * np.abs(Av)
        tail_rejection = np.maximum(((gm_m0 + gm_m2 + gmb_m0 + gmb_m2) / np.maximum((gds_m4 + gds_m0 + gds_m2), 1e-18)), 1e-18)
        Acm = (cm_path_mirror + cm_path_tail) / tail_rejection
        results["CMRR_dB"] = self._log_db(Av / np.maximum(Acm, 1e-18))

        return results


def load_scalar_evaluator(path):
    module_name = "scalar_evaluator_reference"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load scalar evaluator from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "PerformanceModel"):
        raise AttributeError("Scalar evaluator does not define PerformanceModel")
    return module.PerformanceModel()


def run_scalar_reference(model, device_params, candidates, C_load, Vdd, Vss):
    kwargs = candidates if isinstance(candidates, dict) else {}
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink):
            return model.compute(device_params=device_params, C_load=C_load, Vdd=Vdd, Vss=Vss, **kwargs)


def compare_metrics(scalar_metrics, vector_metrics):
    scalar_keys = list(scalar_metrics.keys())
    vector_keys = list(vector_metrics.keys())
    metric_names = scalar_keys + [name for name in vector_keys if name not in scalar_metrics]
    all_pass = True

    print(f"{'METRIC':<24} {'STATUS':<6} {'SCALAR':>18} {'VECTORIZED':>18} {'ABS_ERR':>12} {'REL_ERR':>12}")
    print("-" * 96)
    for name in metric_names:
        scalar_present = name in scalar_metrics
        vector_present = name in vector_metrics
        if not scalar_present or not vector_present:
            all_pass = False
            status = "FAIL"
            scalar_value = float(scalar_metrics[name]) if scalar_present else float("nan")
            vector_value = float(np.asarray(vector_metrics[name]).reshape(-1)[0]) if vector_present else float("nan")
            abs_err = abs(vector_value - scalar_value) if scalar_present and vector_present else float("nan")
            rel_err = abs_err / max(abs(scalar_value), 1e-18) if scalar_present and vector_present else float("nan")
        else:
            scalar_value = float(scalar_metrics[name])
            vector_arr = np.asarray(vector_metrics[name], dtype=float).reshape(-1)
            vector_value = float(vector_arr[0]) if vector_arr.size else float("nan")
            abs_err = abs(vector_value - scalar_value)
            rel_err = abs_err / max(abs(scalar_value), 1e-18)
            passed = bool(np.isclose(vector_value, scalar_value, rtol=1e-9, atol=1e-12))
            status = "PASS" if passed else "FAIL"
            all_pass = all_pass and passed
        print(f"{name:<24} {status:<6} {scalar_value:18.10e} {vector_value:18.10e} {abs_err:12.4e} {rel_err:12.4e}")
        if status == "FAIL":
            print(f"  mismatch {name}: scalar={scalar_value!r} vectorized={vector_value!r} abs_error={abs_err!r} relative_error={rel_err!r}")

    return all_pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vectorized batch checker for OTA scalar evaluator.")
    parser.add_argument("--op_json", required=True)
    parser.add_argument("--scalar_evaluator", required=True)
    parser.add_argument("--candidate_json", default=None)
    parser.add_argument("--C_load", type=float, default=1e-12)
    parser.add_argument("--Vdd", type=float, default=1.0)
    parser.add_argument("--Vss", type=float, default=0.0)
    args = parser.parse_args(argv)

    op_data = _load_json(args.op_json)
    device_params = normalize_op_json(op_data)
    device_params_batch = scalar_device_params_to_batch(device_params)

    candidates = None
    candidates_batch = None
    if args.candidate_json:
        candidate_data = _load_json(args.candidate_json)
        candidates = normalize_candidate_json(candidate_data)
        candidates_batch = scalar_candidates_to_batch(candidates)

    scalar_model = load_scalar_evaluator(args.scalar_evaluator)
    scalar_metrics = run_scalar_reference(scalar_model, device_params, candidates, args.C_load, args.Vdd, args.Vss)

    vector_model = VectorizedPerformanceModel()
    vector_metrics = vector_model.compute_batch(
        device_params_batch=device_params_batch,
        candidates_batch=candidates_batch,
        C_load=args.C_load,
        Vdd=args.Vdd,
        Vss=args.Vss,
    )

    all_pass = compare_metrics(scalar_metrics, vector_metrics)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
