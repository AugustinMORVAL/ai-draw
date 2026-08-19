"""The slice-0 manual test, automated: submit, queue, run, finish, and still there."""

from __future__ import annotations

import asyncio

import pytest

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
