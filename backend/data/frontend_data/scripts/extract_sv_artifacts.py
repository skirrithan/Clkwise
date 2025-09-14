#!/usr/bin/env python3
"""
extract_sv_artifacts.py

Read a JSON file (or stdin), extract the Verilog artifact under:
  result.artifacts.top_sv.content   -> writes to top.sv
  result.artifacts.top_sv.ui.text   -> writes to top.txt

Usage:
  python3 extract_sv_artifacts.py input.json
  cat input.json | python3 extract_sv_artifacts.py
  python3 extract_sv_artifacts.py input.json --sv out.sv --txt out.txt
"""

import sys
import json
import argparse
from pathlib import Path

def load_json(path: str | None) -> dict:
    data = sys.stdin.read() if path in (None, "-") else Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        sys.exit(f"[error] Invalid JSON: {e}")

def dig(d: dict, *keys, default=None):
    """Safe nested dict get: dig(obj, 'a','b','c', default=None)."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def main():
    ap = argparse.ArgumentParser(description="Extract SV artifacts from timing-fix JSON.")
    ap.add_argument("json", nargs="?", default="-", help="Path to JSON file (or '-' for stdin).")
    ap.add_argument("--sv",  default="top.sv",  help="Output filename for Verilog (default: top.sv)")
    ap.add_argument("--txt", default="top.txt", help="Output filename for UI text (default: top.txt)")
    args = ap.parse_args()

    obj = load_json(args.json)

    # Navigate to result.artifacts.top_sv
    top_sv = dig(obj, "result", "artifacts", "top_sv")
    if top_sv is None:
        sys.exit("[error] Could not find result.artifacts.top_sv in the JSON.")

    # Extract content for .sv and ui.text for .txt with fallbacks
    sv_content = dig(top_sv, "content")
    ui_text    = dig(top_sv, "ui", "text")

    # If primary fields missing, try reasonable fallbacks
    if sv_content is None:
        sv_content = ui_text  # fallback to UI text for .sv if needed
    if ui_text is None:
        ui_text = sv_content  # fallback to content for .txt if needed

    if not sv_content:
        sys.exit("[error] No Verilog content found (neither 'content' nor 'ui.text' contain data).")

    # Write files (UTF-8)
    Path(args.sv).write_text(sv_content, encoding="utf-8")
    Path(args.txt).write_text(ui_text or "", encoding="utf-8")

    print(f"[ok] Wrote {args.sv} and {args.txt}")

if __name__ == "__main__":
    main()
