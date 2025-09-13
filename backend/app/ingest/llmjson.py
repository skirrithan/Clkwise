#app/ingest/llmjson.py
import re
from collections import defaultdict

FLOAT = r"[-+]?\d+(?:\.\d+)?"

def _first(pat, s, flags=re.M):
    m = re.search(pat, s, flags)
    return m.group(1) if m else None

def _first_float(pat, s, flags=re.M):
    v = _first(pat, s, flags)
    return float(v) if v is not None else None

def _first_int(pat, s, flags=re.M):
    v = _first(pat, s, flags)
    return int(v) if v is not None else None

def classify_path(v):
    raw = v.get("raw","")
    # be strict about flip-flops to avoid false positives
    src_is_ff = bool(re.search(r"\bFD\w*\b", raw))
    dst_is_out = " (OUT)" in raw or "(output port" in raw or re.search(r"\b\(output port\b", raw)
    if src_is_ff and dst_is_out: return "reg->out"
    if src_is_ff and not dst_is_out: return "reg->reg"
    if not src_is_ff and dst_is_out: return "in->out"
    return "in->reg"

def bus_name(sig):
    # y[63] -> ("y", 63)
    m = re.match(r"([A-Za-z_]\w*)\[(\d+)\]", sig)
    if m: return m.group(1), int(m.group(2))
    return sig, None

def enrich_from_raw(v):
    """Mine additional fields from the violation 'raw' text to help the LLM."""
    raw = v.get("raw","")

    # --- Skew components & uncertainty/jitter ---
    dcd_ns = _first_float(r"Destination Clock Delay\s*\(DCD\):\s*(" + FLOAT + r")ns", raw)
    scd_ns = _first_float(r"Source Clock Delay\s*\(SCD\):\s*(" + FLOAT + r")ns", raw)
    cpr_ns = _first_float(r"Clock Pessimism Removal\s*\(CPR\):\s*(" + FLOAT + r")ns", raw)
    clk_unc_ns = _first_float(r"Clock Uncertainty:\s*(" + FLOAT + r")ns", raw)
    tsj_ns = _first_float(r"Total System Jitter\s*\(TSJ\):\s*(" + FLOAT + r")ns", raw)
    tij_ns = _first_float(r"Total Input Jitter\s*\(TIJ\):\s*(" + FLOAT + r")ns", raw)
    dj_ns  = _first_float(r"Discrete Jitter\s*\(DJ\):\s*(" + FLOAT + r")ns", raw)
    pe_ns  = _first_float(r"Phase Error\s*\(PE\):\s*(" + FLOAT + r")ns", raw)

    # --- Required/arrival times (footer table) ---
    req_ns = _first_float(r"^\s*required time\s+(" + FLOAT + r")", raw)
    arr_ns = _first_float(r"^\s*arrival time\s+(" + FLOAT + r")", raw)

    # --- Sites/primitives (first occurrences) ---
    io_site = _first(r"^\s*([A-Z]\d+)\s+OBUF\b", raw)
    io_primitive = "OBUF" if re.search(r"\bOBUF\b", raw) else None
    src_slice = _first(r"^\s*(SLICE_[A-Z0-9XY]+)\s+FD\w+\b", raw)

    # --- Clock net fanout and delays before the first FDxx entry ---
    clock_section = raw.split("FD", 1)[0] if "FD" in raw else raw
    clock_net_fanouts = [int(x) for x in re.findall(r"net\s*\(fo=(\d+)", clock_section)]
    clock_net_fanout_max = max(clock_net_fanouts) if clock_net_fanouts else None
    clock_net_delays = [float(x) for x in re.findall(r"net\s*\(fo=\d+.*?\)\s+(" + FLOAT + r")", clock_section)]
    clock_net_delay_ns_total = sum(clock_net_delays) if clock_net_delays else None

    return {
        "dcd_ns": dcd_ns,
        "scd_ns": scd_ns,
        "cpr_ns": cpr_ns,
        "clock_uncertainty_ns": clk_unc_ns,
        "tsj_ns": tsj_ns,
        "tij_ns": tij_ns,
        "dj_ns": dj_ns,
        "pe_ns": pe_ns,
        "required_time_ns": req_ns,
        "arrival_time_ns": arr_ns,
        "io_primitive": io_primitive,
        "io_site": io_site,
        "src_slice": src_slice,
        "clock_net_fanout_max": clock_net_fanout_max,
        "clock_net_delay_ns_total": clock_net_delay_ns_total,
    }

