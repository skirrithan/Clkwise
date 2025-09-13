# app/ingest/parse_vivado.py
import re, json, sys, pathlib
from typing import Dict, Any, List

FLOAT = r"[-+]?(?:\d+\.\d+|\d+)"
PCT   = r"(?:\d+\.\d+|\d+)"  # percentage without %

def _between(txt: str, start_pat: str, end_pat: str) -> str:
    s = re.search(start_pat, txt, flags=re.S|re.M)
    if not s:
        return ""
    start = s.end()
    e = re.search(end_pat, txt[start:], flags=re.S|re.M)
    return txt[start: start + (e.start() if e else len(txt))]

def parse_design_timing_summary(txt: str) -> Dict[str, Any]:
    """
    Extract WNS/TNS from the 'Design Timing Summary' table.
    """
    block = _between(txt, r"Design Timing Summary\s*[-\s|]*\n", r"\n\s*Clock Summary")
    # Look for the first numeric row under the header (WNS(ns) TNS(ns) ...)
    m = re.search(
        rf"^\s*({FLOAT})\s+({FLOAT})\s+(\d+)\s+(\d+)\s+({FLOAT})\s+({FLOAT})\s+(\d+)\s+(\d+)",
        block, flags=re.M)
    out = {"wns": None, "tns": None}
    if m:
        out["wns"] = float(m.group(1))
        out["tns"] = float(m.group(2))
    return out

def parse_clock_summary(txt: str) -> Dict[str, Dict[str, float]]:
    """
    Parse the 'Clock Summary' table: name -> {period, freq_mhz}
    """
    block = _between(txt, r"Clock Summary\s*[-\s|]*\n", r"\n\s*Intra Clock Table")
    clocks = {}
    # Rows like: sys_clk  {0.000 1.000}        2.000           500.000
    for line in block.splitlines():
        m = re.match(r"\s*([A-Za-z0-9_./]+)\s+\{[^\}]*\}\s+(" + FLOAT + r")\s+(" + FLOAT + r")", line)
        if m:
            clocks[m.group(1)] = {
                "period_ns": float(m.group(2)),
                "frequency_mhz": float(m.group(3)),
            }
    return clocks

def iter_path_blocks(txt: str) -> List[Dict[str, Any]]:
    """
    Iterate 'Max Delay Paths' blocks. Each starts with:
      Slack (VIOLATED) :   -7.614ns ...
    and ends at the next 'Slack (' or at 'Pulse Width Checks'.
    """
    paths = []
    # Work only within the 'Max Delay Paths' section to avoid false matches
    max_block = _between(txt, r"Max Delay Paths", r"Pulse Width Checks|$\Z")
    if not max_block:
        return paths

    # Find each path's span
    path_iter = list(re.finditer(r"^Slack \((VIOLATED|MET)\)\s*:\s*(" + FLOAT + r")ns.*?$",
                                 max_block, flags=re.M))
    for i, m in enumerate(path_iter):
        start = m.start()
        end = path_iter[i+1].start() if i+1 < len(path_iter) else len(max_block)
        block = max_block[start:end]

        status = m.group(1)
        slack  = float(m.group(2))

        # Simple field captures
        source = _first(r"^\s*Source:\s*(.+)$", block)
        dest   = _first(r"^\s*Destination:\s*(.+)$", block)
        group  = _first(r"^\s*Path Group:\s*(.+)$", block)
        req    = _first_float(r"^\s*Requirement:\s*(" + FLOAT + r")ns", block)
        levels = _first_int(r"^\s*Logic Levels:\s*(\d+)", block)
        outdel = _first_float(r"^\s*Output Delay:\s*(" + FLOAT + r")ns", block)
        skew   = _first_float(r"^\s*Clock Path Skew:\s*(" + FLOAT + r")ns", block)

        # Data Path Delay with breakdown:
        # Data Path Delay: 4.737ns  (logic 2.757ns (58.196%)  route 1.980ns (41.804%))
        d = re.search(
            rf"Data Path Delay:\s*({FLOAT})ns\s*\(logic\s*({FLOAT})ns\s*\(({PCT})%\)\s*route\s*({FLOAT})ns\s*\(({PCT})%\)\)",
            block)
        data_delay = logic_ns = route_ns = logic_pct = route_pct = None
        if d:
            data_delay = float(d.group(1))
            logic_ns   = float(d.group(2))
            logic_pct  = float(d.group(3))
            route_ns   = float(d.group(4))
            route_pct  = float(d.group(5))

        paths.append({
            "status": status,
            "slack": slack,
            "source": source,
            "destination": dest,
            "path_group": group,
            "requirement_ns": req,
            "data_path_delay_ns": data_delay,
            "logic_delay_ns": logic_ns,
            "logic_pct": logic_pct,
            "route_delay_ns": route_ns,
            "route_pct": route_pct,
            "levels_of_logic": levels,
            "output_delay_ns": outdel,
            "clock_path_skew_ns": skew,
            "raw": block.strip()[:4000],
        })
    return paths

def _first(pat: str, txt: str) -> str:
    m = re.search(pat, txt, flags=re.M)
    return m.group(1).strip() if m else None

def _first_float(pat: str, txt: str):
    m = re.search(pat, txt, flags=re.M)
    return float(m.group(1)) if m else None

def _first_int(pat: str, txt: str):
    m = re.search(pat, txt, flags=re.M)
    return int(m.group(1)) if m else None

def parse_checks(txt: str) -> Dict[str, int]:
    """
    Parse 'check_timing report' headings like:
      5. checking no_input_delay (1)
    """
    checks = {}
    block = _between(txt, r"check_timing report", r"\n\s*Design Timing Summary")
    for m in re.finditer(r"\d+\.\s*checking\s+([a-zA-Z0-9_]+)\s*\((\d+)\)", block):
        checks[m.group(1)] = int(m.group(2))
    return checks

def parse_summary(txt: str) -> Dict[str, Any]:
    summary = {}
    summary.update(parse_design_timing_summary(txt))
    summary["clocks"] = parse_clock_summary(txt)
    summary["checks"] = parse_checks(txt)
    summary["violations"] = iter_path_blocks(txt)
    return summary

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app/ingest/parse_vivado.py <path/to/report.rpt>")
        sys.exit(1)
    p = pathlib.Path(sys.argv[1])
    t = p.read_text(errors="ignore")
    data = parse_summary(t)
    out = p.with_suffix(".json")
    out.write_text(json.dumps(data, indent=2))
    print(f"Wrote {out} with {len(data.get('violations', []))} paths; WNS={data.get('wns')} TNS={data.get('tns')}")
