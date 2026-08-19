"""The supported pool: the 864 cards the frozen Pilot can represent.

Read `data/pilot-864/pool.txt`, never `code_list.txt` — the code list is longer on
purpose and being in it does not mean being in the pool (CONTEXT.md).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_REPO_POOL = Path(__file__).resolve().parents[3] / "data" / "pilot-864" / "pool.txt"


def pool_file() -> Path:
    """Where to read the pool from. `AI_DRAW_POOL` overrides the in-repo copy."""
    override = os.environ.get("AI_DRAW_POOL")
    return Path(override) if override else _REPO_POOL


@lru_cache(maxsize=1)
def supported_pool() -> tuple[int, ...]:
    """Card codes of the supported pool, in `embed864.pkl` order."""
    path = pool_file()
    codes = tuple(int(line) for line in path.read_text().split() if line.strip())
    if not codes:
        raise RuntimeError(f"supported pool is empty: {path}")
    return codes
