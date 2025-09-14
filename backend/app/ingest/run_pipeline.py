#!/usr/bin/env python3
#python3 run_pipeline.py <path to timing_summary.rpt>
import argparse
import json
import os
import pathlib
import sys

# Local imports (assumes this file lives alongside parse_vivado.py and llmjson.py)
from parse_vivado import parse_summary
from llmjson import simplify_sta

def run_pipeline(
    rpt_path: pathlib.Path,
    out_dir: pathlib.Path = None,
    write_intermediate: bool = True,
    also_print: bool = False,
    fail_on_violations: bool = False,
) -> int:
    if not rpt_path.exists():
        print(f"[error] Report not found: {rpt_path}", file=sys.stderr)
        return 2

    text = rpt_path.read_text(errors="ignore")
    parsed = parse_summary(text)

    # Determine output directory & filenames
    out_dir = out_dir or rpt_path.parent
    out_dir = out_dir / "rpt_json_con"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Full parsed JSON
    intermediate_json_path = out_dir / (rpt_path.stem + ".json")
    if write_intermediate:
        try:
            intermediate_json_path.write_text(json.dumps(parsed, indent=2))
            print(f"[ok] Wrote {intermediate_json_path} (violations={len(parsed.get('violations', []))}, WNS={parsed.get('wns')})")
        except Exception as e:
            print(f"[error] Writing intermediate JSON failed: {e}", file=sys.stderr)
            return 3

    # 2) Simplified LLM JSON
    simple = simplify_sta(parsed)
    simple_json_path = out_dir / "llm_json_simple.json"
    try:
        simple_json_path.write_text(json.dumps(simple, indent=2))
        print(f"[ok] Wrote {simple_json_path}")
    except Exception as e:
        print(f"[error] Writing simplified JSON failed: {e}", file=sys.stderr)
        return 3

    if also_print:
        print(json.dumps(simple, indent=2))

    # Optional CI-friendly exit status
    if fail_on_violations:
        wns = parsed.get("wns")
        nvio = len(parsed.get("violations", []))
        if (wns is not None and wns < 0) or nvio > 0:
            return 10

    return 0

def main():
    ap = argparse.ArgumentParser(description="Vivado timing report → JSON → LLM JSON")
    ap.add_argument("report", help="Path to Vivado timing_summary.rpt")
    ap.add_argument("--out-dir", default=None, help="Directory to write outputs. Default: report's folder")
    ap.add_argument("--no-intermediate", action="store_true", help="Do not write the large intermediate JSON")
    ap.add_argument("--print", dest="also_print", action="store_true", help="Also print the simplified JSON to stdout")
    ap.add_argument("--fail-on-violations", action="store_true",
                    help="Exit non-zero if WNS<0 or there are any violations (CI mode)")
    args = ap.parse_args()

    rpt = pathlib.Path(args.report)
    out_dir = pathlib.Path(args.out_dir) if args.out_dir else None

    rc = run_pipeline(
        rpt_path=rpt,
        out_dir=out_dir,
        write_intermediate=not args.no_intermediate,
        also_print=args.also_print,
        fail_on_violations=args.fail_on_violations,
    )
    sys.exit(rc)

if __name__ == "__main__":
    main()
