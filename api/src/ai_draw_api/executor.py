"""The seam: one `DuelExecutor` interface, two implementations (ADR-0005).

`FakeExecutor` is what every slice is built on. `YgoenvExecutor` lands with Stage 1
(#3) behind the same interface, and nothing above this module learns which one it
is talking to except through `live`.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Iterator
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from .cards import card_index
from .gauntlet import gauntlet_decks, gauntlet_names
from .models import (
    Deck,
    DuelEvent,
    DuelPhase,
    DuelReplay,
    DuelSeat,
    Fidelity,
    Matchup,
)

#: How many of a job's duels are kept with their action logs: one per Gauntlet
#: deck. An evaluation runs hundreds of duels; these are the ones a user can sit and
#: watch, and there is one against every opponent so no matchup row is a row that
#: cannot be opened. It lives here rather than with either job because it is a
#: property of `replays()`.
REPLAY_SAMPLE = len(gauntlet_names())

#: Called with each matchup as it finishes, so a job can report progress and stop
#: between opponents. A batch boundary is the only place a duel run may be
#: interrupted (ADR-0004): mid-batch, a deck swap races the core.
MatchupSeen = Callable[[Matchup], Awaitable[None]]


class Evaluation(BaseModel):
    """A win rate and the fidelity that produced it. Never one without the other."""

    win_rate: float
    duels: int
    fidelity: Fidelity
    #: The per-opponent breakdown. Gate evaluation only: at Screening's 100 duels a
    #: matchup row is ten duels, a +/-31 point band under a number ADR-0003 already
    #: forbids quoting. The aggregate above is computed *from* these rows when they
    #: exist, so a headline can never disagree with its own breakdown.
    matchups: list[Matchup] = []


@runtime_checkable
class DuelExecutor(Protocol):
    """Runs duels for a candidate deck against the Gauntlet."""

    name: str
    live: bool

    async def screen(self, deck: Deck, duels: int) -> Evaluation:
        """Screening fidelity: a small paired batch, noisy by design (ADR-0003)."""
        ...

    async def gate(
        self, deck: Deck, duels: int, *, on_matchup: MatchupSeen | None = None
    ) -> Evaluation:
        """Gate evaluation: the only fidelity allowed in claims about strength.

        The duels are split across the Gauntlet and the result carries the split, so
        "52%" always arrives with the ten numbers it is the mean of. `on_matchup` is
        awaited as each opponent finishes -- the batch boundary where a job may
        report progress or be told to stop.
        """
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


def _kind_of(code: int | None) -> str:
    """What the card is: monster, spell or trap.

    Read from the same index the UI draws the card with, so the verb in the log and
    the card on the mat cannot disagree about what was just played.
    """
    card = card_index().get(code) if code is not None else None
    return card.kind if card else "unknown"


def _clamp(rate: float) -> float:
    """A win rate the duel farm could actually have measured."""
    return min(0.99, max(0.01, rate))


def _shares(duels: int, opponents: int) -> list[int]:
    """Split a duel count across the Gauntlet as evenly as the count allows.

    Every opponent is faced the same number of times, give or take the remainder:
    a win rate averaged over an uneven Gauntlet would say more about which decks
    got the extra duels than about the deck being measured.
    """
    base, extra = divmod(duels, opponents)
    return [base + (1 if i < extra else 0) for i in range(opponents)]


# The Gauntlet as it stands in phase 1: the shipped ygo-agent meta decks
# (`vendor/ygo-agent/assets/deck/`), read from committed data rather than the
# submodule so the API container needs neither it nor the network. The names were a
# tuple here while an opponent was only a label on a win rate; a replay plays the
# opponent's own cards, so the decklists come too (`gauntlet.py`).
GAUNTLET = gauntlet_names()

#: How far a fabricated matchup may sit from the deck's overall win rate. Real
#: matchup spreads are wider than this; what is load-bearing is that the spread is
#: stable per deck and centred on zero, not its width.
_MATCHUP_SPREAD = 0.30

#: What the fake says going first is worth. Master Duel Bo1 (ADR-0004), where the
#: seat is often worth more than the decklist -- which is the reason a matchup row
#: carries its first/second split at all.
_FIRST_EDGE = 0.09

# What a duel is made of, as the fake log tells it. Real logs come from the core.
# Keyed by action so the sentence and the action never contradict each other.
_VERBS = {
    "draw": ("draws for turn",),
    "end": ("ends the turn",),
}

# How a card gets onto the field, by what the card is. A Spell is activated and a
# monster is summoned; "Special Summons Super Polymerization" is a sentence no duel
# produces, and the action log is read line by line by someone who knows that. The
# board already places a card by its own type (`board.ts`), so this is the sentence
# catching up with the placement.
_PLAYS = {
    "monster": ("Normal Summons", "Special Summons", "sets"),
    "spell": ("activates", "sets"),
    "trap": ("sets",),
}
_PLAYS_UNKNOWN = ("plays",)


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

    def _measured(self, deck: Deck, duels: int, fidelity: Fidelity) -> float:
        """What the duel farm would have measured, at this fidelity.

        The same deck at the same duel count always comes back with the same number,
        which is the Paired evaluation property #3 asks for: re-running a deck under
        one Environment set reproduces its win rate exactly, so a Delta score is a
        difference between decks and not between two runs.
        """
        spread = 0.05 if fidelity is Fidelity.SCREENING else 0.01
        noise = (_hash_unit(sorted(deck.main), fidelity.value, duels) - 0.5) * 2 * spread
        return _clamp(self._true_win_rate(deck) + noise)

    async def screen(self, deck: Deck, duels: int) -> Evaluation:
        """One small batch, one number. No breakdown: see `Evaluation.matchups`."""
        await asyncio.sleep(self._duel_seconds * duels)
        return Evaluation(
            win_rate=self._measured(deck, duels, Fidelity.SCREENING),
            duels=duels,
            fidelity=Fidelity.SCREENING,
        )

    async def gate(
        self, deck: Deck, duels: int, *, on_matchup: MatchupSeen | None = None
    ) -> Evaluation:
        """The Gauntlet, one opponent at a time, reported as it goes.

        The headline is summed back out of the rows rather than carried beside them:
        the fake could trivially state both and let them disagree, and then the app
        would be showing a breakdown nobody could check against the number above it.
        """
        target = self._measured(deck, duels, Fidelity.GATE)
        rows: list[Matchup] = []
        for row in self._gauntlet(deck, duels, target):
            await asyncio.sleep(self._duel_seconds * row.duels)
            rows.append(row)
            if on_matchup is not None:
                await on_matchup(row)
        played = sum(row.duels for row in rows)
        wins = sum(row.wins for row in rows)
        return Evaluation(
            win_rate=wins / played if played else 0.0,
            duels=played,
            fidelity=Fidelity.GATE,
            matchups=rows,
        )

    def _matchup_rates(self, deck: Deck, centre: float) -> dict[str, float]:
        """This deck's fabricated win rate against each Gauntlet deck.

        Every deck has a good matchup and a bad one, and which is which is stable
        per deck: a breakdown that reshuffled on every run would teach a user to
        distrust the one screen in the app whose numbers are quotable. The offsets
        are centred on zero, so spreading a win rate across the Gauntlet does not
        move it -- the headline stays the number `_measured` produced, up to the
        rounding of whole duels into whole wins.

        One function for the breakdown and for the replay sample, so the duel a user
        opens against an opponent cannot contradict the row that measured it.
        """
        offsets = {
            opponent: (_hash_unit(sorted(deck.main), "matchup", opponent) - 0.5)
            * _MATCHUP_SPREAD
            for opponent in GAUNTLET
        }
        mean = sum(offsets.values()) / len(offsets)
        return {opponent: centre + off - mean for opponent, off in offsets.items()}

    def _gauntlet(
        self, deck: Deck, duels: int, target: float
    ) -> Iterator[Matchup]:
        """Fabricate each opponent's share of a Gate evaluation."""
        shares = _shares(duels, len(GAUNTLET))
        rates = self._matchup_rates(deck, target)
        for opponent, share in zip(GAUNTLET, shares):
            rate = rates[opponent]
            # ADR-0004 forces the seat 50/50. An odd share cannot be halved, so the
            # extra duel goes to the play -- and `first_duels` says which it was.
            first_duels = share - share // 2
            first_wins = round(first_duels * _clamp(rate + _FIRST_EDGE / 2))
            wins = first_wins + round(
                (share - first_duels) * _clamp(rate - _FIRST_EDGE / 2)
            )
            yield Matchup(
                opponent=opponent,
                duels=share,
                wins=wins,
                win_rate=wins / share if share else 0.0,
                first_duels=first_duels,
                first_wins=first_wins,
            )

    async def replays(self, deck: Deck, *, count: int) -> list[DuelReplay]:
        """A stratified sample of fabricated duels: one against each Gauntlet deck.

        Nothing here happened, but three things about the sample are pinned, and they
        are the three a user can check against the numbers on the same screen:

        - **One duel per opponent**, in the Gauntlet's fixed order. Picking the
          opponents by hash -- what this did before -- kept two duels against
          Centur-Ion and none against half the Gauntlet, so a matchup breakdown had
          rows that could not be opened.
        - **Half of them on the play.** ADR-0004 forces the seat 50/50 across a
          batch; a sample that fabricated a seat per duel would drift off it.
        - **The candidate wins as often as it wins.** `round(count * win_rate)` of
          them, and they are its best matchups. A deck that lost the duel it is 80%
          into while winning the one it is 20% into would teach a user to distrust
          the breakdown, which is the one screen in the app whose numbers are
          quotable.

        Drawn against the deck's own strength, with no fidelity noise: a kept duel
        is not a measurement, and rounding a sample of ten to a Screening number's
        wobble would be inventing precision twice over.
        """
        strength = self._true_win_rate(deck)
        rates = self._matchup_rates(deck, strength)
        opponents = [GAUNTLET[i % len(GAUNTLET)] for i in range(max(0, count))]
        # The wins go to the best matchups, ties broken by the fixed order so the
        # same deck always keeps the same sample.
        ranked = sorted(range(len(opponents)), key=lambda i: (-rates[opponents[i]], i))
        won = set(ranked[: round(len(opponents) * strength)])
        return [
            self._one_replay(
                deck,
                index,
                opponent=opponent,
                # Even index on the play. See the 50/50 above: it is the batch that
                # is split, and this sample is the batch.
                going_first=(
                    DuelSeat.CANDIDATE if index % 2 == 0 else DuelSeat.OPPONENT
                ),
                candidate_won=index in won,
            )
            for index, opponent in enumerate(opponents)
        ]

    def _one_replay(
        self,
        deck: Deck,
        index: int,
        *,
        opponent: str,
        going_first: DuelSeat,
        candidate_won: bool,
    ) -> DuelReplay:
        """One fabricated log, with each seat playing out of its own main deck.

        The candidate plays the deck that was submitted; the opponent plays the
        Gauntlet deck it is named after (`gauntlet.py`). The mat draws these cards
        one by one, so an opponent playing the candidate's cards is a lie told in the
        one place a user reads the log card by card.
        """
        cards = {
            DuelSeat.CANDIDATE: sorted(set(deck.main)),
            DuelSeat.OPPONENT: sorted(set(gauntlet_decks()[opponent].main)),
        }
        monsters = {
            seat: [code for code in row if _kind_of(code) == "monster"]
            for seat, row in cards.items()
        }
        #: What each seat has summoned face-up, in order. An attack names the monster
        #: making it, so it has to be a monster this seat actually put down: the mat
        #: highlights the attacker, and a Spell swinging for 1300 is visible there.
        board: dict[DuelSeat, list[int]] = {seat: [] for seat in cards}

        def pick(seat: DuelSeat, *salt: object) -> int:
            # An empty board summons a monster. Otherwise the first battle phase of
            # the duel would have nothing to attack with, and the fake would be
            # inventing an attacker to keep its own life-point arithmetic.
            row = monsters[seat] if not board[seat] and monsters[seat] else cards[seat]
            return row[int(_hash_unit(index, seat.value, *salt) * len(row))]

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
                card = pick(seat, turn, phase.value) if action != "end" else None
                if action == "attack":
                    # The newest monster on the board makes the attack.
                    card = board[seat][-1] if board[seat] else None
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
                elif action == "summon":
                    kind = _kind_of(card)
                    verbs = _PLAYS.get(kind, _PLAYS_UNKNOWN)
                    # A seat with nothing on the field summons face-up rather than
                    # setting: a face-down monster cannot attack, and the next
                    # battle phase is coming.
                    if kind == "monster" and not board[seat]:
                        verbs = tuple(verb for verb in verbs if verb != "sets")
                    text = verbs[int(_hash_unit(index, turn, action) * len(verbs))]
                    if kind == "monster" and not text.startswith("sets"):
                        board[seat].append(card)
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
