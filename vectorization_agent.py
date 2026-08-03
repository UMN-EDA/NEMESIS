#!/usr/bin/env python3
"""
LLM-agent driver for scalar-to-vectorized evaluator conversion.

This script DOES NOT hardcode any circuit equations.

It:
  1. Reads an existing sequential/scalar Python evaluator.
  2. Reads an example .op JSON file.
  3. Builds a prompt asking an external LLM agent to generate one self-contained
     Python checker script containing:
       - the scalar reference behavior
       - the new vectorized evaluator
       - scalar-vs-vectorized comparison logic
  4. Runs the generated checker.
  5. If it fails, sends stdout/stderr back to the LLM agent and asks for a fix.
  6. Repeats until the generated checker passes or --max_iters is reached.

Supported external LLM agent contracts:
  1. stdin/stdout mode:
      - Provide --agent_cmd.
      - The full prompt is passed on stdin.
      - The command prints the Python file on stdout.

  2. prompt-file/output-json mode:
      - Provide --agent_cmd_template.
      - The driver writes the prompt to --prompt_file.
      - The command template may use:
          {prompt_file}, {model}, {reasoning}, {output_json}
      - The agent writes JSON to --agent_output_json.
      - The Python file is extracted from --agent_response_key or common fields.

  3. call_codex.py mode:
      - Provide --call_codex call_codex.py.
      - The driver invokes:
          python3 call_codex.py -p PROMPT -o OUTPUT_JSON -m MODEL -r REASONING [-i IMAGE...]

Example:
  python3 vectorized_evaluator_check.py \
    --scalar_evaluator Example_evaluator.py \
    --op_json testbenches/spice_run/op_results.json \
    --agent_cmd "python3 my_llm_agent.py" \
    --generated_script generated_vectorized_evaluator_check.py

  python3 vectorized_evaluator_check.py \
    --scalar_evaluator Example_evaluator.py \
    --op_json testbenches/spice_run/op_results.json \
    --agent_cmd_template 'bash run_llm_agent.sh {prompt_file} {model} {reasoning} {output_json}' \
    --model gpt-5 \
    --reasoning high \
    --prompt_file vectorize_prompt.txt \
    --agent_output_json vectorize_agent_output.json

  python3 vectorized_evaluator_check.py \
    --scalar_evaluator Example_evaluator.py \
    --op_json testbenches/spice_run/op_results.json \
    --call_codex call_codex.py \
    --model gpt-5.5 \
    --reasoning high \
    --agent_output_json vectorize_agent_output.json

Shape contract the generated script must implement:
  - pymoo X: np.ndarray, shape (N, D)
      N = number of particles/candidate designs
      D = number of optimization variables
  - device_params scalar:
      dict[device_name][param_name] -> scalar float
  - device_params_batch:
      dict[device_name][param_name] -> np.ndarray shape (N,)
  - candidates_batch:
      dict[param_name] -> np.ndarray shape (N,)
  - metrics_batch:
      dict[metric_name] -> np.ndarray shape (N,)
  - pymoo single-objective output:
      costs shape (N,)
      out["F"] shape (N, 1)
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List


BASE_PROMPT = r"""
You are converting an existing scalar circuit performance evaluator into a
vectorized batch evaluator.

You will be given:
1. The existing scalar evaluator Python source.
2. One example .op JSON file.
3. Optional candidate JSON.

Your task:
Create ONE complete self-contained Python script. Do not create multiple files.
Do not hardcode circuit-specific equations unless they are copied/translated
from the provided scalar evaluator. The scalar evaluator is the source of truth.

The generated script must:
1. Implement a standalone vectorized evaluator that computes the same metrics
   over a batch.
2. Load the provided .op JSON.
3. Normalize the OP JSON into scalar device_params.
4. Convert that scalar OP data into a batch of size 1.
5. For verification only, dynamically load the scalar evaluator from the
   --scalar_evaluator path and run it as the external reference oracle.
6. Run the standalone vectorized evaluator.
7. Compare every metric with rtol=1e-9 and atol=1e-12.
8. Print a PASS/FAIL table for all metrics.
9. Exit with code 0 only if all metrics match.

Very important:
  - The generated VectorizedPerformanceModel must NOT import from the scalar
    evaluator.
  - The generated VectorizedPerformanceModel must NOT call the scalar
    PerformanceModel.
  - The scalar evaluator may be imported only in the generated script's test
    harness for comparison/reference.
  - The vectorized evaluator logic must be an actual NumPy vectorized
    translation of the scalar equations.
  - Do not implement compute_batch by looping over particles and calling the
    scalar evaluator.

