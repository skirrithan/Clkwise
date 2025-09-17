#!/usr/bin/env python3
# python3 cerebras_int_no_schema.py --timing <path to llm simple json> --verilog <path to top.sv> --out cerebras_out.json
"""
cerebras_int_no_schema.py
Generate timing-fix plans from distilled violation JSON + Verilog using
Cerebras LLMs without requiring structured output schema validation.

Env:
  CEREBRAS_API_KEY=...   # Cerebras key

Install:
  pip install cerebras-cloud-sdk
"""

from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from typing import Any, Dict, List

# ---- Cerebras SDK ----
try:
    from cerebras.cloud.sdk import Cerebras
except Exception as e:
    print("ERROR: pip install cerebras-cloud-sdk", file=sys.stderr)
    raise

# ---- Config ----
DEFAULT_MODEL = "gpt-oss-120b"  # Model to use
MAX_VERILOG_CHARS = 240_000  # guard mega-contexts

# ---- Prompt ----
SYSTEM_PROMPT = (
    "You are a senior FPGA/ASIC timing-closure expert.\n"
    "TAKE YOUR TIME AND ENSURE THE FIX YOU ARE PROVIDING WILL FIX THE TIMING ISSUE GIVEN.\n"
    "Consider the required clock cycle and ensure that the pipeline staging is designed to meet the timing constraints.\n"
    "IMPORTANT: If you are unsure whether your solution will fully meet timing, ALWAYS ADD ADDITIONAL PIPELINE STAGES. "
    "It is better to over-pipeline with extra registers than to risk failing timing closure. "
    "Aim for at least 20% positive slack to account for unexpected implementation variations.\n"
    "Return a SINGLE valid JSON object with the following structure.\n"
    "No code fences, no prose outside JSON, no trailing commas. Be concise and deterministic.\n\n"
    "== Expected Output Structure ==\n"
    "- summary: { clock_name, period_ns, wns_ns, path_kind, signal_group, root_cause }\n"
    "- fixes: array[1+] with precise placement + patch details:\n"
    "  - id (e.g., \"F1\"), title, rationale\n"
    "  - where: { file, anchor_regex, ports_touched[], signals_new[] }\n"
    "  - verilog_patch: { kind: \"insert_block\"|\"replace_regex\"|\"append_before_endmodule\", after_regex?, before_regex?, block }\n"
    "  - latency_impact_cycles: integer >= 0\n"
    "- artifacts: {\n"
    "  - top_sv: {\n"
    "      path: \"top.sv\", language: \"verilog\", encoding: \"utf-8\",\n"
    "      content: FULL FILE TEXT (final rewritten file),\n"
    "      ui: { text: FULL FILE TEXT for UI display }\n"
    "    }\n"
    "  }\n"
    "- risks: array[string]\n"
    "- verification: array[string]\n\n"
    "== STRICT RULES ==\n"
    "1) SYSTEM-VERILOG-ONLY edits. Use SystemVerilog syntax and features like 'logic' type, 'always_ff', etc. Do NOT output constraints/XDC/floorplanning/Tcl.\n"
    "2) Use ONLY identifiers/files present in the provided code. Do NOT invent names. "
    "   If adding a new signal, derive a deterministic suffix from existing names (e.g., <base>_pipe1).\n"
    "3) If adding latency, set fixes[*].latency_impact_cycles to the exact number of cycles added at the interface.\n"
    "4) The solution MUST meet the required clock cycle with sufficient margin (at least 20% positive slack). Solutions cutting it close or violating timing constraints are NOT acceptable.\n"
    "5) For critical paths with tight timing, ALWAYS add extra pipeline stages - it's better to have more latency than to miss timing.\n"
    "6) artifacts.top_sv MUST include the complete, fully rewritten top.sv and module MUST still be named module top under \"content\".\n"
    "7) Preserve module headers, parameters, port lists, comments, and formatting wherever logic is unchanged.\n"
    "8) Always use (* IOB=\"TRUE\" *) attributes for output registers to improve timing.\n"
    "9) When implementing pipelining, split complex operations (especially multipliers) into multiple stages.\n"
    "10) Use explicit SystemVerilog constructs: 'logic' instead of 'reg/wire', 'always_ff' for sequential logic, 'always_comb' for combinational logic.\n"
    "11) Use SystemVerilog initialization syntax like '0 with appropriate apostrophes for default values.\n"
    "12) ENSURE EVERY SIGNAL HAS EXACTLY ONE DRIVER. A net/variable must be assigned from a single continuous assignment OR a single always block, never both.\n"
    "13) Do not override or redeclare assignments in SystemVerilog.\n"
    "14) Before returning the JSON, re-read the produced code to verify that all signals are wired correctly, all pipelines connect cleanly, and no multiple drivers exist.\n"
)

