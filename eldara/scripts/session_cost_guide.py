#!/usr/bin/env python3
"""Decide what to do about an issue: weigh each candidate fix's
EFFECTIVENESS against its SESSION DRAW, with draw costed from run
artifacts on disk and budget read from recorded rate-limit observations.

THE PROCEDURE THIS SUPPORTS
---------------------------
  1. Search for information on the issue        (agent)
  2. Rank candidate fixes: effectiveness vs draw, against BOTH the
     short-window and long-window budgets         <- this script
  3. Apply the recommended fix                   (agent)
  4. Report findings                             (agent)
  5. Wait for user input                         (agent)

Steps 1, 3, 4 and 5 are agent actions; no script can do them. What a
script CAN do is step 2 without flattering itself: the draw numbers come
from what past runs actually spent, and the budget from what get_session
actually returned, so neither is a remembered figure.

WHY BOTH WINDOWS
----------------
rate_limit_info reports only the ONE window currently binding. It read
five_hour in the morning and, once that window reset, seven_day with a
reset four days out. A single snapshot therefore cannot show both, and
reading only the binding one is how a four-day constraint gets mistaken
for a four-hour one. This reads the per-window history the guard records
and prints every window it has ever seen, each labelled with the age of
its observation, so a stale entry cannot pass as current.

WHAT IT REFUSES TO ESTIMATE
---------------------------
Tokens, dollars, and any "percent remaining". Nothing on disk supports
them and no remaining-figure is exposed to a session. A confident number
here would be worse than no number, because it would get quoted back.

Effectiveness is the one judged input and is labelled as such. The script
does not pretend to derive it -- it makes the judgement explicit and
puts it next to a measured cost, which is the whole value.

Usage:
    python3 scripts/session_cost_guide.py                    # tiers + budget
    python3 scripts/session_cost_guide.py --rank fixes.json  # rank candidates
"""
import argparse
import glob
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "saves" / "exports"
REPO = ROOT.parent
HISTORY_FILE = REPO / ".claude" / "rate_limit_history.json"
ISSUES_FILE = ROOT / "docs" / "open_issues.json"

# Draw weight per tier. Not a token count -- a count of nested `claude -p`
# sessions, which is the quantity that actually moves the rate limit.
TIER_DRAW = {0: 0, 1: 0, 2: 0, 3: 1, 4: 1}

FREE_TIERS = [
    (0, "Re-analyse run artifacts already on disk",
     "retained campaign copies, continuity_notes, journal, per-turn git history"),
    (1, "Run project tooling against an existing campaign copy",
     "playtest_audit.py, validate_state.py, prune_advisor.py, gm_cases.py"),
    (2, "Unit-test predicates against synthetic states",
     "no model involved at all"),
]


def measure(pattern, session_key):
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
    return (f"{len(secs)} session(s), {min(secs):.0f}-{max(secs):.0f}s each "
            f"(~{sum(secs)/60:.0f} min total)")


def budget():
    """Every window ever observed, each with the age of its observation.

    Returns (rows, worst_status). A window whose reset time has already
    passed is reported as expired rather than as a live constraint --
    that is exactly the five_hour entry that misled once already.
    """
    if not HISTORY_FILE.exists():
        return [], None
    try:
        hist = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], None

    now = int(time.time())
    rank = {"allowed": 0, "allowed_warning": 1}
    rows, worst, worst_n = [], None, -1
    for window, rec in sorted(hist.items()):
        age = now - int(rec.get("recorded_at") or 0)
        resets = rec.get("resets_at")
        if resets and int(resets) > now:
            left = int(resets) - now
            when = f"resets in {left // 86400}d {(left % 86400) // 3600}h"
            live = True
        elif resets:
            when = "that reset has PASSED -- re-check before trusting"
            live = False
        else:
            when = "no reset time recorded"
            live = False
        status = str(rec.get("status") or "?")
        rows.append((window, status, when, age, live))
        n = rank.get(status, 2)
        if live and n > worst_n:
            worst, worst_n = status, n
    return rows, worst


