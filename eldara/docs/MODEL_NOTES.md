# Notes on Running Eldara with Different Models

This project's prompts are model-agnostic in principle — `GM_INSTRUCTIONS.md`
doesn't assume any particular model — but in practice, models vary in how
reliably they follow a long, rule-heavy system prompt over many turns.

## General guidance

- **Context length matters more than raw capability here.** `GM_INSTRUCTIONS.md`,
  `ELDARA_REFERENCE.md`, and `CHAD_BACKSTORY.md` together are long. A model
  with a short effective context window will start dropping rules from
  memory well before it runs out of listed context length. If you notice
  drift (invented gear, forgotten NPCs), suspect context pressure first.
- **The STATE_CHANGE marker and turn_gate.py are a safety net, not a
  guarantee of good narration.** They only catch "did a commit actually
  happen," not "was the commit's content actually correct." Use the
  periodic continuity audit (`GM_INSTRUCTIONS.md`'s "Continuity audit"
  section) and the playtest audit (`python3 scripts/session.py audit`) to
  catch drift the marker system can't.
- **This project doesn't run the LLM itself.** Nothing in `scripts/` makes
  its own API calls to a model — narration always happens in whatever chat
  interface you're using (Claude's app, a browser, etc.), separately from
  the tooling described in `docs/OPERATING.md`. If you want the tooling
  itself to call a model automatically (for example, an automated prose-tone
  judge), that would need to be built as new, separate functionality with
  its own API credentials — it doesn't exist in this project currently.

## What a model needs to be good at for this to work well

1. Hold and follow the full `GM_INSTRUCTIONS.md` contract across a session.
2. Reliably draft valid JSON matching `state_schema.json`'s shape when
   asked to. This is the single most common failure point in practice —
   malformed JSON that `validate_state.py` correctly rejects.
3. Write in the specific tone described in the Prose Craft section rather
   than defaulting to a generic assistant register.

A model that struggles with (2) above is usually a capability issue, not
something more context or a bigger local model file would fix on its own.

## `self_critique.py`'s load-bearing limit, and what would actually close it

`self_critique.py`'s invented-gear check is pattern matching against a
finite set of sentence shapes ("his sword", "his grandfather's sword"),
not comprehension. It can't distinguish an item genuinely attributed to
Chad from one merely mentioned near him ("the sword at his hip", "the
weapon in his hand gleamed — a longsword") — closing that specific gap
needs the sentence's actual meaning resolved, which pattern matching
structurally cannot do no matter how many phrase variants are added.

**What would close it, and at what cost:**

- **A real LLM call** (the Anthropic API, or any other) judging "does
  this narration attribute an unlisted item to Chad" as a semantic
  question — this is the only approach that resolves meaning rather than
  shape. Real per-commit API cost and a new network-failure mode this
  script doesn't currently have; not built into this project as of this
  writing. This is the "own API credentials" option referenced above.
- **A local dependency parser (e.g. spaCy)**, entirely offline, no API
  key — genuinely raises the ceiling above plain regex by identifying
  grammatical possession (`poss`, `nsubj` relations) more reliably than
  a "his ... noun" pattern, closing cases like adjective insertion more
  robustly than the current hand-written regex. It does NOT close the
  metonymy cases above ("the sword at his hip") on its own — those need
  coreference resolution too (what does "the sword" refer to in this
  scene), which in practice means a heavier local model, not just a
  parser. Real memory cost if you go this route: loading
  `en_core_web_sm` alone measures at roughly 150–250MB resident, growing
  further under repeated calls per spaCy's own issue tracker — a real
  consideration on `VM.Standard.E2.1.Micro`'s ~1GB ceiling with no swap
  by default (see `LOCAL.md`), much less so on `VM.Standard.A1.Flex`'s
  larger allocation. Neither shape costs more money either way — this is
  a memory-headroom question, not a billing one.
- **Leaning on the human**, which is what this project already does and
  costs nothing to build further: the continuity audit and the playtest
  audit's Pass 3 exist specifically because pattern matching can't do
  full judgment. Past a certain point, the marginal hour is better spent
  making sure these actually run on schedule than widening the regex or
  standing up a new model dependency for a gap this narrow.

