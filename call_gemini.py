import os
import json
import time
import argparse
from google import genai
from google.genai import types

# --- DEFAULTS ---
DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_OUTPUT = "gemini_output"
DEFAULT_API = "ENTER YOUR API KEY"


class GeminiProcessor:
    def __init__(self, api_key, model_id):
        self.model_id = model_id
        self.static_prompt = ""
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"Error initializing Client: {e}")
            exit(1)

    def load_prompt_files(self, file_paths: list) -> str:
        """
        Reads multiple prompt files, combining static and dynamic sections.

        Marker:
            \\n### DYNAMIC SECTION ###\\n

        - Text before marker: static prompt (goes to system_instruction, cache friendly)
        - Text after marker : dynamic prompt (goes to user contents)
        - If no marker      : entire file is static
        """
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

    def upload_media(self, file_path: str):
        """Uploads a file to Google GenAI Files API."""
        import mimetypes
        import uuid

        unique_name = f"{uuid.uuid4().hex[:6]}_{os.path.basename(file_path)}"
        mime_type, _ = mimetypes.guess_type(file_path)

        print(f"Uploading {os.path.basename(file_path)}...", end=" ", flush=True)
        try:
            with open(file_path, "rb") as f:
                file_ref = self.client.files.upload(
                    file=f,
                    config={
                        "display_name": unique_name,
                        "mime_type": mime_type or "application/octet-stream",
                    },
                )

            while file_ref.state.name == "PROCESSING":
                print(".", end="", flush=True)
                time.sleep(1)
                file_ref = self.client.files.get(name=file_ref.name)

            if file_ref.state.name == "FAILED":
                print(" FAILED.")
                raise ValueError(f"File upload failed: {file_ref.state.name}")

            print(" Done.")
            return file_ref
        except Exception as e:
            print(f"\nError uploading media {file_path}: {e}")
            return None

    def _file_ref_to_part(self, file_ref):
        """Converts a file reference to a Generative AI Part."""
        return types.Part(
            file_data=types.FileData(
                file_uri=file_ref.uri,
                mime_type=file_ref.mime_type,
            )
        )

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

    def generate_response(self, file_refs: list, prompt_text: str, output_base_name: str):
        """
        Sends inputs to Gemini with cache-friendly static system_instruction + dynamic user prompt.

        1) Prefer response.parsed (when response_mime_type is JSON)
        2) Else try json.loads(response.text)
        3) Else save .txt fallback
        """
        json_guardrail = "IMPORTANT: Output strictly as ONE valid JSON object. No markdown. No extra text."

        static_prompt = (self.static_prompt or "").strip()
        if static_prompt:
            system_instruction = f"{static_prompt}\n\n{json_guardrail}"
        else:
            system_instruction = json_guardrail

        dynamic_text = (prompt_text or "").strip()

        # Convert file refs to Parts
        parts = []
        for fr in (file_refs or []):
            try:
                parts.append(self._file_ref_to_part(fr))
            except Exception as e:
                print(f"Warning: could not convert file ref to Part: {e}")

        # Gemini contents: put dynamic text first, then media parts
        contents = []
        if dynamic_text:
            contents.append(dynamic_text)
        else:
            contents.append("Proceed using the system instructions.")
        contents.extend(parts)

        print(f"\nSending request to {self.model_id}...")

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            # --- Usage / cache visibility (best effort) ---
            try:
                usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)

                def _read(obj, key, default=None):
                    if obj is None:
                        return default
                    if isinstance(obj, dict):
                        return obj.get(key, default)
                    return getattr(obj, key, default)

                if usage is not None:
                    # Common Gemini fields
                    input_tokens = _read(usage, "prompt_token_count")
                    output_tokens = _read(usage, "candidates_token_count")
                    total_tokens = _read(usage, "total_token_count")

                    # Some SDKs expose cached token counts
                    cached_tokens = _read(usage, "cached_content_token_count")
                    if cached_tokens is None:
                        cached_tokens = _read(usage, "cached_tokens")

                    print("\n[TOKEN USAGE]")
                    print(f"  input_tokens  : {input_tokens if input_tokens is not None else 'N/A'}")
                    print(f"  output_tokens : {output_tokens if output_tokens is not None else 'N/A'}")
                    print(f"  total_tokens  : {total_tokens if total_tokens is not None else 'N/A'}")
                    print(f"  cached_tokens : {cached_tokens if cached_tokens is not None else 'N/A'}")

                    if isinstance(input_tokens, int) and input_tokens > 0 and isinstance(cached_tokens, int):
                        hit_pct = 100.0 * cached_tokens / input_tokens
                        print(f"  cache_hit_pct : {hit_pct:.2f}%")
                else:
                    print("\n[TOKEN USAGE] usage not returned by API response.")
            except Exception as e:
                print(f"\n[TOKEN USAGE] Could not inspect usage details: {e}")
            # --------------------------------------------

            # 1) Best case: parsed JSON
            if hasattr(response, "parsed") and response.parsed is not None:
                json_data = response.parsed
                output_file = f"{output_base_name}"
                self._save_json(json_data, output_file)
                return json_data

            # 2) Fallback: parse response.text
            raw_text = getattr(response, "text", "")
            cleaned_text = self._clean_json_string(raw_text)

            try:
                json_data = json.loads(cleaned_text)
                output_file = f"{output_base_name}"
                self._save_json(json_data, output_file)
                return json_data
            except json.JSONDecodeError:
                print("\nWarning: Output could not be parsed as JSON.")
                output_file = f"{output_base_name}"
                self._save_text(raw_text, output_file)
                return None

        except Exception as e:
            print(f"API Error: {e}")
            return None

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


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini CLI: Process Directories of PDFs and Images.")

    # Keep args consistent with your OpenAI script
    parser.add_argument("--prompt", "-p", nargs="+", required=True, help="Path(s) to the prompt text file(s).")

    parser.add_argument("--pdfs", nargs="*", help="Directory containing PDFs (or list of PDF files).")
    parser.add_argument("--images", "-i", nargs="*", help="Directory containing Images (or list of image files).")

    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help=f"Output filename (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--api_key", default=DEFAULT_API, help="API Key (overrides env variable).")

    args = parser.parse_args()

    # 1. Setup API Key (same pattern as your OpenAI script)
    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: API Key not found. Set GEMINI_API_KEY env var or use --api_key")
        exit(1)

    # 2. Initialize Processor
    processor = GeminiProcessor(api_key, args.model)

    collected_file_refs = []

    # 3. Scan and Upload PDFs
    pdf_files = scan_paths(args.pdfs, [".pdf"])
    if pdf_files:
        print(f"--- Found {len(pdf_files)} PDFs ---")
        for pdf in pdf_files:
            ref = processor.upload_media(pdf)
            if ref:
                collected_file_refs.append(ref)

    # 4. Scan and Upload Images
    image_files = scan_paths(args.images, [".jpg", ".jpeg", ".png", ".webp"])
    if image_files:
        print(f"--- Found {len(image_files)} Images ---")
        for img in image_files:
            ref = processor.upload_media(img)
            if ref:
                collected_file_refs.append(ref)

    # 5. Load Prompts (multi-file + static/dynamic split)
    user_instructions = processor.load_prompt_files(args.prompt)

    # 6. Run Generation
    if not collected_file_refs:
        print("\nNote: No media files found. Running on text prompt only.")

    result = processor.generate_response(collected_file_refs, user_instructions, args.output)
