#!/usr/bin/env python3
"""
repair_model_py.py

Repairs either:
  1. The original generated JSON that produced a buggy Python model, or
  2. One generated Python model file in place.

Preferred loop mode:
    --model <file_model_py> --out-json <repair.json>

Full-schema preservation mode:
    --model <file_model_py> --source-json <llm_output.json> --out-json <repair.json>

In-place fallback mode:
    --model <file_model_py>

Everything else is temporary and deleted after the run.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


PYTHON_GENERATION_KEY = "4_PYTHON_GENERATION"
PYTHON_CODE_KEY = "code"


def read_error_text(args) -> str:
    if args.error_text:
        return args.error_text

    if args.error_file:
        return Path(args.error_file).read_text(encoding="utf-8", errors="replace")

    if not sys.stdin.isatty():
        return sys.stdin.read()

    return ""


def strip_code_fence(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines).strip()

    return text


def clean_json_text(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = strip_code_fence(text)

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


def extract_repaired_python(response_text: str) -> str:
    """
    Accepts either:
      1. JSON: {"repaired_python": "..."}
      2. Raw Python code
      3. Python code inside markdown fences
    """
    raw = response_text.strip()

    for candidate in [raw, clean_json_text(raw)]:
        try:
            obj = json.loads(candidate)
        except Exception:
            continue

        if isinstance(obj, dict):
            for key in [
                "repaired_python",
                "python_code",
                "code",
                "file_content",
                "content",
            ]:
                val = obj.get(key)
                if isinstance(val, str) and val.strip():
                    return strip_code_fence(val)

        if isinstance(obj, str) and obj.strip():
            return strip_code_fence(obj)

    match = re.search(
        r"```(?:python|py)?\s*(.*?)```",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    return raw


def validate_python(code: str, path: Path) -> None:
    if not code.strip():
        raise RuntimeError("Repaired code is empty.")

    try:
        compile(code, str(path), "exec")
    except SyntaxError as e:
        raise RuntimeError(
            f"Repaired code is not valid Python: line {e.lineno}: {e.msg}"
        ) from e


def extract_json_object(response_text: str):
    raw = response_text.strip()

    for candidate in [raw, clean_json_text(raw)]:
        try:
            obj = json.loads(candidate)
        except Exception:
            continue

        if isinstance(obj, dict) and "repaired_json" in obj:
            return obj["repaired_json"]

        return obj

    match = re.search(
        r"```(?:json)?\s*(.*?)```",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return json.loads(match.group(1).strip())

    raise RuntimeError("Codex response did not contain valid JSON.")


def get_embedded_python_code(obj, label: str) -> str:
    if not isinstance(obj, dict):
        raise RuntimeError(f"{label} JSON top level must be an object.")

    if PYTHON_GENERATION_KEY not in obj:
        raise RuntimeError(
            f"{label} JSON is missing key: {PYTHON_GENERATION_KEY!r}"
        )

    section = obj[PYTHON_GENERATION_KEY]
    if not isinstance(section, dict):
        raise RuntimeError(
            f"{label} JSON key {PYTHON_GENERATION_KEY!r} must contain an object."
        )

    if PYTHON_CODE_KEY not in section:
        raise RuntimeError(
            f"{label} JSON is missing key path: "
            f"[{PYTHON_GENERATION_KEY!r}][{PYTHON_CODE_KEY!r}]"
        )

    code = section[PYTHON_CODE_KEY]
    if not isinstance(code, str) or not code.strip():
        raise RuntimeError(
            f"{label} JSON key path "
            f"[{PYTHON_GENERATION_KEY!r}][{PYTHON_CODE_KEY!r}] "
            "must contain a non-empty string."
        )

    return code


def assert_same_schema_except_code(source_obj, repaired_obj, path: str = "$") -> None:
    if path == f"$['{PYTHON_GENERATION_KEY}']['{PYTHON_CODE_KEY}']":
        if not isinstance(repaired_obj, str):
            raise RuntimeError("Repaired embedded Python code must remain a string.")
        return

    if type(source_obj) is not type(repaired_obj):
        raise RuntimeError(
            f"JSON schema type changed at {path}: "
            f"{type(source_obj).__name__} -> {type(repaired_obj).__name__}"
        )

    if isinstance(source_obj, dict):
        source_keys = set(source_obj.keys())
        repaired_keys = set(repaired_obj.keys())
        if source_keys != repaired_keys:
            missing = sorted(source_keys - repaired_keys)
            extra = sorted(repaired_keys - source_keys)
            raise RuntimeError(
                f"JSON keys changed at {path}. Missing={missing}, extra={extra}"
            )

        for key in source_obj:
            assert_same_schema_except_code(
                source_obj[key],
                repaired_obj[key],
                f"{path}[{key!r}]",
            )
        return

    if isinstance(source_obj, list):
        if len(source_obj) != len(repaired_obj):
            raise RuntimeError(
                f"JSON list length changed at {path}: "
                f"{len(source_obj)} -> {len(repaired_obj)}"
            )

        for idx, (source_item, repaired_item) in enumerate(
            zip(source_obj, repaired_obj)
        ):
            assert_same_schema_except_code(
                source_item,
                repaired_item,
                f"{path}[{idx}]",
            )
        return

    if type(source_obj) is not type(repaired_obj):
        raise RuntimeError(
            f"JSON value type changed at {path}: "
            f"{type(source_obj).__name__} -> {type(repaired_obj).__name__}"
        )


def validate_repaired_json(repaired_obj, source_obj) -> None:
    get_embedded_python_code(source_obj, "Source")
    repaired_code = get_embedded_python_code(repaired_obj, "Repaired")
    assert_same_schema_except_code(source_obj, repaired_obj)
    validate_python(repaired_code, Path("<embedded_json_python_code>"))


def normalize_compiler_json(obj):
    try:
        get_embedded_python_code(obj, "Repaired")
        return obj
    except RuntimeError:
        pass

    if isinstance(obj, dict):
        for key in ["repaired_python", "python_code", "code", "file_content", "content"]:
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                return {PYTHON_GENERATION_KEY: {PYTHON_CODE_KEY: strip_code_fence(val)}}

    if isinstance(obj, str) and obj.strip():
        return {PYTHON_GENERATION_KEY: {PYTHON_CODE_KEY: strip_code_fence(obj)}}

    raise RuntimeError(
        "Repaired JSON must contain key path "
        f"[{PYTHON_GENERATION_KEY!r}][{PYTHON_CODE_KEY!r}]."
    )


def build_compiler_json_repair_prompt(
    model_path: Path,
    model_text: str,
    error_text: str,
) -> str:
    return f"""You are repairing ONE generated Python model file used by design_sizer.py in an OTA equation-evaluation flow.

