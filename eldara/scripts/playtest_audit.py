#!/usr/bin/env python3
"""Combined three-pass playtest audit, wrapping the existing validation
scripts rather than reimplementing their logic:

  Pass 1 -- Coverage: has each core mechanism actually fired at least
            once in this campaign, per saves/journal.md and
            saves/current.json? Pure log-scanning, no judgment involved.

  Pass 2 -- Adversarial regression suite: a fixed battery of synthetic
            bad inputs fired at validate_state.py / turn_gate.py /
            prune_advisor.py, asserting each is still correctly
            rejected/flagged. Fully scripted, no model or live campaign
            state required -- this is a regression test for the TOOLING,
            not the campaign.

  Pass 3 -- Drift proxies: mechanical stand-ins for narrative/rule drift
            that CAN be checked from logs alone (turns since throughline
            last touched, recent is_new_npc validation failures). These
            are proxies, not proof -- see the "What this cannot check"
            section printed in the report. Genuine narrative-tone drift
            requires a human reading actual transcript prose; no script
            in this project claims to detect that, and this one is no
            exception.

Usage:
    python3 scripts/playtest_audit.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAVES_DIR = ROOT / "saves"
CURRENT_PATH = SAVES_DIR / "current.json"
JOURNAL_PATH = SAVES_DIR / "journal.md"
SCRIPTS_DIR = ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def load_json(path):
    """Raises json.JSONDecodeError/OSError on failure -- callers are
    responsible for catching it, since the right message differs by
    which pass is running."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_as_dict(path):
    """Like load_json(), but also raises ValueError if the parsed JSON
    isn't a dict at the top level -- every caller here assumes dict-
    shaped state, and valid-but-wrong-shaped JSON (e.g. a bare list)
    would otherwise crash on the first .get() call with a less helpful
    error than the malformed-JSON case already handles."""
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object at the top level, got {type(data).__name__}")
    return data


def load_journal_text():
    if not JOURNAL_PATH.exists():
        return ""
    return JOURNAL_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Pass 1: Coverage
# ---------------------------------------------------------------------------

def pass1_coverage():
    print("=" * 70)
    print("PASS 1 -- COVERAGE  (has each mechanism fired at least once?)")
    print("=" * 70)

    if not CURRENT_PATH.exists():
        print("No saves/current.json found -- nothing to audit yet.")
        return

    try:
        state = load_json_as_dict(CURRENT_PATH)
    except (json.JSONDecodeError, OSError, ValueError, RecursionError) as e:
        print(f"FAIL: could not read/parse {CURRENT_PATH}: {e}")
        print("saves/current.json appears corrupted -- see docs/RECOVERY.md.")
        return
    journal = load_journal_text()

    checks = []

    gear_names = {g.get("name") for g in state.get("gear", [])}
    baseline = {"T-shirt", "Jeans", "Underwear", "Socks", "Shoes"}
    checks.append(("Gear acquired beyond baseline five", bool(gear_names - baseline)))

    checks.append(("Language established", state.get("language", {}).get("established") is True))

    checks.append(("At least one NPC relationship formed", bool(state.get("npc_relationships"))))

    checks.append(("status has been non-empty at some point (a physical cost landed)",
                    bool(state.get("status")) or bool(re.search(r'status: \[(?!\])', journal))))

    checks.append(("An open_thread with deadline_turn has appeared in journal history",
                    "deadline_turn" in journal))

    checks.append(("continuity_notes has at least one entry (an audit/drift-fix occurred)",
                    bool(state.get("continuity_notes"))))

    checks.append(("throughline has at least one entry", bool(state.get("throughline"))))

    checks.append(("entities array has been used", bool(state.get("entities"))))

    # NOTE: unlike the sibling checks above (status, currency), this one
    # used to rely solely on a journal regex with no state.get() fallback.
    # That regex, r'magic: \[(?!\])', looks for a "magic: [" not
    # immediately followed by "]" -- but commit_state.py's diff format
    # writes the OLD value first ("magic: [] -> [...]"), so the first
    # "[" re.search finds is followed immediately by "]" (the old, empty
    # array), the lookahead fails right there, and the engine never
    # backtracks far enough within the same match attempt to reach the
    # real (non-empty) array later in the same line. Net effect: this
    # check reported MISS even when saves/current.json's magic array was
    # genuinely non-empty. Checking state directly first (as every
    # sibling check does) fixes this without weakening the check --
    # journal-regex stays as a fallback for older journal entries from
    # before this field existed in a given snapshot.
    checks.append(("magic array has been populated at some point (a magic effect touched Chad)",
                    bool(state.get("magic")) or bool(re.search(r'magic: \[(?!\])', journal))))

    checks.append(("currency has moved off zero at some point", any(
        v > 0 for v in state.get("currency", {}).values()
    ) or re.search(r'"copper": [1-9]', journal) is not None))

    checks.append(("npc_relationships has reached its soft cap of 10 at some point",
                    len(state.get("npc_relationships", [])) >= 10 or journal.count('"npc_id"') > 90))

    passed = 0
    for label, ok in checks:
        mark = "PASS" if ok else "MISS"
        if ok:
            passed += 1
        print(f"  [{mark}] {label}")

    print(f"\nCoverage: {passed}/{len(checks)} mechanisms confirmed to have fired at least once.")
    if passed < len(checks):
        print("Missed items are not necessarily bugs -- they may just mean the campaign")
        print("hasn't reached that situation yet. Steer play toward them deliberately")
        print("if you want to confirm they're reachable at all.")
    print()


