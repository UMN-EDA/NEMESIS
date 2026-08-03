import os
import json
import argparse
import base64
from openai import OpenAI

# --- DEFAULTS ---
DEFAULT_MODEL = "gpt-5.2" 
DEFAULT_OUTPUT = "gemini_output" # Reverted to match your original structure exactly
DEFAULT_API="ENTER YOUR API KEY"
class OpenAIProcessor:
    def __init__(self, api_key, model_id):
        self.model_id = model_id
        self.static_prompt = ""
        try:
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            print(f"Error initializing OpenAI Client: {e}")
            exit(1)

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

            # If the marker exists, split it
            if marker in full_text:
                static_part, dynamic_part = full_text.split(marker, 1)
                if static_part.strip(): combined_static.append(static_part.strip())
                if dynamic_part.strip(): combined_dynamic.append(dynamic_part.strip())
            else:
                # If no marker exists, treat the ENTIRE file as static
                if full_text.strip(): combined_static.append(full_text.strip())
            
        # Join all static parts together and save to the class instance
        self.static_prompt = "\n\n".join(combined_static)
        
        # Return all dynamic parts joined together
        return "\n\n".join(combined_dynamic)

    def process_media(self, file_path: str):
        """Replaces Gemini's upload_media. Handles both PDFs and Images, returning a unified reference."""
        ext = os.path.splitext(file_path)[1].lower()
        
        # 1. Handle PDFs via OpenAI Files API
        if ext == ".pdf":
            print(f"Uploading {os.path.basename(file_path)}...", end=" ", flush=True)
            try:
                with open(file_path, "rb") as f:
                    file_response = self.client.files.create(file=f, purpose="user_data")
                print("Done.")
                return {"type": "pdf", "id": file_response.id}
            except Exception as e:
                print(f"\nError uploading PDF {file_path}: {e}")
                return None
                
        # 2. Handle Images via Base64 Encoding
        else:
            print(f"Encoding {os.path.basename(file_path)}...", end=" ", flush=True)
            try:
                with open(file_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
                mime_type = "image/jpeg"
                if ext == ".png": mime_type = "image/png"
                elif ext == ".webp": mime_type = "image/webp"

                print("Done.")
                return {"type": "image", "data": f"data:{mime_type};base64,{encoded_string}"}
            except Exception as e:
                print(f"\nError encoding image {file_path}: {e}")
                return None

    def _file_ref_to_part(self, file_ref):
        """Converts our internal file reference to an OpenAI Generative Part dictionary."""
        if file_ref["type"] == "pdf":
            return {
                "type": "file",
                "file": {"file_id": file_ref["id"]}
            }
        elif file_ref["type"] == "image":
            return {
                "type": "image_url",
                "image_url": {"url": file_ref["data"]}
            }

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
        """Sends inputs to OpenAI with cache-friendly static system prompt + dynamic user prompt."""
        # Keep this stable so it can be cached too
        json_guardrail = "IMPORTANT: Output strictly as ONE valid JSON object. No markdown. No extra text."

        # If no static prompt was set (for safety), fall back gracefully
        static_prompt = (self.static_prompt or "").strip()
        if static_prompt:
            system_text = f"{static_prompt}\n\n{json_guardrail}"
        else:
            system_text = json_guardrail

        dynamic_text = (prompt_text or "").strip()

        # Convert file refs to Parts
        parts = []
        for fr in (file_refs or []):
            try:
                parts.append(self._file_ref_to_part(fr))
            except Exception as e:
                print(f"Warning: could not convert file ref to Part: {e}")

        user_content = []
        if dynamic_text:
            user_content.append({"type": "text", "text": dynamic_text})
        user_content.extend(parts)

        # If nothing dynamic/media is present, still send a small user message
        if not user_content:
            user_content = [{"type": "text", "text": "Proceed using the system instructions."}]

        print(f"\nSending request to {self.model_id}...")

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            # --- Usage / cache visibility (robust) ---
            try:
                usage = getattr(response, "usage", None)
                if usage is not None:
                    # Helper to safely read attr or dict key
                    def _read(obj, key, default=None):
                        if obj is None:
                            return default
                        if isinstance(obj, dict):
                            return obj.get(key, default)
                        return getattr(obj, key, default)

                    # Top-level token counts (different SDKs may name these differently)
                    input_tokens = _read(usage, "prompt_tokens")
                    if input_tokens is None:
                        input_tokens = _read(usage, "input_tokens")

                    output_tokens = _read(usage, "completion_tokens")
                    if output_tokens is None:
                        output_tokens = _read(usage, "output_tokens")

                    total_tokens = _read(usage, "total_tokens")

                    # Cached tokens may be nested under prompt_tokens_details or input_tokens_details
                    cached_tokens = None
                    prompt_details = _read(usage, "prompt_tokens_details")
                    if prompt_details is not None:
                        cached_tokens = _read(prompt_details, "cached_tokens")

                    if cached_tokens is None:
                        input_details = _read(usage, "input_tokens_details")
                        if input_details is not None:
                            cached_tokens = _read(input_details, "cached_tokens")

                    # Some SDKs can expose audio/image token details; we ignore unless you want to print them too
                    print("\n[TOKEN USAGE]")
                    print(f"  input_tokens  : {input_tokens if input_tokens is not None else 'N/A'}")
                    print(f"  output_tokens : {output_tokens if output_tokens is not None else 'N/A'}")
                    print(f"  total_tokens  : {total_tokens if total_tokens is not None else 'N/A'}")
                    print(f"  cached_tokens : {cached_tokens if cached_tokens is not None else 'N/A'}")

                    # Optional cache hit ratio (best effort)
                    if isinstance(input_tokens, int) and input_tokens > 0 and isinstance(cached_tokens, int):
                        hit_pct = 100.0 * cached_tokens / input_tokens
                        print(f"  cache_hit_pct : {hit_pct:.2f}%")
                else:
                    print("\n[TOKEN USAGE] usage not returned by API response.")
            except Exception as e:
                print(f"\n[TOKEN USAGE] Could not inspect usage details: {e}")
            # -----------------------------------------------

            raw_text = response.choices[0].message.content

            if raw_text is None:
                finish_reason = response.choices[0].finish_reason
                refusal = getattr(response.choices[0].message, "refusal", None)

                print(f"\n[ERROR] OpenAI API returned an empty response (Content is None).")
                print(f"Finish Reason: {finish_reason}")
                if refusal:
                    print(f"Model Refusal: {refusal}")
                return None

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
    parser = argparse.ArgumentParser(description="OpenAI CLI: Process Directories of PDFs and Images.")
    
    #parser.add_argument("--prompt", "-p", required=True, help="Path to the prompt text file.")
    parser.add_argument("--prompt", "-p", nargs="+", required=True, help="Path(s) to the prompt text file(s).")
    parser.add_argument("--pdfs", nargs="*", help="Directory containing PDFs (or list of PDF files).")
    parser.add_argument("--images", "-i", nargs="*", help="Directory containing Images (or list of image files).")
    
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help=f"Output filename (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--api_key", default=DEFAULT_API, help="API Key (overrides env variable).")

    args = parser.parse_args()

    # 1. Setup API Key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: API Key not found. Set OPENAI_API_KEY env var or use --api_key")
        exit(1)

    # 2. Initialize Processor
    processor = OpenAIProcessor(api_key, args.model)
    
    collected_file_refs = []

    # 3. Scan and Upload PDFs
    pdf_files = scan_paths(args.pdfs, [".pdf"])
    if pdf_files:
        print(f"--- Found {len(pdf_files)} PDFs ---")
        for pdf in pdf_files:
            ref = processor.process_media(pdf)
            if ref: collected_file_refs.append(ref)

    # 4. Scan and Upload Images
    image_files = scan_paths(args.images, [".jpg", ".jpeg", ".png", ".webp"])
    if image_files:
        print(f"--- Found {len(image_files)} Images ---")
        for img in image_files:
            ref = processor.process_media(img)
            if ref: collected_file_refs.append(ref)

    # 5. Load Prompt
#    user_instructions = processor.load_prompt_file(args.prompt)
    # 5. Load Prompts
    user_instructions = processor.load_prompt_files(args.prompt)
    # 6. Run Generation
    if not collected_file_refs:
        print("\nNote: No media files found. Running on text prompt only.")
    
    result = processor.generate_response(collected_file_refs, user_instructions, args.output)
