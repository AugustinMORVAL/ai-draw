"""The slice-4 manual test: a Gate evaluation, and the ten numbers behind it.

`gate()` is the only fidelity ADR-0003 lets anyone quote, so these tests are about
the properties that make a number quotable: it is reproducible, it is the sum of
the duels it claims to be made of, and it never arrives without saying so.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ai_draw_api.constraints import random_deck
from ai_draw_api.executor import GAUNTLET, REPLAY_SAMPLE, FakeExecutor, _shares
from ai_draw_api.gate import run_test
from ai_draw_api.models import (
    Deck,
    Fidelity,
    Progress,
    GateParams,
    wald_margin,
)
from ai_draw_api.refine import Cancelled

SEED_DECK = Path(__file__).parent / "fixtures" / "Shaddoll.ydk"

pytestmark = pytest.mark.asyncio

DECK = Deck(main=sorted(random_deck(seed=11).main))


async def _noop(_: Progress, checkpoint: object | None = None) -> None:
    return None


async def never_cancel() -> bool:
    return False


def fake() -> FakeExecutor:
    return FakeExecutor(duel_seconds=0.0)


async def _await_state(client, job_id: str, states: set[str], timeout: float = 10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["state"] in states:
            return job
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached {states}; last was {job}")


# --- the evaluation ------------------------------------------------------


async def test_the_whole_gauntlet_is_faced():
    """Fixed opponents, evenly split: a win rate over an uneven Gauntlet is a lie."""
    evaluation = await fake().gate(DECK, 500)
    assert [row.opponent for row in evaluation.matchups] == list(GAUNTLET)
    assert {row.duels for row in evaluation.matchups} == {50}
    assert evaluation.duels == 500


async def test_the_headline_is_the_sum_of_its_matchups():
    """The number on screen has to be checkable against the rows under it."""
    evaluation = await fake().gate(DECK, 500)
    wins = sum(row.wins for row in evaluation.matchups)
    duels = sum(row.duels for row in evaluation.matchups)
    assert duels == evaluation.duels
    assert evaluation.win_rate == pytest.approx(wins / duels)


async def test_every_matchup_splits_its_seats_fifty_fifty():
    """ADR-0004 forces the seat, so a deck cannot be measured on the play only."""
    for row in (await fake().gate(DECK, 500)).matchups:
        assert row.first_duels == row.duels - row.first_duels
        assert 0 <= row.first_wins <= row.first_duels
        assert row.first_wins <= row.wins


async def test_a_gate_evaluation_says_what_it_is():
    evaluation = await fake().gate(DECK, 500)
    assert evaluation.fidelity is Fidelity.GATE


async def test_screening_carries_no_matchup_breakdown():
    """Ten duels per opponent is a +/-31 point band under an unquotable number."""
    assert (await fake().screen(DECK, 100)).matchups == []


async def test_the_same_deck_measured_twice_gives_the_same_number():
    """#3's first acceptance, at the seam: one Environment set, one answer.

    Without this a Delta score is the difference between two runs rather than
    between two decks, and everything downstream of it is unfalsifiable.
    """
    first = await fake().gate(DECK, 500)
    second = await fake().gate(Deck(main=list(reversed(DECK.main))), 500)
    assert first.win_rate == second.win_rate
    assert [row.wins for row in first.matchups] == [row.wins for row in second.matchups]


async def test_a_deck_has_good_and_bad_matchups():
    """A flat breakdown would be a breakdown worth nothing to read."""
    rates = [row.win_rate for row in (await fake().gate(DECK, 500)).matchups]
    assert max(rates) - min(rates) > 0.10


async def test_the_split_is_even_whatever_the_duel_count():
    for duels in (500, 501, 999, 5000):
        shares = _shares(duels, len(GAUNTLET))
        assert sum(shares) == duels
        assert max(shares) - min(shares) <= 1


# --- the job -------------------------------------------------------------


async def test_the_job_reports_one_opponent_at_a_time():
    seen: list[Progress] = []

    async def report(progress: Progress, checkpoint: object | None = None) -> None:
        seen.append(progress)

    result = await run_test(
        GateParams(deck=DECK, gate_duels=500), fake(), report, never_cancel
    )

    named = [p for p in seen if any(p.message.startswith(o) for o in GAUNTLET)]
    assert len(named) == len(GAUNTLET), "each matchup is news while a test runs"
    assert [p.step for p in named] == list(range(1, len(GAUNTLET) + 1))
    assert result.duels == 500


async def test_the_job_keeps_duels_to_watch():
    result = await run_test(
        GateParams(deck=DECK, gate_duels=500), fake(), _noop, never_cancel
    )
    assert result.replays, "a Gate number is watchable, not only readable"
    assert all(replay.live is False for replay in result.replays)
    assert result.live is False


async def test_a_test_job_stops_between_matchups():
    """A candidate deck may only be swapped at a batch boundary (ADR-0004)."""
    calls = 0

    async def cancel_after_three() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 3

    with pytest.raises(Cancelled):
        await run_test(
            GateParams(deck=DECK, gate_duels=500), fake(), _noop, cancel_after_three
        )


async def test_the_margin_is_the_band_the_duel_count_earns():
    """+/-4.4 points at 500 duels, +/-13.9 at the fifty one matchup gets."""
    assert wald_margin(250, 500) == pytest.approx(0.0438, abs=0.001)
    assert wald_margin(25, 50) == pytest.approx(0.1386, abs=0.001)
    assert wald_margin(0, 0) == 0.0

    result = await run_test(
        GateParams(deck=DECK, gate_duels=500), fake(), _noop, never_cancel
    )
    assert 0.02 < result.margin < 0.05
    assert all(row.margin > result.margin for row in result.matchups), (
        "fifty duels can never be as sharp as five hundred"
    )


# --- over HTTP -----------------------------------------------------------


async def test_run_a_test_and_get_a_win_rate_with_its_matchups(client):
    """The slice-4 manual test: run a test, read the breakdown, labelled Gate."""
    text = SEED_DECK.read_text()
    report = (await client.post("/api/decks/parse", json={"text": text})).json()
    assert report["legal"] is True

    r = await client.post("/api/jobs/test", json={"deck": report["deck"]})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["kind"] == "test"
    assert job["params"]["gate_duels"] == 500

    done = await _await_state(client, job["id"], {"succeeded", "failed"})
    assert done["state"] == "succeeded", done["error"]
    result = done["result"]

    assert result["fidelity"] == "gate", "the only fidelity anyone may quote"
    assert result["duels"] == 500
    assert 0.0 < result["win_rate"] < 1.0
    assert result["margin"] > 0

    matchups = result["matchups"]
    assert len(matchups) == 10
    assert sum(row["duels"] for row in matchups) == 500
    assert sum(row["wins"] for row in matchups) / 500 == pytest.approx(
        result["win_rate"]
    )
    assert all(row["opponent"] for row in matchups)

    # Every row in the breakdown has a duel behind it: the sample is one duel per
    # Gauntlet deck, so a matchup a user wants to look at can always be opened.
    watchable = (await client.get(f"/api/jobs/{job['id']}/replays")).json()
    assert len(watchable) == REPLAY_SAMPLE, "the same sample a refine job keeps"
    assert [replay["opponent"] for replay in watchable] == [
        row["opponent"] for row in matchups
    ]


async def test_a_gate_evaluation_cannot_be_run_at_screening_size(client):
    """500 is the floor ADR-0003 sets, and it is not the caller's to lower."""
    r = await client.post("/api/jobs/test", json={"gate_duels": 100})
    assert r.status_code == 422
    assert "gate_duels" in r.text


async def test_a_test_job_refuses_an_illegal_deck_like_a_refine_job(client):
    """Same refusal, same body: `ygopro-core` aborts on a malformed deck (#4)."""
    token = 91512836
    r = await client.post("/api/jobs/test", json={"deck": {"main": [token] * 40}})
    assert r.status_code == 422
    assert r.json()["detail"]["flags"][0]["issue"] == "token"


async def test_a_test_job_builds_a_deck_when_it_is_given_none(client):
    r = await client.post("/api/jobs/test", json={})
    assert r.status_code == 201, r.text
    job = r.json()
    assert len(job["params"]["deck"]["main"]) == 40
    await client.post(f"/api/jobs/{job['id']}/cancel")


async def test_a_test_job_records_what_the_deck_was_asked_for(client):
    """A win rate read months later has to say what it measured."""
    constraint = {
        "main_size": 40,
        "clauses": [
            {"facet": "race", "value": "Spellcaster", "bound": "at_least", "count": 20}
        ],
    }
    r = await client.post("/api/jobs/test", json={"constraint": constraint})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["params"]["constraint"]["clauses"][0]["value"] == "Spellcaster"
    await client.post(f"/api/jobs/{job['id']}/cancel")
