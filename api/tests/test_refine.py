"""The refine job: legal decks in, legal decks out, only positive Deltas kept."""

from __future__ import annotations

import pytest

from collections import Counter

from ai_draw_api import constraints
from ai_draw_api.cards import card_index
from ai_draw_api.constraints import construct, random_deck
from ai_draw_api.executor import FakeExecutor
from ai_draw_api.models import (
    Bound,
    Constraint,
    ConstraintClause,
    ConstraintFacet,
    Progress,
    RefineParams,
)
from ai_draw_api.pool import supported_pool
from ai_draw_api.refine import Cancelled, run_refine

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


def _dragons(codes: list[int]) -> int:
    index = card_index()
    return sum(1 for code in codes if index.pool[code].race == "Dragon")


DRAGONS = Constraint(
    main_size=40,
    clauses=[
        ConstraintClause(
            facet=ConstraintFacet.RACE,
            value="Dragon",
            bound=Bound.AT_LEAST,
            count=10,
        )
    ],
)


async def test_a_constraint_survives_every_swap_of_a_refine_job():
    """A job that only respected the Constraint at the end would not respect it.

    Masking is per pick (CONTEXT.md): the deck has to be conformant after every
    accepted swap, because any of them could be the last one before a crash, a
    cancel, or a user reading the progress log.
    """
    index = card_index()
    start = construct(index, DRAGONS, seed=8)
    params = RefineParams(
        deck=start, mutations=20, screening_duels=10, constraint=DRAGONS
    )
    result = await run_refine(
        params, FakeExecutor(duel_seconds=0.0), _noop, never_cancel
    )

    deck = list(start.main)
    for swap in result.swaps:
        if not swap.accepted:
            continue
        deck.remove(swap.card_out)
        deck.append(swap.card_in)
        report = constraints.review(
            index, Counter(deck), DRAGONS, main_count=len(deck)
        )
        assert report.satisfied, f"swap {swap.step} broke it: {report.flags}"
    assert deck == sorted(result.deck.main)


async def test_a_deck_that_does_not_meet_the_constraint_is_pulled_toward_it():
    """Every masked swap pays down the floor -- but only accepted swaps land.

    So a refine job moves an unconformant deck toward the Constraint and is not
    guaranteed to arrive: the mask decides what may be proposed, the Delta score
    decides what is kept. Building under the Constraint is what guarantees it.
    """
    index = card_index()
    start = random_deck(seed=4)
    assert _dragons(start.main) < 10, "the fixture is a deck that does not conform"

    params = RefineParams(
        deck=start, mutations=30, screening_duels=10, constraint=DRAGONS
    )
    result = await run_refine(
        params, FakeExecutor(duel_seconds=0.0), _noop, never_cancel
    )

    assert _dragons(result.deck.main) > _dragons(start.main)
    added = [
        index.pool[swap.card_in].race
        for swap in result.swaps
        if swap.accepted
    ]
    assert added and all(race == "Dragon" for race in added), (
        "while the floor is unmet, the mask leaves nothing else to add"
    )
