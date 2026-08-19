"""The slice-0 manual test, automated: submit, queue, run, finish, and still there."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

SEED_DECK = Path(__file__).parent / "fixtures" / "Shaddoll.ydk"

pytestmark = pytest.mark.asyncio


async def _await_state(client, job_id: str, states: set[str], timeout: float = 10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["state"] in states:
            return job
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached {states}; last was {job}")


async def test_health_says_it_is_not_live(client):
    body = (await client.get("/api/health")).json()
    assert body["live"] is False
    assert body["executor"] == "fake"
    assert body["pool_size"] == 864
    assert body["main_deck_pool_size"] == 408, "most of the pool is not deckable"
    assert body["banlist"] == "2024.7"


async def test_submit_runs_and_finishes(client):
    r = await client.post("/api/jobs/refine", json={"mutations": 5, "screening_duels": 10})
    assert r.status_code == 201
    job = r.json()
    assert job["state"] == "queued"
    assert job["queue_position"] == 1
    assert len(job["params"]["deck"]["main"]) == 40

    done = await _await_state(client, job["id"], {"succeeded", "failed"})
    assert done["state"] == "succeeded", done["error"]
    assert done["queue_position"] is None
    assert done["progress"]["step"] == 5
    result = done["result"]
    assert len(result["swaps"]) == 5
    assert result["fidelity"] == "screening", "a refine result is never Gate-quality"
    assert result["live"] is False


async def test_second_submission_queues_behind_the_first(client):
    first = (await client.post("/api/jobs/refine", json={"mutations": 40})).json()
    second = (await client.post("/api/jobs/refine", json={"mutations": 1})).json()

    fetched = (await client.get(f"/api/jobs/{second['id']}")).json()
    assert fetched["state"] == "queued"
    assert fetched["queue_position"] >= 1, "users see a position, not a spinner"

    await client.post(f"/api/jobs/{first['id']}/cancel")
    await client.post(f"/api/jobs/{second['id']}/cancel")


async def test_a_job_outlives_the_browser_tab(client):
    """Reloading the page is just another GET — the job is in the database."""
    job = (await client.post("/api/jobs/refine", json={"mutations": 3})).json()
    listed = (await client.get("/api/jobs")).json()
    assert job["id"] in [j["id"] for j in listed]

    done = await _await_state(client, job["id"], {"succeeded", "failed"})
    assert done["state"] == "succeeded"


async def test_cancel_a_running_job(client):
    job = (await client.post("/api/jobs/refine", json={"mutations": 200})).json()
    await _await_state(client, job["id"], {"running"})
    await client.post(f"/api/jobs/{job['id']}/cancel")
    stopped = await _await_state(client, job["id"], {"cancelled"})
    assert stopped["progress"]["step"] < 200


async def test_unknown_job_is_a_404(client):
    assert (await client.get("/api/jobs/nope")).status_code == 404


async def test_card_search_marks_what_the_pilot_cannot_play(client):
    hits = (await client.get("/api/cards", params={"q": "dark magician"})).json()
    assert hits, "a user searching a real card is never shown an empty box"
    assert all(hit["in_pool"] is False for hit in hits)


async def test_one_card_by_code(client):
    card = (await client.get("/api/cards/14558127")).json()
    assert card["name"] == "Ash Blossom & Joyous Spring"
    assert (await client.get("/api/cards/999999999")).status_code == 404


async def test_parsing_a_deck_flags_both_problems(client):
    """The slice-1 manual test, over HTTP."""
    text = "3 Ash Blossom & Joyous Spring\n4 Pot of Desires\nDark Magician\n"
    report = (await client.post("/api/decks/parse", json={"text": text})).json()

    assert report["legal"] is False
    assert report["banlist"] == "2024.7"
    reasons = {flag["issue"]: flag["reason"] for flag in report["flags"]}
    assert "over_limit" in reasons and "Pot of Desires" in reasons["over_limit"]
    assert "not_in_pool" in reasons and "Dark Magician" in reasons["not_in_pool"]
    assert report["mask"]["legal_picks"] > 0


async def test_an_illegal_deck_is_refused_at_the_door(client):
    """`ygopro-core` aborts on a malformed deck, so the queue never sees one (#4)."""
    token = 91512836
    deck = {"main": [token] * 40}
    r = await client.post("/api/jobs/refine", json={"deck": deck, "mutations": 1})
    assert r.status_code == 422
    assert r.json()["detail"]["flags"][0]["issue"] == "token"


async def test_a_legal_deck_is_accepted(client):
    text = SEED_DECK.read_text()
    report = (await client.post("/api/decks/parse", json={"text": text})).json()
    assert report["legal"] is True
    r = await client.post(
        "/api/jobs/refine", json={"deck": report["deck"], "mutations": 1}
    )
    assert r.status_code == 201, r.text


async def test_the_random_deck_the_app_submits_is_legal(client):
    """It is the deck the executor would actually be handed."""
    job = (await client.post("/api/jobs/refine", json={"mutations": 1})).json()
    codes = job["params"]["deck"]["main"]
    text = "\n".join(str(code) for code in codes)
    report = (await client.post("/api/decks/parse", json={"text": text})).json()
    assert report["legal"] is True, report["flags"]


async def test_the_whole_pool_comes_back_in_one_response(client):
    """The deck editor holds the pool and filters it locally."""
    pool = (await client.get("/api/pool")).json()
    assert len(pool) == 864
    assert all(card["in_pool"] for card in pool)
    assert sum(card["section"] == "main" for card in pool) == 411
    ash = next(c for c in pool if c["name"] == 'Maxx "C"')
    assert ash["desc"], "the inspector reads the card text out of this"
