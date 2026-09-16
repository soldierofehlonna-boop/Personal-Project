#!/usr/bin/env python3
"""PreToolUse guard on Bash: refuse to launch a tier-3/4 nested-session run
unless it is safe to do so.

Tier 3/4 scripts spawn one `claude -p` session per case (run_stress_prompts.py)
or per turn per chain (run_drift_chain.py). A default drift chain is 18 nested
sessions and roughly 69 minutes. That cost is invisible until the rate limit
warns, which is exactly the kind of mistake a human makes once and an agent
makes repeatedly.

WHAT THIS CAN AND CANNOT ENFORCE -- read this before trusting it
----------------------------------------------------------------
The kill switch and the concurrency guard are fully mechanical: they read
the filesystem and the process table, and nothing the agent believes can
talk them out of it.

This docstring previously claimed THREE such guards. That was wrong, and
a code review caught it: the containment guard compared paths that could
never be equal, so it had never once fired -- dead code in the shape of
protection, counted on precisely because it was written down here. It has
been replaced with a narrower check that can actually fire. Treat this
paragraph as a claim to re-verify, not a guarantee; it has been wrong
before.

The fourth (FRESH) is different and must not be oversold. No live
rate-limit status is readable from a shell on this machine -- it was
looked for: `~/.claude.json` carries only feature flags, and the session
transcript's "rate_limit" hits are the agent's own commands echoed back.
The only source is the `get_session` MCP call, which only the agent can
make. So this guard cannot check the budget itself. What it CAN do is
refuse to run unless a recent check has been recorded, which converts
"check the budget" from a rule the agent may forget into a precondition
it cannot skip.

That defends against the realistic failure -- forgetting to check, or
relying on a reading from hours ago. It does NOT defend against an agent
writing a false status file. That is not the threat being modelled, and
claiming otherwise would make this security theatre. The status file is
a memory aid with teeth, not an oracle.

RECORDING A CHECK
-----------------
    python3 .claude/hooks/tier34_guard.py --record <status> <window> <resetsAt>
    python3 .claude/hooks/tier34_guard.py --record allowed_warning seven_day 1789959600

Pass all three. rate_limit_info reports only the window currently
BINDING, so the window name is part of the reading, not decoration -- the
same "allowed_warning" means a four-hour wait on five_hour and a
four-day wait on seven_day.

Only ever record what `get_session` actually returned in
external_metadata.rate_limit_info.status.

BYPASS
------
    touch .claude/ALLOW_EXPENSIVE_RUN     # one run, consumed on use

The bypass is deliberately single-use: it is deleted the moment it lets a
run through, so an override cannot silently become the new default.

Exit codes: 0 allow (silent), 0 with deny JSON to block.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CLAUDE_DIR = REPO / ".claude"
STATUS_FILE = CLAUDE_DIR / "rate_limit_status.json"
HISTORY_FILE = CLAUDE_DIR / "rate_limit_history.json"
KILL_SWITCH = CLAUDE_DIR / "BLOCK_EXPENSIVE_RUNS"
BYPASS = CLAUDE_DIR / "ALLOW_EXPENSIVE_RUN"

# How recent a recorded rate-limit check must be. The window it describes is
# five_hour and rolling, so a reading from 30 minutes ago is still broadly
# true; one from this morning is not.
MAX_AGE_SECONDS = 30 * 60

# Must look like RUNNING one of these, not merely naming one. The pattern
# used to match the filename anywhere, so `grep run_drift_chain.py` and
# `git show HEAD:...run_drift_chain.py` were denied for want of a fresh
# budget record -- read-only commands blocked by a guard about spending,
# which pushes toward the single-use bypass rather than away from it.
TIER34 = re.compile(
    r"(?:^|[\s;&|])(?:python3?|py)\s+\S*\b(run_stress_prompts|run_drift_chain)\.py\b"
    r"|(?:^|[\s;&|])\./\S*\b(run_stress_prompts|run_drift_chain)\.py\b")

# Flags that make a tier-3/4 script harmless: it prints and exits without
# spawning anything. Blocking these would train the agent to route around
# the guard, which is worse than not having it.
HARMLESS = re.compile(r"(^|\s)--(help|dry-run|list-stress-prompts)(\s|$)|(^|\s)-h(\s|$)")

# Shell operators that separate one command from the next. The harmless
# check used to be applied to the WHOLE command string, so
# `run_drift_chain.py --help && run_drift_chain.py --chains 3` was read as
# harmless and bypassed all four guards -- the --help in segment one
# excused the real run in segment two. Every segment is now judged on its
# own, and the guards fire if ANY segment is a real invocation.
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")


def dangerous_segments(command):
    """Segments that actually launch a tier-3/4 run."""
    return [s for s in SEGMENT_SPLIT.split(command)
            if TIER34.search(s) and not HARMLESS.search(s)]


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def allow():
    sys.exit(0)


def record(status, window=None, resets_at=None):
    """Record one observation, and append it to a per-window history.

    rate_limit_info reports only the ONE window currently binding -- it
    read five_hour this morning and seven_day once that window reset. So
    a single snapshot can never show both. The history keeps the last
    observation of EACH window, which is the only way to answer "what is
    the weekly position" while the five-hour window happens to be the one
    reporting. Entries go stale and are labelled with their age rather
    than quietly presented as current.
    """
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    rec = {
        "status": status,
        "window": window,
        "resets_at": int(resets_at) if resets_at else None,
        "recorded_at": now,
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "source": "get_session -> external_metadata.rate_limit_info",
    }
    STATUS_FILE.write_text(json.dumps(rec, indent=2), encoding="utf-8")

    hist = {}
    if HISTORY_FILE.exists():
        try:
            hist = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            hist = {}
    if window:
        hist[window] = rec
        HISTORY_FILE.write_text(json.dumps(hist, indent=2), encoding="utf-8")

    where = f" [{window}]" if window else ""
    when = ""
    if resets_at:
        left = int(resets_at) - now
        when = f", resets in {left // 3600}h {(left % 3600) // 60}m"
    print(f"recorded {status!r}{where}{when} at "
          f"{time.strftime('%H:%M:%SZ', time.gmtime(now))}")


def long_window_clear():
    """Is a day-or-longer window on record, recent, and allowed?

    The budget guard used to check only `status == "allowed"` on the single
    most recent reading, ignoring which window it described. So a
    five_hour:allowed record green-lit an 18-session tier-4 run while
    session_cost_guide.budget() returned "unknown-long" for the same
    history and CLAUDE.md said short-window clearance is not clearance.
    The fail-open was closed in the advisory script and left open in the
    gate that actually enforces -- the wrong one of the two to miss.

    rate_limit_info reports one window at a time, so a clear five-hour
    reading says nothing about the weekly position, and the weekly one is
    what blocks a run for days.
    """
    if not HISTORY_FILE.exists():
        return False, "no window history recorded at all"
    try:
        hist = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return False, f"window history unreadable ({e})"
    now = int(time.time())
    for window, rec in hist.items():
        name = str(window).lower()
        if not ("day" in name or "week" in name):
            continue
        if str(rec.get("status")) != "allowed":
            return False, (f"{window} last read {rec.get('status')!r}")
        resets = rec.get("resets_at")
        if resets and int(resets) <= now:
            return False, f"{window}'s recorded reset has already passed"
        age = now - int(rec.get("recorded_at") or 0)
        if age > MAX_AGE_SECONDS:
            return False, (f"{window} was observed {age // 60} min ago "
                           f"(max {MAX_AGE_SECONDS // 60})")
        return True, f"{window} allowed"
    return False, ("only a short window has been observed; a clear five-hour "
                   "reading is not clearance for a run that spans days")


def running_tier34():
    """Tier-3/4 processes already running, excluding this hook itself.

    This is the guard that would have caught launching three chains in
    parallel without weighing what three concurrent runs cost.
    """
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []          # can't tell -> don't block on a guess
    me = str(os.getpid())
    hits = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, args = parts
        if pid == me or "tier34_guard" in args:
            continue
        if TIER34.search(args) and not HARMLESS.search(args):
            hits.append(f"pid {pid}: {args[:90]}")
    return hits


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--record":
        if len(sys.argv) < 3:
            print("usage: tier34_guard.py --record <status> [window] [resetsAt]",
                  file=sys.stderr)
            sys.exit(1)
        record(sys.argv[2],
               sys.argv[3] if len(sys.argv) > 3 else None,
               sys.argv[4] if len(sys.argv) > 4 else None)
        return

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()            # malformed input is not the agent's fault
    command = str((payload.get("tool_input") or {}).get("command") or "")

    if not dangerous_segments(command):
        allow()

    # --- guard 1: kill switch (mechanical) ---
    if KILL_SWITCH.exists():
        deny(f"BLOCKED: {KILL_SWITCH} exists. Expensive nested-session runs "
             "are switched off. Remove that file to re-enable them.")

    # --- guard 2: containment ---
    # The previous version of this guard COULD NOT FIRE. It compared
    # $CLAUDE_PROJECT_DIR/saves/current.json against
    # eldara/saves/current.json -- but the project dir is the repo root,
    # which has no saves/ at all, so the paths never matched and the check
    # was dead code wearing the shape of protection. It was also described
    # to the user as one of three working mechanical guards. A check that
    # can never fire is worse than no check, because it is counted on.
    #
    # What it was guarding against also turned out not to be reachable the
    # way it imagined: both harnesses derive ROOT from their own location
    # and copy FROM the live campaign into a throwaway, so invoking them
    # normally never makes the live campaign the working tree.
    #
    # What IS worth refusing is an invocation that has been pointed at the
    # live saves explicitly -- a path argument or an env override aimed at
    # eldara/saves. That is narrow, but it is real and it can fire.
    live_saves = str((REPO / "eldara" / "saves").resolve())
    for seg in dangerous_segments(command):
        if live_saves in seg or "eldara/saves" in seg:
            deny("BLOCKED: this invocation names the LIVE campaign's saves "
                 f"directory ({live_saves}). These harnesses commit and push; "
                 "they must run against their own throwaway copies, which they "
                 "make for themselves. Drop the path argument.")

    # --- guard 3: concurrency (mechanical) ---
    busy = running_tier34()
    if busy:
        deny("BLOCKED: a tier-3/4 run is already in flight, and each one "
             "spawns a nested session per case/turn. Starting another "
             "multiplies the draw.\n  " + "\n  ".join(busy) +
             "\nWait for it to finish, or kill it deliberately first.")

    # --- guard 4: a fresh recorded budget check (enforces, does not verify) ---
    # Computed BEFORE the bypass is considered, so an override is only spent
    # when it actually changes the outcome. Checking the bypass first burned
    # it on runs that would have passed anyway -- an override that evaporates
    # without doing anything teaches you to touch the file pre-emptively,
    # which is how a single-use escape hatch becomes the default path.
    problem = None
    if not STATUS_FILE.exists():
        problem = ("no rate-limit check on record.\n"
                   "Call get_session (claude-code-remote MCP, session_id omitted), "
                   "read external_metadata.rate_limit_info.status, then record it:\n"
                   "  python3 .claude/hooks/tier34_guard.py --record <status>\n"
                   "This hook cannot read the budget itself -- no live rate-limit "
                   "source is reachable from a shell here.")
    else:
        try:
            rec = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            rec = None
            problem = (f"{STATUS_FILE} is unreadable ({e}). Re-record with "
                       "--record after calling get_session.")
        if rec is not None:
            age = int(time.time()) - int(rec.get("recorded_at") or 0)
            status = str(rec.get("status") or "")
            if age > MAX_AGE_SECONDS:
                problem = (f"the recorded rate-limit check is {age // 60} minutes "
                           f"old (max {MAX_AGE_SECONDS // 60}). Re-check with "
                           "get_session and re-record before starting a run this "
                           "expensive.")
            elif status != "allowed":
                problem = (f"last recorded rate-limit status is {status!r}, not "
                           "'allowed'.\nCLAUDE.md: on allowed_warning, do not start "
                           "a tier 3 or 4 run -- report the reset time and offer "
                           "tier 0-2 work instead.\nTier 0 (re-analysing artifacts "
                           "already on disk) has repeatedly beaten tier 4 on "
                           "findings per minute.")

    if problem is None:
        ok_long, why = long_window_clear()
        if not ok_long:
            problem = (f"the WEEKLY window is not clear: {why}.\n"
                       f"Only one window is reported at a time, so a clear "
                       f"short window says nothing about the weekly position "
                       f"-- and the weekly one is what blocks a run for days. "
                       f"Record a day-or-longer window with "
                       f"--record <status> <window> <resetsAt>.")

    if problem is None:
        allow()

    if BYPASS.exists():
        try:
            BYPASS.unlink()        # single use, consumed only because it mattered
        except OSError:
            pass
        allow()

    deny("BLOCKED: " + problem +
         "\nOverride for one run: touch .claude/ALLOW_EXPENSIVE_RUN")


if __name__ == "__main__":
    main()
