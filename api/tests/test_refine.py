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
    Deck,
    Progress,
    RefineCheckpoint,
    RefineParams,
)
from ai_draw_api.pool import supported_pool
from ai_draw_api.refine import Cancelled, deck_diff, run_refine

pytestmark = pytest.mark.asyncio


async def _noop(_: Progress, checkpoint: RefineCheckpoint | None = None) -> None:
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

    async def report(p: Progress, checkpoint: RefineCheckpoint | None = None) -> None:
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


class CountingExecutor(FakeExecutor):
    """A fake that says how many times it was asked to screen a deck.

    Resuming is only worth having if it does not pay for the duels the job already
    ran, and the count is the only way to see that from outside.
    """

    def __init__(self) -> None:
        super().__init__(duel_seconds=0.0)
        self.screens = 0

    async def screen(self, deck, duels):
        self.screens += 1
        return await super().screen(deck, duels)


async def test_the_diff_is_the_net_change_not_the_swap_log():
    """A card cut at step 3 and picked back up at step 17 is two swaps, no change."""
    diff = deck_diff(Deck(main=[1, 1, 2, 3]), Deck(main=[1, 2, 3, 4]))
    assert [(c.card, c.count) for c in diff.removed] == [(1, 1)]
    assert [(c.card, c.count) for c in diff.added] == [(4, 1)]
    assert diff.unchanged == 3


async def test_the_result_says_which_cards_changed():
    params = RefineParams(deck=random_deck(seed=13), mutations=20, screening_duels=10)
    result = await run_refine(
        params, FakeExecutor(duel_seconds=0.0), _noop, never_cancel
    )

    assert result.starting_deck.main == params.deck.main, "changed from what?"
    assert result.diff == deck_diff(params.deck, result.deck)
    added = sum(c.count for c in result.diff.added)
    removed = sum(c.count for c in result.diff.removed)
    assert added == removed, "a swap trades one card for one card"
    assert added + result.diff.unchanged == len(result.deck.main)
    assert added <= result.accepted, "an accepted swap need not survive to the end"


async def test_a_checkpoint_is_written_after_every_mutation():
    """The swap log is readable while the job runs, not only when it ends."""
    kept: list[tuple[int, RefineCheckpoint | None]] = []

    async def record(p: Progress, checkpoint: RefineCheckpoint | None = None) -> None:
        kept.append((p.step, checkpoint))

    params = RefineParams(deck=random_deck(seed=12), mutations=8, screening_duels=10)
    result = await run_refine(
        params, FakeExecutor(duel_seconds=0.0), record, never_cancel
    )

    checkpointed = [step for step, checkpoint in kept if checkpoint is not None]
    assert checkpointed == [0, 1, 2, 3, 4, 5, 6, 7, 8, 8]
    growth = [len(c.swaps) for _, c in kept if c is not None]
    assert growth == [0, 1, 2, 3, 4, 5, 6, 7, 8, 8], "the log builds up, swap by swap"
    last = kept[-1][1]
    assert last is not None
    assert last.deck == result.deck and last.swaps == result.swaps


async def test_an_interrupted_job_resumes_where_it_stopped():
    """A restart costs the mutations the job had not run, not the ones it had."""
    kept: list[RefineCheckpoint] = []

    async def record(p: Progress, checkpoint: RefineCheckpoint | None = None) -> None:
        if checkpoint is not None:
            kept.append(checkpoint)

    params = RefineParams(deck=random_deck(seed=11), mutations=12, screening_duels=10)
    uninterrupted = CountingExecutor()
    whole = await run_refine(params, uninterrupted, record, never_cancel)

    # The process dies after mutation 5. A fresh worker picks the checkpoint up.
    halfway = next(c for c in kept if c.step == 5)
    resumed_on = CountingExecutor()
    resumed = await run_refine(params, resumed_on, _noop, never_cancel, halfway)

    assert resumed.deck == whole.deck, "the same job, not a similar one"
    assert resumed.swaps == whole.swaps
    assert resumed.diff == whole.diff
    assert resumed_on.screens == uninterrupted.screens - 6, (
        "the starting screen and the five mutations it had already run"
    )
