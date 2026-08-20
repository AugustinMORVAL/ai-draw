"""The slice-0 manual test, automated: submit, queue, run, finish, and still there."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_draw_api.executor import FakeExecutor
from ai_draw_api.main import create_app
from ai_draw_api.store import JobStore

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


SPELLCASTERS = {
    "main_size": 40,
    "clauses": [
        {"facet": "race", "value": "Spellcaster", "bound": "at_least", "count": 20},
        {"facet": "kind", "value": "trap", "bound": "at_most", "count": 4},
    ],
}


async def test_the_facets_a_constraint_can_be_written_against(client):
    listed = (await client.get("/api/constraints/facets")).json()
    assert listed["main_deck_pool_size"] == 408
    by_value = {(v["facet"], v["value"]): v for v in listed["values"]}
    assert by_value[("race", "Spellcaster")]["copies"] > 0
    cyberse = by_value[("race", "Cyberse")]
    assert cyberse["copies"] == 0 and cyberse["elsewhere"] == 34


async def test_building_a_deck_under_a_constraint(client):
    """The slice-2 manual test, over HTTP: ask, and get a legal deck that respects it."""
    r = await client.post(
        "/api/decks/build", json={"constraint": SPELLCASTERS, "seed": 2}
    )
    assert r.status_code == 200, r.text
    report = r.json()

    assert report["legal"] is True, report["flags"]
    assert report["main_count"] == 40
    assert report["constraint"]["satisfied"] is True, report["constraint"]["flags"]
    held = {c["clause"]["value"]: c["held"] for c in report["constraint"]["clauses"]}
    assert held["Spellcaster"] >= 20
    assert held["trap"] <= 4


async def test_a_constraint_the_pool_cannot_satisfy_is_refused_with_its_reason(client):
    """No main-deck Cyberse card is in the 864, so there is no deck to queue."""
    r = await client.post(
        "/api/decks/build",
        json={
            "constraint": {
                "main_size": 40,
                "clauses": [
                    {
                        "facet": "race",
                        "value": "Cyberse",
                        "bound": "at_least",
                        "count": 12,
                    }
                ],
            }
        },
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["feasible"] is False
    assert detail["flags"][0]["issue"] == "impossible"
    assert "Extra Deck monster" in detail["flags"][0]["reason"]


async def test_parsing_judges_a_constraint_beside_legality_not_inside_it(client):
    text = SEED_DECK.read_text()
    report = (
        await client.post(
            "/api/decks/parse", json={"text": text, "constraint": SPELLCASTERS}
        )
    ).json()

    assert report["legal"] is True, "a Constraint is not a rule, so it cannot make it illegal"
    assert report["constraint"]["satisfied"] is False
    assert any(
        flag["issue"] == "unmet_minimum" for flag in report["constraint"]["flags"]
    )


async def test_a_constrained_job_builds_its_own_deck_and_keeps_it_conformant(client):
    r = await client.post(
        "/api/jobs/refine",
        json={"constraint": SPELLCASTERS, "mutations": 6, "screening_duels": 10},
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["params"]["constraint"]["main_size"] == 40

    done = await _await_state(client, job["id"], {"succeeded", "failed"})
    assert done["state"] == "succeeded", done["error"]

    final = done["result"]["deck"]
    checked = (
        await client.post(
            "/api/decks/parse",
            json={
                "text": "\n".join(str(code) for code in final["main"]),
                "constraint": SPELLCASTERS,
            },
        )
    ).json()
    assert checked["legal"] is True, checked["flags"]
    assert checked["constraint"]["satisfied"] is True, checked["constraint"]["flags"]


@asynccontextmanager
async def _running_app(db_path, *, duel_seconds: float):
    """The app over a given database, at a chosen duel speed.

    Slice 3 is about what a user sees *while* a job runs, so its tests need a job
    that takes long enough to be watched, and a second process over the same file.
    """
    app = create_app(
        store=JobStore(db_path), executor=FakeExecutor(duel_seconds=duel_seconds)
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_the_slice_3_manual_test(db_path):
    """Submit a deck, watch it swap by swap, then read what actually changed."""
    async with _running_app(db_path, duel_seconds=0.002) as client:
        report = (
            await client.post(
                "/api/decks/parse", json={"text": SEED_DECK.read_text()}
            )
        ).json()
        assert report["legal"] is True

        submitted = (
            await client.post(
                "/api/jobs/refine",
                json={
                    "deck": report["deck"],
                    "mutations": 40,
                    "screening_duels": 10,
                },
            )
        ).json()

        # Watched swap by swap: the log grows as the job runs. It is not one
        # spinner that turns into forty mutations at the end.
        widths = []
        while True:
            job = (await client.get(f"/api/jobs/{submitted['id']}")).json()
            if job["checkpoint"]:
                widths.append(len(job["checkpoint"]["swaps"]))
            if job["state"] in {"succeeded", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.02)

        assert job["state"] == "succeeded", job["error"]
        assert len(set(widths)) > 1, "the swap log was only readable once it ended"
        assert widths == sorted(widths), "a swap log never un-happens"

        result = job["result"]
        assert job["checkpoint"] is None, "the result supersedes the checkpoint"
        assert result["starting_deck"]["main"] == report["deck"]["main"]

        # And which cards changed, as cards: the net of the log, not the log.
        diff = result["diff"]
        added = sum(change["count"] for change in diff["added"])
        removed = sum(change["count"] for change in diff["removed"])
        assert added == removed, "a swap trades one card for one card"
        assert added + diff["unchanged"] == len(result["deck"]["main"])
        for change in diff["added"]:
            card = (await client.get(f"/api/cards/{change['card']}")).json()
            assert card["in_pool"] is True, card["name"]


async def test_a_restart_resumes_a_job_instead_of_starting_it_over(db_path):
    """The known gap slice 0 left: a job survived a restart but redid its work."""
    async with _running_app(db_path, duel_seconds=0.002) as client:
        submitted = (
            await client.post(
                "/api/jobs/refine", json={"mutations": 60, "screening_duels": 10}
            )
        ).json()
        checkpoint = None
        while checkpoint is None or checkpoint["step"] < 5:
            job = (await client.get(f"/api/jobs/{submitted['id']}")).json()
            checkpoint = job["checkpoint"]
            await asyncio.sleep(0.01)

    # The process dies here, mid-job. A new one opens the same database.
    async with _running_app(db_path, duel_seconds=0.0) as client:
        done = await _await_state(client, submitted["id"], {"succeeded", "failed"})
        assert done["state"] == "succeeded", done["error"]
        swaps = done["result"]["swaps"]
        assert [s["step"] for s in swaps] == list(range(1, 61)), "no mutation is lost"
        assert swaps[: len(checkpoint["swaps"])] == checkpoint["swaps"], (
            "the mutations run before the restart are the ones it came back with"
        )


async def test_the_queue_list_is_summaries_not_payloads(client):
    """What the browser polls carries no decks, no results and no duel logs."""
    submitted = (await client.post("/api/jobs/refine", json={"mutations": 2})).json()
    done = await _await_state(client, submitted["id"], {"succeeded", "failed"})
    assert done["result"]["replays"], "the job kept duels"

    (listed,) = (await client.get("/api/jobs")).json()
    assert listed["id"] == submitted["id"]
    assert listed["replays"] == len(done["result"]["replays"])
    assert "result" not in listed and "params" not in listed
