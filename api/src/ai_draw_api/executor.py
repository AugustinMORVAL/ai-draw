"""The seam: one `DuelExecutor` interface, two implementations (ADR-0005).

`FakeExecutor` is what every slice is built on. `YgoenvExecutor` lands with Stage 1
(#3) behind the same interface, and nothing above this module learns which one it
is talking to except through `live`.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from .models import Deck, Fidelity


class Evaluation(BaseModel):
    """A win rate and the fidelity that produced it. Never one without the other."""

    win_rate: float
    duels: int
    fidelity: Fidelity


@runtime_checkable
class DuelExecutor(Protocol):
    """Runs duels for a candidate deck against the Gauntlet."""

    name: str
    live: bool

    async def screen(self, deck: Deck, duels: int) -> Evaluation:
        """Screening fidelity: a small paired batch, noisy by design (ADR-0003)."""
        ...

    async def gate(self, deck: Deck, duels: int) -> Evaluation:
        """Gate evaluation: the only fidelity allowed in claims about strength."""
        ...


def _hash_unit(*parts: object) -> float:
    """A stable float in [0, 1) from anything hashable to a string."""
    blob = "|".join(str(p) for p in parts).encode()
    return int.from_bytes(hashlib.sha256(blob).digest()[:8], "big") / 2**64


class FakeExecutor:
    """Plausible numbers with no duels behind them.

    A deck's "true" strength is a stable hash of its multiset of cards, so the same
    deck always scores the same and a swap moves the number a little. Screening adds
    hash-derived noise in the +/-5 point band ADR-0003 describes; Gate evaluation, run
    over more duels, adds much less. Both are fabricated — `live` is False so the UI
    says so.
    """

    name = "fake"
    live = False

    def __init__(self, *, duel_seconds: float = 0.004) -> None:
        self._duel_seconds = duel_seconds

    def _true_win_rate(self, deck: Deck) -> float:
        base = _hash_unit(sorted(deck.main))
        return 0.30 + 0.40 * base

    async def _run(self, deck: Deck, duels: int, fidelity: Fidelity) -> Evaluation:
        await asyncio.sleep(self._duel_seconds * duels)
        spread = 0.05 if fidelity is Fidelity.SCREENING else 0.01
        noise = (_hash_unit(sorted(deck.main), fidelity.value, duels) - 0.5) * 2 * spread
        win_rate = min(0.99, max(0.01, self._true_win_rate(deck) + noise))
        return Evaluation(win_rate=win_rate, duels=duels, fidelity=fidelity)

    async def screen(self, deck: Deck, duels: int) -> Evaluation:
        return await self._run(deck, duels, Fidelity.SCREENING)

    async def gate(self, deck: Deck, duels: int) -> Evaluation:
        return await self._run(deck, duels, Fidelity.GATE)
