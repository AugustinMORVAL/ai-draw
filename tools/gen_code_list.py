#!/usr/bin/env python3
"""Regenerate data/pilot-864/code_list.txt, the Pilot-aligned card-id list.

The env assigns every card an id equal to its 1-based line number in the
``--code_list_file`` it was initialised with (``init_module`` in
``vendor/ygo-agent/ygoenv/ygoenv/ygopro/ygopro.h``: ``card_ids_[code] = i``).
The frozen Pilot ``0546_22750M`` carries a card-embedding table of exactly
1000 rows, whose rows 1..864 are the vectors of the v0.1 release asset
``embed864.pkl`` in that pickle's insertion order (row 0 is "unknown", rows
865..999 are zero).

So the Pilot is only wired up correctly when the code list *starts* with these
864 codes in *this* order. Running it against the vendored 13,472-line
``scripts/code_list.txt`` puts 552 of the 604 cards used by the shipped decks
beyond row 999. That is an out-of-bounds embedding gather -- undefined behaviour
under ``jit``, measured here as NaN -- so every logit goes NaN and ``probs.argmax``
silently plays action 0 forever, scoring the ~0.50 of a coin flip. See ADR-0001.

The 864 codes alone are not a usable code list, though: ``card_ids_``/``cards_data_``
are populated *only* from this file, and ``card_reader_callback`` aborts the whole
process when a card script asks the core for a code the file never listed (measured:
``[card_reader_callback] Card not found: 40005099`` -- "Shiranui Style Synthesis",
a card no shipped .ydk plays but a Shiranui script references). So the generated file
is the 864 embedded codes *first*, in embedding-row order, followed by every remaining
code of the vendored list in its original order. Lines 1..864 line up with the Pilot's
embedding rows, and measurement says nothing above 864 ever reaches the policy -- the
tail exists so the C++ core can answer a script's question without killing the run.
The phase-1 pool is still the first 864 lines and nothing else, emitted separately as
``data/pilot-864/pool.txt`` so no caller has to know that.

Usage:
    python tools/gen_code_list.py [--check]

Inputs (both fetched/vendored, neither committed):
    vendor/ygo-agent/scripts/checkpoints/embed864.pkl   gh release download v0.1 \
        --repo sbl1996/ygo-agent -p embed864.pkl -D vendor/ygo-agent/scripts/checkpoints
    vendor/ygo-agent/scripts/code_list.txt              (for the has-script flag)
"""

import argparse
import pickle
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMBED = ROOT / "vendor/ygo-agent/scripts/checkpoints/embed864.pkl"
FULL_LIST = ROOT / "vendor/ygo-agent/scripts/code_list.txt"
CARD_DB = ROOT / "vendor/ygo-agent/assets/locale/en/cards.cdb"
SCRIPT_DIR = ROOT / "vendor/ygopro-scripts"
OUT = ROOT / "data/pilot-864/code_list.txt"
POOL = ROOT / "data/pilot-864/pool.txt"
POOL_SIZE = 864


def audit(codes: list) -> None:
    """Fail on anything that would make the executor abort, or the Pilot see NaN.

    Three aborts live in `ygopro.h` and none of them degrade gracefully:
    `card_reader_callback` and `c_get_card_id` throw (killing the process) on a code
    the list omits, and `script_reader_callback` throws on a script path never
    preloaded. A fourth failure is worse because it is silent: an id past the Pilot's
    1000-row table is an out-of-bounds gather, i.e. undefined behaviour, which returns
    NaN -- `probs.argmax` then plays action 0 forever and still reports a plausible
    win rate. Every one of these is decidable here, before a duel runs.
    """
    db_ids = {row[0] for row in sqlite3.connect(f"file:{CARD_DB}?mode=ro", uri=True)
              .execute("select id from datas")}
    if set(codes) != db_ids:
        missing, extra = db_ids - set(codes), set(codes) - db_ids
        raise SystemExit(
            f"code list must cover the card db exactly: {len(missing)} db cards absent "
            f"{sorted(missing)[:5]}, {len(extra)} unknown codes {sorted(extra)[:5]}")

    scripted = {int(p.stem[1:]) for p in SCRIPT_DIR.glob("c*.lua") if p.stem[1:].isdigit()}
    shared = {p.name for p in SCRIPT_DIR.glob("*.lua")} - {f"c{c}.lua" for c in scripted}
    if shared != {"constant.lua", "utility.lua", "procedure.lua"}:
        raise SystemExit(
            f"ygopro.h preloads constant/utility/procedure only; found {sorted(shared)}")


def build() -> str:
    with EMBED.open("rb") as f:
        embeddings = pickle.load(f)
    if len(embeddings) != POOL_SIZE:
        raise SystemExit(f"expected {POOL_SIZE} embeddings, got {len(embeddings)}")

    has_script = {}
    for line in FULL_LIST.read_text().splitlines():
        if not line.strip():
            continue
        code, flag = line.split()
        has_script[int(code)] = int(flag)

    missing = [c for c in embeddings if int(c) not in has_script]
    if missing:
        raise SystemExit(f"{len(missing)} codes absent from the full code list: {missing[:5]}")

    # dict insertion order is the checkpoint's embedding row order -- do not sort.
    pool = [int(code) for code in embeddings]
    # Everything else keeps its vendored order and lands past the Pilot's table,
    # so the core can read those cards without any of them displacing a pool row.
    tail = [code for code in has_script if code not in set(pool)]
    codes = pool + tail
    audit(codes)
    return "".join(f"{code} {has_script[code]}\n" for code in codes)


def pool_file(code_list: str) -> str:
    """The phase-1 pool as its own artifact, so no caller has to know to slice [:864]."""
    return "".join(
        line.split()[0] + "\n" for line in code_list.splitlines()[:POOL_SIZE])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if a committed file is stale")
    args = parser.parse_args()

    generated = build()
    pool = pool_file(generated)
    n = generated.count("\n")
    summary = f"{n} codes; the first {POOL_SIZE} are the Pilot's pool"
    outputs = [(OUT, generated), (POOL, pool)]

    if args.check:
        stale = [p for p, want in outputs if not p.exists() or p.read_text() != want]
        if stale:
            print(f"stale, re-run tools/gen_code_list.py: {', '.join(str(p) for p in stale)}",
                  file=sys.stderr)
            return 1
        print(f"{OUT} is up to date ({summary}); {POOL} matches its first {POOL_SIZE} lines")
        return 0

    for path, want in outputs:
        path.write_text(want)
    print(f"wrote {OUT} ({summary}) and {POOL} ({POOL_SIZE} codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
