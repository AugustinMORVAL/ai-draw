"""The seam. `FakeExecutor` must satisfy the interface every slice is built on."""

from __future__ import annotations

import pytest

from ai_draw_api.executor import DuelExecutor, FakeExecutor
from ai_draw_api.models import Deck, Fidelity

pytestmark = pytest.mark.asyncio


async def test_fake_satisfies_the_protocol():
    assert isinstance(FakeExecutor(), DuelExecutor)


async def test_fake_is_never_labelled_live():
    assert FakeExecutor().live is False


async def test_same_deck_scores_the_same():
    executor = FakeExecutor(duel_seconds=0.0)
    deck = Deck(main=[1, 2, 3, 4])
    first = await executor.screen(deck, 100)
    second = await executor.screen(Deck(main=[4, 3, 2, 1]), 100)
    assert first.win_rate == second.win_rate, "card order must not change the score"


async def test_evaluations_carry_their_fidelity():
    executor = FakeExecutor(duel_seconds=0.0)
    deck = Deck(main=[1, 2, 3])
    assert (await executor.screen(deck, 100)).fidelity is Fidelity.SCREENING
    assert (await executor.gate(deck, 500)).fidelity is Fidelity.GATE


async def test_screening_is_noisier_than_the_gate():
    """ADR-0003: Screening is noisy by design; Gate evaluation is what gets quoted."""
    executor = FakeExecutor(duel_seconds=0.0)
    decks = [Deck(main=[i, i + 1, i + 2]) for i in range(200)]
    truth = [executor._true_win_rate(d) for d in decks]
    screening = [abs((await executor.screen(d, 100)).win_rate - t) for d, t in zip(decks, truth)]
    gate = [abs((await executor.gate(d, 500)).win_rate - t) for d, t in zip(decks, truth)]
    assert sum(screening) / len(screening) > sum(gate) / len(gate)
