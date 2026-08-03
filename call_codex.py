#!/usr/bin/env python3
import os
import json
import argparse
import subprocess
import tempfile
from pathlib import Path

# ==============================================================================
# DEFAULTS
# ==============================================================================

# MODEL OPTIONS:
# Leave DEFAULT_MODEL = None to use whatever model Codex CLI is already configured to use.
#
# You can override from command line using:
#   -m gpt-5.5
#   -m gpt-5.2
#   -m gpt-5
#
# Example:
#   python call_codex.py -p prompt.txt -i image.png -o result.json -m gpt-5.5
#
# NOTE:
# Actual model availability depends on the account you are logged into with Codex CLI.
DEFAULT_MODEL = None

# REASONING OPTIONS:
# Codex supports the following reasoning effort values:
#   minimal
#   low
#   medium
#   high
#   xhigh
#
# Recommended for your equation-generation / circuit-analysis task:
#   high
#
# Example:
#   python call_codex.py -p prompt.txt -i image.png -o result.json -m gpt-5.5 -r high
#
# Leave DEFAULT_REASONING = None to use Codex CLI default.
DEFAULT_REASONING = None

DEFAULT_OUTPUT = "codex_output.json"
DEFAULT_CODEX_BIN = "codex"


class CodexCLIProcessor:
    def __init__(
        self,
        model_id=None,
        reasoning_effort=None,
        codex_bin=DEFAULT_CODEX_BIN,
        workspace=None,
        sandbox="workspace-write",
        approval="never",
        output_schema=None,
        timeout=None,
    ):
        self.model_id = model_id
        self.reasoning_effort = reasoning_effort
        self.codex_bin = codex_bin
        self.workspace = os.path.abspath(workspace or os.getcwd())
        self.sandbox = sandbox
        self.approval = approval
        self.output_schema = output_schema
        self.timeout = timeout
        self.static_prompt = ""

    def load_prompt_files(self, file_paths: list):
        """Reads multiple prompt files, combining static and dynamic sections."""
        combined_static = []
        combined_dynamic = []
        marker = "\n### DYNAMIC SECTION ###\n"

        for file_path in file_paths:
            if not os.path.exists(file_path):
                print(f"Warning: Prompt file '{file_path}' not found. Skipping.")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    full_text = f.read()
            except Exception as e:
                print(f"Error reading prompt file {file_path}: {e}")
                continue

            if marker in full_text:
                static_part, dynamic_part = full_text.split(marker, 1)
                if static_part.strip():
                    combined_static.append(static_part.strip())
                if dynamic_part.strip():
                    combined_dynamic.append(dynamic_part.strip())
            else:
                if full_text.strip():
                    combined_static.append(full_text.strip())

        self.static_prompt = "\n\n".join(combined_static)
        return "\n\n".join(combined_dynamic)

    def _clean_json_string(self, text: str) -> str:
        """Removes Markdown code blocks to assist JSON parsing."""
        if not text:
            return ""

        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    def _build_full_prompt(self, pdf_paths: list, dynamic_prompt: str) -> str:
        """Build one complete prompt for `codex exec -`."""
        json_guardrail = (
            "IMPORTANT: Output strictly as ONE valid JSON object. "
            "No markdown. No extra text."
        )

        sections = []

        if self.static_prompt.strip():
            sections.append("### STATIC INSTRUCTIONS ###\n" + self.static_prompt.strip())

        sections.append("### OUTPUT FORMAT REQUIREMENT ###\n" + json_guardrail)

        if dynamic_prompt.strip():
            sections.append("### DYNAMIC INSTRUCTIONS ###\n" + dynamic_prompt.strip())

        if pdf_paths:
            abs_pdfs = [os.path.abspath(p) for p in pdf_paths]
            pdf_text = "\n".join(f"- {p}" for p in abs_pdfs)
            sections.append(
                "### LOCAL PDF INPUT FILES ###\n"
                "The following PDF files are available locally. "
                "Inspect/read them from the filesystem as needed. "
                "Do not invent content that is not present in these files.\n"
                f"{pdf_text}"
            )

        return "\n\n".join(sections).strip() + "\n"

    def generate_response(
        self,
        pdf_paths: list,
        image_paths: list,
        prompt_text: str,
        output_base_name: str,
    ):
        """
        Runs Codex CLI non-interactively.

        Images are attached with --image.
        PDFs are not uploaded; they are passed as local file paths in the prompt.
        """
        full_prompt = self._build_full_prompt(pdf_paths, prompt_text)

        image_paths = [os.path.abspath(p) for p in (image_paths or [])]

        final_msg_tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".codex.final.txt",
            delete=False,
            encoding="utf-8",
        )
        final_msg_path = final_msg_tmp.name
        final_msg_tmp.close()

        cmd = [
            self.codex_bin,
            "exec",
            "--cd",
            self.workspace,
            "--sandbox",
            self.sandbox,

            # Do not touch ~/.codex/config.toml.
            # This passes approval policy only for this run.
            "-c",
            f'approval_policy="{self.approval}"',

            "--skip-git-repo-check",
            "--color",
            "never",
            "--output-last-message",
            final_msg_path,
        ]

        # Model override for this run.
        # Example:
        #   --model gpt-5.5
        #   --model gpt-5.2
        #   --model gpt-5
        if self.model_id:
            cmd.extend(["--model", self.model_id])

        # Reasoning effort override for this run.
        # Valid options:
        #   minimal, low, medium, high, xhigh
        #
        # For your analog equation generation, use:
        #   --reasoning high
        if self.reasoning_effort:
            cmd.extend(["-c", f'model_reasoning_effort="{self.reasoning_effort}"'])

        if self.output_schema:
            cmd.extend(["--output-schema", os.path.abspath(self.output_schema)])

        for img in image_paths:
            cmd.extend(["--image", img])

        # "-" means Codex reads the prompt from stdin.
        cmd.append("-")

        print("\nRunning Codex CLI:")
        print(" ".join(cmd[:-1]) + " -")
        print(f"Workspace: {self.workspace}")

        try:
            completed = subprocess.run(
                cmd,
                input=full_prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workspace,
                timeout=self.timeout,
            )
        except FileNotFoundError:
            print(f"Error: Could not find '{self.codex_bin}'. Is Codex CLI in PATH?")
            return None
        except subprocess.TimeoutExpired:
            print("Error: Codex CLI run timed out.")
            return None

        if completed.stdout.strip():
            print("\n[CODEX STDOUT]")
            print(completed.stdout)

        if completed.stderr.strip():
            print("\n[CODEX STDERR]")
            print(completed.stderr)

        if completed.returncode != 0:
            print(f"\nError: Codex CLI exited with code {completed.returncode}.")
            return None

        try:
            raw_text = Path(final_msg_path).read_text(encoding="utf-8")
        except Exception:
            raw_text = completed.stdout

        if not raw_text.strip():
            print("\nError: Codex produced no final message.")
            return None

        cleaned_text = self._clean_json_string(raw_text)

        try:
            json_data = json.loads(cleaned_text)
            self._save_json(json_data, output_base_name)
            return json_data
        except json.JSONDecodeError:
            print("\nWarning: Codex output could not be parsed as JSON.")
            self._save_text(raw_text, output_base_name)
            return None
        finally:
            try:
                os.remove(final_msg_path)
            except OSError:
                pass

    def _save_json(self, data: dict, filename: str):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n[SUCCESS] Output saved to JSON: {filename}")
        except Exception as e:
            print(f"Error saving JSON file: {e}")

    def _save_text(self, text: str, filename: str):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"\n[FALLBACK] Raw output saved to TXT: {filename}")
        except Exception as e:
            print(f"Error saving TXT file: {e}")


