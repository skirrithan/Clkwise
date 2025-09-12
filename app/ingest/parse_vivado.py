import re, json, sys, pathlib

def parse_summary(txt):
    out = {"wns": None, "tns": None, "violations": []}
    wns_m = re.search(r"Worst Negative Slack\s*:\s*([-\d\.]+)", txt)
    tns_m = re.search(r"Total Negative Slack\s*:\s*([-\d\.]+)", txt)
    if wns_m: out["wns"] = float(wns_m.group(1))
    if tns_m: out["tns"] = float(tns_m.group(1))
    
    # crude path blocks
    for blk in re.split(r"-{5,}\s*Path\s*\d+.*?\n", txt)[1:]:
        sp = re.search(r"Startpoint:\s*(.+)", blk)
        ep = re.search(r"Endpoint:\s*(.+)", blk)
        sl = re.search(r"Slack\s*\(VIOLATED\)\s*:\s*([-\d\.]+)", blk) or \
             re.search(r"Slack\s*:\s*([-\d\.]+)", blk)
        lev = re.search(r"Levels of Logic:\s*(\d+)", blk)
        route_pct = re.search(r"Routing\s+Delay\s*:\s*([\d\.]+)\s*ns\s*\((\d+)%\)", blk)
        out["violations"].append({
            "startpoint": sp.group(1).strip() if sp else None,
            "endpoint":   ep.group(1).strip() if ep else None,
            "slack": float(sl.group(1)) if sl else None,
            "levels_of_logic": int(lev.group(1)) if lev else None,
            "routing_pct": int(route_pct.group(2)) if route_pct else None,
            "raw": blk[:2000]
        })
    return out

if __name__ == "__main__":
    rpt = pathlib.Path(sys.argv[1]).read_text(errors="ignore")
    data = parse_summary(rpt)
    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps(data, indent=2))
    print(f"Wrote {out}")
