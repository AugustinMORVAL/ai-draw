"""The refine job: propose a swap, Screen it, keep it if the Delta score is positive.

The proposer here is a stand-in, not the Builder — it picks swaps by hash, not by a
policy. It exists so the job pipeline (queue, progress, result, cancel) is finished
and clickable before the real Builder and `YgoenvExecutor` are wired in (ADR-0005).
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable

from .cards import card_index
from .executor import DuelExecutor, _hash_unit
from .models import Deck, Fidelity, Progress, RefineParams, RefineResult, Swap

Report = Callable[[Progress], Awaitable[None]]
ShouldCancel = Callable[[], Awaitable[bool]]


class Cancelled(Exception):
    """The user asked for this job to stop."""


def random_deck(size: int = 40, *, seed: int | None = None) -> Deck:
    """A legal deck drawn from the supported pool. Legal, not good.

    Draws from `main_deck_codes()`, not the raw 864: over half the pool is Tokens
    and Extra Deck monsters that exist so the Pilot can recognise them on the field.
    Putting one in a main deck does not make a weak deck, it aborts `ygopro-core`.
    """
    rng = random.Random(seed)
    index = card_index()
    codes = index.main_deck_codes()
    main: list[int] = []
    counts: dict[int, int] = {}
    while len(main) < size:
        code = rng.choice(codes)
        if counts.get(code, 0) >= index.pool[code].limit:
            continue
        counts[code] = counts.get(code, 0) + 1
        main.append(code)
    return Deck(main=sorted(main))


def _propose(deck: Deck, step: int) -> tuple[int, int]:
    """Pick one card to cut and one to add, from inside the Masked action space."""
    index = card_index()
    codes = index.main_deck_codes()
    out_index = int(_hash_unit(deck.main, step, "out") * len(deck.main))
    card_out = deck.main[out_index]
    counts: dict[int, int] = {}
    for code in deck.main:
        counts[code] = counts.get(code, 0) + 1
    offset = int(_hash_unit(deck.main, step, "in") * len(codes))
    for i in range(len(codes)):
        card_in = codes[(offset + i) % len(codes)]
        if card_in == card_out:
            continue
        if counts.get(card_in, 0) < index.pool[card_in].limit:
            return card_out, card_in
    raise RuntimeError("no legal card to add from the supported pool")


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
        card_out, card_in = _propose(deck, step)
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

    return RefineResult(
        deck=deck,
        swaps=swaps,
        accepted=sum(1 for s in swaps if s.accepted),
        win_rate=current.win_rate,
        fidelity=Fidelity.SCREENING,
        live=executor.live,
    )
