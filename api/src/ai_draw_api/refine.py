"""The refine job: propose a swap, Screen it, keep it if the Delta score is positive.

The proposer here is a stand-in, not the Builder — it picks swaps by hash, not by a
policy. It exists so the job pipeline (queue, progress, result, cancel) is finished
and clickable before the real Builder and `YgoenvExecutor` are wired in (ADR-0005).

What is *not* a stand-in is where its picks come from: every swap is drawn from
`constraints.action_space`, so both Legality and the user's Constraint hold at every
step of the job rather than being checked at the end. Masking is the whole of "the
Builder built what I asked for" until Conditioning lands (ADR-0005), and a job that
only respected the Constraint in its final deck would not be that.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable

from . import constraints
from .cards import CardIndex, card_index
from .executor import DuelExecutor, _hash_unit
from .models import (
    Bound,
    Constraint,
    Deck,
    Fidelity,
    Progress,
    RefineParams,
    RefineResult,
    Swap,
)

#: How many of the final deck's duels are kept with their action logs. A refine
#: job screens thousands; these are the ones a user can actually sit and watch.
REPLAY_SAMPLE = 6

Report = Callable[[Progress], Awaitable[None]]
ShouldCancel = Callable[[], Awaitable[bool]]


class Cancelled(Exception):
    """The user asked for this job to stop."""


def _cuts(
    index: CardIndex, main: Counter[int], constraint: Constraint | None
) -> tuple[int, ...]:
    """Which cards this deck should give up first.

    With no Constraint, any card may go. With one, a card the Constraint calls
    surplus goes first: cutting into a group that is over its cap is the only move
    that can fix an over-cap deck, because an add never can. Cards holding a
    minimum at exactly its floor are cut last, so a swap does not spend itself
    putting back what it just took.
    """
    codes = tuple(sorted(main))
    if constraint is None or not constraint.clauses:
        return codes

    held = constraints.held_counts(index, main, constraint)
    surplus, spare, load_bearing = [], [], []
    for code in codes:
        card = index.get(code)
        if card is None:
            spare.append(code)
            continue
        over = any(
            clause.bound is Bound.AT_MOST
            and held[i] > clause.count
            and constraints.matches(card, clause)
            for i, clause in enumerate(constraint.clauses)
        )
        needed = any(
            clause.bound is Bound.AT_LEAST
            and held[i] <= clause.count
            and constraints.matches(card, clause)
            for i, clause in enumerate(constraint.clauses)
        )
        (surplus if over else load_bearing if needed else spare).append(code)
    return tuple(surplus or spare or load_bearing)


def _propose(
    deck: Deck, step: int, constraint: Constraint | None = None
) -> tuple[int, int]:
    """Pick one card to cut and one to add, from inside the Masked action space."""
    index = card_index()
    main = Counter(deck.main)
    cuts = _cuts(index, main, constraint)
    card_out = cuts[int(_hash_unit(deck.main, step, "out") * len(cuts))]

    without = main.copy()
    without[card_out] -= 1
    if without[card_out] == 0:
        del without[card_out]
    # The mask is computed on the deck *minus* the cut, so the slot the cut freed is
    # what an at-least clause sees as owed: drop the deck's last Dragon under "at
    # least 20 Dragons" and the only legal add is another Dragon.
    space = constraints.action_space(
        index, without, constraint, target_size=len(deck.main)
    )
    if not space.allowed:
        raise RuntimeError(
            "no card may be added to this deck: its Constraint and the supported "
            "pool leave the Builder nothing to pick"
        )
    offset = int(_hash_unit(deck.main, step, "in") * len(space.allowed))
    for i in range(len(space.allowed)):
        card_in = space.allowed[(offset + i) % len(space.allowed)]
        if card_in != card_out:
            return card_out, card_in
    return card_out, space.allowed[offset]


def _apply(deck: Deck, card_out: int, card_in: int) -> Deck:
    main = list(deck.main)
    main.remove(card_out)
    main.append(card_in)
    return Deck(main=sorted(main))


async def run_refine(
    params: RefineParams,
    executor: DuelExecutor,
    report: Report,
    should_cancel: ShouldCancel,
) -> RefineResult:
    total = params.mutations
    deck = params.deck
    duels = params.screening_duels

    await report(Progress(step=0, total=total, message="Screening the starting deck"))
    current = await executor.screen(deck, duels)

    swaps: list[Swap] = []
    for step in range(1, total + 1):
        if await should_cancel():
            raise Cancelled
        card_out, card_in = _propose(deck, step, params.constraint)
        candidate = _apply(deck, card_out, card_in)
        evaluation = await executor.screen(candidate, duels)
        delta = evaluation.win_rate - current.win_rate
        accepted = delta > 0
        if accepted:
            deck, current = candidate, evaluation
        swaps.append(
            Swap(
                step=step,
                card_out=card_out,
                card_in=card_in,
                win_rate=evaluation.win_rate,
                delta=delta,
                accepted=accepted,
            )
        )
        await report(
            Progress(
                step=step,
                total=total,
                message=(
                    f"Mutation {step}/{total}: "
                    f"{'kept' if accepted else 'rejected'} {card_out} -> {card_in}"
                ),
            )
        )

    await report(
        Progress(step=total, total=total, message="Keeping a sample of the duels")
    )
    replays = await executor.replays(deck, count=REPLAY_SAMPLE)

    return RefineResult(
        deck=deck,
        swaps=swaps,
        accepted=sum(1 for s in swaps if s.accepted),
        win_rate=current.win_rate,
        fidelity=Fidelity.SCREENING,
        live=executor.live,
        replays=replays,
    )