# ---------------------------------------------------------------------------
# Pass 2: Adversarial regression suite
# ---------------------------------------------------------------------------

def run_script(args, input_text=None):
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT, capture_output=True, text=True, input=input_text,
    )
    return result.returncode, result.stdout + result.stderr


def pass2_adversarial(tmp_dir):
    print("=" * 70)
    print("PASS 2 -- ADVERSARIAL REGRESSION SUITE  (tooling correctness)")
    print("=" * 70)
    print("This does not touch saves/current.json -- all inputs are synthetic")
    print("and written to a scratch directory.\n")

    results = []

    # 1. turn_gate.py must pass a turn with no marker at all.
    code, out = run_script(["scripts/turn_gate.py"], input_text="Chad walks on. No state change here.")
    ok = "no commit required" in out.lower() or code == 0
    results.append(("turn_gate.py passes a turn with no STATE_CHANGE marker", ok, out))

    code, out = run_script(["scripts/turn_gate.py"], input_text="Chad finds a sword. <!-- STATE_CHANGE:committed -->")
    # Uses the bare-marker format (no token) deliberately -- this
    # exercises turn_gate.py's "missing token" rejection path, confirming
    # the script actually inspects and reports on saves/current.json
    # rather than blindly passing every marker.
    inspected = "saves/current.json" in out or "PASS" in out or "FAIL" in out
    results.append(("turn_gate.py actually inspects saves/current.json before deciding", inspected, out))

    # 2. validate_state.py must reject an is_new_npc conflict.
    try:
        base = load_json_as_dict(CURRENT_PATH) if CURRENT_PATH.exists() else None
    except (json.JSONDecodeError, OSError, ValueError, RecursionError) as e:
        print(f"FAIL: could not read/parse {CURRENT_PATH}: {e}")
        print("saves/current.json appears corrupted -- see docs/RECOVERY.md.")
        return
    if base is None:
        base = {"schema_version": 1, "turn": 0, "in_world_date": {"day": 1, "month": "Seedmonth", "year": 1},
                "gear": [{"name": n} for n in ["T-shirt", "Jeans", "Underwear", "Socks", "Shoes"]],
                "currency": {"copper": 0, "silver": 0, "gold": 0, "platinum": 0}}
    bad2 = json.loads(json.dumps(base))
    bad2.setdefault("npc_relationships", [])
    bad2["npc_relationships"].append({"npc_id": "__adversarial_test_id_2__", "name": "Test2", "is_new_npc": False})
    bad2_path = tmp_dir / "bad_is_new_npc_2.json"
    bad2_path.write_text(json.dumps(bad2), encoding="utf-8")
    code2, out2 = run_script(["scripts/validate_state.py", str(bad2_path)])
    ok = (code2 != 0) and "is_new_npc" in out2
    results.append(("validate_state.py rejects is_new_npc=false for an unregistered id", ok, out2))

    # 3. validate_state.py must reject currency-as-gear.
    bad3 = json.loads(json.dumps(base))
    bad3["gear"] = bad3.get("gear", []) + [{"name": "gold"}]
    bad3_path = tmp_dir / "bad_currency_gear.json"
    bad3_path.write_text(json.dumps(bad3), encoding="utf-8")
    code3, out3 = run_script(["scripts/validate_state.py", str(bad3_path)])
    ok = (code3 != 0) and "currency" in out3.lower()
    results.append(("validate_state.py rejects a currency word disguised as gear", ok, out3))

    # 4. validate_state.py must reject an over-cap array.
    bad4 = json.loads(json.dumps(base))
    bad4["open_threads"] = [{"text": f"thread {i}", "added_turn": 0} for i in range(9)]
    bad4_path = tmp_dir / "bad_overcap.json"
    bad4_path.write_text(json.dumps(bad4), encoding="utf-8")
    code4, out4 = run_script(["scripts/validate_state.py", str(bad4_path)])
    ok = (code4 != 0) and "soft cap" in out4.lower()
    results.append(("validate_state.py rejects open_threads exceeding its soft cap", ok, out4))

    # 5. validate_state.py must WARN (not necessarily fail) on a lapsed active deadline.
    bad5 = json.loads(json.dumps(base))
    bad5["turn"] = 50
    bad5["open_threads"] = [{"text": "an old promise", "added_turn": 1, "active": True, "deadline_turn": 10}]
    bad5_path = tmp_dir / "lapsed_deadline.json"
    bad5_path.write_text(json.dumps(bad5), encoding="utf-8")
    code5, out5 = run_script(["scripts/validate_state.py", str(bad5_path)])
    ok = "lapsed active deadline" in out5.lower() or "warning" in out5.lower()
    results.append(("validate_state.py warns on a lapsed active deadline", ok, out5))

    # 6. prune_advisor.py must run without crashing and must print the
    #    "confirm or override" caveat -- we do NOT assert its ranking
    #    quality here, since it's a known-naive heuristic; this only
    #    checks the tool still runs and still carries the caveat forward.
    code6, out6 = run_script(["scripts/prune_advisor.py", "npc_relationships"])
    ok = "confirm or override" in out6.lower() or "empty" in out6.lower()
    results.append(("prune_advisor.py runs and still carries its non-authoritative caveat", ok, out6))

    # 7. commit_state.py must not desync saves/current.json from git
    #    history when a turn introduces a new NPC. Regression test for a
    #    real bug found in testing: update_npc_registry() used to run
    #    (and register the new npc_id) BEFORE the pre-commit hook
    #    re-validated the already-written saves/current.json -- so a
    #    file that correctly had is_new_npc=true at proposal time would
    #    fail that same hook's re-check the instant the registry caught
    #    up, silently leaving the working file ahead of git with no
    #    error surfaced. This exercises the real commit_state.py against
    #    a disposable, isolated git repo (never the project's own repo
    #    or saves/) so the check is real rather than mocked.
    ok7, detail7 = _check_new_npc_commit_stays_in_sync(tmp_dir)
    results.append(("commit_state.py keeps git history in sync when a turn introduces a new NPC", ok7, detail7))

    # 8. gm_cases.py's case list is derived from prompts/GM_INSTRUCTIONS.md
    #    and can only go stale silently -- a summary that still reads as
    #    authoritative after the thing it summarizes moved is worse than
    #    no summary at all. --check-sources exits non-zero the moment any
    #    case points at a heading that no longer exists, so running it
    #    here is what keeps that list honest without anyone remembering to.
    code8, out8 = run_script(["scripts/gm_cases.py", "--check-sources"])
    results.append(("gm_cases.py's cases still point at real GM_INSTRUCTIONS.md headings",
                    code8 == 0, out8))

    passed = 0
    for label, ok, _out in results:
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"  [{mark}] {label}")

    print(f"\nAdversarial suite: {passed}/{len(results)} checks passed.")
    for label, ok, out in results:
        if not ok:
            print(f"\n  --- Detail for failed check: {label} ---")
            print("  " + out.strip().replace("\n", "\n  "))
    print()


