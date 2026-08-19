"""The refine job: legal decks in, legal decks out, only positive Deltas kept."""

from __future__ import annotations

import pytest

from ai_draw_api.executor import FakeExecutor
from ai_draw_api.models import Progress, RefineParams
from ai_draw_api.pool import supported_pool
from ai_draw_api.refine import Cancelled, random_deck, run_refine

pytestmark = pytest.mark.asyncio


async def _noop(_: Progress) -> None:
    return None


async def never_cancel() -> bool:
    return False


async def test_random_deck_is_legal():
    deck = random_deck(seed=7)
    pool = set(supported_pool())
    assert len(deck.main) == 40
    assert set(deck.main) <= pool
    assert max(deck.main.count(c) for c in set(deck.main)) <= 3


async def test_refine_keeps_the_deck_legal_and_the_same_size():
    params = RefineParams(deck=random_deck(seed=1), mutations=10, screening_duels=10)
    result = await run_refine(
        params, FakeExecutor(duel_seconds=0.0), _noop, never_cancel
    )
    pool = set(supported_pool())
    assert len(result.deck.main) == 40
    assert set(result.deck.main) <= pool
    assert max(result.deck.main.count(c) for c in set(result.deck.main)) <= 3
    assert len(result.swaps) == 10
    assert result.live is False


async def test_only_positive_deltas_are_kept():
    params = RefineParams(deck=random_deck(seed=2), mutations=15, screening_duels=10)
    result = await run_refine(
        params, FakeExecutor(duel_seconds=0.0), _noop, never_cancel
    )
    assert all(swap.accepted == (swap.delta > 0) for swap in result.swaps)
    assert result.accepted == sum(1 for s in result.swaps if s.accepted)


async def test_cancel_stops_the_loop():
    seen: list[Progress] = []

    async def report(p: Progress) -> None:
        seen.append(p)

    async def cancel_after_three() -> bool:
        return len(seen) > 3

    params = RefineParams(deck=random_deck(seed=3), mutations=50, screening_duels=10)
    with pytest.raises(Cancelled):
        await run_refine(params, FakeExecutor(duel_seconds=0.0), report, cancel_after_three)
    assert len(seen) < 50
