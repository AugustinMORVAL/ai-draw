"""The queue must be single-slot, honest about position, and survive a restart."""

from __future__ import annotations

import pytest

from ai_draw_api.models import Deck, JobKind, JobState, Progress, RefineCheckpoint
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


CHECKPOINT = RefineCheckpoint(
    step=4, total=10, deck=Deck(main=[14558127] * 3), win_rate=0.52
)


async def test_a_checkpoint_survives_a_restart(db_path):
    """The work a job has already done outlives the process that did it."""
    store = JobStore(db_path)
    await store.open()
    job = await store.enqueue(JobKind.REFINE, {"mutations": 10})
    await store.claim_next()
    await store.set_progress(
        job.id, Progress(step=4, total=10, message="Mutation 4/10"), CHECKPOINT
    )
    await store.close()

    reopened = JobStore(db_path)
    await reopened.open()
    survivor = await reopened.get(job.id)
    assert survivor.checkpoint == CHECKPOINT.model_dump()

    # A report with nothing new to checkpoint must not throw the old one away.
    await reopened.set_progress(job.id, Progress(step=4, total=10, message="Resuming"))
    assert (await reopened.get(job.id)).checkpoint == CHECKPOINT.model_dump()
    await reopened.close()


async def test_a_result_replaces_the_checkpoint_but_a_cancel_keeps_it(store):
    finished = await store.enqueue(JobKind.REFINE, {})
    cancelled = await store.enqueue(JobKind.REFINE, {})
    for job in (finished, cancelled):
        await store.set_progress(job.id, Progress(), CHECKPOINT)

    await store.finish(finished.id, JobState.SUCCEEDED, result={"swaps": []})
    assert (await store.get(finished.id)).checkpoint is None, "the result supersedes it"

    await store.finish(cancelled.id, JobState.CANCELLED)
    assert (await store.get(cancelled.id)).checkpoint == CHECKPOINT.model_dump(), (
        "a job that stopped early keeps the only record of what it did"
    )


async def test_the_queue_list_carries_no_payload(store):
    """It is polled every 700 ms; a refine result holds six full duel logs."""
    job = await store.enqueue(JobKind.REFINE, {"mutations": 10})
    await store.claim_next()
    await store.set_progress(job.id, Progress(step=4, total=10), CHECKPOINT)
    await store.finish(
        job.id, JobState.SUCCEEDED, result={"replays": [{"index": 0}, {"index": 1}]}
    )

    (summary,) = await store.list()
    assert summary.id == job.id
    assert summary.progress.step == 4
    assert summary.replays == 2, "counted in SQL, so no log crosses the wire"
    assert not hasattr(summary, "result")
    assert not hasattr(summary, "checkpoint")


async def test_a_job_with_no_result_has_no_duels_to_watch(store):
    await store.enqueue(JobKind.REFINE, {})
    (summary,) = await store.list()
    assert summary.replays == 0