def dominant_delay(v):
    """Classify dominant delay considering OBUF cost and skew magnitude."""
    lp, rp = v.get("logic_pct",0), v.get("route_pct",0)
    levels = v.get("levels_of_logic",0)
    raw = v.get("raw","")
    obuf_present = bool(re.search(r"\bOBUF\b", raw))
    skew = v.get("clock_path_skew_ns", 0.0) or 0.0
    req = v.get("requirement_ns", 0.0) or 0.0

    # If OBUF is on the only logic level and routing >= logic, call it out
    if obuf_present and (rp >= lp or levels <= 1):
        label = "OBUF + routing"
        # If skew is large (|skew| >= 0.5*period), include skew in label
        if req and abs(skew) >= 0.5 * req:
            return label + " + skew"
        return label

    base = "logic" if lp > rp else "routing"
    if req and abs(skew) >= 0.5 * req:
        return base + " + skew"
    return base

def skew_character(v, extras):
    """Return a compact skew label to steer fixes."""
    scd = extras.get("scd_ns"); dcd = extras.get("dcd_ns")
    req = v.get("requirement_ns")
    if scd is None or dcd is None or not req:
        return None
    delta = (dcd - scd)  # negative => source clock path slower (arrives later) than destination
    if delta <= -0.5 * req:   return "negative_source_skew_large"
    if delta <= -0.1 * req:   return "negative_source_skew"
    if delta >=  0.5 * req:   return "negative_destination_skew_large"
    if delta >=  0.1 * req:   return "negative_destination_skew"
    return "balanced"

def root_cause_sentence(pk, dom, v, extras):
    skew = v.get("clock_path_skew_ns", 0.0) or 0.0
    req  = v.get("requirement_ns", 0.0) or 0.0
    scd  = extras.get("scd_ns"); dcd = extras.get("dcd_ns")
    skew_note = ""
    if req and abs(skew) >= 0.5 * req:
        direction = ""
        if scd is not None and dcd is not None:
            direction = " (source path > dest path)" if (scd > dcd) else " (dest path > source path)"
        skew_note = f" and large negative source clock skew{direction}" if skew < 0 else f" and large destination clock skew{direction}"

    if pk == "reg->out":
        return f"Unpipelined REG->OBUF path to top-level port with high {dom}{skew_note}."
    if pk == "reg->reg":
        return f"Deep combinational logic on REG->REG path with high {dom}{skew_note}."
    return f"Path limited by {dom}{skew_note}."

def pick_fixes(pk, dom, v, extras):
    """Produce targeted, actionable hints."""
    fixes = []
    skew = v.get("clock_path_skew_ns", 0.0) or 0.0
    req  = v.get("requirement_ns", 0.0) or 0.0
    obufy = "OBUF" in (extras.get("io_primitive") or "")
    big_skew = bool(req and abs(skew) >= 0.5 * req)

    if pk == "reg->out":
        fixes += [
            "Add output pipeline/reg in IOB (Vivado: set_property IOB TRUE [get_cells <y_reg[*]>]).",
            "Use ODDR/OSERDES or dedicated IO primitives for high-speed buses.",
            "Floorplan: LOC the output regs near the target IO bank; add Pblock over the bank; reduce long routes.",
            "If external timing allows, relax set_output_delay -max/-min or the clock period.",
        ]
        if obufy or "OBUF" in dom:
            fixes += [
                "Try OBUFDS (if differential) or faster IO standard/drive settings; evaluate SLEW=FAST where signal integrity permits.",
            ]
    elif pk == "reg->reg":
        fixes += [
            "Insert a pipeline stage (retime) to split combinational depth.",
            "Duplicate high-fanout registers to reduce net delay; add MAX_FANOUT or phys_opt_design -dup_registers.",
            "Constrain/floorplan critical cells closer together; pblock and keep hierarchy.",
        ]

    if "routing" in dom:
        fixes += [
            "Constrain placement to shorten critical nets; resolve congestion hot spots near the IO bank.",
        ]

    if big_skew:
        # Clock tree / region-aware guidance
        fixes += [
            "Reduce negative source skew: place the launching FF in the same clock region as the IO bank; prefer BUFH/regional clocks if feasible.",
            "Minimize source clock insertion delay (review BUFG/clock spine usage, avoid detours; check CLOCK_DEDICATED_ROUTE and timing DRCs).",
            "Review create_clock and set_clock_uncertainty; ensure uncertainty isn’t overly pessimistic.",
        ]

    # De-duplicate & cap
    seen = set(); uniq = []
    for f in fixes:
        if f not in seen:
            uniq.append(f); seen.add(f)
    return uniq[:6]

