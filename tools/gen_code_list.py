#!/usr/bin/env python3
"""Regenerate data/pilot-864/code_list.txt, the phase-1 card-id list.

The env assigns every card an id equal to its 1-based line number in the
``--code_list_file`` it was initialised with (``init_module`` in
``vendor/ygo-agent/ygoenv/ygoenv/ygopro/ygopro.h``: ``card_ids_[code] = i``).
The frozen Pilot ``0546_22750M`` carries a card-embedding table of exactly
1000 rows, whose rows 1..864 are the vectors of the v0.1 release asset
``embed864.pkl`` in that pickle's insertion order (row 0 is "unknown", rows
865..999 are zero).

So the Pilot is only wired up correctly when the code list is *these* 864
codes in *this* order. Running it against the vendored 13,472-line
``scripts/code_list.txt`` puts 552 of the 604 cards used by the shipped decks
beyond row 999, where the gather clamps and every one of them reaches the
policy as the same zero "unknown" vector -- a card-blind Pilot. See ADR-0001.

Usage:
    python tools/gen_code_list.py [--check]

Inputs (both fetched/vendored, neither committed):
    vendor/ygo-agent/scripts/checkpoints/embed864.pkl   gh release download v0.1 \
        --repo sbl1996/ygo-agent -p embed864.pkl -D vendor/ygo-agent/scripts/checkpoints
    vendor/ygo-agent/scripts/code_list.txt              (for the has-script flag)
"""

import argparse
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMBED = ROOT / "vendor/ygo-agent/scripts/checkpoints/embed864.pkl"
FULL_LIST = ROOT / "vendor/ygo-agent/scripts/code_list.txt"
OUT = ROOT / "data/pilot-864/code_list.txt"


def build() -> str:
    with EMBED.open("rb") as f:
        embeddings = pickle.load(f)
    if len(embeddings) != 864:
        raise SystemExit(f"expected 864 embeddings, got {len(embeddings)}")

    has_script = {}
    for line in FULL_LIST.read_text().splitlines():
        code, flag = line.split()
        has_script[int(code)] = int(flag)

    missing = [c for c in embeddings if int(c) not in has_script]
    if missing:
        raise SystemExit(f"{len(missing)} codes absent from the full code list: {missing[:5]}")

    # dict insertion order is the checkpoint's embedding row order -- do not sort.
    return "".join(f"{int(code)} {has_script[int(code)]}\n" for code in embeddings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    args = parser.parse_args()

    generated = build()
    if args.check:
        if not OUT.exists() or OUT.read_text() != generated:
            print(f"{OUT} is stale; re-run tools/gen_code_list.py", file=sys.stderr)
            return 1
        print(f"{OUT} is up to date (864 codes)")
        return 0

    OUT.write_text(generated)
    print(f"wrote {OUT} (864 codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
