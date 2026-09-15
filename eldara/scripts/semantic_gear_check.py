#!/usr/bin/env python3
"""Decide whether a possessed noun is an ITEM by looking it up in
WordNet, instead of matching it against a hand-written word list.

WHY THIS EXISTS
---------------
self_critique.py's invented-gear check is two separate things bolted
together: a set of regexes that find possession ("his X", "his
grandfather's X"), and a hardcoded 35-word list of what counts as an
item. The regexes are fine. The list is the limitation -- "his falchion"
and "his kukri" pass silently because nobody wrote those words down.

The obvious fix is a longer list, which just moves the boundary. The
better fix is to stop maintaining a list at all: WordNet already
organizes English nouns into is-a chains, so "is this noun a man-made
object" is a lookup, not an opinion. sword -> weapon -> instrumentality
-> artifact. competence -> ability -> cognition -> abstraction.

Note what this does NOT need: a dependency parser. The grammar half
already works. Swapping the list for WordNet closes the larger hole with
one dependency, and spaCy would only add better possession grammar on
top (see docs/DEVICES_AND_SERVICES.md for that tradeoff).

WHY IT IS A HARNESS FIRST
-------------------------
The idea is only as good as its false-positive rate, and prose is full
of possessed nouns that are not items -- "his competence", "his
childhood", "his hands". Measured against this project's own writing,
roughly 24 of 25 "his X" constructions are not gear. A check that
flagged those would be worse than no check, because a noisy gate gets
skipped.

So this ships with --self-test, which runs the classifier against
labelled words drawn from this project's actual prose and from the
weapon nouns the current 35-word list misses, and reports exactly what
it got wrong. Run that BEFORE wiring any of this into self_critique.py.
Nothing here is imported by the commit path; adopting it is a separate,
later decision that should be made on the numbers that --self-test
prints.

WHAT IT STILL CANNOT DO
-----------------------
WordNet resolves vocabulary, not reference. It does not know that "the
sword at his hip" is Chad's, it cannot tell a remembered item from a
carried one, and it has no memory of previous turns. Those gaps are
unchanged -- see docs/MODEL_NOTES.md.

USAGE
-----
    python3 scripts/semantic_gear_check.py --self-test
        Score the classifier against labelled words and print every
        misclassification. Start here.

    python3 scripts/semantic_gear_check.py --check turn.txt
        Run the check over a drafted turn, the way self_critique.py
        would, and print what it would flag.

    python3 scripts/semantic_gear_check.py --explain falchion
        Print a noun's WordNet hypernym chains, to see why it did or
        didn't classify as an item.

Requires the WordNet corpus: `pip install nltk` then
`python -m nltk.downloader wordnet`. It is a one-time download of tens
of megabytes; after that this runs entirely offline, with no API, no
credential, and no network access at commit time.
"""
import argparse
import functools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT_PATH = ROOT / "saves" / "current.json"

# A noun counts as an item if one of its WordNet hypernym chains passes
# through any of these. 'artifact' is the load-bearing one: it means
# man-made object, which excludes body parts ("his hands") that would
# slip through a looser test against 'physical_entity'.
ITEM_ROOTS = {"artifact", "instrumentality", "instrument"}


def load_wordnet():
    """Return the WordNet corpus reader, or None with a printed reason.

    Kept optional in the same spirit as validate_state.py's handling of
    jsonschema: a machine without the corpus should get a clear message,
    not a traceback.
    """
    try:
        from nltk.corpus import wordnet
    except ImportError:
        print("nltk is not installed -- `pip install nltk`, then "
              "`python -m nltk.downloader wordnet`.")
        return None
    try:
        wordnet.synsets("test", pos=wordnet.NOUN)
    except LookupError:
        print("nltk is installed but the WordNet corpus is missing -- run "
              "`python -m nltk.downloader wordnet`.")
        return None
    return wordnet


@functools.lru_cache(maxsize=4096)
def _chains(noun, first_sense_only):
    """Hypernym chains for a noun, as sets of lemma names."""
    wn = load_wordnet.cached
    senses = wn.synsets(noun.lower(), pos=wn.NOUN)
    if first_sense_only:
        # WordNet orders senses by frequency, so the first is the
        # everyday meaning. Restricting to it avoids classifying "hand"
        # as an item because a clock has hands.
        senses = senses[:1]
    return [
        {s.name().split(".")[0] for s in path}
        for sense in senses
        for path in sense.hypernym_paths()
    ]


def is_item(noun, first_sense_only=True):
    """Is this noun a man-made object, per WordNet?"""
    return any(ITEM_ROOTS & chain for chain in _chains(noun, first_sense_only))


# Possession shapes, deliberately the same ones self_critique.py already
# matches -- plus a named possessor, which it currently misses entirely
# ("Chad's sword" passes its check clean).
POSSESSIVE_PATTERNS = [
    r"\bhis\s+(\w+)\b",
    r"\bhis(?:\s+\w+){1,3}\s+(\w+)\b",
    r"\bhis\s+\w+'s\s+(\w+)\b",
    r"\b[A-Z]\w+'s\s+(\w+)\b",
]


