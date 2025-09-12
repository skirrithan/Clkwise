import json, sys
from ingest.parse_vivado import parse_summary
from rules.heuristics import suggest_fix

rpt = open(sys.argv[1], "r", errors="ignore").read()
print(rpt)
summary = parse_summary(rpt)
print(f"WNS={summary['wns']}  TNS={summary['tns']}  paths={len(summary['violations'])}")
for i, p in enumerate(summary["violations"][:5], 1):
    print(f"\nPath {i}  slack={p['slack']}  levels={p['levels_of_logic']}  routing%={p['routing_pct']}")
    for tip in suggest_fix(p):
        print("  -", tip)