Goal:
Fix the Python runtime/syntax error reported below with the smallest possible edit.

Important downstream compiler contract:
The next script will read your JSON output using exactly this path:
data["4_PYTHON_GENERATION"]["code"]

Hard constraints:
- Return a valid JSON object with the key path ["4_PYTHON_GENERATION"]["code"].
- Put the COMPLETE corrected Python file as the string value at ["4_PYTHON_GENERATION"]["code"].
- Modify ONLY the Python code required to fix the reported error.
- Preserve all existing public interfaces, especially class names, function names, method signatures, metric names, return keys, and input argument names.
- Do NOT rewrite the model.
- Do NOT refactor the file.
- Do NOT rename variables globally.
- Do NOT change equations unrelated to the reported error.
- Do NOT change unrelated functionality.
- Do NOT add external dependencies.
- Do NOT invent new files or change any file paths.
- The corrected embedded Python must be syntactically valid Python.

Output format:
Return exactly one valid JSON object and nothing else:
{{"4_PYTHON_GENERATION": {{"code": "<complete corrected Python file as a string>"}}}}

Buggy Python model path:
{model_path}

Error from design_sizer.py:
```text
{error_text}
```

Current buggy Python file:
```python
{model_text}
```
"""


def build_json_repair_prompt(
    model_path: Path,
    model_text: str,
    source_json_path: Path,
    source_json_text: str,
    error_text: str,
) -> str:
    return f"""You are repairing ONE generated JSON equation file used by compile_ota_model_script.py to generate a Python model for design_sizer.py.

