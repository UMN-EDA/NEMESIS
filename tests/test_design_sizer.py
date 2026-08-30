import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from design_sizer import CircuitSizer, run_general_flow, validate_lut_csv

VALID_LUT = "L,gmid,id,W,optional\n1.8e-7,10,5e-6,1e-6,unused\n"


class LUTValidationTests(unittest.TestCase):
    def test_valid_lut_accepts_required_columns_and_does_not_create_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "valid LUT.csv"
            lut_path.write_text(VALID_LUT, encoding="utf-8")

            self.assertEqual(validate_lut_csv(lut_path), 1)
            self.assertFalse(lut_path.with_suffix(".pkl").exists())

    def test_missing_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "missing.csv"

            with self.assertRaisesRegex(ValueError, "cannot read LUT CSV"):
                validate_lut_csv(lut_path)

    def test_missing_required_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "missing-width.csv"
            lut_path.write_text("L,gmid,id\n1.8e-7,10,5e-6\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing required columns: W"):
                validate_lut_csv(lut_path)

    def test_empty_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "empty.csv"
            lut_path.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "cannot read LUT CSV"):
                validate_lut_csv(lut_path)

    def test_malformed_csv_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "malformed.csv"
            lut_path.write_text(
                'L,gmid,id,W\n1.8e-7,"unterminated,5e-6,1e-6\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "cannot read LUT CSV"):
                validate_lut_csv(lut_path)

    def test_header_only_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "header-only.csv"
            lut_path.write_text("L,gmid,id,W\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "contains no data rows"):
                validate_lut_csv(lut_path)

    def test_non_numeric_required_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "bad-number.csv"
            lut_path.write_text("L,gmid,id,W\n1.8e-7,bad,5e-6,1e-6\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "finite numeric values in columns: gmid"
            ):
                validate_lut_csv(lut_path)

    def test_non_finite_required_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lut_path = Path(temp_dir) / "infinite.csv"
            lut_path.write_text("L,gmid,id,W\n1.8e-7,inf,5e-6,nan\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "finite numeric values in columns: gmid, W"
            ):
                validate_lut_csv(lut_path)

    def test_validation_cli_accepts_paths_with_spaces_without_writing_caches(self):
        script_path = Path(__file__).parents[1] / "design_sizer.py"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            nmos_path = temp_path / "NMOS LUT.csv"
            pmos_path = temp_path / "PMOS LUT.csv"
            nmos_path.write_text(VALID_LUT, encoding="utf-8")
            pmos_path.write_text(VALID_LUT, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--validate-luts",
                    "--nmos-lut",
                    str(nmos_path),
                    "--pmos-lut",
                    str(pmos_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Validated NMOS LUT", result.stdout)
            self.assertIn("Validated PMOS LUT", result.stdout)
            self.assertEqual(list(temp_path.glob("*.pkl")), [])


class DesignSizerFlowTests(unittest.TestCase):
    def test_verify_does_not_require_lut_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            specs_path = temp_path / "specs.json"
            op_path = temp_path / "op.json"
            output_path = temp_path / "output.json"

            specs_path.write_text(json.dumps({"meta": {}}), encoding="utf-8")
            op_path.write_text(
                json.dumps({"m1": {"W": 1.0, "L": 0.18}}),
                encoding="utf-8",
            )

            args = SimpleNamespace(
                specs=str(specs_path),
                model=None,
                out=str(output_path),
                dump_model_preds=None,
                opjson=str(op_path),
                optimize=False,
                nmos_lut=str(temp_path / "missing-nmos.csv"),
                pmos_lut=str(temp_path / "missing-pmos.csv"),
            )

            run_general_flow(args, verify=True)

            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["devices"]["m1"], {"W": 1.0, "L": 0.18})

    def test_sizing_uses_configured_lut_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            specs_path = temp_path / "specs.json"
            output_path = temp_path / "output.json"
            nmos_path = temp_path / "custom-nmos.csv"
            pmos_path = temp_path / "custom-pmos.csv"

            specs_path.write_text(
                json.dumps({"meta": {}, "devices": {}}),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                specs=str(specs_path),
                model=None,
                out=str(output_path),
                dump_model_preds=None,
                optimize=False,
                nmos_lut=str(nmos_path),
                pmos_lut=str(pmos_path),
            )

            with (
                patch("design_sizer.LUTLoader") as loader_class,
                patch.object(CircuitSizer, "size_topology", return_value={}),
            ):
                run_general_flow(args)

            loader_class.assert_called_once_with(str(nmos_path), str(pmos_path))


class DriverPreflightTests(unittest.TestCase):
    @unittest.skipUnless(
        os.name != "nt" and shutil.which("bash"), "requires a POSIX shell"
    )
    def test_invalid_lut_fails_before_existing_work_dir_is_deleted(self):
        script_path = Path(__file__).parents[1] / "llm_aided_modelling.sh"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            sentinel_path = temp_path / "5t_ota" / "keep.txt"
            nmos_path = temp_path / "valid NMOS LUT.csv"
            pmos_path = temp_path / "invalid PMOS LUT.csv"
            sentinel_path.parent.mkdir()
            sentinel_path.write_text("keep", encoding="utf-8")
            nmos_path.write_text(VALID_LUT, encoding="utf-8")
            pmos_path.write_text(
                "L,gmid,id,W\n1.8e-7,not-a-number,5e-6,1e-6\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["NMOS_LUT_FILE"] = str(nmos_path)
            env["PMOS_LUT_FILE"] = str(pmos_path)
            result = subprocess.run(
                ["bash", str(script_path)],
                cwd=temp_path,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("finite numeric values in columns: gmid", result.stderr)
            self.assertTrue(sentinel_path.exists())


if __name__ == "__main__":
    unittest.main()
