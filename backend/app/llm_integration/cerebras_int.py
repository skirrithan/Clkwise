#!/usr/bin/env python3
# python3 cerebras_int.py --timing <path to llm simple json> --verilog <path to top.sv> --out cerebras_out.json
"""
cerebras_int.py
Generate STRICT timing-fix plans from distilled violation JSON + Verilog using
Cerebras Structured Outputs (JSON Schema) and include a full rewritten top.sv.

Env:
  CER_API_KEY=...   # Cerebras key

Install:
  pip install cerebras-cloud-sdk jsonschema
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
DEFAULT_MODEL = "llama-4-scout-17b-16e-instruct"  # supports structured outputs
MAX_VERILOG_CHARS = 240_000  # guard mega-contexts

# ---- STRICT JSON SCHEMA for Structured Outputs ----
# NOTE (per Cerebras docs):
# - additionalProperties must be False wherever 'required' is used
# - Keep schema concise (< ~5000 chars)
TIMING_FIX_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "object",
            "properties": {
                "clock_name": {"type": "string"},
                "period_ns": {"type": "number"},
                "wns_ns": {"type": "number"},
                "path_kind": {"type": "string"},
                "signal_group": {"type": "string"},
                "root_cause": {"type": "string"}
            },
            "required": ["clock_name", "period_ns", "wns_ns", "path_kind", "signal_group", "root_cause"],
            "additionalProperties": False
        },
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "where": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "anchor_regex": {"type": "string"},
                            "ports_touched": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "signals_new": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["file", "anchor_regex"],
                        "additionalProperties": False
                    },
                    "verilog_patch": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["insert_block", "replace_regex", "append_before_endmodule"]},
                            "after_regex": {"type": "string"},
                            "before_regex": {"type": "string"},
                            "block": {"type": "string"}
                        },
                        "required": ["kind", "block"],
                        "additionalProperties": False
                    },
                    "latency_impact_cycles": {"type": "integer"}
                },
                "required": ["id", "title", "rationale", "where", "verilog_patch", "latency_impact_cycles"],
                "additionalProperties": False
            }
        },
        "artifacts": {
            "type": "object",
            "properties": {
                "top_sv": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "language": {"type": "string"},
                        "encoding": {"type": "string"},
                        "content": {"type": "string"},
                        "ui": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"}
                            },
                            "required": ["text"],
                            "additionalProperties": False
                        }
                    },
                    "required": ["path", "language", "encoding", "content", "ui"],
                    "additionalProperties": False
                }
            },
            "required": ["top_sv"],
            "additionalProperties": False
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"}
        },
        "verification": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["summary", "fixes", "artifacts", "risks", "verification"],
    "additionalProperties": False
}

# ---- Prompt ----
SYSTEM_PROMPT = (
    "You are a senior FPGA/ASIC timing-closure expert.\n"
    "TAKE YOUR TIME AND ENSURE THE FIX YOU ARE PROVIDING WILL FIX THE TIMING ISSUE GIVEN.\n"
    "Consider the required clock cycle and ensure that the pipeline staging is designed to meet the timing constraints.\n"
    "Return a SINGLE valid JSON object that strictly conforms to the provided JSON Schema. "
    "No code fences, no prose outside JSON, no trailing commas. Be concise and deterministic.\n\n"
    "== Output Schema (summary) ==\n"
    "- summary: { clock_name, period_ns, wns_ns, path_kind, signal_group, root_cause }\n"
    "- fixes: array[1+] with precise placement + patch details:\n"
    "  - id (e.g., \"F1\"), title, rationale\n"
    "  - where: { file, anchor_regex, ports_touched[], signals_new[] }\n"
    "  - verilog_patch: { kind: \"insert_block\"|\"replace_regex\"|\"append_before_endmodule\", after_regex?, before_regex?, block }\n"
    "  - latency_impact_cycles: integer >= 0\n"
    "- artifacts:\n"
    "  - files: array[1+] of {\n"
    "      path (.sv), language:\"verilog\", encoding:\"utf-8\",\n"
    "      content: FULL FILE TEXT (final rewritten file),\n"
    "      ui: { text: FULL FILE TEXT for UI display }\n"
    "    }\n"
    "- risks: array[string]\n"
    "- verification: array[string]\n\n"
    "== STRICT RULES ==\n"
    "1) VERILOG-ONLY edits. Do NOT output constraints/XDC/floorplanning/Tcl.\n"
    "2) Use ONLY identifiers/files present in the provided code. Do NOT invent names. "
    "   If adding a new signal, derive a deterministic suffix from existing names (e.g., <base>_pipe1).\n"
    "3) If adding latency, set fixes[*].latency_impact_cycles to the exact number of cycles added at the interface.\n"
    "4) The solution MUST meet the required clock cycle. Solutions exceeding the timing constraints are NOT acceptable.\n"
    "5) artifacts.files MUST include a complete, fully rewritten top.sv and module MUST still be named module top under \"content\" (and any other edited files). "
    "6) Preserve module headers, parameters, port lists, comments, and formatting wherever logic is unchanged.\n"
    "7) Patches and the rewritten file MUST be consistent (patches describe what changed; artifacts.content shows the final result).\n"
    "8) artifacts.files[*].ui.text MUST be identical to artifacts.files[*].content (normalized newlines allowed).\n"
)

USER_TEMPLATE = """\
Violation JSON:
{violation_json}

Verilog sources (filename then content):
{verilog_bundle}

Return ONLY the JSON that validates against the schema.
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
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        print("ERROR: CEREBRAS_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    return Cerebras(api_key=api_key)

# ---- Cerebras call (Structured Outputs) ----
def call_cerebras_structured(client: Cerebras, model: str, system: str, user: str, max_tokens: int) -> Dict[str, Any]:
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "timing_fix_schema",
                "strict": True,
                "schema": TIMING_FIX_SCHEMA
            }
        },
        max_tokens=max_tokens
    )
    content = completion.choices[0].message.content
    return json.loads(content)

# ---- Main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", required=True, help="violation JSON/JSONL (object, array, or jsonl)")
    ap.add_argument("--verilog", nargs="+", required=True, help="one or more Verilog files")
    ap.add_argument("--out", required=True, help="output path (.jsonl or .json)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out-format", choices=["jsonl","json"], default="jsonl")
    ap.add_argument("--indent", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=4096)
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
            obj = call_cerebras_structured(client, args.model, SYSTEM_PROMPT, user_msg, args.max_tokens)
            elapsed = time.time() - t0
            # sanity: ensure top.sv is present in artifacts
            has_top = any(f.get("path","").endswith(".sv") for f in obj.get("artifacts",{}).get("files",[]))
            records.append({
                "id": v.get("id", f"violation#{i}"),
                "input": v,
                "result": obj,
                "has_sv_artifact": bool(has_top),
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