Required generated-script CLI:
  python3 GENERATED_SCRIPT.py \
    --op_json OP_JSON \
    --scalar_evaluator SCALAR_EVALUATOR \
    [--candidate_json CANDIDATE_JSON] \
    [--C_load FLOAT] [--Vdd FLOAT] [--Vss FLOAT]

Required vectorized API inside generated script:

class VectorizedPerformanceModel:
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

Mandatory nomenclature:
  - The vectorized model class name must be exactly
    VectorizedPerformanceModel.
  - The vectorized batch method name must be exactly compute_batch.
  - The first batch input argument name must be exactly device_params_batch.
  - The optional candidate batch argument name must be exactly candidates_batch.
  - The generated script must not expose the vectorized evaluator only as
    PerformanceModel, Model, evaluate_batch, a module-level compute_batch, or
    any other alternate API.
  - A downstream comparison command must be able to import the generated file
    and call:
        VectorizedPerformanceModel().compute_batch(
            device_params_batch=...,
            candidates_batch=None,
            C_load=...,
            Vdd=...,
            Vss=...,
        )

Shape contract:
  - pymoo X has shape (N, D)
  - N is number of particles/candidate designs in one generation
  - D is number of optimization variables
  - device_params_batch["m0"]["gm"] has shape (N,)
  - candidates_batch["IBIAS"] has shape (N,)
  - metrics_batch["DC_Gain_dB"] has shape (N,)
  - for pymoo single-objective minimization:
      costs has shape (N,)
      out["F"] must have shape (N, 1)

Important conversion rules:
  - Preserve metric names exactly.
  - Preserve units exactly.
  - Preserve fallback values exactly.
  - Preserve all numerical guards exactly:
      max(x, eps) -> np.maximum(x, eps)
      abs(x) -> np.abs(x)
      min(a, b) -> np.minimum(a, b)
      scalar conditionals -> np.where(...)
  - Do not change formulas to "improve" them.
  - If the scalar evaluator prints debug lines, the generated checker may ignore
    prints but must compare returned metric dictionaries.
  - If one metric mismatches, print scalar value, vectorized value, abs error,
    and relative error.
  - The generated file should be directly runnable.
  - The generated vectorized model should be reusable by optimizers without the
    scalar evaluator present. Only the test harness may need --scalar_evaluator.

Return ONLY the complete Python script content. No explanation.
"""


REFINE_PROMPT = r"""
The generated script failed. Revise the complete Python script so that scalar
and vectorized metrics match exactly within rtol=1e-9 and atol=1e-12.

Do not change the scalar reference behavior.
Do not hardcode the final metric values from this one OP file.
Fix the vectorized translation or normalization logic.
The VectorizedPerformanceModel must remain standalone and must not import or
call the scalar evaluator. Use the scalar evaluator only in the test harness as
the oracle for comparison.
Keep the vectorized API exactly:
    class VectorizedPerformanceModel
    compute_batch(self, device_params_batch, candidates_batch=None, C_load=1e-12, Vdd=1.0, Vss=0.0)
Do not rename the class, method, or argument names while refining.

