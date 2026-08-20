#!/usr/bin/env python3
"""Regenerate data/pilot-864/gauntlet.json, the ten decks the Gauntlet plays.

The executor only ever needed the Gauntlet's *names* -- it sits the Pilot behind a
deck file and reports a win rate -- so those were a tuple in `executor.py`. A duel
replay needs more than the name: a log that says "Sky Striker Ace summons Shaddoll
Dragon" is a fabrication in the one place the app draws a board a user reads card by
card. So the ten decklists ship as data, and each seat in a replay plays its own
cards.

The order in this file is the Gauntlet's fixed order, and it is load-bearing: it is
fixed within a phase so two decks' matchup rows line up (CONTEXT.md). It matches the
order the tuple in `executor.py` had.

Sources, both already in the repo, so this script never touches the network:

  vendor/ygo-agent/assets/deck/*.ydk   the shipped meta decks the Gauntlet is made
                                       of, at whatever commit the submodule is on.
  data/pilot-864/cards.json            for the alias map and the pool, so a code is
                                       written here as the printing the index
                                       carries and this script fails if the deck
                                       plays a card the Pilot cannot represent.

The output is committed so the API container needs neither the submodule nor the
network -- the same reason `cards.json` is committed.

Usage:
    python tools/gen_gauntlet.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECKS = ROOT / "vendor/ygo-agent/assets/deck"
CARDS = ROOT / "data/pilot-864/cards.json"
OUT = ROOT / "data/pilot-864/gauntlet.json"

#: The Gauntlet, in its fixed order: the display name, and the shipped deck file it
#: is. One entry per opponent, and nothing here is chosen per run -- a Gauntlet that
#: changed between two decks' evaluations would make their win rates incomparable.
GAUNTLET = (
    ("Snake-Eye Fire", "SnakeEyeFire.ydk"),
    ("Labrynth", "Labrynth.ydk"),
    ("Branded", "Branded.ydk"),
    ("Shaddoll", "Shaddoll.ydk"),
    ("Sky Striker Ace", "SkyStrikerAce.ydk"),
    ("Centur-Ion", "CenturIon.ydk"),
    ("Blue-Eyes", "BlueEyes.ydk"),
    ("Floowandereeze", "Floowandereeze.ydk"),
    ("Tenyi Sword", "TenyiSword.ydk"),
    ("Chimera", "Chimera.ydk"),
)


def read_ydk(path: Path) -> tuple[list[int], list[int]]:
    """The main and extra deck of a `.ydk`, in file order.

    The Side Deck is dropped: phase 1 has no use for one (there is no Bo3), and a
    replay is a duel, not a match.
    """
    main: list[int] = []
    extra: list[int] = []
    section: list[int] | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#main"):
            section = main
        elif line.startswith("#extra"):
            section = extra
        elif line.startswith("!side"):
            section = None
        elif line.startswith(("#", "!")):
            continue
        elif section is not None and line.isdigit():
            section.append(int(line))
    return main, extra


def build() -> dict:
    index = json.loads(CARDS.read_text(encoding="utf-8"))
    pool = {int(code) for code in index["pool"]}
    alias = {int(code): int(target) for code, target in index["alias"].items()}

    def resolve(code: int) -> int:
        """The printing the card index carries. `.ydk` exports are full of alt art."""
        return alias.get(code, code)

    decks = []
    for name, filename in GAUNTLET:
        path = DECKS / filename
        if not path.exists():
            raise SystemExit(
                f"{path.relative_to(ROOT)} is missing -- is the ygo-agent submodule "
                "checked out? (git submodule update --init)"
            )
        main, extra = read_ydk(path)
        main = [resolve(code) for code in main]
        extra = [resolve(code) for code in extra]
        # The Gauntlet is what the Pilot plays *against*, but it plays it inside the
        # same 864-card representation, so a card the pool cannot represent in one of
        # these decks means the pool and the Gauntlet have drifted apart.
        outside = sorted({code for code in main + extra if code not in pool})
        if outside:
            raise SystemExit(
                f"{name}: {len(outside)} cards are outside the supported pool "
                f"({outside[:5]}) -- the Gauntlet and data/pilot-864/pool.txt "
                "no longer describe the same phase"
            )
        decks.append(
            {"name": name, "file": filename, "main": main, "extra": extra}
        )

    return {
        "meta": {
            "generated_by": "tools/gen_gauntlet.py",
            "source": "vendor/ygo-agent/assets/deck",
            "order_note": (
                "The Gauntlet's fixed order (CONTEXT.md). Fixed within a phase so "
                "two decks' matchup rows line up; never sorted per deck."
            ),
            "decks": len(decks),
        },
        "gauntlet": decks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the committed file is stale"
    )
    args = parser.parse_args()

    payload = build()
    text = json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n"

    if args.check:
        if not OUT.exists():
            print(f"{OUT} does not exist", file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT} is stale -- rerun tools/gen_gauntlet.py", file=sys.stderr)
            return 1
        print(f"{OUT} is up to date")
        return 0

    OUT.write_text(text, encoding="utf-8")
    sizes = ", ".join(
        f"{deck['name']} {len(deck['main'])}+{len(deck['extra'])}"
        for deck in payload["gauntlet"]
    )
    print(f"wrote {OUT.relative_to(ROOT)}: {len(payload['gauntlet'])} decks -- {sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
