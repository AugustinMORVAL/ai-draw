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
    #: The printed card text. Pool cards only: the inspector never opens a card the
    #: Pilot cannot see, so the other 12,384 are carried by name alone.
    desc: str | None = None


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
    #: Only when the caller asked for one. Legality is always judged; a Constraint
    #: exists only because a user wrote it.
    constraint: ConstraintReport | None = None
    main_count: int = 0
    extra_count: int = 0


class ConstraintFacet(str, Enum):
    """Which property of a card a Constraint clause counts."""

    RACE = "race"
    ATTRIBUTE = "attribute"
    KIND = "kind"
    SUBTYPE = "subtype"


class Bound(str, Enum):
    """A floor or a ceiling. A Constraint clause is always one of the two."""

    AT_LEAST = "at_least"
    AT_MOST = "at_most"


class ConstraintClause(BaseModel):
    """One counted restriction: "at least 20 cards whose race is Spellcaster"."""

    facet: ConstraintFacet
    value: str = Field(min_length=1, max_length=48)
    bound: Bound
    count: int = Field(ge=0, le=60)


class Constraint(BaseModel):
    """What the user asked for, and may drop. Legality is neither (CONTEXT.md).

    `main_size` is the card-count cap: legality permits 40 to 60 and says nothing
    about which, so choosing is the user's, not the rulebook's. `None` means the
    user did not choose -- a 42-card deck is then not flagged for being 42, because
    nobody asked for 40.
    """

    main_size: int | None = Field(default=None, ge=40, le=60)
    clauses: list[ConstraintClause] = Field(default_factory=list, max_length=8)


class ConstraintIssue(str, Enum):
    """Why a Constraint is not met, or cannot be."""

    #: No legal deck satisfies it. Nothing to build, so nothing is queued.
    IMPOSSIBLE = "impossible"
    UNMET_MINIMUM = "unmet_minimum"
    OVER_MAXIMUM = "over_maximum"
    WRONG_SIZE = "wrong_size"


class ConstraintFlag(BaseModel):
    """One way this deck, or this Constraint, falls short. With the sentence."""

    issue: ConstraintIssue
    reason: str
    clause: ConstraintClause | None = None


class ClauseStatus(BaseModel):
    """One clause, against this deck and against what the pool can supply."""

    clause: ConstraintClause
    held: int
    satisfied: bool
    #: The most copies the supported pool could ever supply for this clause, the
    #: banlist included. A floor above it is a Constraint no deck can satisfy.
    ceiling: int


class ConstraintReport(BaseModel):
    """Whether a deck respects what was asked for, kept apart from Legality.

    A Constraint violation never makes a deck illegal: an illegal deck aborts
    `ygopro-core`, an unmet Constraint is just not what the user wanted. Both are
    reported, and only one of them stops a job.
    """

    constraint: Constraint
    #: False when no legal deck could satisfy it -- the pool's fault, not the deck's.
    feasible: bool
    satisfied: bool
    clauses: list[ClauseStatus] = []
    flags: list[ConstraintFlag] = []


class FacetValue(BaseModel):
    """One value a clause may name, with the ceiling the supported pool sets."""

    facet: ConstraintFacet
    value: str
    #: Main-deck pool cards carrying this value, and the copies they add up to.
    cards: int
    copies: int
    #: Pool cards with this value that no main deck can hold -- Tokens and Extra
    #: Deck monsters. This is why a pool can know 34 Cyberse cards and still build
    #: no Cyberse deck: the Pilot recognises them, a main deck cannot play them.
    elsewhere: int


class Facets(BaseModel):
    """Every value a Constraint can be written against, with its ceiling."""

    main_deck_pool_size: int
    values: list[FacetValue] = []


class BuildDeck(BaseModel):
    """Ask for a deck built under a Constraint. Masking, not Conditioning."""

    constraint: Constraint
    #: Fixes the draw, so a build can be shown to someone else and reproduced.
    seed: int | None = None


class ParseDeck(BaseModel):
    """A pasted decklist: `.ydk` codes, or names one per line with counts."""

    text: str = Field(max_length=100_000)
    #: Judged against this too, when given. Legality and Constraint are reported
    #: side by side and never merged into one verdict.
    constraint: Constraint | None = None


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
    #: Every swap is masked to this, so the deck respects it at every step and not
    #: only at the end. Until Conditioning (phase 3) this is the whole of "the
    #: Builder built what I asked for" (ADR-0005).
    constraint: Constraint | None = None


class RefineResult(BaseModel):
    deck: Deck
    swaps: list[Swap]
    accepted: int
    win_rate: float
    fidelity: Fidelity = Fidelity.SCREENING
    live: bool
    #: A sample of the duels the *final* deck played, kept so the run can be watched
    #: rather than only counted. Sampled, not complete: a refine job screens
    #: thousands of duels and storing every log would dwarf the job database.
    replays: list["DuelReplay"] = []


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
    #: Masks every swap, and builds the deck when none was given.
    constraint: Constraint | None = None


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


class DuelSeat(str, Enum):
    """Who did something. The candidate deck always sits in `CANDIDATE`."""

    CANDIDATE = "candidate"
    OPPONENT = "opponent"


class DuelPhase(str, Enum):
    DRAW = "draw"
    STANDBY = "standby"
    MAIN1 = "main1"
    BATTLE = "battle"
    MAIN2 = "main2"
    END = "end"


class DuelEvent(BaseModel):
    """One step of a duel, as the replay viewer walks it.

    `life_candidate` / `life_opponent` are the totals *after* the event, so a viewer
    scrubbing to any index can paint the board without replaying from zero.
    """

    index: int
    turn: int
    seat: DuelSeat
    phase: DuelPhase
    action: str
    card: int | None = None
    target: int | None = None
    text: str
    life_candidate: int
    life_opponent: int


class DuelReplaySummary(BaseModel):
    """A duel, without its events. What the replay list shows."""

    index: int
    opponent: str
    going_first: DuelSeat
    winner: DuelSeat
    turns: int
    events: int
    live: bool


class DuelReplay(DuelReplaySummary):
    """A duel with its full action log."""

    log: list[DuelEvent] = []