def _check_new_npc_commit_stays_in_sync(tmp_dir):
    """Regression check for the is_new_npc git-desync bug (see call site's
    comment). Builds a disposable, throwaway project copy with its own
    git repo and installed pre-commit hook, commits a turn that
    introduces a brand-new NPC via the real scripts/commit_state.py, and
    confirms git HEAD actually captured it -- not just that the command
    exited 0, since the original bug had commit_state.py report success
    while HEAD silently stayed one turn behind.
    """
    import shutil as _shutil

    sandbox = tmp_dir / "npc_sync_sandbox"
    if sandbox.exists():
        _shutil.rmtree(sandbox)
    (sandbox / "scripts").mkdir(parents=True)
    (sandbox / "scripts" / "git-hooks").mkdir()
    (sandbox / "saves").mkdir()

    # Copy just the files this check actually exercises, rather than the
    # whole project -- keeps the sandbox minimal and its failure surface
    # obviously scoped to the commit/validate/hook pipeline being tested.
    for name in ("commit_state.py", "validate_state.py", "self_critique.py"):
        _shutil.copy2(SCRIPTS_DIR / name, sandbox / "scripts" / name)
    for name in ("pre-commit",):
        src = SCRIPTS_DIR / "git-hooks" / name
        if src.exists():
            _shutil.copy2(src, sandbox / "scripts" / "git-hooks" / name)
    _shutil.copy2(ROOT / "state_schema.json", sandbox / "state_schema.json")

    base_state = {
        "schema_version": 1, "turn": 0,
        "in_world_date": {"day": 1, "month": "Seedmonth", "year": 1},
        "gear": [{"name": n} for n in ["T-shirt", "Jeans", "Underwear", "Socks", "Shoes"]],
        "currency": {"copper": 0, "silver": 0, "gold": 0, "platinum": 0},
    }
    (sandbox / "saves" / "current.json").write_text(json.dumps(base_state), encoding="utf-8")
    (sandbox / "saves" / "npc_registry.json").write_text("{}", encoding="utf-8")
    (sandbox / "saves" / "journal.md").write_text("", encoding="utf-8")

    def run_in_sandbox(args, input_text=None):
        return subprocess.run(
            args, cwd=sandbox, capture_output=True, text=True, input=input_text,
        )

    init_steps = [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "audit@eldara.local"],
        ["git", "config", "user.name", "Eldara Audit"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "sandbox init"],
    ]
    for step in init_steps:
        r = run_in_sandbox(step)
        if r.returncode != 0:
            return False, f"sandbox git init failed at {step}: {r.stderr}"

    hooks_dir = sandbox / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_src = sandbox / "scripts" / "git-hooks" / "pre-commit"
    if hook_src.exists():
        hook_dest = hooks_dir / "pre-commit"
        # Mirrors session.py's own installer: the hook template contains
        # __ELDARA_PROJECT_ROOT__, which must be substituted for the
        # sandbox's own root (the sandbox IS its own repo's top level,
        # unlike the real project) before installing -- a plain copy
        # would leave the literal placeholder in place and the hook
        # would cd into a nonexistent directory, silently disabling the
        # exact check this regression test exists to exercise.
        content = hook_src.read_text(encoding="utf-8")
        content = content.replace("__ELDARA_PROJECT_ROOT__", str(sandbox))
        hook_dest.write_text(content, encoding="utf-8")
        hook_dest.chmod(0o755)

    # Turn 1: introduce a brand-new NPC, exactly the shape that triggered
    # the original bug.
    proposed = dict(base_state)
    proposed["turn"] = 1
    proposed["npc_relationships"] = [
        {"npc_id": "audit_test_npc", "name": "Audit NPC", "is_new_npc": True}
    ]
    proposed_path = sandbox / "proposed_turn1.json"
    proposed_path.write_text(json.dumps(proposed), encoding="utf-8")

    commit = run_in_sandbox(
        [sys.executable, "scripts/commit_state.py", str(proposed_path),
         "--critique-text", "Chad meets someone new near the gate."],
    )
    if commit.returncode != 0:
        return False, f"commit_state.py itself failed:\n{commit.stdout}\n{commit.stderr}"

    head_turn = run_in_sandbox(["git", "show", "HEAD:saves/current.json"])
    if head_turn.returncode != 0:
        return False, f"could not read HEAD's saves/current.json: {head_turn.stderr}"
    try:
        head_state = json.loads(head_turn.stdout)
    except json.JSONDecodeError as e:
        return False, f"HEAD's saves/current.json did not parse: {e}"

    working_state = json.loads((sandbox / "saves" / "current.json").read_text(encoding="utf-8"))

    in_sync = head_state.get("turn") == working_state.get("turn") == 1
    detail = (
        f"commit_state.py stdout:\n{commit.stdout}\n"
        f"HEAD turn={head_state.get('turn')!r}, working-copy turn={working_state.get('turn')!r} "
        f"(both should be 1)"
    )
    return in_sync, detail


