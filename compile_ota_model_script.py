import json
import argparse
import sys
import os


def sanitize_code(raw_code):
    """
    Cleans up common formatting issues found in JSON-embedded code.
    """
    clean_code = raw_code.replace('\u00a0', ' ')

    if not clean_code.endswith('\n'):
        clean_code += '\n'

    return clean_code


def get_nested_value(data, key_path):
    """
    Extracts a nested value from a dictionary using a dot-separated key path.

    Example:
        key_path = "4_PYTHON_GENERATION.code"

        Equivalent to:
        data["4_PYTHON_GENERATION"]["code"]

    For a single key:
        key_path = "code"
    """
    keys = key_path.split(".")

    current = data
    for key in keys:
        if not isinstance(current, dict):
            raise KeyError(
                f"Cannot access key '{key}' because the current object is not a dictionary."
            )

        if key not in current:
            raise KeyError(f"Key '{key}' not found in JSON path: '{key_path}'")

        current = current[key]

    return current


def extract_python_from_json(input_json_path, output_py_path, json_key):
    print(f"Reading from: {input_json_path}")
    print(f"Using JSON key path: {json_key}")

    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        try:
            raw_code_string = get_nested_value(data, json_key)
        except KeyError as e:
            print("Error: The JSON structure does not match expectations.")
            print(f"Could not extract key path: '{json_key}'")
            print(f"Details: {e}")
            sys.exit(1)

        if not isinstance(raw_code_string, str):
            print(f"Error: Extracted value from '{json_key}' is not a string.")
            print(f"Actual type: {type(raw_code_string).__name__}")
            sys.exit(1)

        final_code = sanitize_code(raw_code_string)

        with open(output_py_path, 'w', encoding='utf-8') as f:
            f.write(final_code)

        print("Success! ?")
        print(f"Generated executable file: {os.path.abspath(output_py_path)}")
        print("Note: The script automatically replaced non-breaking spaces with standard spaces.")

    except FileNotFoundError:
        print(f"Error: Input file '{input_json_path}' not found.")
        sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in input file. {e}")
        sys.exit(1)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract embedded Python code from a JSON file."
    )

    parser.add_argument(
        "--input_file",
        required=True,
        help="Path to the source .json file"
    )

    parser.add_argument(
        "--output_file",
        required=True,
        help="Path for the generated .py file"
    )

    parser.add_argument(
        "--json_key",
        default="4_PYTHON_GENERATION.code",
        help=(
            "Dot-separated JSON key path to extract code from. "
            "Default: '4_PYTHON_GENERATION.code'. "
            "Examples: 'code', 'stage4.code', '4_PYTHON_GENERATION.code'"
        )
    )

    args = parser.parse_args()

    extract_python_from_json(
        input_json_path=args.input_file,
        output_py_path=args.output_file,
        json_key=args.json_key
    )
