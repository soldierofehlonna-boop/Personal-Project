#!/usr/bin/env python3
"""Suggest which entry in npc_relationships or open_threads is the safest
candidate to prune when a soft cap is about to be exceeded. This ranks
candidates; it does not decide -- the final call is always a narrative
judgment. Its ranking heuristic is naive (see caveats below) -- always
confirm or override the top suggestion rather than trusting it blindly.

Ranking heuristics:
  - npc_relationships: when last_referenced_turn is available (stamped by
    commit_state.py whenever an NPC's name is matched in a turn's
    narration -- see stamp_npc_recency() there), rank by actual turns
    since last mention -- a real, checkable staleness signal instead of
    a guess. Falls back to the older note/disposition-length heuristic
    for any entry without that field yet (older saves, or a name never
    yet matched verbatim). CAVEAT on the fallback path only: it can rank
    a narratively important but recently-thin-on-detail NPC (e.g. an
    authority figure introduced but not yet elaborated) as "safe to
    prune" when they're actually not -- thinness of recorded detail is
    not the same as narrative importance. The recency-based path doesn't
    share this specific flaw, but has its own: an NPC referred to only
    by title, pronoun, or a prior display name won't be matched by
    stamp_npc_recency()'s whole-word name check, so their entry can look
    stale even while narratively active.
  - open_threads: prefer pruning entries with no deadline_turn and the
    lowest added_turn (oldest, least urgent, most likely to have quietly
    stopped mattering).

Usage:
    python3 scripts/prune_advisor.py npc_relationships
    python3 scripts/prune_advisor.py open_threads
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT_PATH = ROOT / "saves" / "current.json"


def load_state():
    with open(CURRENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def rank_npcs(npcs, current_turn=None):
    """Ranks prune candidates using last_referenced_turn when it's
    present (stamped by commit_state.py's stamp_npc_recency() whenever an
    NPC's name is matched in a turn's narration) -- an NPC not mentioned
    in a long time is a genuinely safer prune candidate than one just
    mentioned, which the old note/disposition-only heuristic had no way
    to express at all. Falls back to the original heuristic for any NPC
    missing the field (older saves predating this addition, or an NPC
    whose name has never yet been matched by stamp_npc_recency()'s
    whole-word check), so this is additive, not a hard requirement on
    every entry having the new field.

    Scoring convention: HIGHER score = safer to prune (list is sorted
    descending, safest-first).

    Entries WITH recency data and entries WITHOUT it are deliberately
    kept on two non-overlapping ranges rather than one shared number
    line: an untracked entry is capped below every possible
    recency-based score (see UNTRACKED_SAFETY_CEILING), so "we don't
    know how stale this is" can never look safer than "confirmed
    mentioned N turns ago" purely by coincidence of the fallback
    heuristic's small note/disposition adjustments landing higher than a
    small turns-since-mention gap. Untracked entries still sort among
    themselves by the fallback heuristic; they just can never outrank a
    tracked entry."""
    UNTRACKED_SAFETY_CEILING = -1000  # Always below any real turns-since-mention value.

    def score(npc):
        has_recency = "last_referenced_turn" in npc and current_turn is not None
        if has_recency:
            # Turns since last mention is the entire signal on this
            # branch: a real, checkable staleness measure the old
            # heuristic never had access to.
            return current_turn - npc["last_referenced_turn"]
        # Original heuristic, unchanged, for entries with no recency
        # data yet -- still carries the same documented caveat: this can
        # misjudge a thinly-detailed-but-currently-relevant NPC. Offset
        # below the ceiling so it never crosses into the tracked range.
        s = 0
        if npc.get("note"):
            s -= 2
        if npc.get("disposition"):
            s -= 1
        return UNTRACKED_SAFETY_CEILING + s

    return sorted(npcs, key=score, reverse=True)


def rank_threads(threads):
    def score(thread):
        # Prefer pruning: no active deadline, then oldest added_turn.
        active_penalty = 100 if thread.get("active") else 0
        return active_penalty - thread.get("added_turn", 0)

    return sorted(threads, key=score)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("npc_relationships", "open_threads"):
        print("Usage: python3 scripts/prune_advisor.py npc_relationships|open_threads")
        sys.exit(1)

    field = sys.argv[1]
    if not CURRENT_PATH.exists():
        print(f"No state file found at {CURRENT_PATH}")
        sys.exit(1)

    try:
        state = load_state()
    except (json.JSONDecodeError, OSError) as e:
        print(f"FAIL: could not read/parse {CURRENT_PATH}: {e}")
        sys.exit(1)

    if not isinstance(state, dict):
        # Valid JSON that isn't an object at the top level (e.g. a bare
        # list) would otherwise crash on the first state.get() call below.
        print(f"FAIL: {CURRENT_PATH} parsed as valid JSON but is not an object "
              f"(got {type(state).__name__}, expected a dict).")
        sys.exit(1)

    items = state.get(field, [])

    if not items:
        print(f"{field} is empty -- nothing to prune.")
        return

    if field == "npc_relationships":
        current_turn = state.get("turn")
        ranked = rank_npcs(items, current_turn=current_turn)
        print("Ranked prune candidates (safest first):")
        for npc in ranked:
            recency = ""
            if "last_referenced_turn" in npc and current_turn is not None:
                gap = current_turn - npc["last_referenced_turn"]
                recency = f", last referenced turn {npc['last_referenced_turn']} ({gap} turns ago)"
            else:
                recency = ", last referenced: unknown (predates recency tracking, or name never matched)"
            print(f"  - {npc.get('name')} ({npc.get('npc_id')}) — disposition: {npc.get('disposition', '(none)')!r}{recency}")
    else:
        ranked = rank_threads(items)
        print("Ranked prune candidates (safest first):")
        for t in ranked:
            deadline = f", deadline_turn={t['deadline_turn']}" if t.get("deadline_turn") else ""
            print(f"  - \"{t.get('text')}\" (added_turn={t.get('added_turn')}, active={t.get('active', False)}{deadline})")

    print("\nThis is a ranked suggestion, not a decision -- confirm or override the top pick.")
    print("The ranking is a naive heuristic (see this script's own docstring for its known")
    print("limitation); a narratively important NPC or thread can rank as 'safe' here.")


if __name__ == "__main__":
    main()
