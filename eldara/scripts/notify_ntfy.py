#!/usr/bin/env python3
"""Sends a push notification via ntfy (https://ntfy.sh) -- used to page
the human when a scheduled audit flags something for review.

ntfy is a single HTTP POST to a topic URL, with no account or sign-up at
all -- the topic name itself is the only "credential" (see the security
note below). Install the ntfy app on your phone, subscribe to a topic
you choose, and any POST to that topic arrives as a real push
notification. Because you're typically already in the same Claude Code
session when you'd run the manual checklist described in LOCAL.md, a
push notification arriving on your phone is a useful backup for whenever
you aren't looking at that session already (e.g. a Cloud Session running
while you're doing something else).

Configuration lives in ntfy_config.json (untracked, see
ntfy_config.example.json for the template) rather than in code, so the
topic name (see security note) never ends up in git.

Security note: ntfy's public server (ntfy.sh) has no authentication by
default -- anyone who knows or guesses your topic name can publish to it
or read messages sent to it. Treat the topic name like a lightweight
secret: make it long and unguessable (a random string, not "eldara" or
your name), the same way you would with any unauthenticated webhook URL.
For anything more sensitive, ntfy supports self-hosting or an
authenticated topic (see docs.ntfy.sh) -- out of scope for this simple
integration, but worth knowing exists.

Usage as a library:
    from notify_ntfy import send_notification, load_config
    cfg = load_config()
    if cfg:
        send_notification(cfg, "Eldara audit flagged something -- check the log.")

Usage standalone (useful for testing the setup once):
    python3 scripts/notify_ntfy.py "test message"
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "ntfy_config.json"
DEFAULT_SERVER = "https://ntfy.sh"


def load_config():
    """Returns the parsed config dict, or None if it's missing/incomplete
    (treated as 'ntfy notifications simply aren't set up', not an error
    -- callers should keep working without it)."""
    if not CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARNING: ntfy_config.json exists but couldn't be read/parsed ({e}); "
              f"skipping ntfy notification.", file=sys.stderr)
        return None

    if not cfg.get("topic"):
        print("WARNING: ntfy_config.json is missing 'topic'; skipping ntfy notification.",
              file=sys.stderr)
        return None
    return cfg


def send_notification(cfg, body, title=None, priority=None, tags=None):
    """Publishes body to the configured ntfy topic. Returns True on
    success, False on failure (never raises -- a notification failure
    should never take down the audit run that triggered it).

    priority: one of "min", "low", "default", "high", "urgent" (ntfy's
    own scale) -- omit for ntfy's default.
    tags: a list of ntfy emoji-shortcode tags (e.g. ["warning", "skull"]),
    rendered by the client app -- purely cosmetic, safe to omit.
    """
    try:
        server = cfg.get("server", DEFAULT_SERVER).rstrip("/")
        url = f"{server}/{cfg['topic']}"
        headers = {}
        if title:
            headers["Title"] = title
        if priority:
            headers["Priority"] = priority
        if tags:
            headers["Tags"] = ",".join(tags)

        request = urllib.request.Request(
            url, data=body.encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, KeyError, TypeError, ValueError) as e:
        # Catches both network-layer failures (URLError, covering both
        # connection problems and non-2xx HTTP responses raised as
        # HTTPError, a URLError subclass) and config-shape failures
        # (a missing 'topic' key, etc.) -- any of these should degrade
        # to a warning, not an unhandled exception.
        print(f"WARNING: failed to send ntfy notification: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    cfg = load_config()
    if cfg is None:
        print(f"No usable config at {CONFIG_PATH}.")
        print(f"Copy ntfy_config.example.json to {CONFIG_PATH.name} and fill it in first.")
        sys.exit(1)

    text = " ".join(sys.argv[1:]) or "Eldara Project: test notification."
    ok = send_notification(cfg, text, title="Eldara test")
    print("Sent." if ok else "Failed -- see warning above.")
    sys.exit(0 if ok else 1)
