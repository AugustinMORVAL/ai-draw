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
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from . import constraints
from .cards import CardIndex, card_index
from .executor import REPLAY_SAMPLE, DuelExecutor, _hash_unit
from .models import (
    Bound,
    Constraint,
    Deck,
    DeckChange,
    DeckDiff,
    Fidelity,
    Progress,
    RefineCheckpoint,
    RefineParams,
    RefineResult,
    Swap,
)

class Report(Protocol):
    """Where the job writes what it has done, after every mutation.

    Progress and checkpoint travel together because they are one fact: a job that
    said it was on step 12 and checkpointed step 11 would resume by running a swap
    a user has already watched.
    """

    async def __call__(
        self, progress: Progress, checkpoint: RefineCheckpoint | None = None
    ) -> None: ...


ShouldCancel = Callable[[], Awaitable[bool]]


def diff_codes(before: Sequence[int], after: Sequence[int]) -> DeckDiff:
    """Which cards changed between two card lists, as copies gained and lost.

    Lists rather than decks, because the deck library compares Extra Decks with
    this too and an Extra Deck is not a `Deck` -- a `Deck` is the main deck a job
    is run on. One counting function, so no second answer to "what changed?" can
    exist in this app.
    """
    start, end = Counter(before), Counter(after)
    added = end - start
    removed = start - end
    return DeckDiff(
        added=[
            DeckChange(card=code, count=count) for code, count in sorted(added.items())
        ],
        removed=[
            DeckChange(card=code, count=count)
            for code, count in sorted(removed.items())
        ],
        unchanged=sum((start & end).values()),
    )


def deck_diff(before: Deck, after: Deck) -> DeckDiff:
    """Which cards changed between two decks' main decks."""
    return diff_codes(before.main, after.main)


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


def _name(index: CardIndex, code: int) -> str:
    card = index.get(code)
    return card.name if card is not None else str(code)


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
    resume: RefineCheckpoint | None = None,
) -> RefineResult:
    """Screen the deck, then mutate it, keeping only the swaps that scored better.

    `resume` is a checkpoint this same job wrote before it was interrupted. Picking
    it up is safe because a mutation is a pure function of the deck and the step
    number: the job re-derives the swap it was about to make and carries on, rather
    than re-running the ones a user already watched.
    """
    index = card_index()
    total = params.mutations
    start = params.deck
    duels = params.screening_duels

    def checkpoint(step: int, deck: Deck, win_rate: float) -> RefineCheckpoint:
        return RefineCheckpoint(
            step=step,
            total=total,
            deck=deck,
            win_rate=win_rate,
            swaps=swaps,
            diff=deck_diff(start, deck),
        )

    if resume is not None and resume.total == total:
        deck, win_rate, swaps = resume.deck, resume.win_rate, list(resume.swaps)
        first = resume.step + 1
        await report(
            Progress(
                step=resume.step,
                total=total,
                message=f"Resuming at mutation {min(first, total)}/{total}",
            ),
            checkpoint(resume.step, deck, win_rate),
        )
    else:
        deck, swaps = start, []
        await report(
            Progress(step=0, total=total, message="Screening the starting deck")
        )
        win_rate = (await executor.screen(deck, duels)).win_rate
        first = 1
        # Checkpointed before the first mutation, so a crash here does not pay for
        # the starting deck's duels twice.
        await report(
            Progress(step=0, total=total, message="Screened the starting deck"),
            checkpoint(0, deck, win_rate),
        )

    for step in range(first, total + 1):
        if await should_cancel():
            raise Cancelled
        card_out, card_in = _propose(deck, step, params.constraint)
        candidate = _apply(deck, card_out, card_in)
        evaluation = await executor.screen(candidate, duels)
        delta = evaluation.win_rate - win_rate
        accepted = delta > 0
        if accepted:
            deck, win_rate = candidate, evaluation.win_rate
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
                    f"{'kept' if accepted else 'rejected'} "
                    f"{_name(index, card_out)} -> {_name(index, card_in)}"
                ),
            ),
            checkpoint(step, deck, win_rate),
        )

    await report(
        Progress(step=total, total=total, message="Keeping a sample of the duels"),
        checkpoint(total, deck, win_rate),
    )
    replays = await executor.replays(deck, count=REPLAY_SAMPLE)

    return RefineResult(
        deck=deck,
        starting_deck=start,
        diff=deck_diff(start, deck),
        swaps=swaps,
        accepted=sum(1 for s in swaps if s.accepted),
        win_rate=win_rate,
        fidelity=Fidelity.SCREENING,
        live=executor.live,
        replays=replays,
    )
