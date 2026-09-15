# Personal Project

This repository holds **The Eldara Project** — see [`eldara/README.md`](eldara/README.md)
for the full write-up. In short: it's a git-backed framework for running a
persistent solo interactive-fiction campaign. An LLM (e.g. Claude, in a chat
interface) acts as GM and narrates; the player only controls their
character's attempted actions and dialogue. Everything that actually
happens in the story — inventory, injuries, NPC relationships, open plot
threads — lives in a single JSON save file that's validated against a
schema and committed to git after every state-changing turn, so the
campaign can't silently drift and survives across sessions and devices.

The `scripts/` directory automates the mechanical side (setup, validation,
backups, journaling, commits, audits) — it never writes the story itself,
only enforces that the story stays consistent with a file that can't drift
on its own.

See `eldara/README.md` for the quick start, full project layout, and the
reasoning behind the tooling; `eldara/LOCAL.md` for how to run this from
Claude iOS/Claude PC/GitHub specifically.