Goal:
Fix the embedded Python code in the generated equation JSON so that, after it is compiled again, the generated Python model no longer produces the runtime/syntax error reported below.

Important compiler contract:
The downstream compiler reads exactly this JSON path:
data["4_PYTHON_GENERATION"]["code"]

Hard constraints:
- Preserve the EXACT JSON schema of the current JSON file.
- Preserve all existing top-level keys.
- Preserve the key path ["4_PYTHON_GENERATION"]["code"].
- Modify ONLY the string value at ["4_PYTHON_GENERATION"]["code"] unless the reported error absolutely proves another existing value must change.
- Preserve all public model interfaces implied by the JSON: class names, function names, method names, metric names, return keys, and input argument names.
- Modify ONLY the JSON fields required to fix the reported error.
- Do NOT rewrite unrelated equations.
- Do NOT refactor the JSON structure.
- Do NOT add external dependencies.
- Do NOT invent new files or change file paths.
- Return the COMPLETE corrected JSON file, not a diff.
- The corrected output must be valid JSON.

Output format:
Return exactly the corrected JSON object itself and nothing else.
Do NOT wrap it inside another object.
Do NOT return markdown fences.
The corrected Python must be embedded as a JSON string at ["4_PYTHON_GENERATION"]["code"].

Source JSON path:
{source_json_path}

Generated buggy Python model path:
{model_path}

Error from design_sizer.py:
```text
{error_text}
```

Current source JSON file:
```json
{source_json_text}
```

Generated buggy Python model:
```python
{model_text}
```
"""


def build_repair_prompt(model_path: Path, model_text: str, error_text: str) -> str:
    return f"""You are repairing ONE generated Python model file used by design_sizer.py in an OTA equation-evaluation flow.

Goal:
Fix the Python runtime/syntax error reported below with the smallest possible edit.

Hard constraints:
- Modify ONLY the Python code required to fix the reported error.
- Preserve all existing public interfaces, especially class names, function names, method signatures, metric names, return keys, and input argument names.
- Do NOT rewrite the model.
- Do NOT refactor the file.
- Do NOT rename variables globally.
- Do NOT change equations unrelated to the reported error.
- Do NOT change unrelated functionality.
- Do NOT add external dependencies.
- Do NOT invent new files or change any file paths.
- Return the COMPLETE corrected Python file, not a diff.
- The corrected file must be syntactically valid Python.

Output format:
Return exactly one valid JSON object and nothing else:
{{"repaired_python": "<complete corrected Python file as a string>"}}

Buggy file path:
{model_path}

Error from design_sizer.py:
```text
{error_text}
```

