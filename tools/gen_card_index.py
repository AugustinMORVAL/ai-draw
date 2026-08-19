#!/usr/bin/env python3
"""Regenerate data/pilot-864/cards.json, the app's card index.

The executor never needs card names -- it deals in codes -- but a user pasting a
decklist does, and so does anyone reading a flag that says why a card was rejected.
This is a display-and-legality index, not a second source of truth about the pool:
membership still comes from `data/pilot-864/pool.txt` (CONTEXT.md), and this script
fails if the two disagree.

Two tiers, because the domain has two tiers:

  ``pool``   the 864 codes the frozen Pilot can represent, with the metadata the UI
             and the Masking preview need (name, kind, race, deck section, limit)
             and the printed card text the inspector reads out.
  ``known``  every other card in `cards.cdb`, name only. Being here means the C++
             core knows the card and the Pilot does not -- exactly the distinction
             CONTEXT.md warns not to collapse. It is what lets the app say
             "Dark Magician is a real card, but it is not in the supported pool"
             instead of "unknown card".
  ``alias``  alt-art printings: a code that names the same card as another code.
             `.ydk` exports are full of them, and 60 of them point at cards that
             *are* in the pool -- dropping them would reject a supported card for
             the crime of being the pretty version. Aliases that are themselves
             pool members (59 of them, mostly Tokens) stay in ``pool``: the Pilot
             has an embedding row for that exact code, so membership wins.

Both sources are pinned, so the file regenerates byte-identically:

  cards.cdb   mycard/ygopro-database @ 7b18743 -- the same URL and commit the
              ygoenv build fetches (`vendor/ygo-agent/Makefile`), so names here are
              the names the executor's own database carries.
  lflist.conf mycard/ygopro @ 7042373 -- the historical OCG/TCG banlists. We read
              the OCG list in force when the Pilot's pool was frozen, not today's:
              upstream's last push was 2024-08-16 (ADR-0001), so the deck a user
              pastes is judged against 2024.7, the list those cards were legal under.

Usage:
    python tools/gen_card_index.py [--check]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data/pilot-864/pool.txt"
OUT = ROOT / "data/pilot-864/cards.json"

CDB_URL = (
    "https://github.com/mycard/ygopro-database/raw/"
    "7b1874301fc1aa52bd60585589f771e372ff52cc/locales/en-US/cards.cdb"
)
LFLIST_URL = (
    "https://raw.githubusercontent.com/mycard/ygopro/"
    "7042373189a8d1e39fb38b3b11f71edca23d06c2/lflist.conf"
)
BANLIST = "2024.7"

# ygopro type bits (`common.h`). Only the ones that change where a card may live.
TYPE_MONSTER = 0x1
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_TOKEN = 0x4000
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000
TYPE_EXTRA = TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK

SUBTYPES = {
    0x10: "normal",
    0x20: "effect",
    0x40: "fusion",
    0x80: "ritual",
    0x100: "trap-monster",
    0x200: "spirit",
    0x400: "union",
    0x800: "gemini",
    0x1000: "tuner",
    0x2000: "synchro",
    0x10000: "quick-play",
    0x20000: "continuous",
    0x40000: "equip",
    0x80000: "field",
    0x100000: "counter",
    0x200000: "flip",
    0x400000: "toon",
    0x800000: "xyz",
    0x1000000: "pendulum",
    0x2000000: "special-summon",
    0x4000000: "link",
}

RACES = {
    0x1: "Warrior",
    0x2: "Spellcaster",
    0x4: "Fairy",
    0x8: "Fiend",
    0x10: "Zombie",
    0x20: "Machine",
    0x40: "Aqua",
    0x80: "Pyro",
    0x100: "Rock",
    0x200: "Winged Beast",
    0x400: "Plant",
    0x800: "Insect",
    0x1000: "Thunder",
    0x2000: "Dragon",
    0x4000: "Beast",
    0x8000: "Beast-Warrior",
    0x10000: "Dinosaur",
    0x20000: "Fish",
    0x40000: "Sea Serpent",
    0x80000: "Reptile",
    0x100000: "Psychic",
    0x200000: "Divine-Beast",
    0x400000: "Creator God",
    0x800000: "Wyrm",
    0x1000000: "Cyberse",
    0x2000000: "Illusion",
}

ATTRIBUTES = {
    0x1: "EARTH",
    0x2: "WATER",
    0x4: "FIRE",
    0x8: "WIND",
    0x10: "LIGHT",
    0x20: "DARK",
    0x40: "DIVINE",
}


def fetch(url: str, dest: Path) -> Path:
    """Download once into a temp dir. Neither source is committed."""
    if dest.exists():
        return dest
    print(f"fetching {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=180) as response:
        dest.write_bytes(response.read())
    return dest


def parse_lflist(text: str, name: str) -> dict[int, int]:
    """The per-card copy limit of one named list. Absent means the default of 3."""
    limits: dict[int, int] = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("!"):
            current = line[1:].strip()
            continue
        if current != name or not line or line.startswith("#"):
            continue
        match = re.match(r"^(\d+)\s+(-?\d+)", line)
        if match:
            limits[int(match.group(1))] = int(match.group(2))
    if not limits:
        raise SystemExit(f"banlist {name!r} not found in lflist.conf")
    return limits


def kind_of(type_bits: int) -> str:
    if type_bits & TYPE_SPELL:
        return "spell"
    if type_bits & TYPE_TRAP:
        return "trap"
    if type_bits & TYPE_MONSTER:
        return "monster"
    return "other"


def section_of(type_bits: int) -> str:
    """Where a card may be put. A Token may be put nowhere -- it is only ever made."""
    if type_bits & TYPE_TOKEN:
        return "token"
    if type_bits & TYPE_EXTRA:
        return "extra"
    return "main"


def subtypes_of(type_bits: int) -> list[str]:
    return [name for bit, name in sorted(SUBTYPES.items()) if type_bits & bit]


def build() -> dict:
    tmp = Path(tempfile.gettempdir()) / "ai-draw-card-sources"
    tmp.mkdir(exist_ok=True)
    cdb = fetch(CDB_URL, tmp / "cards.cdb")
    lflist = fetch(LFLIST_URL, tmp / "lflist.conf")

    limits = parse_lflist(lflist.read_text(encoding="utf-8", errors="replace"), BANLIST)
    pool_codes = [int(line) for line in POOL.read_text().split() if line.strip()]

    connection = sqlite3.connect(cdb)
    rows = {
        row[0]: row
        for row in connection.execute(
            "select d.id, t.name, d.type, d.race, d.attribute, d.level, d.atk, "
            "d.def, d.alias, t.desc from datas d join texts t on t.id = d.id"
        )
    }
    connection.close()

    absent = [code for code in pool_codes if code not in rows]
    if absent:
        raise SystemExit(
            f"{len(absent)} pool codes are missing from cards.cdb: {absent[:5]} -- "
            "the pinned database no longer covers the pool"
        )

    pool: dict[str, dict] = {}
    for code in pool_codes:
        (
            _,
            name,
            type_bits,
            race,
            attribute,
            level,
            atk,
            defense,
            _alias,
            desc,
        ) = rows[code]
        monster = bool(type_bits & TYPE_MONSTER)
        pool[str(code)] = {
            "name": name,
            "kind": kind_of(type_bits),
            "subtypes": subtypes_of(type_bits),
            "section": section_of(type_bits),
            "race": RACES.get(race) if monster else None,
            "attribute": ATTRIBUTES.get(attribute) if monster else None,
            "level": (level & 0xFF) if monster else None,
            "atk": atk if monster else None,
            "def": defense if monster and not (type_bits & TYPE_LINK) else None,
            "limit": limits.get(code, 3),
            # The printed card text. Only the pool carries it: it is what the card
            # inspector reads out, and no UI ever inspects a card the Pilot cannot
            # see. Carrying it for all 12,384 known cards would quadruple the index
            # to buy nothing.
            "desc": " ".join((desc or "").split()),
        }

    in_pool = set(pool_codes)
    alias = {
        str(code): row[8]
        for code, row in sorted(rows.items())
        if row[8] and row[8] != code and code not in in_pool
    }
    aliased = {int(code) for code in alias}
    known = {
        str(code): row[1]
        for code, row in sorted(rows.items())
        if code not in in_pool and code not in aliased
    }

    return {
        "meta": {
            "generated_by": "tools/gen_card_index.py",
            "cards_cdb": CDB_URL,
            "lflist": LFLIST_URL,
            "banlist": BANLIST,
            "banlist_note": (
                "The OCG list in force when the Pilot's pool was frozen "
                "(upstream last pushed 2024-08-16, ADR-0001), not today's."
            ),
            "pool_size": len(pool),
            "known_size": len(known),
            "alias_size": len(alias),
        },
        "pool": pool,
        "known": known,
        "alias": alias,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the committed file is stale"
    )
    args = parser.parse_args()

    index = build()
    text = json.dumps(index, indent=1, ensure_ascii=False, sort_keys=False) + "\n"

    if args.check:
        if not OUT.exists():
            print(f"{OUT} does not exist", file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT} is stale -- rerun tools/gen_card_index.py", file=sys.stderr)
            return 1
        print(f"{OUT} is up to date")
        return 0

    OUT.write_text(text, encoding="utf-8")
    meta = index["meta"]
    sections: dict[str, int] = {}
    for card in index["pool"].values():
        sections[card["section"]] = sections.get(card["section"], 0) + 1
    print(
        f"wrote {OUT.relative_to(ROOT)}: {meta['pool_size']} pool cards "
        f"({', '.join(f'{n} {s}' for s, n in sorted(sections.items()))}), "
        f"{meta['known_size']} known-but-unsupported, {meta['alias_size']} alt-art "
        f"aliases, banlist {meta['banlist']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
