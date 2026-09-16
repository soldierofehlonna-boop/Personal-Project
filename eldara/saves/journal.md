# Campaign Journal

Mechanical, auto-generated summaries of state changes appear below.
Add a freeform note alongside a state commit via
`python3 scripts/commit_state.py <file> --note "..."`
(or `python3 scripts/session.py commit <file> --note "..."`).

---

### Turn 1 — 2026-09-16 18:00 UTC

_Turn 1: assessed the ankle, climbed to the ruin, found a cold fire ring and dry-stacked cut wood_

Self-critique: ran clean (self_critique.py passed)

- commit_token: null -> "1-1bb5f0"
- entities: null -> [{"name": "The roofed ruin on the slope", "type": "location", "note": "Old stonework where Chad landed, vines structural. One corner still roofed by two fallen lintels. Someone is using it: cold fire ring of eight carried stones, ash dry and unrained-on, and cut wood stacked dry against the back wall. Not abandoned."}]
- scene: null -> "Early morning, Day 1 of Seedmonth, in the Northern March. Chad has climbed roughly two hundred yards upslope to the vine-covered stonework. He has found a cold fire ring of eight set stones and an armful of cut, squared, dry-stacked wood under the one corner that still has a roof. A single thin column of hearth smoke stands up out of the trees downhill, distance unknown."
- status: [] -> ["Twisted right ankle -- swollen, bears weight but worsens with use; calf tight after the climb to the ruin"]
- turn: 0 -> 1


### Turn 2 — 2026-09-16 18:07 UTC

_Turn 2: read the site -- one regular user, axe-cut wood, no water; rested the ankle; heard chopping to the NE_

Self-critique: ran clean (self_critique.py passed)

- commit_token: "1-1bb5f0" -> "2-6f31e2"
- entities: [{"name": "The roofed ruin on the slope", "type": "location", "note": "Old stonework where Chad landed, vines structural. One corner still roofed by two fallen lintels. Someone is using it: cold fire ring of eight carried stones, ash dry and unrained-on, and cut wood stacked dry against the back wall. Not abandoned."}] -> [{"name": "The roofed ruin on the slope", "type": "location", "note": "Old stonework where Chad landed, vines structural, one corner roofed by fallen lintels. Used regularly by ONE person, not a camp: a single sitting-patch with heel-scuffs and a round set-down mark for a flat-bottomed pot, 11 pieces of seasoned wood cut with an axe (not a saw) and stacked dry, and a fire ring with at least two fires' worth of layered ash. NO water at or near the ruin -- searched and not found."}]
- scene: "Early morning, Day 1 of Seedmonth, in the Northern March. Chad has climbed roughly two hundred yards upslope to the vine-covered stonework. He has found a cold fire ring of eight set stones and an armful of cut, squared, dry-stacked wood under the one corner that still has a roof. A single thin column of hearth smoke stands up out of the trees downhill, distance unknown." -> "Late morning, Day 1 of Seedmonth, under the lintels at the ruin. Chad has searched the immediate area and is sitting against the back wall with his bad leg up on a stone. He has heard an axe working steadily in the trees to the northeast, out of sight. The hearth smoke is still visible downhill."
- status: ["Twisted right ankle -- swollen, bears weight but worsens with use; calf tight after the climb to the ruin"] -> ["Twisted right ankle -- swollen; eased by ten minutes elevated on a fallen stone, but still worsens with use", "No water since arrival; mouth dry. Nothing eaten or drunk in Eldara."]
- turn: 1 -> 2


### Turn 2 — 2026-09-16 18:08 UTC

_Turn 2 correction: 'a language this place has never heard' logged as Chad's assumption, not canon; language stays unresolved per 2.12_

Self-critique: skipped (--skip-critique passed explicitly)

- commit_token: "2-6f31e2" -> "2-8674dd"
- continuity_notes: null -> ["Turn 2: the narration called Chad's muttered word 'a language this place has never heard'. Read as a world fact that oversteps ELDARA_REFERENCE.md 2.12, which says not to assume mutual intelligibility OR a total barrier, and to resolve it on-screen the first time Chad tries to communicate with someone. He spoke to nobody, so nothing was established. Treat that phrase as Chad's own assumption, not canon: language remains UNRESOLVED and is still to be settled in-scene at the first real attempt."]

