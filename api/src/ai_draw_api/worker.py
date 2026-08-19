"""The single-slot worker: one job at a time, progress written through to the store."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from .executor import DuelExecutor
from .models import Job, JobKind, JobState, Progress, RefineParams
from .refine import Cancelled, run_refine
from .store import JobStore

log = logging.getLogger(__name__)


class Worker:
    def __init__(
        self, store: JobStore, executor: DuelExecutor, *, poll_seconds: float = 0.05
    ) -> None:
        self.store = store
        self.executor = executor
        self.poll_seconds = poll_seconds
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        await self.store.recover_orphans()
        self._task = asyncio.create_task(self._loop(), name="ai-draw-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                job = await self.store.claim_next()
            except Exception:  # a broken store must not kill the loop
                log.exception("failed to claim a job")
                job = None
            if job is None:
                await asyncio.sleep(self.poll_seconds)
                continue
            await self._run(job)

    async def _run(self, job: Job) -> None:
        async def report(progress: Progress) -> None:
            await self.store.set_progress(job.id, progress)

        async def should_cancel() -> bool:
            return await self.store.cancel_requested(job.id)

        try:
            if job.kind is JobKind.REFINE:
                result = await run_refine(
                    RefineParams.model_validate(job.params),
                    self.executor,
                    report,
                    should_cancel,
                )
            else:
                raise NotImplementedError(f"{job.kind.value} jobs land in a later slice")
        except Cancelled:
            await self.store.finish(job.id, JobState.CANCELLED)
        except asyncio.CancelledError:
            # Shutdown mid-job: leave it RUNNING so recovery re-queues it on restart.
            raise
        except Exception as exc:
            log.exception("job %s failed", job.id)
            await self.store.finish(job.id, JobState.FAILED, error=f"{type(exc).__name__}: {exc}")
        else:
            await self.store.finish(
                job.id, JobState.SUCCEEDED, result=result.model_dump()
            )
