#!/usr/bin/env python3
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description="Merge multiple prompt files into one prompt file.")
parser.add_argument("-i", "--inputs", nargs="+", required=True, help="Input prompt files to merge")
parser.add_argument("-o", "--output", required=True, help="Merged output prompt file")
args = parser.parse_args()

merged = []

for file_path in args.inputs:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    merged.append(f"\n\n===== BEGIN {file_path} =====\n")
    merged.append(path.read_text(encoding="utf-8"))
    merged.append(f"\n===== END {file_path} =====\n")

Path(args.output).write_text("".join(merged).strip() + "\n", encoding="utf-8")
print(f"Merged {len(args.inputs)} files into {args.output}")
