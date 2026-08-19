"""FastAPI app: submit a job, watch the queue, read the result."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .executor import DuelExecutor, FakeExecutor
from .models import Health, Job, JobKind, RefineParams, SubmitRefine
from .pool import supported_pool
from .refine import random_deck
from .store import JobStore
from .worker import Worker

DEFAULT_DB = Path(__file__).resolve().parents[2] / "var" / "jobs.db"

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def create_app(
    *, store: JobStore | None = None, executor: DuelExecutor | None = None
) -> FastAPI:
    store = store or JobStore(os.environ.get("AI_DRAW_DB", DEFAULT_DB))
    executor = executor or FakeExecutor()
    worker = Worker(store, executor)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await store.open()
        await worker.start()
        try:
            yield
        finally:
            await worker.stop()
            await store.close()

    app = FastAPI(title="ai-draw", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = store
    app.state.executor = executor
    app.state.worker = worker

    @app.get("/api/health", response_model=Health)
    async def health() -> Health:
        return Health(
            status="ok",
            live=executor.live,
            executor=executor.name,
            pool_size=len(supported_pool()),
            version=__version__,
        )

    @app.post("/api/jobs/refine", response_model=Job, status_code=201)
    async def submit_refine(body: SubmitRefine) -> Job:
        params = RefineParams(
            deck=body.deck or random_deck(),
            mutations=body.mutations,
            screening_duels=body.screening_duels,
        )
        return await store.enqueue(JobKind.REFINE, params.model_dump())

    @app.get("/api/jobs", response_model=list[Job])
    async def list_jobs(limit: int = 50) -> list[Job]:
        return await store.list(limit=min(max(limit, 1), 200))

    @app.get("/api/jobs/{job_id}", response_model=Job)
    async def get_job(job_id: str) -> Job:
        job = await store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such job")
        return job

    @app.post("/api/jobs/{job_id}/cancel", response_model=Job)
    async def cancel_job(job_id: str) -> Job:
        job = await store.request_cancel(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such job")
        return job

    return app


app = create_app()