def simplify_sta(report):
    out = {
        "clock": None,
        "overview": {
            "wns_ns": report.get("wns"),
            "tns_ns": report.get("tns"),
            "violations": len(report.get("violations", []))
        },
        "sdc_gaps": [],   # new: surface global constraint gaps that block closure
        "issues": []
    }

    # single-clock assumption; extend if multi-clock
    clocks = report.get("clocks", {})
    if clocks:
        name, meta = next(iter(clocks.items()))
        out["clock"] = f"{name}@{meta.get('frequency_mhz')}MHz ({meta.get('period_ns')}ns)"

    # highlight checks that commonly block closure
    checks = report.get("checks", {})
    if checks:
        if checks.get("no_input_delay", 0):
            out["sdc_gaps"].append("Missing set_input_delay on at least one input; verify external timing model.")
        if checks.get("no_output_delay", 0):
            out["sdc_gaps"].append("Missing set_output_delay on outputs; confirm external device setup/hold.")
        if checks.get("generated_clocks", 0):
            out["sdc_gaps"].append("Generated clocks absent; add create_generated_clock where appropriate.")

    # group by (path_kind, bus)
    groups = defaultdict(list)
    for v in report.get("violations", []):
        pk = classify_path(v)
        base, bit = bus_name(v.get("destination",""))
        bus = f"{base}[*]" if bit is not None else base
        key = (pk, bus)
        groups[key].append(v)

    for (pk, bus), arr in groups.items():
        worst = min(arr, key=lambda x: x.get("slack", 0))

        # Enrich worst path from raw
        extras = enrich_from_raw(worst)

        dom = dominant_delay(worst)
        skew_tag = skew_character(worst, extras)

        # collect bits covered
        bits = []
        for v in arr:
            _, b = bus_name(v.get("destination",""))
            if b is not None: bits.append(b)
        bits = sorted(set(bits))

        # compact bit ranges (e.g., 44-63) in MSB:LSB style
        ranges = []
        if bits:
            s = bits[0]; prev = s
            for b in bits[1:]:
                if b == prev+1:
                    prev = b
                else:
                    ranges.append((s, prev)); s = prev = b
            ranges.append((s, prev))

        def fmt_ranges(rs):
            parts=[]
            for a,b in rs:
                parts.append(f"{b}:{a}" if a!=b else f"{a}")  # MSB:LSB or single
            return ",".join(parts)

        dest_port_string = (f"{bus[:-2]}[{fmt_ranges(ranges)}]" if bits else worst.get("destination"))

        issue = {
            "path_kind": pk,
            "signal_group": bus,
            "worst_bit": bus_name(worst.get("destination",""))[1],
            "worst_slack_ns": worst.get("slack"),
            "dominant_delay": dom,
            "skew_character": skew_tag,
            "evidence": {
                "data_path_ns": worst.get("data_path_delay_ns"),
                "logic_ns": worst.get("logic_delay_ns"),
                "route_ns": worst.get("route_delay_ns"),
                "levels_of_logic": worst.get("levels_of_logic"),
                "clock_skew_ns": worst.get("clock_path_skew_ns"),
                "output_delay_ns": worst.get("output_delay_ns"),
                # --- enriched fields for LLM actionability ---
                "dcd_ns": extras.get("dcd_ns"),
                "scd_ns": extras.get("scd_ns"),
                "cpr_ns": extras.get("cpr_ns"),
                "clock_uncertainty_ns": extras.get("clock_uncertainty_ns"),
                "tsj_ns": extras.get("tsj_ns"),
                "tij_ns": extras.get("tij_ns"),
                "dj_ns": extras.get("dj_ns"),
                "pe_ns": extras.get("pe_ns"),
                "required_time_ns": extras.get("required_time_ns"),
                "arrival_time_ns": extras.get("arrival_time_ns"),
                "io_primitive": extras.get("io_primitive"),
                "io_site": extras.get("io_site"),
                "src_slice": extras.get("src_slice"),
                "clock_net_fanout_max": extras.get("clock_net_fanout_max"),
                "clock_net_delay_ns_total": extras.get("clock_net_delay_ns_total"),
            },
            "root_cause": root_cause_sentence(pk, dom, worst, extras),
            "where_in_code": {
                "dest_port": dest_port_string,
                "src_ff_regex": r"y_reg\[(\d+)\]" if bus.startswith("y") else r"(\w+)_reg\[(\d+)\]"
            },
            "fix_hints": pick_fixes(pk, dom, worst, extras)
        }
        out["issues"].append(issue)

    # sort issues by worst slack
    out["issues"].sort(key=lambda i: i["worst_slack_ns"])
    return out

if __name__ == "__main__":
    import os
    import sys
    import json

    # Check if the user provided a JSON file as an argument
    if len(sys.argv) != 2:
        print("Usage: python llmjson.py <report.json>")
        sys.exit(1)

    # Read the JSON file
    report_file = sys.argv[1]
    try:
        with open(report_file, "r") as f:
            report = json.load(f)
    except Exception as e:
        print(f"Error reading report file '{report_file}': {e}")
        sys.exit(1)

    # Process the report
    result = simplify_sta(report)

    # Save the result to a file
    input_dir = os.path.dirname(report_file)
    output_file = os.path.join(input_dir, "llm_json_simple.json")

    try:
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Result saved to {output_file}")
    except Exception as e:
        print(f"Error writing to file '{output_file}': {e}")
        sys.exit(1)