Return ONLY the complete corrected Python script content. No explanation.
"""


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def extract_python(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip() + "\n"
    return text.strip() + "\n"


def get_nested(data, dotted_key: str):
    cur = data
    for key in dotted_key.split("."):
        if isinstance(cur, list) and key.isdigit():
            idx = int(key)
            cur = cur[idx] if idx < len(cur) else None
        elif isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur


def extract_text_from_agent_json(path: str, response_key: str = None) -> str:
    data = json.loads(read_text(path))

    if response_key:
        value = get_nested(data, response_key)
        if value is None:
            raise KeyError(f"Response key '{response_key}' not found in {path}")
        return value if isinstance(value, str) else json.dumps(value, indent=2)

    candidate_keys = [
        "python",
        "code",
        "script",
        "content",
        "response",
        "text",
        "output",
        "message.content",
        "choices.0.message.content",
    ]
    for key in candidate_keys:
        value = get_nested(data, key)
        if isinstance(value, str) and value.strip():
            return value

    raise KeyError(
        "Could not find generated Python text in agent JSON. "
        "Pass --agent_response_key with the JSON field path."
    )


def run_agent(agent_cmd: str, prompt: str, timeout_sec: int) -> str:
    cmd = shlex.split(agent_cmd)
    completed = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "LLM agent command failed\n"
            f"command: {agent_cmd}\n"
            f"returncode: {completed.returncode}\n"
            f"stdout:\n{completed.stdout[-4000:]}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )
    return completed.stdout


def run_agent_template(
    agent_cmd_template: str,
    prompt: str,
    prompt_file: str,
    model: str,
    reasoning: str,
    output_json: str,
    response_key: str,
    timeout_sec: int,
) -> str:
    Path(prompt_file).parent.mkdir(parents=True, exist_ok=True)
    Path(prompt_file).write_text(prompt, encoding="utf-8")
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)

    command = agent_cmd_template.format(
        prompt_file=prompt_file,
        model=model,
        reasoning=reasoning,
        output_json=output_json,
    )
    cmd = shlex.split(command)
    completed = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "LLM agent template command failed\n"
            f"command: {command}\n"
            f"returncode: {completed.returncode}\n"
            f"stdout:\n{completed.stdout[-4000:]}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )
    if not os.path.exists(output_json):
        raise FileNotFoundError(f"LLM agent did not create output JSON: {output_json}")
    return extract_text_from_agent_json(output_json, response_key=response_key)


def run_call_codex_agent(
    call_codex: str,
    prompt: str,
    prompt_file: str,
    model: str,
    reasoning: str,
    output_json: str,
    images: List[str],
    response_key: str,
    timeout_sec: int,
) -> str:
    Path(prompt_file).parent.mkdir(parents=True, exist_ok=True)
    Path(prompt_file).write_text(prompt, encoding="utf-8")
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable if call_codex.endswith(".py") else call_codex,
    ]
    if call_codex.endswith(".py"):
        cmd.append(call_codex)
    cmd.extend(["-p", prompt_file, "-o", output_json, "-m", model, "-r", reasoning])
    for image in images:
        if image:
            cmd.extend(["-i", image])

    completed = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "call_codex command failed\n"
            f"command: {' '.join(shlex.quote(x) for x in cmd)}\n"
            f"returncode: {completed.returncode}\n"
            f"stdout:\n{completed.stdout[-4000:]}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )
    if not os.path.exists(output_json):
        raise FileNotFoundError(f"call_codex did not create output JSON: {output_json}")
    return extract_text_from_agent_json(output_json, response_key=response_key)


def run_generated_script(
    generated_script: str,
    scalar_evaluator: str,
    op_json: str,
    candidate_json: str,
    c_load: float,
    vdd: float,
    vss: float,
    timeout_sec: int,
) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        generated_script,
        "--op_json",
        op_json,
        "--scalar_evaluator",
        scalar_evaluator,
        "--C_load",
        str(c_load),
        "--Vdd",
        str(vdd),
        "--Vss",
        str(vss),
    ]
    if candidate_json:
        cmd.extend(["--candidate_json", candidate_json])

    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


def build_initial_prompt(args: argparse.Namespace) -> str:
    scalar_source = read_text(args.scalar_evaluator)
    op_json_text = read_text(args.op_json)
    candidate_text = read_text(args.candidate_json) if args.candidate_json else ""

    return (
        BASE_PROMPT
        + "\n\n"
        + "SCALAR_EVALUATOR_PATH:\n"
        + os.path.abspath(args.scalar_evaluator)
        + "\n\n"
        + "SCALAR_EVALUATOR_SOURCE:\n"
        + "```python\n"
        + scalar_source
        + "\n```\n\n"
        + "EXAMPLE_OP_JSON_PATH:\n"
        + os.path.abspath(args.op_json)
        + "\n\n"
        + "EXAMPLE_OP_JSON_CONTENT:\n"
        + "```json\n"
        + op_json_text
        + "\n```\n\n"
        + "OPTIONAL_CANDIDATE_JSON_CONTENT:\n"
        + "```json\n"
        + candidate_text
        + "\n```\n\n"
        + f"TESTBENCH_DEFAULTS: C_load={args.C_load}, Vdd={args.Vdd}, Vss={args.Vss}\n"
    )


def build_refine_prompt(previous_prompt: str, generated_code: str, result: subprocess.CompletedProcess) -> str:
    return (
        previous_prompt
        + "\n\n"
        + REFINE_PROMPT
        + "\n\n"
        + "FAILED_GENERATED_SCRIPT:\n"
        + "```python\n"
        + generated_code
        + "\n```\n\n"
        + "FAILED_RUN_STDOUT:\n"
        + "```text\n"
        + result.stdout[-12000:]
        + "\n```\n\n"
        + "FAILED_RUN_STDERR:\n"
        + "```text\n"
        + result.stderr[-12000:]
        + "\n```\n\n"
        + f"FAILED_RUN_RETURNCODE: {result.returncode}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke an LLM agent to generate and refine a vectorized evaluator checker")
    parser.add_argument("--scalar_evaluator", required=True, help="Existing sequential evaluator Python file")
    parser.add_argument("--op_json", required=True, help="Example .op JSON file")
    parser.add_argument("--candidate_json", default=None, help="Optional expanded candidate JSON")
    parser.add_argument("--agent_cmd", default=None, help="stdin/stdout mode: prompt is sent on stdin; Python code is read from stdout.")
    parser.add_argument(
        "--agent_cmd_template",
        default=None,
        help="file/JSON mode command template. Placeholders: {prompt_file}, {model}, {reasoning}, {output_json}",
    )
    parser.add_argument("--call_codex", default=None, help="Path to call_codex.py. Uses: python3 call_codex.py -p PROMPT -o JSON -m MODEL -r REASONING [-i IMAGE...]")
    parser.add_argument("--prompt_file", default="vectorize_evaluator_prompt.txt")
    parser.add_argument("--agent_output_json", default="vectorize_evaluator_agent_output.json")
    parser.add_argument("--agent_response_key", default=None, help="Dotted JSON key containing generated script, e.g. response or choices.0.message.content")
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--reasoning", default="high")
    parser.add_argument("--images", nargs="*", default=[], help="Optional image path(s), passed to call_codex with -i")
    parser.add_argument("--generated_script", default="generated_vectorized_evaluator_check.py")
    parser.add_argument("--max_iters", type=int, default=5)
    parser.add_argument("--agent_timeout_sec", type=int, default=300)
    parser.add_argument("--run_timeout_sec", type=int, default=60)
    parser.add_argument("--C_load", type=float, default=1e-12)
    parser.add_argument("--Vdd", type=float, default=1.0)
    parser.add_argument("--Vss", type=float, default=0.0)
    args = parser.parse_args()

    modes = [bool(args.agent_cmd), bool(args.agent_cmd_template), bool(args.call_codex)]
    if sum(modes) != 1:
        raise SystemExit("Provide exactly one of --agent_cmd, --agent_cmd_template, or --call_codex")

    prompt = build_initial_prompt(args)
    generated_code = ""

    for iteration in range(1, args.max_iters + 1):
        print(f"[driver] invoking LLM agent, iteration {iteration}/{args.max_iters}", flush=True)
        prompt_path = args.prompt_file
        output_json = args.agent_output_json
        if iteration > 1:
            prompt_base = Path(args.prompt_file)
            prompt_suffix = prompt_base.suffix or ".txt"
            prompt_path = str(prompt_base.with_name(f"{prompt_base.stem}_iter{iteration:02d}{prompt_suffix}"))
            output_base = Path(args.agent_output_json)
            output_suffix = output_base.suffix or ".json"
            output_json = str(output_base.with_name(f"{output_base.stem}_iter{iteration:02d}{output_suffix}"))

        if args.call_codex:
            agent_output = run_call_codex_agent(
                call_codex=args.call_codex,
                prompt=prompt,
                prompt_file=prompt_path,
                model=args.model,
                reasoning=args.reasoning,
                output_json=output_json,
                images=args.images,
                response_key=args.agent_response_key,
                timeout_sec=args.agent_timeout_sec,
            )
        elif args.agent_cmd_template:
            agent_output = run_agent_template(
                agent_cmd_template=args.agent_cmd_template,
                prompt=prompt,
                prompt_file=prompt_path,
                model=args.model,
                reasoning=args.reasoning,
                output_json=output_json,
                response_key=args.agent_response_key,
                timeout_sec=args.agent_timeout_sec,
            )
        else:
            agent_output = run_agent(args.agent_cmd, prompt, args.agent_timeout_sec)
        generated_code = extract_python(agent_output)
        Path(args.generated_script).write_text(generated_code, encoding="utf-8")

        print(f"[driver] wrote {args.generated_script}", flush=True)
        result = run_generated_script(
            generated_script=args.generated_script,
            scalar_evaluator=args.scalar_evaluator,
            op_json=args.op_json,
            candidate_json=args.candidate_json,
            c_load=args.C_load,
            vdd=args.Vdd,
            vss=args.Vss,
            timeout_sec=args.run_timeout_sec,
        )

        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        if result.returncode == 0:
            print(f"[driver] PASS: generated script matched scalar evaluator on iteration {iteration}", flush=True)
            return

        print(f"[driver] FAIL: generated script returned {result.returncode}", flush=True)
        prompt = build_refine_prompt(prompt, generated_code, result)

    raise SystemExit(f"[driver] failed after {args.max_iters} iteration(s); last script: {args.generated_script}")


if __name__ == "__main__":
    main()

