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

    # Checks are identified by their printed label, not by position: the
    # suite counts itself, and nothing here depends on ordering. Append or
    # insert freely -- deliberately un-numbered so that two branches each
    # adding a check don't produce comments that disagree with reality
    # even when the text merges without conflict.

    # turn_gate.py must pass a turn with no marker at all.
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

    # validate_state.py must reject an is_new_npc conflict.
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

    # validate_state.py must reject two npc_ids that differ only by
    #     case. Adversarial testing found both accepted as distinct new
    #     NPCs, because npc_id was the one identifier still compared as
    #     an exact string while gear names and thread text were already
    #     normalized. scripts/adversarial_stress_test.py covers this too,
    #     but only against a turn-0 throwaway campaign that it commits
    #     to -- so the guard belongs here as well, where `session.py
    #     audit` runs it every time against a scratch directory.
    bad2c = json.loads(json.dumps(base))
    bad2c["npc_relationships"] = [
        {"npc_id": "__adversarial_case__", "name": "Variant A", "is_new_npc": True},
        {"npc_id": "__Adversarial_Case__", "name": "Variant B", "is_new_npc": True},
    ]
    bad2c_path = tmp_dir / "bad_npc_id_case_variance.json"
    bad2c_path.write_text(json.dumps(bad2c), encoding="utf-8")
    code2c, out2c = run_script(["scripts/validate_state.py", str(bad2c_path)])
    ok = (code2c != 0) and "differing only by case" in out2c
    results.append(("validate_state.py rejects two npc_ids differing only by case", ok, out2c))

    # The registry lookup behind that rejection must resolve an id
    #     across case, checked directly rather than through a commit.
    #     validate_state.py blocks two variants inside ONE state, but a
    #     variant of an id registered on an EARLIER turn passes
    #     validation and reaches commit_state.py's update_npc_registry()
    #     and snapshot_pruned_npcs(), which both rely on this helper to
    #     avoid writing a second key for one person. Exercising it in
    #     process keeps Pass 2's promise not to touch real save files --
    #     driving that path through a commit would write to
    #     saves/npc_registry.json for real.
    try:
        from validate_state import find_registered_npc_id
        registry_fixture = {"innkeeper-maren": {"name": "Maren"}}
        resolves_variant = find_registered_npc_id(registry_fixture, "Innkeeper-Maren") == "innkeeper-maren"
        resolves_padded = find_registered_npc_id(registry_fixture, "  innkeeper-maren  ") == "innkeeper-maren"
        rejects_other = find_registered_npc_id(registry_fixture, "someone-else") is None
        ok = resolves_variant and resolves_padded and rejects_other
        detail = (f"variant={resolves_variant} padded={resolves_padded} "
                  f"unrelated-id-still-unregistered={rejects_other}")
    except ImportError as e:
        ok, detail = False, f"could not import find_registered_npc_id: {e}"
    results.append(("npc_id registry lookup resolves one NPC across case and whitespace", ok, detail))

    # self_critique.py must treat a named possessor on the player
    #     character as the inventory claim it is. "Chad's sword" makes
    #     exactly the claim "his sword" makes, and passed clean until it
    #     was measured.
    named_path = tmp_dir / "narration_named_possessor.txt"
    named_path.write_text("He drew Chad's sword and stepped forward.\n", encoding="utf-8")
    code2d, out2d = run_script(["scripts/self_critique.py", str(named_path)])
    ok = (code2d != 0) and "sword" in out2d
    results.append(("self_critique.py flags a named possessor on the player character", ok, out2d))

    # ...and must NOT read another character's possessive as Chad's
    #     gear. Armed NPCs carry weapons through most scenes, and an
    #     earlier revision of the semantic advisory anchored its named
    #     pattern to any capitalised word, so "Maren's dagger" was
    #     reported as a possible unlisted item of Chad's. That defect
    #     changed no exit code, so only the advisory text reveals it --
    #     which is what this asserts on. With WordNet absent the advisory
    #     cannot fire at all and the check passes for the right reason.
    npc_path = tmp_dir / "narration_npc_possessor.txt"
    npc_path.write_text("Maren's dagger caught the light.\n", encoding="utf-8")
    code2e, out2e = run_script(["scripts/self_critique.py", str(npc_path)])
    ok = (code2e == 0) and "unlisted carried item" not in out2e
    results.append(("self_critique.py ignores another character's possessive", ok, out2e))

    # validate_state.py must reject currency-as-gear.
    bad3 = json.loads(json.dumps(base))
    bad3["gear"] = bad3.get("gear", []) + [{"name": "gold"}]
    bad3_path = tmp_dir / "bad_currency_gear.json"
    bad3_path.write_text(json.dumps(bad3), encoding="utf-8")
    code3, out3 = run_script(["scripts/validate_state.py", str(bad3_path)])
    ok = (code3 != 0) and "currency" in out3.lower()
    results.append(("validate_state.py rejects a currency word disguised as gear", ok, out3))

    # validate_state.py must reject an over-cap array.
    bad4 = json.loads(json.dumps(base))
    bad4["open_threads"] = [{"text": f"thread {i}", "added_turn": 0} for i in range(9)]
    bad4_path = tmp_dir / "bad_overcap.json"
    bad4_path.write_text(json.dumps(bad4), encoding="utf-8")
    code4, out4 = run_script(["scripts/validate_state.py", str(bad4_path)])
    ok = (code4 != 0) and "soft cap" in out4.lower()
    results.append(("validate_state.py rejects open_threads exceeding its soft cap", ok, out4))

    # validate_state.py must WARN (not necessarily fail) on a lapsed active deadline.
    bad5 = json.loads(json.dumps(base))
    bad5["turn"] = 50
    bad5["open_threads"] = [{"text": "an old promise", "added_turn": 1, "active": True, "deadline_turn": 10}]
    bad5_path = tmp_dir / "lapsed_deadline.json"
    bad5_path.write_text(json.dumps(bad5), encoding="utf-8")
    code5, out5 = run_script(["scripts/validate_state.py", str(bad5_path)])
    ok = "lapsed active deadline" in out5.lower() or "warning" in out5.lower()
    results.append(("validate_state.py warns on a lapsed active deadline", ok, out5))

    # A deadline the fiction dated must be judged by the DATE, not by the
    # turn count. Both halves are checked, because the old turn-only code
    # got each one backwards in a different direction: it would warn about
    # a thread whose in-world date is still days away (turn count high),
    # and stay silent on one whose date has passed (turn count low).
    far = json.loads(json.dumps(base))
    far["turn"] = 400
    far["in_world_date"] = {"day": 13, "month": "Seedmonth", "year": 1}
    far["open_threads"] = [{"text": "be there on the sixteenth", "added_turn": 1,
                            "active": True,
                            "deadline_date": {"day": 16, "month": "Seedmonth", "year": 1}}]
    far_path = tmp_dir / "date_still_live.json"
    far_path.write_text(json.dumps(far), encoding="utf-8")
    _, out_far = run_script(["scripts/validate_state.py", str(far_path)])
    quiet = "lapsed active deadline" not in out_far.lower()

    past = json.loads(json.dumps(base))
    past["turn"] = 2
    past["in_world_date"] = {"day": 20, "month": "Seedmonth", "year": 1}
    past["open_threads"] = [{"text": "be there on the sixteenth", "added_turn": 1,
                             "active": True,
                             "deadline_date": {"day": 16, "month": "Seedmonth", "year": 1}}]
    past_path = tmp_dir / "date_lapsed.json"
    past_path.write_text(json.dumps(past), encoding="utf-8")
    _, out_past = run_script(["scripts/validate_state.py", str(past_path)])
    loud = "lapsed active deadline" in out_past.lower()

    results.append(("validate_state.py judges a dated deadline by the date, "
                    "not the turn count", quiet and loud, out_far + out_past))

    # The two units disagreeing is the drift becoming visible, and is the
    # only signal that an existing deadline_turn has gone stale.
    dis = json.loads(json.dumps(base))
    dis["turn"] = 30
    dis["in_world_date"] = {"day": 13, "month": "Seedmonth", "year": 1}
    dis["open_threads"] = [{"text": "salt carter", "added_turn": 1, "active": True,
                            "deadline_turn": 20,
                            "deadline_date": {"day": 16, "month": "Seedmonth", "year": 1}}]
    dis_path = tmp_dir / "deadline_units_disagree.json"
    dis_path.write_text(json.dumps(dis), encoding="utf-8")
    _, out_dis = run_script(["scripts/validate_state.py", str(dis_path)])
    results.append(("validate_state.py warns when deadline_turn and "
                    "deadline_date disagree", "disagree" in out_dis.lower(), out_dis))

    # A save validated by path must be checked against the registry that
    # sits NEXT TO IT, not the one next to this script -- and a proposal
    # with no campaign around it must still fall back to this script's
    # registry, because the is_new_npc check is a blocking gate and
    # deriving paths unconditionally would make it fail open on the one
    # path that matters most (commit_state.py validates /tmp proposals).
    other = tmp_dir / "other_campaign" / "saves"
    other.mkdir(parents=True, exist_ok=True)
    (other / "npc_registry.json").write_text(
        json.dumps({"established-elsewhere": "Someone"}), encoding="utf-8")
    known = json.loads(json.dumps(base))
    known["npc_relationships"] = [{"npc_id": "established-elsewhere", "name": "Someone",
                                   "disposition": "known", "note": "n",
                                   "is_new_npc": False}]
    (other / "current.json").write_text(json.dumps(known), encoding="utf-8")
    code_o, out_o = run_script(["scripts/validate_state.py", str(other / "current.json")])
    sibling_used = code_o == 0

    orphan = json.loads(json.dumps(base))
    orphan["npc_relationships"] = [{"npc_id": "established-elsewhere", "name": "Someone",
                                    "disposition": "known", "note": "n",
                                    "is_new_npc": False}]
    orphan_path = tmp_dir / "orphan_proposal.json"
    orphan_path.write_text(json.dumps(orphan), encoding="utf-8")
    code_p, out_p = run_script(["scripts/validate_state.py", str(orphan_path)])
    fallback_held = "npc_registry" in out_p

    results.append(("validate_state.py reads the registry beside the save, and "
                    "still falls back for an orphan proposal",
                    sibling_used and fallback_held, out_o + out_p))

    # A price stated in a thread's prose and the recorded amount must not
    # be able to disagree -- otherwise `amount` is just another field the
    # narration can contradict. The rate-and-total case is checked too,
    # because the first version of the extractor summed repeated
    # denominations and misread this project's own fixture.
    money = json.loads(json.dumps(base))
    money["open_threads"] = [{"text": "Owes Maren 22 copper", "added_turn": 1,
                              "active": True, "amount": {"copper": 14}}]
    money_path = tmp_dir / "price_disagrees.json"
    money_path.write_text(json.dumps(money), encoding="utf-8")
    _, out_m = run_script(["scripts/validate_state.py", str(money_path)])
    disagree_caught = "disagree" in out_m.lower()

    rate = json.loads(json.dumps(base))
    rate["open_threads"] = [{"text": "2 copper a night, 14 copper for the week",
                             "added_turn": 1, "active": True,
                             "amount": {"copper": 14}}]
    rate_path = tmp_dir / "price_rate_and_total.json"
    rate_path.write_text(json.dumps(rate), encoding="utf-8")
    _, out_r = run_script(["scripts/validate_state.py", str(rate_path)])
    rate_quiet = "disagree" not in out_r.lower()

    results.append(("validate_state.py catches a thread whose stated price and "
                    "recorded amount disagree", disagree_caught and rate_quiet,
                    out_m + out_r))

    # A committed turn must leave its narration on record. The prose is
    # the evidence the state is a claim about; before this, commit_state.py
    # received it, checked it, and deleted it in a finally block, which made
    # Pass 3's own "a human reading actual transcript prose" fallback
    # impossible to carry out. Checked by importing the writer directly --
    # driving a full commit here would need a git repo and a clean gate run,
    # and this suite is meant to stay hermetic.
    sys.path.insert(0, str(SCRIPTS_DIR))
    narration_ok = False
    narration_out = ""
    try:
        import importlib
        cs = importlib.import_module("commit_state")
        original = cs.NARRATION_DIR
        cs.NARRATION_DIR = tmp_dir / "narration_probe"
        try:
            st = {"turn": 7, "commit_token": "7-abc123",
                  "in_world_date": {"day": 3, "month": "Seedmonth", "year": 1}}
            written = cs.persist_narration(st, "He counts the coin twice and says nothing.")
            blank = cs.persist_narration(st, "   ")
            if written and written.exists():
                body = written.read_text(encoding="utf-8")
                narration_ok = ("7-abc123" in body
                                and "counts the coin twice" in body
                                and written.name == "turn-0007.md"
                                and blank is None)
                narration_out = body[:200]
        finally:
            cs.NARRATION_DIR = original
    except Exception as e:                       # noqa: BLE001 - report, don't crash the suite
        narration_out = f"raised {e!r}"
    results.append(("commit_state.py archives a turn's narration, stamped with "
                    "its commit_token", narration_ok, narration_out))

    # git add must never be handed a path git cannot resolve. `git add a b
    # missing` is fatal and stages NOTHING -- not even the paths that exist
    # -- so naming saves/narration unconditionally would, on a campaign that
    # has not archived one yet, commit nothing while saves/current.json
    # advanced on disk. Verified against real git rather than by reading the
    # source, because the failure is in git's behaviour, not the project's.
    gitprobe = tmp_dir / "gitprobe"
    (gitprobe / "saves").mkdir(parents=True, exist_ok=True)
    (gitprobe / "saves" / "current.json").write_text("{}", encoding="utf-8")
    def git(*a):
        return subprocess.run(["git", *a], cwd=gitprobe, capture_output=True, text=True)
    git("init", "-q", ".")
    git("config", "user.email", "probe@local")
    git("config", "user.name", "probe")
    git("add", "saves/current.json")
    git("commit", "-qm", "base")
    (gitprobe / "saves" / "current.json").write_text('{"turn": 1}', encoding="utf-8")
    git("add", "saves/current.json", "saves/narration")
    staged_despite_missing = git("diff", "--cached", "--name-only").stdout.strip()
    results.append(("git add stages nothing when handed a missing path (the "
                    "reason saves/narration is only added when it exists)",
                    staged_despite_missing == "",
                    f"staged: {staged_despite_missing!r}"))

    # prune_advisor.py must run without crashing and must print the
    #    "confirm or override" caveat -- we do NOT assert its ranking
    #    quality here, since it's a known-naive heuristic; this only
    #    checks the tool still runs and still carries the caveat forward.
    code6, out6 = run_script(["scripts/prune_advisor.py", "npc_relationships"])
    ok = "confirm or override" in out6.lower() or "empty" in out6.lower()
    results.append(("prune_advisor.py runs and still carries its non-authoritative caveat", ok, out6))

    # commit_state.py must not desync saves/current.json from git
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
    # Until narration was archived this deferral pointed at nothing: the
    # prose did not survive the turn, so the fallback it names could never
    # be exercised by anyone. Say where the prose is, or the instruction
    # is the same dead end it was before.
    narr = SAVES_DIR / "narration"
    files = sorted(narr.glob("turn-*.md")) if narr.exists() else []
    if files:
        print(f"  The prose IS on record: {len(files)} turn(s) in "
              f"saves/narration/ ({files[0].name}..{files[-1].name}), each stamped")
        print("  with the commit_token of the state it justified. Read those against")
        print("  saves/current.json to answer the questions above.")
    else:
        print("  NOTE: saves/narration/ is empty, so the prose for these turns is not")
        print("  on record and the review below cannot actually be carried out. Turns")
        print("  committed before narration archiving existed are gone for good.")
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