def scan_paths(paths, allowed_extensions):
    """Scans the provided paths."""
    collected_files = []

    if not paths:
        return collected_files

    for path in paths:
        if os.path.isdir(path):
            print(f"Scanning directory: {path} ...")
            for root, dirs, files in os.walk(path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in allowed_extensions):
                        collected_files.append(os.path.join(root, file))

        elif os.path.isfile(path):
            if any(path.lower().endswith(ext) for ext in allowed_extensions):
                collected_files.append(path)

        else:
            print(f"Warning: '{path}' is not a valid file or directory.")

    return sorted(list(set(collected_files)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Codex CLI runner: process prompt files plus local PDFs/images "
            "without using the OpenAI API directly."
        )
    )

    parser.add_argument(
        "--prompt",
        "-p",
        nargs="+",
        required=True,
        help="Path(s) to prompt text file(s).",
    )

    parser.add_argument(
        "--pdfs",
        nargs="*",
        help="Directory containing PDFs, or list of PDF files.",
    )

    parser.add_argument(
        "--images",
        "-i",
        nargs="*",
        help="Directory containing images, or list of image files.",
    )

    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output filename (default: {DEFAULT_OUTPUT})",
    )

    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_MODEL,
        help=(
            "Codex model override for this run. "
            "Examples: gpt-5.5, gpt-5.2, gpt-5. "
            "Omit to use Codex CLI default."
        ),
    )

    parser.add_argument(
        "--reasoning",
        "-r",
        default=DEFAULT_REASONING,
        choices=["minimal", "low", "medium", "high", "xhigh"],
        help=(
            "Codex reasoning effort for this run. "
            "Options: minimal, low, medium, high, xhigh. "
            "Recommended for equation generation: high."
        ),
    )

    parser.add_argument(
        "--codex_bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex executable name/path.",
    )

    parser.add_argument(
        "--workspace",
        default=os.getcwd(),
        help="Workspace root for Codex to run in.",
    )

    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Codex sandbox mode.",
    )

    parser.add_argument(
        "--approval",
        default="on-request",
        choices=["untrusted", "on-request", "never"],
        help="Codex approval mode.",
    )

    parser.add_argument(
        "--schema",
        default=None,
        help="Optional JSON schema file for Codex --output-schema.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Optional timeout in seconds.",
    )

    args = parser.parse_args()

    processor = CodexCLIProcessor(
        model_id=args.model,
        reasoning_effort=args.reasoning,
        codex_bin=args.codex_bin,
        workspace=args.workspace,
        sandbox=args.sandbox,
        approval=args.approval,
        output_schema=args.schema,
        timeout=args.timeout,
    )

    pdf_files = scan_paths(args.pdfs, [".pdf"])
    image_files = scan_paths(args.images, [".jpg", ".jpeg", ".png", ".webp"])

    if pdf_files:
        print(f"--- Found {len(pdf_files)} PDFs ---")

    if image_files:
        print(f"--- Found {len(image_files)} Images ---")

    user_instructions = processor.load_prompt_files(args.prompt)

    if not pdf_files and not image_files:
        print("\nNote: No media files found. Running on text prompt only.")

    processor.generate_response(
        pdf_paths=pdf_files,
        image_paths=image_files,
        prompt_text=user_instructions,
        output_base_name=args.output,
    )
