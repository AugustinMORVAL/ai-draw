"""Slice 6: a finished job keeps a sample of duels, and they can be watched.

The logs are fabricated -- `FakeExecutor` has no duels behind it (ADR-0005) -- so
every assertion here is about the *shape* the replay viewer relies on, never about
Yu-Gi-Oh. The one thing that must hold either way: a replay that names a winner has
to show that winner winning.
"""

from __future__ import annotations

import asyncio

import pytest

from ai_draw_api.executor import GAUNTLET, FakeExecutor
from ai_draw_api.refine import REPLAY_SAMPLE, random_deck

pytestmark = pytest.mark.asyncio


async def _finished_job(client) -> dict:
    r = await client.post(
        "/api/jobs/refine", json={"mutations": 2, "screening_duels": 10}
    )
    job_id = r.json()["id"]
    deadline = asyncio.get_running_loop().time() + 10.0
    while asyncio.get_running_loop().time() < deadline:
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["state"] in {"succeeded", "failed"}:
            assert job["state"] == "succeeded", job["error"]
            return job
        await asyncio.sleep(0.02)
    raise AssertionError("job never finished")


async def test_a_finished_job_keeps_a_sample_of_duels(client):
    job = await _finished_job(client)
    replays = (await client.get(f"/api/jobs/{job['id']}/replays")).json()
    assert len(replays) == REPLAY_SAMPLE
    assert all(r["opponent"] in GAUNTLET for r in replays)
    assert all(r["live"] is False for r in replays), "a fake duel must say so"
    assert "log" not in replays[0], "the list is summaries; logs come one at a time"


async def test_one_replay_comes_back_with_its_log(client):
    job = await _finished_job(client)
    replay = (await client.get(f"/api/jobs/{job['id']}/replays/0")).json()
    log = replay["log"]
    assert len(log) == replay["events"]
    assert [event["index"] for event in log] == list(range(len(log)))
    assert {event["seat"] for event in log} == {"candidate", "opponent"}


async def test_the_winner_is_the_one_still_standing(client):
    """A declared winner with the loser above 0 life points is a broken log."""
    job = await _finished_job(client)
    for summary in (await client.get(f"/api/jobs/{job['id']}/replays")).json():
        replay = (
            await client.get(f"/api/jobs/{job['id']}/replays/{summary['index']}")
        ).json()
        last = replay["log"][-1]
        loser_life = (
            last["life_opponent"]
            if replay["winner"] == "candidate"
            else last["life_candidate"]
        )
        assert loser_life == 0, f"replay {summary['index']} ends with a living loser"


async def test_life_points_only_ever_fall(client):
    job = await _finished_job(client)
    log = (await client.get(f"/api/jobs/{job['id']}/replays/0")).json()["log"]
    for before, after in zip(log, log[1:]):
        assert after["life_candidate"] <= before["life_candidate"]
        assert after["life_opponent"] <= before["life_opponent"]


async def test_an_unfinished_job_has_nothing_to_replay(client):
    r = await client.post(
        "/api/jobs/refine", json={"mutations": 200, "screening_duels": 1000}
    )
    job_id = r.json()["id"]
    r = await client.get(f"/api/jobs/{job_id}/replays")
    assert r.status_code == 409
    assert "no duels to replay yet" in r.json()["detail"]


async def test_unknown_job_and_unknown_replay_are_404(client):
    assert (await client.get("/api/jobs/nope/replays")).status_code == 404
    job = await _finished_job(client)
    assert (await client.get(f"/api/jobs/{job['id']}/replays/99")).status_code == 404


async def test_replays_are_played_with_the_decks_own_cards():
    """The log names cards from the deck. It is fake, not unrelated."""
    deck = random_deck(seed=7)
    replays = await FakeExecutor(duel_seconds=0.0).replays(deck, count=4)
    played = {e["card"] for r in replays for e in (x.model_dump() for x in r.log)}
    played.discard(None)
    assert played, "a duel with no cards in it is not a duel"
    assert played <= set(deck.main)
