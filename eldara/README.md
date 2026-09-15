# The Eldara Project

A git-backed framework for running a persistent solo interactive-fiction
campaign: Chad Michael Davis, an ordinary 40-year-old pulled out of his life
in present-day Columbus, Ohio and dropped into the fantasy world of Eldara.

The GM (an LLM — narration happens in a chat interface, e.g. Claude) narrates;
the player controls only Chad's attempted actions and dialogue. State — gear,
currency, injuries, NPC relationships, open threads — is tracked in
`saves/current.json`, validated against `state_schema.json`, and committed to
git after every state-changing turn so the campaign survives across sessions.

## How this project is meant to be run

The mechanical side of this project (validation, commits, audits) runs
inside a Claude Code session, which supplies both the narration (an LLM
in the same conversation) and the shell/filesystem/git access the
scripts need — no separate guest VM or SSH bridge required. Concretely,
this project assumes:

- **Claude PC** (the Claude Code Desktop app, or the Claude Code CLI in
  a terminal) on a real computer — this is where `scripts/` actually
  runs, with direct filesystem and git access to this repository.
- **Claude iOS**, connected to that same session via **Remote Control**
  (driving a session running on your computer) or a **Cloud Session**
  (running on Anthropic-managed infrastructure instead, which requires
  this repository to be pushed to GitHub). See `LOCAL.md` for the
  tradeoff between the two and full setup steps.
- **This repository, on GitHub** — required for Cloud Sessions, and the
  same git-push safety net this project has always depended on either
  way.
- **A chat interface with an LLM for the actual narration** — with this
  setup, that's simply the same Claude Code conversation doing the
  mechanical work, not a separate app. See `docs/OPERATING.md` for why
  narration and mechanics are still treated as distinct responsibilities
  even though one conversation covers both.

None of this is a hard requirement — the same files and scripts run fine
on any machine with a POSIX shell and Python 3, reached however you like.
But `LOCAL.md` is written against the Claude iOS + Claude PC + GitHub
chain specifically, since that's what this project is built around.

## Quick start

```
git clone <repo-url> eldara_new && cd eldara_new
git init                                # if the clone didn't already
python3 scripts/session.py bootstrap    # one-time: setup + check + start in one pass
```

(`bootstrap` is just `setup`, `check`, and `start` run in sequence, stopping at
the first failure — run them separately instead if you want to inspect each
step's output on its own:)

```
python3 scripts/session.py setup        # one-time: installs deps + git hooks
python3 scripts/session.py check        # confirm everything's in order
python3 scripts/session.py start        # validate + print current status
```

Run `python3 scripts/session.py --help` for the full subcommand list —
`commit <file>` and `loop` are the ones you'll use turn to turn once a
campaign is underway; `audit` runs the full three-pass playtest audit on
demand; `export` bundles the current save into one shareable/archivable
file; `earn-coverage` plays a fixed set of real turns through the real
commit pipeline against a fresh/throwaway campaign to legitimately earn
full Pass-1 audit coverage (see `docs/OPERATING.md`). It automates every
mechanical step (validation, backup, journaling, NPC registry updates, git
commits) but — like every script here — it cannot narrate the story
itself; that step always needs an actual LLM in the loop.

Once set up, paste `prompts/GM_INSTRUCTIONS.md` into your chat interface of
choice, and `prompts/FIRST_MESSAGE.md` if this is a brand-new campaign.

## Project layout

| Path | Purpose |
|---|---|
| `prompts/GM_INSTRUCTIONS.md` | The full roleplay contract and operating instructions. Paste at session start. |
| `prompts/FIRST_MESSAGE.md` | Opening scene for a brand-new campaign. |
| `prompts/STATUS_TEMPLATE.md` | The status-check format and hard interrupt words. |
| `docs/ELDARA_REFERENCE.md` | World lore: geography, history, factions, magic, economy. |
| `docs/CHAD_BACKSTORY.md` | Chad's personal/old-world canon, kept separate from world lore. |
| `docs/OPERATING.md` | How the tooling actually fits together, and why narration stays external. |
| `docs/RECOVERY.md` | What to do if state gets corrupted or a hard rule is broken mid-session. |
| `docs/MODEL_NOTES.md` | Notes on running this with different LLMs. |
| `docs/lore_keywords.json` | Keyword → lore-section mapping backing `scripts/world_info_lookup.py`. Data, not code — add a new keyword here rather than editing the script. |
| `state_schema.json` | The schema `saves/current.json` is validated against. |
| `saves/current.json` | The single source of truth for Chad's current state. |
| `saves/journal.md` | Auto-generated, mechanical log of state changes over time. |
| `saves/npc_registry.json` | Permanent record of every NPC id ever assigned, so identity survives pruning. Also holds a last-known snapshot (disposition, note, last-referenced turn) for any NPC pruned from `current.json`'s capped working set — Eldara's answer to Auferet's Character Library still remembering someone who's out of the spotlight. |
| `saves/pinned_facts.json` | Short, load-bearing "never forget" facts (Auferet's pinned-facts idea), hard-checked against every drafted turn by `scripts/lore_consistency_check.py`. Add to it during play as new facts get established. |
| `saves/locations.json` | Fixed places and pairwise travel durations, sourced from `docs/ELDARA_REFERENCE.md` §2.8/§2.3. Backs `current_location`/`travel` in `saves/current.json` and `scripts/location_lookup.py`. |
| `saves/player_notes.md` | Out-of-character preferences (pacing, tone, content limits) — never narrated. |
| `scripts/session.py` | Single entry point for setup, checks, commits, audits, and earning coverage. `bootstrap` runs setup + check + start in one pass. |
| `scripts/location_lookup.py` | Look up a tracked place or the travel duration between two, from `saves/locations.json` — the fixed-coordinate "world map" analog. Read-only and advisory, like `world_info_lookup.py`. |
| `scripts/add_lore.py` | Add a new lore section to `docs/ELDARA_REFERENCE.md`/`docs/CHAD_BACKSTORY.md` and/or register keyword(s) for it in `docs/lore_keywords.json`, in one command instead of hand-editing both. |
| `scripts/export_save.py` | Bundle `current.json`, `journal.md`, `locations.json` and `npc_registry.json` into one shareable/archivable file. Excludes `player_notes.md` unless `--include-player-notes` is passed. |
| `saves/dashboard/campaign_dashboard.html` | Standalone, offline dashboard. Open directly in a browser and paste in the contents of `current.json` (and optionally `locations.json`/`npc_registry.json`, or an `export_save.py` bundle's `current_state` field) to view a glanceable status summary. Never writes back to any save file. |
| `scripts/earn_clean_slate.py` | Plays fixed, schema-valid turns through the real commit pipeline to legitimately earn Pass-1 audit coverage on a fresh/throwaway campaign. Wrapped by `session.py earn-coverage`; never run against real campaign history. |
| `scripts/` | The rest: individual validation/commit/audit scripts, plus git hooks, that `session.py` wraps. |

## Why the tooling exists

An LLM narrating a long campaign will drift — inventing gear, forgetting
injuries, losing track of who a named NPC is. This project's answer is to
keep a small, boring, mechanically-validated JSON file as the actual source
of truth, and make every state-changing turn go through a validator before
it's allowed to become canon. The GM is still the GM; the tooling just makes
sure its memory of the story matches a file that can't drift on its own.

See `docs/OPERATING.md` for the full mechanics.
