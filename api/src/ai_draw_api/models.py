"""Wire models. Every number carries the fidelity it was measured at (ADR-0003)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class JobKind(str, Enum):
    REFINE = "refine"
    TEST = "test"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset(
    {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}
)


class Fidelity(str, Enum):
    """Which evaluation produced a win rate. Never let the UI guess."""

    SCREENING = "screening"
    GATE = "gate"


class Deck(BaseModel):
    """A candidate deck, as main-deck card codes."""

    main: list[int] = Field(min_length=1)


class Swap(BaseModel):
    """One accepted or rejected mutation, with its Delta score."""

    step: int
    card_out: int
    card_in: int
    win_rate: float
    delta: float
    accepted: bool


class RefineParams(BaseModel):
    deck: Deck
    mutations: int = Field(default=25, ge=1, le=200)
    screening_duels: int = Field(default=100, ge=10, le=1000)


class RefineResult(BaseModel):
    deck: Deck
    swaps: list[Swap]
    accepted: int
    win_rate: float
    fidelity: Fidelity = Fidelity.SCREENING
    live: bool


class Progress(BaseModel):
    step: int = 0
    total: int = 0
    message: str = ""


class Job(BaseModel):
    id: str
    kind: JobKind
    state: JobState
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    queue_position: int | None = None
    progress: Progress = Progress()
    params: dict = {}
    result: dict | None = None
    error: str | None = None


class SubmitRefine(BaseModel):
    """A refine submission. Omit the deck to get a random legal one from the pool."""

    deck: Deck | None = None
    mutations: int = Field(default=25, ge=1, le=200)
    screening_duels: int = Field(default=100, ge=10, le=1000)


class Health(BaseModel):
    status: str
    live: bool
    executor: str
    pool_size: int
    version: str