USER_TEMPLATE = """\
Violation JSON:
{violation_json}

Verilog sources (filename then content):
{verilog_bundle}

Return ONLY the JSON with your detailed timing fix solution.
"""

# ---- Helpers ----
def read_json_any(path: Path) -> List[Dict[str, Any]]:
    if path.suffix == ".jsonl":
        out = []
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    raise ValueError(f"{path.name}#{i} not an object")
                out.append(obj)
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]

def bundle_verilog(files: List[Path]) -> str:
    parts = []
    for p in files:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            content = f"<<ERROR READING {p.name}: {e}>>"
        parts.append(f"\n--- FILE: {p.name} ---\n{content}\n")
    blob = "".join(parts)
    return blob[:MAX_VERILOG_CHARS]

def get_client() -> Cerebras:
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        print("ERROR: CEREBRAS_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    return Cerebras(api_key=api_key)

# ---- Cerebras call (Standard Output) ----
def call_cerebras(client: Cerebras, model: str, system: str, user: str, max_tokens: int) -> str:
    # Base parameters for all models
    params = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                    {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.1  # Lower temperature for more deterministic outputs
    }
    
    # Add reasoning_effort only for models that support it (not gpt-oss models)
    if not "gpt-oss" in model.lower():
        params["reasoning_effort"] = "high"
    
    # Make the API call
    completion = client.chat.completions.create(**params)
    
    # Extract the content, with safety check
    content = completion.choices[0].message.content
    if content is None:
        raise ValueError(f"Empty response from model {model}")
    
    return content

# ---- Main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", required=True, help="violation JSON/JSONL (object, array, or jsonl)")
    ap.add_argument("--verilog", nargs="+", required=True, help="one or more Verilog files")
    ap.add_argument("--out", required=True, help="output path (.jsonl or .json)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out-format", choices=["jsonl","json"], default="jsonl")
    ap.add_argument("--indent", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=8192)  # Increased default tokens
    args = ap.parse_args()

    client = get_client()
    violations = read_json_any(Path(args.timing))
    vbundle = bundle_verilog([Path(p) for p in args.verilog])

    records: List[Dict[str, Any]] = []
    for i, v in enumerate(violations):
        user_msg = USER_TEMPLATE.format(
            violation_json=json.dumps(v, ensure_ascii=False, indent=2),
            verilog_bundle=vbundle
        )
        t0 = time.time()
        try:
            response_text = call_cerebras(client, args.model, SYSTEM_PROMPT, user_msg, args.max_tokens)
            elapsed = time.time() - t0
            
            # Try to parse the JSON response
            try:
                obj = json.loads(response_text)
                # Check for minimal required structure
                has_top = "artifacts" in obj and "top_sv" in obj.get("artifacts", {})
                
                records.append({
                    "id": v.get("id", f"violation#{i}"),
                    "input": v,
                    "result": obj,
                    "has_sv_artifact": bool(has_top),
                    "model": args.model,
                    "elapsed_sec": round(elapsed, 3)
                })
            except json.JSONDecodeError as e:
                records.append({
                    "id": v.get("id", f"violation#{i}"),
                    "input": v,
                    "error": f"JSON parsing error: {e}",
                    "raw_response": response_text[:1000] + ("..." if len(response_text) > 1000 else ""),
                    "model": args.model,
                    "elapsed_sec": round(elapsed, 3)
                })
        except Exception as e:
            elapsed = time.time() - t0
            records.append({
                "id": v.get("id", f"violation#{i}"),
                "input": v,
                "error": f"{type(e).__name__}: {e}",
                "model": args.model,
                "elapsed_sec": round(elapsed, 3)
            })

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    if args.out_format == "jsonl":
        with outp.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False, indent=2) + "\n")
    else:
        with outp.open("w", encoding="utf-8") as f:
            json.dump(records if len(records) > 1 else records[0],
                      f, ensure_ascii=False, indent=args.indent)

if __name__ == "__main__":
    main()