def load_issues(path=None):
    p = Path(path) if path else ISSUES_FILE
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return d.get("issues", d) if isinstance(d, dict) else d


def inventory(issues):
    """Open issues, with what is known and what is deliberately not scored.

    Deliberately NOT a ranking. An issue whose candidates carry no
    effectiveness score has not been researched, and inventing one here
    would read as a measurement the next time anyone looks.
    """
    open_ = [i for i in issues if i.get("status") != "fixed"]
    fixed = [i for i in issues if i.get("status") == "fixed"]
    print(f"\nOPEN ISSUES ({len(open_)} open, {len(fixed)} fixed):")
    if not open_ and not fixed:
        print("  (none tracked -- see docs/open_issues.json)")
    for i in open_:
        owner = i.get("owner", "?")
        mark = "[YOURS]" if owner == "user-decision" else "[agent]"
        cands = i.get("candidates") or []
        scored = [c for c in cands if c.get("effectiveness") is not None]
        state = (f"{len(scored)}/{len(cands)} candidate(s) scored" if cands
                 else "no candidates yet -- not researched")
        print(f"\n  {mark} {i.get('id')}")
        print(f"     {i.get('summary','')[:100]}")
        print(f"     {state}")
        if owner == "user-decision":
            print("     not scored on purpose: this was put to the user as a design call")
    for i in fixed:
        print(f"\n  [done ] {i.get('id')}  ({i.get('fixed_by','')})")
    return open_


