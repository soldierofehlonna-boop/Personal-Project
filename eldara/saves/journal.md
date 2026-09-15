# Campaign Journal

Mechanical, auto-generated summaries of state changes appear below.
Add a freeform note alongside a state commit via
`python3 scripts/commit_state.py <file> --note "..."`
(or `python3 scripts/session.py commit <file> --note "..."`).

---

### Turn 1 — 2026-09-15 22:40 UTC

_Turn 1: acquired traveler's cloak_

Self-critique: ran clean (self_critique.py passed)

- commit_token: null -> "1-1377b6"
- gear: [{"name": "T-shirt", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Jeans", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Underwear", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Socks", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Shoes", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}] -> [{"name": "T-shirt", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Jeans", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Underwear", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Socks", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Shoes", "acquired_turn": 0, "acquired_event": "Baseline starting clothes"}, {"name": "Traveler's cloak", "acquired_turn": 1, "acquired_event": "Given by an innkeeper against the cold"}]
- turn: 0 -> 1


### Turn 2 — 2026-09-15 22:40 UTC

_Turn 2: language established_

Self-critique: ran clean (self_critique.py passed)

- commit_token: "1-1377b6" -> "2-a50122"
- language: null -> {"established": true, "detail": "Common tongue, learned by ear over the first days"}
- turn: 1 -> 2


### Turn 3 — 2026-09-15 22:40 UTC

_Turn 3: first NPC relationship (Maren)_

Self-critique: ran clean (self_critique.py passed)

- commit_token: "2-a50122" -> "3-6c18bd"
- npc_relationships: null -> [{"npc_id": "innkeeper-maren", "name": "Maren", "disposition": "wary but not unkind", "note": "Runs the inn where Chad first woke; gave him the cloak.", "last_referenced_turn": 3}]
- turn: 2 -> 3


### Turn 4 — 2026-09-15 22:40 UTC

_Turn 4: twisted ankle_

Self-critique: ran clean (self_critique.py passed)

- commit_token: "3-6c18bd" -> "4-5f82d3"
- npc_relationships: [{"npc_id": "innkeeper-maren", "name": "Maren", "disposition": "wary but not unkind", "note": "Runs the inn where Chad first woke; gave him the cloak.", "last_referenced_turn": 3}] -> [{"npc_id": "innkeeper-maren", "name": "Maren", "disposition": "wary but not unkind", "note": "Runs the inn where Chad first woke; gave him the cloak."}]
- status: [] -> ["twisted ankle, favors it going down stairs"]
- turn: 3 -> 4


### Turn 5 — 2026-09-15 22:40 UTC

_Turn 5: open thread with deadline (rent due)_

Self-critique: ran clean (self_critique.py passed)

- commit_token: "4-5f82d3" -> "5-0a7ab1"
- npc_relationships: [{"npc_id": "innkeeper-maren", "name": "Maren", "disposition": "wary but not unkind", "note": "Runs the inn where Chad first woke; gave him the cloak."}] -> [{"npc_id": "innkeeper-maren", "name": "Maren", "disposition": "wary but not unkind", "note": "Runs the inn where Chad first woke; gave him the cloak.", "last_referenced_turn": 5}]
- open_threads: null -> [{"text": "Maren wants payment for the room by the week's end", "added_turn": 5, "active": true, "deadline_turn": 12}]
- turn: 4 -> 5


### Turn 6 — 2026-09-15 22:41 UTC

_Turn 6: throughline entry (forward planning)_

Self-critique: ran clean (self_critique.py passed)

- commit_token: "5-0a7ab1" -> "6-37a92c"
- npc_relationships: [{"npc_id": "innkeeper-maren", "name": "Maren", "disposition": "wary but not unkind", "note": "Runs the inn where Chad first woke; gave him the cloak.", "last_referenced_turn": 5}] -> [{"npc_id": "innkeeper-maren", "name": "Maren", "disposition": "wary but not unkind", "note": "Runs the inn where Chad first woke; gave him the cloak."}]
- throughline: null -> ["Starting to plan more than one step ahead, instead of just reacting"]
- turn: 5 -> 6