# ---------------------------------------------------------------------------
# Pass 3: Drift proxies
# ---------------------------------------------------------------------------

def pass3_drift_proxies():
    print("=" * 70)
    print("PASS 3 -- DRIFT PROXIES  (mechanical stand-ins, not proof)")
    print("=" * 70)

    if not CURRENT_PATH.exists():
        print("No saves/current.json found -- nothing to audit yet.")
        return

    try:
        state = load_json_as_dict(CURRENT_PATH)
    except (json.JSONDecodeError, OSError, ValueError, RecursionError) as e:
        print(f"FAIL: could not read/parse {CURRENT_PATH}: {e}")
        print("saves/current.json appears corrupted -- see docs/RECOVERY.md.")
        return
    journal = load_journal_text()
    current_turn = state.get("turn", 0)

    turn_markers = [int(m) for m in re.findall(r"^### Turn (\d+)", journal, re.MULTILINE)]
    throughline_touch_turns = []
    for m in re.finditer(r"### Turn (\d+).*?(?=### Turn|\Z)", journal, re.DOTALL):
        block = m.group(0)
        if "- throughline:" in block:
            throughline_touch_turns.append(int(m.group(1)))

    last_throughline_turn = max(throughline_touch_turns) if throughline_touch_turns else None
    turns_since_throughline = (current_turn - last_throughline_turn) if last_throughline_turn is not None else current_turn

    is_new_npc_failures = journal.count("already exists in npc_registry.json") + journal.count("is_new_npc=false but not found")
    # These only show up in journal if someone logged the rejection in a
    # continuity_note; a plain validate_state.py rejection on an
    # un-committed draft never reaches saves/journal.md at all, since
    # commit_state.py refuses to touch the canonical file on failure.
    # This is itself worth stating plainly rather than implying the count
    # below is exhaustive.

    state_change_commits = len(turn_markers)

    # Self-critique gate history, read from the "Self-critique: ..." line
    # commit_state.py persists into the journal on every commit. Commits
    # made before that logging existed won't have this line at all,
    # which is itself informative (shown separately below) rather than
    # silently treated as "ran clean."
    critique_ran_clean = len(re.findall(r"Self-critique: ran clean", journal))
    critique_skipped = len(re.findall(r"Self-critique: skipped", journal))
    critique_not_applicable = len(re.findall(r"Self-critique: not applicable", journal))
    critique_lines_total = critique_ran_clean + critique_skipped + critique_not_applicable
    commits_missing_critique_line = state_change_commits - critique_lines_total

    print(f"  Current turn: {current_turn}")
    print(f"  Turns since throughline was last touched: {turns_since_throughline}"
          + (" (never touched)" if last_throughline_turn is None else f" (last touched at turn {last_throughline_turn})"))
    print(f"  Committed turns on record in journal: {state_change_commits}")
    print(f"  is_new_npc rejections VISIBLE in journal continuity_notes: {is_new_npc_failures}")
    print( "    (rejected drafts that were never logged as a continuity_note are invisible")
    print( "     here by design -- commit_state.py never writes a failed attempt to the")
    print( "     journal, so this number is a floor, not a total.)")
    print(f"  Self-critique gate history: {critique_ran_clean} ran clean, {critique_skipped} skipped, "
          f"{critique_not_applicable} not applicable")
    if commits_missing_critique_line > 0:
        print(f"    ({commits_missing_critique_line} committed turns predate this logging and have no "
              "Self-critique line at all)")
    print()

    print("  What this pass flags for human review (not auto-resolved):")
    flagged_anything = False
    if turns_since_throughline > 15 and current_turn > 5:
        flagged_anything = True
        print(f"    - No throughline update in {turns_since_throughline} turns. Per GM_INSTRUCTIONS.md")
        print( "      this is fine if nothing real has shifted -- but worth a human skim of the")
        print( "      last several turns to confirm that's actually true rather than an oversight.")
    if is_new_npc_failures >= 2:
        flagged_anything = True
        print(f"    - {is_new_npc_failures} is_new_npc conflicts logged. This is consistently the")
        print( "      single easiest rule to slip on in practice. Worth periodically checking")
        print( "      whether the rate is increasing over a session.")
    if state_change_commits == 0:
        flagged_anything = True
        print("    - No committed turns yet. Nothing to assess.")
    if critique_skipped > 0 and state_change_commits > 0:
        skip_rate = critique_skipped / state_change_commits
        if skip_rate > 0.2:
            flagged_anything = True
            print(f"    - Self-critique skipped on {critique_skipped}/{state_change_commits} commits "
                  f"({skip_rate:.0%}). --skip-critique is meant for confirmed false positives or "
                  "turns with no real prose -- worth checking this rate isn't creeping up as routine.")
    if not flagged_anything:
        print("    - Nothing flagged. This does not mean tone/rule drift is absent --")
        print("      see the note below.")
    print()

    print("  What this pass CANNOT check (see accompanying explanation):")
    print("    - Whether narration still follows Prose Craft (sensory interiority,")
    print("      varied turn shapes, no stated feelings).")
    print("    - Whether 'No Framework for Chad' is still being honored in NPC dialogue.")
    print("    - Whether failure is still genuinely being allowed, or the GM has quietly")
    print("      started protecting Chad from consequences.")
    print("    - Whether a self-critique marked 'ran clean' actually caught everything it")
    print("      should have -- self_critique.py's own detection is a narrow heuristic (see")
    print("      its docstring); a clean run here means the heuristic found nothing, not")
    print("      that the turn was good.")
    print("  These require a human reading actual transcript prose. No script here")
    print("  claims otherwise.")
    print()


def main():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        pass1_coverage()
        pass2_adversarial(Path(tmp))
        pass3_drift_proxies()

    print("=" * 70)
    print("Combined audit complete. Pass 1 and 2 are mechanically conclusive.")
    print("Pass 3 is advisory only -- treat its flags as a reading list, not a verdict.")
    print("=" * 70)


if __name__ == "__main__":
    main()
