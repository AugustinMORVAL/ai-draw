"""Durable job state. A job outlives the request, the tab, and an API restart.

State lives here, not in process memory (ADR-0005). The queue is single-slot: exactly
one job runs at a time because the duel farm already saturates every core, so a second
concurrent job would only make both users wait longer.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import aiosqlite

from .models import TERMINAL_STATES, Job, JobKind, JobState, Progress

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    id               TEXT    NOT NULL UNIQUE,
    kind             TEXT    NOT NULL,
    state            TEXT    NOT NULL,
    params           TEXT    NOT NULL,
    progress         TEXT    NOT NULL,
    result           TEXT,
    error            TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at       REAL    NOT NULL,
    started_at       REAL,
    finished_at      REAL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs (state, seq);
"""


class JobStore:
    """SQLite-backed job table. One connection, awaited from the event loop."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._db: aiosqlite.Connection | None = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("JobStore is not open")
        return self._db

    async def open(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def recover_orphans(self) -> int:
        """Re-queue jobs left RUNNING by a crash or restart. Returns how many."""
        cur = await self.db.execute(
            "UPDATE jobs SET state = ?, started_at = NULL WHERE state = ?",
            (JobState.QUEUED.value, JobState.RUNNING.value),
        )
        await self.db.commit()
        return cur.rowcount or 0

    async def enqueue(self, kind: JobKind, params: dict) -> Job:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        await self.db.execute(
            "INSERT INTO jobs (id, kind, state, params, progress, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                job_id,
                kind.value,
                JobState.QUEUED.value,
                json.dumps(params),
                Progress().model_dump_json(),
                now,
            ),
        )
        await self.db.commit()
        job = await self.get(job_id)
        assert job is not None
        return job

    async def claim_next(self) -> Job | None:
        """Take the oldest queued job and mark it RUNNING. Single slot: if one is
        already running, claim nothing."""
        async with self.db.execute(
            "SELECT COUNT(*) FROM jobs WHERE state = ?", (JobState.RUNNING.value,)
        ) as cur:
            (running,) = await cur.fetchone()
        if running:
            return None
        async with self.db.execute(
            "SELECT id FROM jobs WHERE state = ? ORDER BY seq LIMIT 1",
            (JobState.QUEUED.value,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        await self.db.execute(
            "UPDATE jobs SET state = ?, started_at = ? WHERE id = ? AND state = ?",
            (JobState.RUNNING.value, time.time(), row["id"], JobState.QUEUED.value),
        )
        await self.db.commit()
        return await self.get(row["id"])

    async def set_progress(self, job_id: str, progress: Progress) -> None:
        await self.db.execute(
            "UPDATE jobs SET progress = ? WHERE id = ?",
            (progress.model_dump_json(), job_id),
        )
        await self.db.commit()

    async def finish(
        self,
        job_id: str,
        state: JobState,
        *,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        await self.db.execute(
            "UPDATE jobs SET state = ?, result = ?, error = ?, finished_at = ?"
            " WHERE id = ?",
            (
                state.value,
                json.dumps(result) if result is not None else None,
                error,
                time.time(),
                job_id,
            ),
        )
        await self.db.commit()

    async def request_cancel(self, job_id: str) -> Job | None:
        """Cancel a queued job outright; flag a running one for the worker to stop."""
        job = await self.get(job_id)
        if job is None or job.state in TERMINAL_STATES:
            return job
        if job.state is JobState.QUEUED:
            await self.finish(job_id, JobState.CANCELLED)
        else:
            await self.db.execute(
                "UPDATE jobs SET cancel_requested = 1 WHERE id = ?", (job_id,)
            )
            await self.db.commit()
        return await self.get(job_id)

    async def cancel_requested(self, job_id: str) -> bool:
        async with self.db.execute(
            "SELECT cancel_requested FROM jobs WHERE id = ?", (job_id,)
        ) as cur:
            row = await cur.fetchone()
        return bool(row and row["cancel_requested"])

    async def get(self, job_id: str) -> Job | None:
        async with self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return await self._to_job(row)

    async def list(self, limit: int = 50) -> list[Job]:
        async with self.db.execute(
            "SELECT * FROM jobs ORDER BY seq DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [await self._to_job(row) for row in rows]

    async def _queue_position(self, row: aiosqlite.Row) -> int | None:
        """1 = next to run. Running jobs are 0. Finished jobs have no position."""
        state = JobState(row["state"])
        if state is JobState.RUNNING:
            return 0
        if state is not JobState.QUEUED:
            return None
        async with self.db.execute(
            "SELECT COUNT(*) FROM jobs WHERE state = ? AND seq < ?",
            (JobState.QUEUED.value, row["seq"]),
        ) as cur:
            (ahead,) = await cur.fetchone()
        return ahead + 1

    async def _to_job(self, row: aiosqlite.Row) -> Job:
        return Job(
            id=row["id"],
            kind=JobKind(row["kind"]),
            state=JobState(row["state"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            queue_position=await self._queue_position(row),
            progress=Progress.model_validate_json(row["progress"]),
            params=json.loads(row["params"]),
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
        )
