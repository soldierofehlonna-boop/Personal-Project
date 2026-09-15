#!/usr/bin/env python3
"""Run the GM stress prompts through fresh Claude Code sessions and export
one file holding every input and its output.

WHY THIS EXISTS
---------------
adversarial_stress_test.py has two ways to get a GM response for its
GM_STRESS_PROMPTS: --auto-gm, which calls the Messages API and therefore
tests a model with no tools and no file access, and
--submit-stress-prompt, which tests the real thing but needs a person to
paste five prompts by hand and save what comes back.

This is the third way, and it is the one that actually answers the
question the other two can't. Each prompt goes to its own `claude -p`
invocation: a fresh non-interactive Claude Code session, with real file
access to the campaign, that has never seen the conversation in which
these instructions were written or these cases chosen. That last part is
the whole point. Anyone who helped design a check is the worst person to
measure it, because they know what it is looking for.

WHAT IT DOES NOT SEND
---------------------
Each case in GM_STRESS_PROMPTS carries a `watch_for` note describing the
failure mode it probes. That note is written into the exported transcript
for whoever reads it, and is NEVER sent to the session under test.
Telling the subject what is being measured would defeat the measurement.

CONTAINMENT
-----------
A session reached this way has tools, so a prompt ending "draft the
resulting state" may well try to commit one. Every run therefore happens
against a throwaway copy of the project, made fresh per run, and the live
campaign is never the working directory. Anything a session commits lands
in the copy and is reported, not hidden. The copy has no git remote, so
nothing can be pushed from it.

The exported transcript is the deliverable: prompts, responses, timings,
exit codes, and provenance, in one file a human can read end to end.

USAGE
-----
    python3 scripts/run_stress_prompts.py
        Run all cases at the default model, write the transcript to
        saves/exports/.

    python3 scripts/run_stress_prompts.py --case pressure-to-invent-gear
        One case only.

    python3 scripts/run_stress_prompts.py --label opus5-high --effort high
        Tag the run and set the effort level, so two runs can be compared.

    python3 scripts/run_stress_prompts.py --dry-run
        Print what would be sent, and to what, without spending anything.

Each case is a real model call against a real campaign copy. Five cases
is five calls; --effort high or above makes each one slower and dearer.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
INSTRUCTIONS_PATH = ROOT / "prompts" / "GM_INSTRUCTIONS.md"
EXPORTS_DIR = ROOT / "saves" / "exports"

sys.path.insert(0, str(SCRIPTS))
from adversarial_stress_test import GM_STRESS_PROMPTS  # noqa: E402

# Appended to each case prompt so there is a state draft to read, phrased
# the same way --auto-gm phrases it so the three paths stay comparable.
STATE_ASK = (
    "\n\nDraft the resulting proposed state as a complete JSON object "
    "(the full saves/current.json shape, not just a diff) in a ```json "
    "fenced code block, with your narration as ordinary text around it."
)


def make_campaign_copy():
    """A throwaway copy of the project for the sessions to act on."""
    tmp = Path(tempfile.mkdtemp(prefix="eldara-stress-"))
    dest = tmp / "eldara"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc"))
    return dest


def run_case(case, model, effort, timeout, permission_mode):
    """One case, one fresh session, one fresh campaign copy.

    The copy is per-case on purpose. Sharing one copy across the run would
    let a case that commits change the campaign the next case reads, so
    case five would be answering a different question than case one --
    "npc_relationships is full" means something else once an earlier case
    has added NPCs. Whether a session commits at all depends on the
    permission mode, which makes shared state an accident waiting rather
    than a decision. Each case gets the same turn-0 baseline instead.
    """
    workdir = make_campaign_copy()
    system_prompt = INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    cmd = ["claude", "-p", case["prompt"] + STATE_ASK,
           "--append-system-prompt", system_prompt, "--model", model]
    if effort:
        cmd += ["--effort", effort]
    if permission_mode:
        cmd += ["--permission-mode", permission_mode]

    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True,
                              text=True, timeout=timeout)
        out, err, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        out, err, code = "", f"timed out after {timeout}s", None
    except FileNotFoundError:
        out, err, code = "", "the `claude` CLI is not on PATH", None
    elapsed = round(time.monotonic() - started, 1)

    return {
        "case_id": case["id"],
        "campaign_copy": str(workdir),
        "copy_end_turn": campaign_turn(workdir),
        "prompt_sent": case["prompt"] + STATE_ASK,
        "watch_for": case["watch_for"],   # for the reader, never sent
        "response": out.strip(),
        "stderr": err.strip(),
        "exit_code": code,
        "seconds": elapsed,
    }


def campaign_turn(path):
    try:
        return json.loads((path / "saves" / "current.json")
                          .read_text(encoding="utf-8")).get("turn")
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def write_transcript(out_path, label, model, effort, results):
    lines = [
        f"# GM stress prompt transcript — {label}",
        "",
        f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Model: `{model}`" + (f", effort `{effort}`" if effort else ""),
        f"- Cases: {len(results)}",
        "- Each case ran against its own fresh copy of the campaign at turn 0, so no",
        "  case could be affected by what an earlier one committed.",
        "",
        "Each response below came from its own `claude -p` session: fresh, with real",
        "file access to its campaign copy, and with no knowledge of the conversation",
        "that wrote these instructions or chose these cases. The **watch for** note",
        "on each case was written into this file for you and was never sent to the",
        "session — it names what the case probes, which the subject must not know.",
        "",
        "A clean-looking response is not a pass. Read each one against its watch-for.",
        "",
    ]
    for i, r in enumerate(results, start=1):
        lines += [
            "---", "",
            f"## {i}. `{r['case_id']}`",
            "",
            "### Prompt sent", "", "```text", r["prompt_sent"], "```", "",
            "### Watch for (not sent)", "", r["watch_for"], "",
            f"### Response  ({r['seconds']}s, exit {r['exit_code']}, "
            f"copy ended at turn {r['copy_end_turn']})", "",
        ]
        lines += ["```text", r["response"] or "(no output)", "```", ""]
        if r["stderr"]:
            lines += ["### stderr", "", "```text", r["stderr"], "```", ""]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default="unlabeled")
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument("--effort", help="Effort level, e.g. medium, high, xhigh.")
    parser.add_argument("--case", metavar="CASE_ID", help="Run one case only.")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Seconds per case (default 600).")
    parser.add_argument("--permission-mode",
                        help="Passed through to `claude`. Left unset by default: the "
                             "session gets whatever the CLI allows without being "
                             "asked, which is enough to read the campaign. Set this "
                             "only if you want the session able to commit inside the "
                             "throwaway copy.")
    parser.add_argument("--out", help="Transcript path (default under saves/exports/).")
    parser.add_argument("--json", action="store_true",
                        help="Also write a .json sidecar of the same run.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cases = GM_STRESS_PROMPTS
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"Unknown case '{args.case}'. Known: "
                  + ", ".join(c["id"] for c in GM_STRESS_PROMPTS))
            return 1

    out_path = Path(args.out) if args.out else (
        EXPORTS_DIR / f"stress_transcript_{args.label}.md")

    if args.dry_run:
        print(f"Would run {len(cases)} case(s) as `claude -p`, model={args.model}"
              + (f", effort={args.effort}" if args.effort else "")
              + f", timeout={args.timeout}s each.")
        print(f"System prompt: {INSTRUCTIONS_PATH.relative_to(ROOT)} "
              f"({len(INSTRUCTIONS_PATH.read_text(encoding='utf-8')):,} chars)")
        print(f"Transcript would be written to: {out_path}")
        print("Each session would run against a fresh throwaway copy of this "
              "project, never the live campaign.\n")
        for c in cases:
            print(f"  {c['id']}: {c['prompt'][:70]}...")
        return 0

    print(f"Running {len(cases)} case(s), each against its own fresh copy of the "
          f"campaign (live campaign at turn {campaign_turn(ROOT)} is never the "
          "working directory)\n")

    results = []
    for i, case in enumerate(cases, start=1):
        print(f"-- {i}/{len(cases)}: {case['id']} ... ", end="", flush=True)
        r = run_case(case, args.model, args.effort,
                     args.timeout, args.permission_mode)
        state = "ok" if r["exit_code"] == 0 else f"exit {r['exit_code']}"
        print(f"{state}, {r['seconds']}s, {len(r['response'])} chars")
        results.append(r)

    write_transcript(out_path, args.label, args.model, args.effort, results)
    print(f"\nTranscript: {out_path}")
    if args.json:
        json_path = out_path.with_suffix(".json")
        json_path.write_text(json.dumps({
            "label": args.label, "model": args.model, "effort": args.effort,
            "results": results}, indent=2) + "\n", encoding="utf-8")
        print(f"JSON:       {json_path}")
    copies = [r["campaign_copy"] for r in results]
    print(f"\n{len(copies)} campaign copies left in place for inspection "
          f"(each under {Path(copies[0]).parent.parent}); the transcript names "
          "each one and the turn it ended at. Delete them when you're done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
