"""The test job: Gate evaluation of one deck against the Gauntlet.

A refine job answers "did this deck get better?", and it answers in Screening
numbers that ADR-0003 forbids quoting. This job answers "how strong is this deck?"
-- 500+ paired duels, split evenly across the ten Gauntlet decks, and the only
number in the app a user may repeat somewhere else.

So the job is deliberately thin. It runs no mutations, proposes nothing, and needs
no Masking: there is no pick to mask. What it adds over one call to
`executor.gate()` is the three things a queued job owes its user -- progress while
it runs, a stopping point, and a result that carries its own provenance.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .executor import GAUNTLET, REPLAY_SAMPLE, DuelExecutor
from .models import Matchup, Progress, GateParams, GateResult
from .refine import Cancelled  # one exception for both jobs: the worker catches one

Report = Callable[..., Awaitable[None]]
ShouldCancel = Callable[[], Awaitable[bool]]


async def run_test(
    params: GateParams,
    executor: DuelExecutor,
    report: Report,
    should_cancel: ShouldCancel,
) -> GateResult:
    """Sit the deck down against every Gauntlet deck in turn and report the split.

    Cancellation lands between opponents and nowhere else. That is not a shortcut:
    a candidate deck may only be swapped out at a batch boundary (ADR-0004), so
    "stop now" has to mean "stop after this matchup" or it means "race the core".
    A cancelled test is therefore always cancelled with whole matchups behind it.
    """
    total = len(GAUNTLET)
    seen: list[Matchup] = []

    async def on_matchup(row: Matchup) -> None:
        seen.append(row)
        await report(
            Progress(
                step=len(seen),
                total=total,
                message=(
                    f"{row.opponent}: {row.wins}/{row.duels} "
                    f"({row.win_rate * 100:.0f}%)"
                ),
            )
        )
        if await should_cancel():
            raise Cancelled

    await report(
        Progress(
            step=0,
            total=total,
            message=f"Gate evaluation: {params.gate_duels} duels over {total} decks",
        )
    )
    evaluation = await executor.gate(
        params.deck, params.gate_duels, on_matchup=on_matchup
    )

    await report(
        Progress(step=total, total=total, message="Keeping a sample of the duels")
    )
    replays = await executor.replays(params.deck, count=REPLAY_SAMPLE)

    return GateResult(
        deck=params.deck,
        win_rate=evaluation.win_rate,
        duels=evaluation.duels,
        fidelity=evaluation.fidelity,
        matchups=evaluation.matchups,
        live=executor.live,
        replays=replays,
    )
