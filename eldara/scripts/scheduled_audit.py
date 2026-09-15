#!/usr/bin/env python3
"""Runs the full playtest audit and appends its output to a rotating log
file, intended to be invoked unattended (via cron) on a persistent VM
rather than only when someone remembers to run it manually.

This is what actually closes the gap Pass 3 of playtest_audit.py flags
about itself: drift-proxy checks are only useful if they're run
regularly. A laptop that gets closed overnight can't do this reliably;
an always-on VM can.

Usage:
    python3 scripts/scheduled_audit.py
    (intended to be called from crontab -- see 'session.py cron install')
"""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notify_ntfy import load_config as load_ntfy_config, send_notification  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "saves" / "audit_log.md"
MAX_LOG_BYTES = 2 * 1024 * 1024  # 2MB, then rotate -- small VM disk in mind


def rotate_if_large():
    if LOG_PATH.exists() and LOG_PATH.stat().st_size > MAX_LOG_BYTES:
        rotated = LOG_PATH.with_suffix(".md.1")
        rotated.unlink(missing_ok=True)
        LOG_PATH.rename(rotated)


def main():
    rotate_if_large()

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "playtest_audit.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    output = result.stdout + result.stderr

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # Only bother recording a flagged/failed run in detail; a clean run
    # gets a one-line entry so the log doesn't balloon with routine passes.
    is_clean = "FAIL" not in output and "FLAGGED" not in output and "flags for human review" in output and \
        "Nothing flagged." in output

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n### Scheduled audit — {stamp}\n")
        if is_clean:
            f.write("Clean run -- nothing flagged. Full output suppressed to keep this log short.\n")
        else:
            f.write("```\n")
            f.write(output)
            f.write("\n```\n")

    print(f"Audit complete, logged to {LOG_PATH} ({'clean' if is_clean else 'see log for detail'}).")

    # Only page the human for runs worth interrupting them for -- a clean
    # run already gets a one-line log entry above and doesn't need an
    # alert. Silently does nothing if ntfy_config.json isn't set up yet
    # (see notify_ntfy.py).
    if not is_clean:
        ntfy_cfg = load_ntfy_config()
        if ntfy_cfg is not None:
            alert_body = (
                f"Eldara audit ({stamp}) flagged something for review. "
                f"Check saves/audit_log.md on the VM."
            )
            send_notification(ntfy_cfg, alert_body, title="Eldara audit flagged", priority="high")


if __name__ == "__main__":
    main()
