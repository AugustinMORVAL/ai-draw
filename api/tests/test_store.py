"""The queue must be single-slot, honest about position, and survive a restart."""

from __future__ import annotations

import pytest

from ai_draw_api.models import JobKind, JobState, Progress
from ai_draw_api.store import JobStore

pytestmark = pytest.mark.asyncio


async def test_queue_positions_are_honest(store):
    a = await store.enqueue(JobKind.REFINE, {})
    b = await store.enqueue(JobKind.REFINE, {})
    c = await store.enqueue(JobKind.REFINE, {})

    assert [(await store.get(j.id)).queue_position for j in (a, b, c)] == [1, 2, 3]

    claimed = await store.claim_next()
    assert claimed.id == a.id
    assert (await store.get(a.id)).queue_position == 0  # running
    assert [(await store.get(j.id)).queue_position for j in (b, c)] == [1, 2]

    await store.finish(a.id, JobState.SUCCEEDED, result={"ok": True})
    assert (await store.get(a.id)).queue_position is None


async def test_single_slot(store):
    await store.enqueue(JobKind.REFINE, {})
    await store.enqueue(JobKind.REFINE, {})

    assert await store.claim_next() is not None
    assert await store.claim_next() is None, "a second job must not start"


async def test_running_job_survives_a_restart(db_path):
    store = JobStore(db_path)
    await store.open()
    job = await store.enqueue(JobKind.REFINE, {"mutations": 3})
    await store.claim_next()
    await store.set_progress(job.id, Progress(step=1, total=3, message="halfway"))
    await store.close()

    # The process dies here. A fresh store over the same file finds the job.
    reopened = JobStore(db_path)
    await reopened.open()
    survivor = await reopened.get(job.id)
    assert survivor is not None
    assert survivor.state is JobState.RUNNING
    assert survivor.progress.step == 1
    assert survivor.params == {"mutations": 3}

    assert await reopened.recover_orphans() == 1
    requeued = await reopened.get(job.id)
    assert requeued.state is JobState.QUEUED
    assert requeued.queue_position == 1
    await reopened.close()


async def test_cancel_a_queued_job_is_immediate(store):
    await store.enqueue(JobKind.REFINE, {})
    queued = await store.enqueue(JobKind.REFINE, {})

    cancelled = await store.request_cancel(queued.id)
    assert cancelled.state is JobState.CANCELLED
    assert cancelled.finished_at is not None


async def test_cancel_a_running_job_only_flags_it(store):
    job = await store.enqueue(JobKind.REFINE, {})
    await store.claim_next()

    flagged = await store.request_cancel(job.id)
    assert flagged.state is JobState.RUNNING, "the worker stops it, not the request"
    assert await store.cancel_requested(job.id) is True