def possessed_nouns(text):
    """Every noun the narration gives to someone, as (noun, phrase)."""
    found = {}
    for pattern in POSSESSIVE_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            noun = m.group(1).lower()
            found.setdefault(noun, m.group(0))
    return found


def check(text, gear_names, first_sense_only=True):
    """Flag possessed nouns that are items but aren't in gear."""
    known = {g.lower() for g in gear_names}
    flags = []
    for noun, phrase in sorted(possessed_nouns(text).items()):
        if any(noun in name or name in noun for name in known):
            continue
        if is_item(noun, first_sense_only):
            flags.append(f"'{phrase}' names an item ('{noun}') with no matching gear entry")
    return flags


def load_gear_names():
    if not CURRENT_PATH.exists():
        return []
    try:
        state = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, RecursionError):
        return []
    gear = state.get("gear", [])
    return [g.get("name", "") for g in gear if isinstance(g, dict)]


# --- labelled data for --self-test -------------------------------------
# Not invented: the first group is every distinct "his X" noun found in
# this project's own docs/CHAD_BACKSTORY.md and prompts/FIRST_MESSAGE.md,
# which is the real prose this check would run against. The second is
# item nouns absent from self_critique.py's 35-word list.

MUST_NOT_FLAG = [
    "competence", "childhood", "thirties", "weight", "self", "reading",
    "memory", "life", "judgment", "interiority", "parents", "mother",
    "skin", "hands", "brow", "breath", "courage", "shoulder", "name",
]
MUST_FLAG = [
    "falchion", "kukri", "bardiche", "glaive", "naginata", "scimitar",
    "cudgel", "pike", "morningstar", "tunic", "lantern", "waterskin",
    "bedroll", "rope",
]


def self_test():
    wn = load_wordnet()
    if wn is None:
        print("\nCannot score the classifier without the corpus -- see above.")
        return 1
    load_wordnet.cached = wn

    print("Scoring WordNet item-classification against labelled nouns.\n")
    overall_ok = True
    for first_only in (True, False):
        mode = "first sense only" if first_only else "any sense"
        wrong_quiet = [w for w in MUST_NOT_FLAG if is_item(w, first_only)]
        wrong_loud = [w for w in MUST_FLAG if not is_item(w, first_only)]
        correct = (len(MUST_NOT_FLAG) - len(wrong_quiet)) + (len(MUST_FLAG) - len(wrong_loud))
        total = len(MUST_NOT_FLAG) + len(MUST_FLAG)
        print(f"-- {mode} --")
        print(f"   {correct}/{total} correct")
        print(f"   false positives (would flag ordinary prose): "
              f"{', '.join(wrong_quiet) if wrong_quiet else 'none'}")
        print(f"   missed items (would stay silent): "
              f"{', '.join(wrong_loud) if wrong_loud else 'none'}")
        if wrong_quiet or wrong_loud:
            overall_ok = False
        print()

    print("How to read this: false positives are the number that decides "
          "adoption.\nA check that flags ordinary narration gets skipped, "
          "and a skipped gate\ncatches nothing. Missed items are the "
          "status quo -- the current list\nmisses all of them already.")
    return 0 if overall_ok else 2


def explain(noun):
    wn = load_wordnet()
    if wn is None:
        return 1
    load_wordnet.cached = wn
    senses = wn.synsets(noun.lower(), pos=wn.NOUN)
    if not senses:
        print(f"'{noun}' is not in WordNet as a noun.")
        return 0
    print(f"'{noun}' -- {len(senses)} noun sense(s); first sense is the common one.\n")
    for i, sense in enumerate(senses):
        marker = " (first)" if i == 0 else ""
        print(f"  {sense.name()}{marker}: {sense.definition()}")
        for path in sense.hypernym_paths()[:1]:
            print("    " + " -> ".join(s.name().split(".")[0] for s in path))
    print(f"\nclassified as an item: first-sense={is_item(noun, True)} "
          f"any-sense={is_item(noun, False)}")
    return 0


def run_check(path):
    wn = load_wordnet()
    if wn is None:
        return 1
    load_wordnet.cached = wn
    text = Path(path).read_text(encoding="utf-8")
    flags = check(text, load_gear_names())
    if not flags:
        print("CLEAN: no possessed noun classified as an unlisted item.")
        print("(Vocabulary only -- this cannot see 'the sword at his hip'.)")
        return 0
    print("FLAGGED:")
    for f in flags:
        print(f"  - {f}")
    return 1


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true",
                        help="Score the classifier against labelled nouns. Start here.")
    parser.add_argument("--check", metavar="FILE",
                        help="Run the check over a drafted turn.")
    parser.add_argument("--explain", metavar="NOUN",
                        help="Show a noun's WordNet chains and classification.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.explain:
        return explain(args.explain)
    if args.check:
        return run_check(args.check)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
