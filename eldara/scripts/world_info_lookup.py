#!/usr/bin/env python3
"""Keyword -> lore section lookup, backed by docs/ELDARA_REFERENCE.md
(world canon) and docs/CHAD_BACKSTORY.md (Chad's personal/old-world canon).

Pulls just the relevant section(s) of one reference file instead of
dumping either file whole, so a scene needing one fact doesn't cost the
model the entire lore document in context.

Usage:
    python3 scripts/world_info_lookup.py <keyword>
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
WORLD_REFERENCE = DOCS / "ELDARA_REFERENCE.md"
CHAD_REFERENCE = DOCS / "CHAD_BACKSTORY.md"

# Keyword -> (source file, [section ids]). World reference sections are
# numbered ("## 2.x Heading"); Chad's backstory file uses plain headings
# ("## Heading").
KEYWORDS = {
    "region": (WORLD_REFERENCE, ["2.1"]), "geography": (WORLD_REFERENCE, ["2.1"]),
    "heartlands": (WORLD_REFERENCE, ["2.1"]),
    "elderwoods": (WORLD_REFERENCE, ["2.1"]), "border marches": (WORLD_REFERENCE, ["2.1"]),
    "northern march": (WORLD_REFERENCE, ["2.1"]),
    "raid": (WORLD_REFERENCE, ["2.1"]), "mining rights": (WORLD_REFERENCE, ["2.1"]),
    "mining dispute": (WORLD_REFERENCE, ["2.1"]), "osgood": (WORLD_REFERENCE, ["2.1"]),
    "disappearances": (WORLD_REFERENCE, ["2.1"]),
    "displaced": (WORLD_REFERENCE, ["2.1"]), "refugee": (WORLD_REFERENCE, ["2.1"]),
    "seasons": (WORLD_REFERENCE, ["2.1"]), "weather": (WORLD_REFERENCE, ["2.1"]),
    "history": (WORLD_REFERENCE, ["2.2"]), "sundering": (WORLD_REFERENCE, ["2.2"]),
    "realm": (WORLD_REFERENCE, ["2.3"]), "governance": (WORLD_REFERENCE, ["2.3"]),
    "valenor": (WORLD_REFERENCE, ["2.3"]),
    "settlement": (WORLD_REFERENCE, ["2.3"]), "highcrown": (WORLD_REFERENCE, ["2.3"]),
    "silverhaven": (WORLD_REFERENCE, ["2.3"]), "thrum-gate": (WORLD_REFERENCE, ["2.3"]),
    "millbrook": (WORLD_REFERENCE, ["2.3"]), "riverwatch": (WORLD_REFERENCE, ["2.3"]),
    "port vessar": (WORLD_REFERENCE, ["2.3"]), "npc": (WORLD_REFERENCE, ["2.3"]),
    "chad's nature": (WORLD_REFERENCE, ["2.3"]), "outlander": (WORLD_REFERENCE, ["2.3"]),
    "stranger": (WORLD_REFERENCE, ["2.3"]), "who is chad": (WORLD_REFERENCE, ["2.3"]),
    "hollow creek": (WORLD_REFERENCE, ["2.3"]), "ashen kettle": (WORLD_REFERENCE, ["2.3"]),
    "inn": (WORLD_REFERENCE, ["2.3"]), "market": (WORLD_REFERENCE, ["2.3"]),
    "market day": (WORLD_REFERENCE, ["2.3"]), "caravan": (WORLD_REFERENCE, ["2.3"]),
    "dell": (WORLD_REFERENCE, ["2.3"]), "innkeeper": (WORLD_REFERENCE, ["2.3"]),
    "ironwood": (WORLD_REFERENCE, ["2.3"]),
    "veyl": (WORLD_REFERENCE, ["2.3"]), "artifact": (WORLD_REFERENCE, ["2.3"]),
    "restricted artifacts": (WORLD_REFERENCE, ["2.3"]),
    "ashby": (WORLD_REFERENCE, ["2.3"]), "smith": (WORLD_REFERENCE, ["2.3"]),
    "vane": (WORLD_REFERENCE, ["2.3"]), "talstan": (WORLD_REFERENCE, ["2.3"]),
    "watch": (WORLD_REFERENCE, ["2.3"]), "debt enforcement": (WORLD_REFERENCE, ["2.3"]),
    "wick": (WORLD_REFERENCE, ["2.3"]), "healer": (WORLD_REFERENCE, ["2.3"]),
    "hurst": (WORLD_REFERENCE, ["2.3"]),
    "aldric": (WORLD_REFERENCE, ["2.3"]), "king aldric": (WORLD_REFERENCE, ["2.3"]),
    "marchand": (WORLD_REFERENCE, ["2.3"]), "duke harlan": (WORLD_REFERENCE, ["2.3"]),
    "thrain": (WORLD_REFERENCE, ["2.3"]), "ironvein": (WORLD_REFERENCE, ["2.3"]),
    "stonefist": (WORLD_REFERENCE, ["2.3"]), "goldhammer": (WORLD_REFERENCE, ["2.3"]),
    "sylvandar": (WORLD_REFERENCE, ["2.3"]), "elandriel": (WORLD_REFERENCE, ["2.3"]),
    "moonshadow": (WORLD_REFERENCE, ["2.3"]), "vaelith": (WORLD_REFERENCE, ["2.3"]),
    "greenbottle": (WORLD_REFERENCE, ["2.3"]), "tilda": (WORLD_REFERENCE, ["2.3"]),
    "leafwhisper": (WORLD_REFERENCE, ["2.3"]), "underhill": (WORLD_REFERENCE, ["2.3"]),
    "riverfoot": (WORLD_REFERENCE, ["2.3"]),
    "calendar": (WORLD_REFERENCE, ["2.4"]), "economy": (WORLD_REFERENCE, ["2.4"]),
    "currency": (WORLD_REFERENCE, ["2.4", "2.13"]), "coin": (WORLD_REFERENCE, ["2.4", "2.13"]),
    "copper": (WORLD_REFERENCE, ["2.4", "2.13"]), "silver": (WORLD_REFERENCE, ["2.4", "2.13"]),
    "gold": (WORLD_REFERENCE, ["2.4", "2.13"]),
    "grey market": (WORLD_REFERENCE, ["2.4"]), "smuggling": (WORLD_REFERENCE, ["2.4"]),
    "grain": (WORLD_REFERENCE, ["2.4"]), "wool": (WORLD_REFERENCE, ["2.4"]),
    "wine": (WORLD_REFERENCE, ["2.4"]), "spices": (WORLD_REFERENCE, ["2.4"]),
    "military": (WORLD_REFERENCE, ["2.5"]), "army": (WORLD_REFERENCE, ["2.5"]),
    "combat style": (WORLD_REFERENCE, ["2.5"]),
    "people": (WORLD_REFERENCE, ["2.6"]), "culture": (WORLD_REFERENCE, ["2.6"]),
    "elf": (WORLD_REFERENCE, ["2.6"]), "dwarf": (WORLD_REFERENCE, ["2.6"]),
    "halfling": (WORLD_REFERENCE, ["2.6"]), "human": (WORLD_REFERENCE, ["2.6"]),
    "greenmantle": (WORLD_REFERENCE, ["2.6"]), "moot": (WORLD_REFERENCE, ["2.6"]),
    "harvest moot": (WORLD_REFERENCE, ["2.6"]),
    "age": (WORLD_REFERENCE, ["2.6"]), "aging": (WORLD_REFERENCE, ["2.6"]),
    "old": (WORLD_REFERENCE, ["2.6"]), "half-elf": (WORLD_REFERENCE, ["2.6"]),
    "half-elves": (WORLD_REFERENCE, ["2.6"]),
    "magic": (WORLD_REFERENCE, ["2.7"]),
    "travel": (WORLD_REFERENCE, ["2.8"]), "route": (WORLD_REFERENCE, ["2.8"]),
    "road": (WORLD_REFERENCE, ["2.8"]),
    "holiday": (WORLD_REFERENCE, ["2.9"]), "festival": (WORLD_REFERENCE, ["2.9"]),
    "monster": (WORLD_REFERENCE, ["2.10"]), "hazard": (WORLD_REFERENCE, ["2.10"]),
    "creature": (WORLD_REFERENCE, ["2.10"]),
    "stoneward wisp": (WORLD_REFERENCE, ["2.10"]), "rootblight": (WORLD_REFERENCE, ["2.10"]),
    "vermin": (WORLD_REFERENCE, ["2.10"]),
    "wisp": (WORLD_REFERENCE, ["2.10"]), "will-o-wisp": (WORLD_REFERENCE, ["2.10"]),
    "goblin": (WORLD_REFERENCE, ["2.10"]), "orc": (WORLD_REFERENCE, ["2.10"]),
    "troll": (WORLD_REFERENCE, ["2.10"]), "rock drake": (WORLD_REFERENCE, ["2.10"]),
    "spirit": (WORLD_REFERENCE, ["2.10"]), "forest spirit": (WORLD_REFERENCE, ["2.10"]),
    "custom": (WORLD_REFERENCE, ["2.11"]), "etiquette": (WORLD_REFERENCE, ["2.11"]),
    "language": (WORLD_REFERENCE, ["2.12"]), "english": (WORLD_REFERENCE, ["2.12"]),
    "pricing": (WORLD_REFERENCE, ["2.13"]), "price": (WORLD_REFERENCE, ["2.13"]),
    "wage": (WORLD_REFERENCE, ["2.13"]), "cost": (WORLD_REFERENCE, ["2.13"]),
    "guild": (WORLD_REFERENCE, ["2.14"]), "profession": (WORLD_REFERENCE, ["2.14"]),
    "job": (WORLD_REFERENCE, ["2.14"]), "work": (WORLD_REFERENCE, ["2.14"]),
    "labor": (WORLD_REFERENCE, ["2.14"]), "hiring": (WORLD_REFERENCE, ["2.14"]),
    "foreman": (WORLD_REFERENCE, ["2.14"]),
    "portering": (WORLD_REFERENCE, ["2.14"]), "mine labor": (WORLD_REFERENCE, ["2.14"]),
    "ruin scavenging": (WORLD_REFERENCE, ["2.14a"]),
    "gloves": (WORLD_REFERENCE, ["2.14a"]), "first item": (WORLD_REFERENCE, ["2.14a"]),
    "religion": (WORLD_REFERENCE, ["2.15"]), "faith": (WORLD_REFERENCE, ["2.15"]),
    "clergy": (WORLD_REFERENCE, ["2.15"]), "shrine": (WORLD_REFERENCE, ["2.15"]),
    "waystation": (WORLD_REFERENCE, ["2.15"]),
    "sundering": (WORLD_REFERENCE, ["2.2"]),
    "war of the two crowns": (WORLD_REFERENCE, ["2.2"]),
    "silverwood accords": (WORLD_REFERENCE, ["2.2"]),
    "red harvest famine": (WORLD_REFERENCE, ["2.2"]), "famine": (WORLD_REFERENCE, ["2.2"]),
    # Chad's personal backstory (docs/CHAD_BACKSTORY.md) -- keyed by heading
    # text there rather than a section number.
    "chad": (CHAD_REFERENCE, ["Notes for the GM"]),
    "backstory": (CHAD_REFERENCE, ["Notes for the GM"]),
    "old world": (CHAD_REFERENCE, ["The eviction years", "What he doesn't have anymore"]),
    "eviction": (CHAD_REFERENCE, ["The eviction years"]),
    "walt": (CHAD_REFERENCE, ["The eviction years"]),
    "landlord": (CHAD_REFERENCE, ["The eviction years"]),
    "property manager": (CHAD_REFERENCE, ["The eviction years"]),
    "counterexample": (CHAD_REFERENCE, ["The eviction years"]),
    "single mother": (CHAD_REFERENCE, ["The eviction years"]),
    "owner": (CHAD_REFERENCE, ["The eviction years"]),
    "why chad volunteered": (CHAD_REFERENCE, ["The eviction years"]),
    "columbus": (CHAD_REFERENCE, ["Physical description"]),
    "back": (CHAD_REFERENCE, ["Physical description"]),
    "physical": (CHAD_REFERENCE, ["Physical description"]),
    "appearance": (CHAD_REFERENCE, ["Physical description"]),
    "mother": (CHAD_REFERENCE, ["Early life"]),
    "job history": (CHAD_REFERENCE, ["Work history *(the eviction years are the emotional center; this is the fuller shape around them)*"]),
    "work history": (CHAD_REFERENCE, ["Work history *(the eviction years are the emotional center; this is the fuller shape around them)*"]),
    "relationships": (CHAD_REFERENCE, ["Relationships"]),
    "family": (CHAD_REFERENCE, ["Relationships"]),
    "debt": (CHAD_REFERENCE, ["Why this matters going forward"]),
    "self-image": (CHAD_REFERENCE, ["Why this matters going forward"]),
    "private theory": (CHAD_REFERENCE, ["Why this matters going forward"]),
    "temperament": (CHAD_REFERENCE, ["Temperament"]),
    "personality": (CHAD_REFERENCE, ["Temperament"]),
    "tic": (CHAD_REFERENCE, ["Temperament"]), "habit": (CHAD_REFERENCE, ["Temperament"]),
    "humor": (CHAD_REFERENCE, ["Temperament"]), "sense of humor": (CHAD_REFERENCE, ["Temperament"]),
    "danger": (CHAD_REFERENCE, ["Temperament"]), "risk": (CHAD_REFERENCE, ["Temperament"]),
    "authority": (CHAD_REFERENCE, ["Temperament"]), "fairness": (CHAD_REFERENCE, ["Temperament"]),
    "cooking": (CHAD_REFERENCE, ["Temperament"]), "skill": (CHAD_REFERENCE, ["Temperament"]),
    "what he wants": (CHAD_REFERENCE, ["What He Wants Now"]), "goals": (CHAD_REFERENCE, ["What He Wants Now"]),
    "sensory": (CHAD_REFERENCE, ["Sensory Anchors"]),
    "door": (CHAD_REFERENCE, ["Sensory Anchors"]),
    "phone": (CHAD_REFERENCE, ["What he doesn't have anymore"]),
    "wallet": (CHAD_REFERENCE, ["What he doesn't have anymore"]),
    "keys": (CHAD_REFERENCE, ["What he doesn't have anymore"]),
}

WORLD_SECTION_PATTERN = re.compile(r"^## (\d+\.\d+a?) (.+)$", re.MULTILINE)
CHAD_SECTION_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)


def _load_world_sections(text):
    """Split the world reference file into {section_number: (heading, body)}."""
    matches = list(WORLD_SECTION_PATTERN.finditer(text))
    sections = {}
    for i, m in enumerate(matches):
        number, heading = m.group(1), m.group(2)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[number] = (heading, text[start:end].strip())
    return sections


def _load_chad_sections(text):
    """Split Chad's backstory file into {heading: (heading, body)} -- keyed
    by heading text since that file has no numbering scheme."""
    matches = list(CHAD_SECTION_PATTERN.finditer(text))
    sections = {}
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[heading] = (heading, text[start:end].strip())
    return sections


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/world_info_lookup.py <keyword>")
        print("Available keys:", ", ".join(sorted(KEYWORDS.keys())))
        return

    key = " ".join(sys.argv[1:]).lower()
    matched = KEYWORDS.get(key)
    if matched is None:
        # Matches on word boundaries rather than raw substrings, and
        # prefers the longest (most specific) match among those that
        # qualify. Two distinct failure modes motivate this:
        #
        # 1. Raw substring containment lets a keyword match purely by
        #    coincidence of spelling inside an unrelated word -- e.g.
        #    querying "who was his manager" would match the keyword
        #    "age" (found inside "man-AGE-r") and return fantasy-
        #    peoples/aging lore (§2.6) instead of Chad's actual
        #    property-manager backstory. That's a false match with no
        #    semantic relation at all, not a specificity problem --
        #    word-boundary matching below prevents it.
        # 2. Even among genuinely related matches, dict-insertion order
        #    alone would decide the winner rather than specificity --
        #    e.g. "old world stuff" would resolve to the short keyword
        #    "old" (§2.6) instead of the more specific "old world"
        #    (Chad's backstory) purely because of insertion order.
        #    Preferring the longest qualifying match below prevents this.
        key_words = set(re.findall(r"\w+", key))

        def keyword_matches(k):
            k_words = re.findall(r"\w+", k)
            # A multi-word keyword like "old world" must appear as a
            # contiguous phrase in the query; a single-word keyword must
            # appear as one of the query's own words.
            if len(k_words) > 1:
                return k in key
            return k_words[0] in key_words if k_words else False

        candidates = [k for k in KEYWORDS if keyword_matches(k)]
        if candidates:
            best = max(candidates, key=len)
            matched = KEYWORDS[best]

    if not matched:
        print(f"No lore match for: {key}")
        print("Available keys:", ", ".join(sorted(KEYWORDS.keys())))
        return

    source, section_ids = matched
    if not source.exists():
        print(f"Reference file missing: {source}")
        return

    text = source.read_text(encoding="utf-8")
    sections = _load_world_sections(text) if source == WORLD_REFERENCE else _load_chad_sections(text)

    for sid in section_ids:
        heading, body = sections.get(sid, (None, None))
        if heading is None:
            print(f"Section {sid!r} missing from {source}")
            continue
        label = f"{sid} {heading}" if source == WORLD_REFERENCE else heading
        print(f"=== {label} ===")
        print(body)
        print()


if __name__ == "__main__":
    main()
