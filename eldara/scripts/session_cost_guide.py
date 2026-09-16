#!/usr/bin/env python3
"""Rank the available kinds of work by session draw, with the expensive
tiers costed from run artifacts actually on disk rather than remembered.

WHY
---
The expensive thing in this project is spawning nested `claude -p`
sessions, and the cost is invisible until the rate limit warns. CLAUDE.md
carries the decision rule ("do the cheapest option that can still answer
the question"); this script carries the numbers, recomputed each time, so
the rule does not slowly drift out of date as more runs accumulate.

It deliberately measures only what it can count honestly: the number of
nested sessions a past run actually spawned and how long each took. That
is the quantity that maps to draw. It does NOT estimate tokens or dollars
-- nothing on disk supports that, and a made-up number here would be
worse than no number.

WHAT IT CANNOT TELL YOU
-----------------------
Remaining budget. Rate-limit state lives in the session, not the
filesystem: call `get_session` (claude-code-remote MCP, session_id
omitted) and read external_metadata.rate_limit_info.status. The window is
five_hour and rolling; daily and weekly figures are not exposed anywhere
reachable from a session, so do not report or extrapolate them.

Usage:
    python3 scripts/session_cost_guide.py
"""
import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "saves" / "exports"

# Tiers that spawn no nested sessions. These are flat -- there is nothing
# to measure because there is nothing being spent.
FREE_TIERS = [
    (0, "Re-analyse run artifacts already on disk",
     "retained campaign copies, continuity_notes, journal, per-turn git history"),
    (1, "Run project tooling against an existing campaign copy",
     "playtest_audit.py, validate_state.py, prune_advisor.py, gm_cases.py"),
    (2, "Unit-test predicates against synthetic states",
     "no model involved at all"),
]


def measure(pattern, session_key):
    """Count nested sessions and their durations in past run artifacts.

    Returns (runs, sessions, seconds_list). A run whose JSON is
    unreadable is skipped rather than guessed at.
    """
    runs = sessions = 0
    secs = []
    for f in sorted(glob.glob(str(EXPORTS / pattern))):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        runs += 1
        for rec in session_key(d):
            sessions += 1
            s = rec.get("seconds")
            if isinstance(s, (int, float)):
                secs.append(s)
    return runs, sessions, secs


def fmt(secs):
    if not secs:
        return "no runs on disk yet"
    lo, hi = min(secs), max(secs)
    total = sum(secs)
    return (f"{len(secs)} session(s), {lo:.0f}-{hi:.0f}s each "
            f"(~{total/60:.0f} min total)")


def main():
    print("Work available here, cheapest first. "
          "Do the cheapest option that can still answer the question.\n")

    for tier, what, detail in FREE_TIERS:
        print(f"  TIER {tier}  [no nested sessions]  {what}")
        print(f"          {detail}")
    print()

    sp_runs, sp_n, sp_secs = measure(
        "stress_transcript_*.json",
        lambda d: d.get("results", []) if isinstance(d, dict) else [])
    dc_runs, dc_n, dc_secs = measure(
        "drift_chain_*.json",
        lambda d: [t for c in d.get("chains", []) for t in c.get("turns", [])])

    print(f"  TIER 3  [ONE NESTED SESSION PER CASE]  run_stress_prompts.py")
    print(f"          measured over {sp_runs} run(s): {fmt(sp_secs)}")
    print(f"  TIER 4  [ONE NESTED SESSION PER TURN PER CHAIN]  run_drift_chain.py")
    print(f"          measured over {dc_runs} run(s): {fmt(dc_secs)}")
    print()

    if dc_secs and sp_secs:
        print(f"  A full default drift chain (3 chains x 6 turns = 18 sessions) "
              f"costs roughly\n  {18*(sum(dc_secs)/len(dc_secs))/60:.0f} minutes "
              f"at the measured mean of {sum(dc_secs)/len(dc_secs):.0f}s/session.")
        print()

    print("BEFORE STARTING TIER 3 OR 4:")
    print("  Call get_session (claude-code-remote MCP, session_id omitted) and read")
    print("  external_metadata.rate_limit_info.status --")
    print("    allowed          -> proceed")
    print("    allowed_warning  -> DO NOT start tier 3/4; report reset time,")
    print("                        offer tier 0-2 instead")
    print("  The window is five_hour and rolling. Daily/weekly figures are not")
    print("  exposed to a session -- do not report or extrapolate them.")
    print()

    # The standing reminder that has actually paid off here more than once.
    copies = sorted(glob.glob("/tmp/eldara-chain-*/eldara/saves/current.json")) + \
        sorted(glob.glob("/tmp/eldara-stress-*/eldara/saves/current.json"))
    if copies:
        print(f"UNMINED DATA: {len(copies)} retained campaign copy(ies) still on disk.")
        for c in copies:
            try:
                with open(c, encoding="utf-8") as fh:
                    s = json.load(fh)
                d = s.get("in_world_date") or {}
                print(f"  - turn {s.get('turn')}, day {d.get('day')} "
                      f"{d.get('month')}, {len(s.get('continuity_notes') or [])} "
                      f"continuity note(s)  {os.path.dirname(os.path.dirname(c))}")
            except (OSError, json.JSONDecodeError):
                print(f"  - (unreadable) {c}")
        print("  Tier 0 work on these costs nothing and has outperformed a fresh")
        print("  tier 4 run on findings per minute. Mine them before paying again.")
    else:
        print("No retained campaign copies on disk -- tier 0 has nothing queued.")


if __name__ == "__main__":
    main()
