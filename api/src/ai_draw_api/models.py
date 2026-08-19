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


class CardSection(str, Enum):
    """Where a card may be put. A Token may be put nowhere -- it is only ever made."""

    MAIN = "main"
    EXTRA = "extra"
    TOKEN = "token"


class Card(BaseModel):
    """One card, as the app shows it. `in_pool` is stated, never inferred."""

    code: int
    name: str
    kind: str
    subtypes: list[str] = []
    section: CardSection
    race: str | None = None
    attribute: str | None = None
    level: int | None = None
    atk: int | None = None
    defense: int | None = None
    limit: int = 3
    in_pool: bool


class CardIssue(str, Enum):
    """Why one card in a pasted deck cannot be built with."""

    UNKNOWN_CARD = "unknown_card"
    NOT_IN_POOL = "not_in_pool"
    FORBIDDEN = "forbidden"
    OVER_LIMIT = "over_limit"
    TOKEN = "token"
    WRONG_SECTION = "wrong_section"


class DeckIssue(str, Enum):
    """Why the deck as a whole cannot be built with."""

    MAIN_TOO_SMALL = "main_too_small"
    MAIN_TOO_LARGE = "main_too_large"
    EXTRA_TOO_LARGE = "extra_too_large"
    NOTHING_PARSED = "nothing_parsed"


class CardFlag(BaseModel):
    """One card's problem, with the sentence a user should read."""

    code: int
    name: str | None
    count: int
    section: CardSection
    issue: CardIssue
    reason: str
    limit: int | None = None


class DeckFlag(BaseModel):
    issue: DeckIssue
    reason: str


class UnresolvedLine(BaseModel):
    """A pasted line that named no card at all."""

    line: int
    text: str
    reason: str


class DeckEntry(BaseModel):
    """One distinct card in the pasted deck, with its count."""

    card: Card
    count: int
    section: CardSection


class MaskedGroup(BaseModel):
    reason: str
    count: int


class MaskPreview(BaseModel):
    """What the Builder could still pick, given this deck.

    Masking is hard enforcement: an illegal pick is removed from the action space,
    so an illegal deck is unrepresentable rather than rejected (CONTEXT.md). This is
    that same mask, counted, so a user can see the Builder's real room to move.
    """

    pool_size: int
    legal_picks: int
    masked: list[MaskedGroup]


class DeckReport(BaseModel):
    """Everything the app knows about a pasted decklist."""

    deck: Deck | None
    extra: list[int] = []
    legal: bool
    banlist: str
    entries: list[DeckEntry] = []
    flags: list[CardFlag] = []
    deck_flags: list[DeckFlag] = []
    unresolved: list[UnresolvedLine] = []
    mask: MaskPreview
    main_count: int = 0
    extra_count: int = 0


class ParseDeck(BaseModel):
    """A pasted decklist: `.ydk` codes, or names one per line with counts."""

    text: str = Field(max_length=100_000)


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
    #: Of the pool, how many are main-deck cards. The rest are Tokens and Extra Deck
    #: monsters the Pilot must recognise but no deck can be built from.
    main_deck_pool_size: int
    banlist: str
    version: str
