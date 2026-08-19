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

from .models import Deck, DuelEvent, DuelPhase, DuelReplay, DuelSeat, Fidelity


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

    async def replays(self, deck: Deck, *, count: int) -> list[DuelReplay]:
        """A sample of the duels this deck played, with their action logs.

        Sampled, never complete: an evaluation runs hundreds of duels and the point
        of a replay is to be watched, not archived. Every replay carries `live`, so a
        log from the fake executor can never be mistaken for one from `ygopro-core`.
        """
        ...


def _hash_unit(*parts: object) -> float:
    """A stable float in [0, 1) from anything hashable to a string."""
    blob = "|".join(str(p) for p in parts).encode()
    return int.from_bytes(hashlib.sha256(blob).digest()[:8], "big") / 2**64


# The Gauntlet as it stands in phase 1: the shipped ygo-agent meta decks
# (`vendor/ygo-agent/assets/deck/`). Named here rather than read from disk so the
# API container needs neither the submodule nor the network; `YgoenvExecutor` will
# report whichever deck it actually sat the Pilot behind.
GAUNTLET = (
    "Snake-Eye Fire",
    "Labrynth",
    "Branded",
    "Shaddoll",
    "Sky Striker Ace",
    "Centur-Ion",
    "Blue-Eyes",
    "Floowandereeze",
    "Tenyi Sword",
    "Chimera",
)

# What a duel is made of, as the fake log tells it. Real logs come from the core.
# Keyed by action so the sentence and the action never contradict each other.
_VERBS = {
    "draw": ("draws for turn",),
    "summon": ("Normal Summons", "Special Summons", "sets", "activates"),
    "end": ("ends the turn",),
}


class FakeExecutor:
    """Plausible numbers with no duels behind them.

    A deck's "true" strength is a stable hash of its multiset of cards, so the same
    deck always scores the same and a swap moves the number a little. Screening adds
    hash-derived noise in the +/-5 point band ADR-0003 describes; Gate evaluation, run
    over more duels, adds much less. Both are fabricated -- `live` is False so the UI
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

    async def replays(self, deck: Deck, *, count: int) -> list[DuelReplay]:
        """Fabricated duels, played with this deck's own cards.

        The cards named in the log are drawn from the deck, so the log is at least
        about the right deck; nothing else about it happened. The candidate wins a
        share of them matching its own fake win rate, so a strong deck's replay list
        does not contradict the win rate shown beside it.
        """
        strength = self._true_win_rate(deck)
        return [
            self._one_replay(deck, i, strength) for i in range(count)
        ]

    def _one_replay(self, deck: Deck, index: int, strength: float) -> DuelReplay:
        cards = sorted(set(deck.main))
        pick = lambda *salt: cards[  # noqa: E731
            int(_hash_unit(index, *salt) * len(cards))
        ]
        opponent = GAUNTLET[int(_hash_unit(sorted(deck.main), index) * len(GAUNTLET))]
        going_first = (
            DuelSeat.CANDIDATE
            if _hash_unit(index, "first") < 0.5
            else DuelSeat.OPPONENT
        )
        candidate_won = _hash_unit(sorted(deck.main), index, "won") < strength

        life = {DuelSeat.CANDIDATE: 8000, DuelSeat.OPPONENT: 8000}
        loser = DuelSeat.OPPONENT if candidate_won else DuelSeat.CANDIDATE
        winner = DuelSeat.CANDIDATE if candidate_won else DuelSeat.OPPONENT
        turns = 3 + int(_hash_unit(index, "turns") * 6)
        # Seats alternate from `going_first`, and the duel ends on the blow that
        # takes the loser to 0. So the last turn has to be the winner's, or the log
        # would stop with the loser still alive and a winner already declared.
        if (going_first is winner) != (turns % 2 == 1):
            turns += 1
        log: list[DuelEvent] = []
        seat = going_first

        for turn in range(1, turns + 1):
            for phase, action in (
                (DuelPhase.DRAW, "draw"),
                (DuelPhase.MAIN1, "summon"),
                (DuelPhase.BATTLE, "attack"),
                (DuelPhase.END, "end"),
            ):
                if turn == 1 and phase is DuelPhase.BATTLE and going_first is seat:
                    continue  # no battle phase on the very first turn
                card = pick(turn, phase.value) if action != "end" else None
                if action == "attack":
                    # The loser bleeds out over the duel; the last hit ends it.
                    remaining = turns - turn + 1
                    damage = life[loser] if remaining <= 1 and seat is winner else min(
                        life[loser], 800 + int(_hash_unit(index, turn, "dmg") * 2200)
                    )
                    if seat is winner:
                        life[loser] = max(0, life[loser] - damage)
                    text = (
                        f"attacks for {damage}"
                        if seat is winner
                        else "attacks into a wall"
                    )
                else:
                    verbs = _VERBS[action]
                    text = verbs[int(_hash_unit(index, turn, action) * len(verbs))]
                log.append(
                    DuelEvent(
                        index=len(log),
                        turn=turn,
                        seat=seat,
                        phase=phase,
                        action=action,
                        card=card,
                        text=text,
                        life_candidate=life[DuelSeat.CANDIDATE],
                        life_opponent=life[DuelSeat.OPPONENT],
                    )
                )
                if life[loser] == 0:
                    break
            if life[loser] == 0:
                break
            seat = (
                DuelSeat.OPPONENT if seat is DuelSeat.CANDIDATE else DuelSeat.CANDIDATE
            )

        return DuelReplay(
            index=index,
            opponent=opponent,
            going_first=going_first,
            winner=winner,
            turns=log[-1].turn if log else 0,
            events=len(log),
            live=self.live,
            log=log,
        )