Current buggy Python file:
```python
{model_text}
```
"""


def run_call_codex(args, prompt_path: Path, response_path: Path) -> None:
    base_cmd = [
        sys.executable,
        args.call_codex,
        "-p",
        str(prompt_path),
        "-o",
        str(response_path),
    ]

    for image_path in args.images:
        base_cmd.extend(["-i", image_path])

    if args.llm_model:
        base_cmd.extend(["-m", args.llm_model])

    cmd = list(base_cmd)

    if args.reasoning:
        cmd.extend(["-r", args.reasoning])

    print(">> Running repair Codex call:")
    print(" ".join(shlex.quote(part) for part in cmd))

    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Some older call_codex.py versions may not support -r.
    if proc.returncode != 0 and args.reasoning:
        lower_out = proc.stdout.lower()
        if "unrecognized arguments" in lower_out and "-r" in lower_out:
            print(">> call_codex.py does not support -r. Retrying without reasoning flag.")
            proc = subprocess.run(
                base_cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

    if proc.stdout.strip():
        print(proc.stdout)

    if proc.returncode != 0:
        raise RuntimeError(f"call_codex.py failed with exit code {proc.returncode}")

    if not response_path.exists():
        raise RuntimeError(f"Codex output file was not created: {response_path}")


def overwrite_in_place(path: Path, code: str) -> None:
    code = code.rstrip() + "\n"
    tmp_path = path.with_name(f".{path.name}.repair_tmp")

    try:
        tmp_path.write_text(code, encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.repair_tmp")

    try:
        tmp_path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair generated equation JSON or Python model using call_codex.py."
    )

    parser.add_argument(
        "--model",
        required=True,
        help="Path to buggy file_model_py to repair in place.",
    )
    parser.add_argument(
        "--error-text",
        default="",
        help="Error text captured from the failed command.",
    )
    parser.add_argument(
        "--error-file",
        default="",
        help="Optional file containing error text.",
    )
    parser.add_argument(
        "--source-json",
        default="",
        help="Optional original generated JSON file to repair while preserving its full schema.",
    )
    parser.add_argument(
        "--out-json",
        default="",
        help="Output repaired JSON path expected by compile_ota_model_script.py.",
    )
    parser.add_argument(
        "--call-codex",
        default="call_codex.py",
        help="Path to call_codex.py.",
    )
    parser.add_argument(
        "-i",
        "--image",
        "--images",
        dest="images",
        action="append",
        default=[],
        help="Optional image path passed through to call_codex.py with -i.",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-5.5",
        help="Model name passed to call_codex.py with -m.",
    )
    parser.add_argument(
        "--reasoning",
        default="high",
        help="Reasoning level passed to call_codex.py with -r.",
    )

    args = parser.parse_args()

    model_path = Path(args.model).resolve()

    if not model_path.exists():
        print(f"[ERROR] Model file does not exist: {model_path}", file=sys.stderr)
        return 1

    model_text = model_path.read_text(encoding="utf-8", errors="replace")
    error_text = read_error_text(args).strip()

    if not error_text:
        print("[ERROR] No error text provided.", file=sys.stderr)
        return 1

    source_json_path = Path(args.source_json).resolve() if args.source_json else None
    out_json_path = Path(args.out_json).resolve() if args.out_json else None

    if source_json_path and not source_json_path.exists():
        print(f"[ERROR] Source JSON does not exist: {source_json_path}", file=sys.stderr)
        return 1

    json_repair_mode = bool(out_json_path)
    source_json_obj = None

    if json_repair_mode and source_json_path:
        source_json_text = source_json_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        try:
            source_json_obj = json.loads(source_json_text)
        except Exception as e:
            print(f"[ERROR] Source JSON is not valid JSON: {e}", file=sys.stderr)
            return 1

        prompt_text = build_json_repair_prompt(
            model_path=model_path,
            model_text=model_text,
            source_json_path=source_json_path,
            source_json_text=source_json_text,
            error_text=error_text,
        )
    elif json_repair_mode:
        prompt_text = build_compiler_json_repair_prompt(
            model_path=model_path,
            model_text=model_text,
            error_text=error_text,
        )
    else:
        prompt_text = build_repair_prompt(model_path, model_text, error_text)

    with tempfile.TemporaryDirectory(prefix="model_py_repair_") as td:
        td_path = Path(td)
        prompt_path = td_path / "repair_prompt.txt"
        response_path = td_path / "repair_response.txt"

        prompt_path.write_text(prompt_text, encoding="utf-8")

        try:
            run_call_codex(args, prompt_path, response_path)
            response_text = response_path.read_text(encoding="utf-8", errors="replace")

            if json_repair_mode:
                repaired_json_obj = normalize_compiler_json(
                    extract_json_object(response_text)
                )
                if source_json_obj is not None:
                    validate_repaired_json(repaired_json_obj, source_json_obj)
                else:
                    repaired_code = get_embedded_python_code(
                        repaired_json_obj,
                        "Repaired",
                    )
                    validate_python(repaired_code, Path("<embedded_json_python_code>"))
                write_json(out_json_path, repaired_json_obj)
            else:
                repaired_code = extract_repaired_python(response_text)
                validate_python(repaired_code, model_path)
                overwrite_in_place(model_path, repaired_code)

        except Exception as e:
            print(f"[ERROR] Automatic repair failed: {e}", file=sys.stderr)
            return 1

    if json_repair_mode:
        print(f"[OK] Repaired JSON written: {out_json_path}")
    else:
        print(f"[OK] Repaired and overwritten: {model_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

