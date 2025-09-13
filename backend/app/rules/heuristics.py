def suggest_fix(path, clk_period_ns=2.0):
    tips = []
    slack = path.get("slack", 0.0)
    lev   = path.get("levels_of_logic", 0)
    r_pct = path.get("routing_pct", None)

    if slack < 0:
        # 1) Too many logic levels -> pipeline
        if lev and lev >= 6:
            tips.append("Pipeline long arithmetic chain (insert regs between multiplies/adds).")
        # 2) Routing-dominated path -> placement/floorplanning/fanout
        if r_pct and r_pct >= 60:
            tips.append("High routing delay: reduce fanout, duplicate regs, or add pblocks/LOC hints.")
        # 3) DSP slice present but not inferred?
        if "mul" in path.get("raw","").lower():
            tips.append("Ensure DSP48 inference (`(* use_dsp = \"yes\" *)`) or explicit DSP instantiation.")
        # 4) Consider multicycle if architecturally correct
        tips.append("If result not needed every cycle, use multicycle constraints (set_multicycle_path 2 ...) with care.")
        # 5) If crossing clocks -> CDC / false-paths
        if "Clock Path Skew" in path.get("raw","") and "Startpoint clock" in path.get("raw","") and "Endpoint clock" in path.get("raw",""):
            tips.append("Check for CDC; add 2-flop sync or declare false/multicycle paths if asynchronous.")
    return tips