def rank_fixes(path, rows, worst):
    """Rank candidate fixes by effectiveness against draw.

    Each candidate: {name, tier, effectiveness (1-5), why, notes}.
    Effectiveness is a JUDGED input -- the script prints it as given and
    labels it judged. Draw is measured.
    """
    if path and path != "-":
        with open(path, encoding="utf-8") as fh:
            cands = json.load(fh)
    else:
        cands, skipped = [], []
        for i in load_issues():
            if i.get("status") == "fixed":
                continue
            if i.get("owner") == "user-decision":
                skipped.append(i.get("id"))
                continue
            for c in (i.get("candidates") or []):
                if c.get("effectiveness") is None:
                    skipped.append(f"{i.get('id')}/{c.get('name')} (unscored)")
                    continue
                c = dict(c, name=f"{i.get('id')}: {c.get('name')}")
                cands.append(c)
        if skipped:
            print("\n  NOT RANKED, on purpose:")
            for s in skipped:
                print(f"    - {s}")
        if not cands:
            print("\n  Nothing rankable yet. Research an issue and add scored")
            print("  candidates to docs/open_issues.json first.")
            return []

    blocked = worst is not None and worst != "allowed"
    print(f"\n{'':2}{'CANDIDATE':<34} {'TIER':>4} {'EFFECT':>7} {'DRAW':>6}  VERDICT")
    print("  " + "-" * 84)

    scored = []
    for c in cands:
        tier = int(c.get("tier", 0))
        eff = int(c.get("effectiveness", 0))
        draw = TIER_DRAW.get(tier, 1)
        # Free tiers can't divide by zero; they are simply best-in-class
        # for any effectiveness above nil.
        score = eff if draw == 0 else eff / (draw * 10)
        permitted = not (blocked and tier >= 3)
        scored.append((score, permitted, tier, eff, c))

    # Ties are broken toward LOWER churn, and only ONE candidate is ever
    # marked. An earlier version marked every candidate matching the top
    # score, so two mutually exclusive fixes both came back "RECOMMENDED"
    # -- which is not a ranking, it is a restatement of the problem.
    # `churn` is a judged input like effectiveness: how much existing data
    # or interface the fix breaks. Absent, it counts as 0.
    scored.sort(key=lambda r: (r[1], r[0], -int(r[4].get("churn", 0))),
                reverse=True)
    top = scored[0] if scored and scored[0][1] else None
    for row in scored:
        score, permitted, tier, eff, c = row
        verdict = ("" if permitted else "BLOCKED by budget")
        if top is not None and row is top:
            verdict = "<= RECOMMENDED"
        draw_s = "none" if TIER_DRAW.get(tier, 1) == 0 else "nested"
        print(f"  {c.get('name','?')[:34]:<34} {tier:>4} {eff:>6}/5 {draw_s:>6}  {verdict}")
        if c.get("why"):
            print(f"    why: {c['why']}")
    print("\n  EFFECT is judged, not measured -- it is the author's estimate of how")
    print("  much of the issue the fix actually removes. TIER and DRAW are measured.")
    if blocked:
        print(f"  Tier 3+ candidates are excluded: budget status is {worst!r}.")
    return [c for _, p, _, _, c in scored if p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", metavar="FIXES.json", nargs="?", const="-",
                    help="Rank candidates by effectiveness against draw. With no "
                         "argument, reads docs/open_issues.json.")
    ap.add_argument("--inventory", action="store_true",
                    help="List tracked open issues without ranking them.")
    args = ap.parse_args()

    print("Work available here, cheapest first. "
          "Do the cheapest option that can still answer the question.\n")
    for tier, what, detail in FREE_TIERS:
        print(f"  TIER {tier}  [no nested sessions]  {what}")
        print(f"          {detail}")
    print()

    sp_runs, _, sp_secs = measure(
        "stress_transcript_*.json",
        lambda d: d.get("results", []) if isinstance(d, dict) else [])
    dc_runs, _, dc_secs = measure(
        "drift_chain_*.json",
        lambda d: [t for c in d.get("chains", []) for t in c.get("turns", [])])
    print(f"  TIER 3  [ONE NESTED SESSION PER CASE]  run_stress_prompts.py")
    print(f"          measured over {sp_runs} run(s): {fmt(sp_secs)}")
    print(f"  TIER 4  [ONE NESTED SESSION PER TURN PER CHAIN]  run_drift_chain.py")
    print(f"          measured over {dc_runs} run(s): {fmt(dc_secs)}")
    if dc_secs:
        print(f"          a default 3x6 run = 18 sessions "
              f"~{18*(sum(dc_secs)/len(dc_secs))/60:.0f} min at the measured mean")
    print()

    rows, worst = budget()
    print("BUDGET -- every window observed, with the age of each observation:")
    if not rows:
        print("  (none recorded yet)")
        print("  Record one: get_session -> external_metadata.rate_limit_info, then")
        print("  python3 .claude/hooks/tier34_guard.py --record <status> <window> <resetsAt>")
    for window, status, when, age, live in rows:
        mark = "  " if live else "! "
        print(f"  {mark}{window:<12} {status:<16} {when:<44} "
              f"(observed {age // 60} min ago)")
    if worst and worst != "allowed":
        print(f"\n  BINDING: {worst!r} -- tier 3 and 4 are OFF. Do tier 0-2 work.")
    elif worst:
        print("\n  All observed windows allowed.")
    print("  No remaining-percentage or token budget is exposed to a session;")
    print("  none is estimated here.")

    if args.inventory or args.rank:
        inventory(load_issues())
    if args.rank:
        rank_fixes(args.rank, rows, worst)

    copies = sorted(glob.glob("/tmp/eldara-chain-*/eldara/saves/current.json")) + \
        sorted(glob.glob("/tmp/eldara-stress-*/eldara/saves/current.json"))
    if copies:
        print(f"\nUNMINED DATA: {len(copies)} retained campaign copy(ies) on disk "
              "-- tier 0 work, already paid for.")
        for c in copies:
            try:
                with open(c, encoding="utf-8") as fh:
                    s = json.load(fh)
                d = s.get("in_world_date") or {}
                print(f"  - turn {s.get('turn')}, day {d.get('day')} "
                      f"{d.get('month')}, {len(s.get('continuity_notes') or [])} "
                      f"note(s)  {os.path.dirname(os.path.dirname(c))}")
            except (OSError, json.JSONDecodeError):
                print(f"  - (unreadable) {c}")


if __name__ == "__main__":
    main()
