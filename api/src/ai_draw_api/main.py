"""FastAPI app: submit a job, watch the queue, read the result."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from . import constraints
from .cards import card_index
from .decklist import ParsedDeck
from .decklist import parse as parse_decklist
from .executor import DuelExecutor, FakeExecutor
from .legality import review
from .library import DeckLibrary, compare
from .models import (
    BuildDeck,
    Card,
    CompareDecks,
    Constraint,
    ConstraintReport,
    Deck,
    DeckComparison,
    DeckReport,
    DeckSave,
    DeckSaved,
    Facets,
    DuelReplay,
    DuelReplaySummary,
    Health,
    Job,
    JobKind,
    JobSummary,
    LibraryDeck,
    ParseDeck,
    RefineParams,
    SubmitRefine,
    SubmitTest,
    GateParams,
)
from .pool import supported_pool
from .store import JobStore
from .worker import Worker

DEFAULT_DB = Path(__file__).resolve().parents[2] / "var" / "jobs.db"

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _impossible_detail(
    constraint: Constraint, impossible: constraints.Impossible
) -> ConstraintReport:
    """A 422 body for a Constraint no deck can satisfy, carrying its sentences.

    Shaped like the report the form already renders, so the UI shows the reasons in
    the place the user was reading rather than a wall of JSON.
    """
    return ConstraintReport(
        constraint=constraint, feasible=False, satisfied=False, flags=impossible.flags
    )


def _deck_to_run(
    deck: Deck | None, constraint: Constraint | None
) -> Deck:
    """The deck a job will run on: the one submitted, or one built to order.

    Every refusal a submission can meet is here, so a refine job and a test job
    refuse the same things for the same reasons and with the same body -- the report
    the deck editor was already showing, rather than a wall of JSON:

    - **An illegal deck** is refused at the door because `ygopro-core` aborts the
      process on a malformed deck rather than rejecting it (#4). The queue never
      sees one.
    - **An unsatisfiable Constraint** is refused when there is no deck yet, because
      there is then nothing to build and so no work to queue. A satisfiable one the
      submitted deck does not meet is not refused: a refine job's masked swaps pull
      toward it, and a test job only records what was asked for.
    """
    index = card_index()
    if deck is None:
        if constraint is None:
            return constraints.random_deck()
        try:
            return constraints.construct(index, constraint)
        except constraints.Impossible as impossible:
            raise HTTPException(
                status_code=422,
                detail=_impossible_detail(constraint, impossible).model_dump(
                    mode="json"
                ),
            ) from impossible

    report = review(ParsedDeck(main=list(deck.main)), index, constraint)
    if not report.legal:
        raise HTTPException(status_code=422, detail=report.model_dump(mode="json"))
    return deck


def create_app(
    *, store: JobStore | None = None, executor: DuelExecutor | None = None
) -> FastAPI:
    store = store or JobStore(os.environ.get("AI_DRAW_DB", DEFAULT_DB))
    executor = executor or FakeExecutor()
    worker = Worker(store, executor)
    # The library rides on the job store's connection: it joins against `jobs` to
    # find the Gate result that measured a saved deck (see `library.py`).
    library = DeckLibrary(store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await store.open()
        await library.open()
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
    app.state.library = library

    @app.get("/api/health", response_model=Health)
    async def health() -> Health:
        index = card_index()
        return Health(
            status="ok",
            live=executor.live,
            executor=executor.name,
            pool_size=len(supported_pool()),
            main_deck_pool_size=len(index.main_deck_codes()),
            banlist=index.banlist,
            version=__version__,
        )

    @app.get("/api/cards", response_model=list[Card])
    async def search_cards(
        q: str, limit: int = 20, unsupported: bool = True
    ) -> list[Card]:
        """Name search. Cards outside the pool come back marked, not omitted."""
        return card_index().search(
            q, limit=min(max(limit, 1), 100), unsupported=unsupported
        )

    @app.get("/api/pool", response_model=list[Card])
    async def get_pool() -> list[Card]:
        """Every card the frozen Pilot can represent, in one response.

        The pool is 864 cards and it never changes at runtime, so the deck editor
        holds it and filters locally instead of asking the server on every keystroke.
        Cards *outside* the pool are still a server question: `/api/cards?q=` answers
        it, and answers it with the card marked rather than missing (ADR-0005).
        """
        return list(card_index().pool.values())

    @app.get("/api/cards/{code}", response_model=Card)
    async def get_card(code: int) -> Card:
        card = card_index().get(code)
        if card is None:
            raise HTTPException(status_code=404, detail=f"no card with code {code}")
        return card

    @app.get("/api/constraints/facets", response_model=Facets)
    async def constraint_facets() -> Facets:
        """Every value a Constraint may name, with the ceiling the pool sets on it.

        Values the pool knows but no main deck can hold come back at a ceiling of
        zero rather than being dropped, so a user asking for a Cyberse deck is told
        why the answer is no instead of facing an empty dropdown (ADR-0005).
        """
        return constraints.facets(card_index())

    @app.post("/api/decks/parse", response_model=DeckReport)
    async def parse_deck(body: ParseDeck) -> DeckReport:
        """Read a pasted decklist and say, card by card, what stands in its way."""
        index = card_index()
        return review(parse_decklist(body.text, index), index, body.constraint)

    @app.post("/api/decks/build", response_model=DeckReport)
    async def build_deck(body: BuildDeck) -> DeckReport:
        """Build a deck under a Constraint, and report it the way a paste is reported.

        The deck comes back inside a full `DeckReport`, so the screen that shows a
        built deck is the same screen that shows a pasted one -- legality, Masking
        preview and Constraint conformance all judged by the same code that will
        judge it again once the user has edited it.
        """
        index = card_index()
        try:
            deck = constraints.construct(index, body.constraint, seed=body.seed)
        except constraints.Impossible as impossible:
            raise HTTPException(
                status_code=422,
                detail=_impossible_detail(body.constraint, impossible).model_dump(
                    mode="json"
                ),
            ) from impossible
        return review(ParsedDeck(main=list(deck.main)), index, body.constraint)

    @app.post("/api/jobs/refine", response_model=Job, status_code=201)
    async def submit_refine(body: SubmitRefine) -> Job:
        """Mutate a deck, keeping the swaps that Screen better. Never quotable."""
        params = RefineParams(
            deck=_deck_to_run(body.deck, body.constraint),
            mutations=body.mutations,
            screening_duels=body.screening_duels,
            constraint=body.constraint,
        )
        return await store.enqueue(JobKind.REFINE, params.model_dump())

    @app.post("/api/jobs/test", response_model=Job, status_code=201)
    async def submit_test(body: SubmitTest) -> Job:
        """Gate-evaluate a deck against the Gauntlet.

        The one job whose number may be quoted (ADR-0003), which is why the floor on
        `gate_duels` is 500 and not the caller's to lower: a Gate-labelled win rate
        measured over a Screening-sized batch is precisely what two fidelities with
        two names exist to make impossible.
        """
        params = GateParams(
            deck=_deck_to_run(body.deck, body.constraint),
            gate_duels=body.gate_duels,
            constraint=body.constraint,
        )
        return await store.enqueue(JobKind.TEST, params.model_dump())

    @app.get("/api/jobs", response_model=list[JobSummary])
    async def list_jobs(limit: int = 50) -> list[JobSummary]:
        """The queue. Summaries only -- a job's payload is on the job itself.

        This is what the browser polls while a job runs, so it carries no decks, no
        results and no duel logs. `GET /api/jobs/{id}` carries all three, and is
        polled for the one job a user is actually watching.
        """
        return await store.list(limit=min(max(limit, 1), 200))

    @app.get("/api/jobs/{job_id}", response_model=Job)
    async def get_job(job_id: str) -> Job:
        """One job, whole: its params, its checkpoint, and its result if it has one.

        A running refine job answers with the checkpoint it last wrote, so the swap
        log on screen is the swap log the worker has actually made rather than a
        summary of it, and it builds up mutation by mutation instead of appearing
        all at once when the job ends.
        """
        job = await store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such job")
        return job

    async def _replays_of(job_id: str) -> list[dict]:
        """The duel logs a finished job kept. 404 if the job never got that far."""
        job = await store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such job")
        if job.result is None:
            raise HTTPException(
                status_code=409,
                detail=f"job is {job.state.value}, so it has no duels to replay yet",
            )
        return job.result.get("replays", [])

    @app.get("/api/jobs/{job_id}/replays", response_model=list[DuelReplaySummary])
    async def list_replays(job_id: str) -> list[DuelReplaySummary]:
        """The kept duels, without their logs. A sample, never every duel run."""
        return [DuelReplaySummary.model_validate(r) for r in await _replays_of(job_id)]

    @app.get("/api/jobs/{job_id}/replays/{index}", response_model=DuelReplay)
    async def get_replay(job_id: str, index: int) -> DuelReplay:
        replays = await _replays_of(job_id)
        match = next((r for r in replays if r["index"] == index), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"no replay {index} on this job")
        return DuelReplay.model_validate(match)

    @app.get("/api/library", response_model=list[LibraryDeck])
    async def get_library() -> list[LibraryDeck]:
        """Every saved deck, every version, with the Gate result each one carries.

        One response, like `/api/pool` and for the same kind of reason: the
        comparison picker needs every version to be pickable, and a list that left
        the Gate results out would send a user back for them one deck at a time.
        """
        return await library.list()

    @app.post("/api/library/decks", response_model=DeckSaved, status_code=201)
    async def save_deck(body: DeckSave) -> DeckSaved:
        """Put a decklist on the shelf under a name, as a new version if it is one.

        Unlike a job submission this refuses nothing. Legality gates the queue
        because an illegal deck kills the worker (#4); a shelf has no worker, and a
        32-card deck someone is halfway through building is exactly what a library
        is for. The answer says whether a version was actually written: saving an
        untouched deck twice leaves one version behind.
        """
        return await library.save(body.name, body.main, body.extra, body.note)

    @app.delete("/api/library/decks/{deck_id}", status_code=204)
    async def delete_deck(deck_id: str) -> None:
        """Forget a deck and all its versions. Its jobs, and their results, stay."""
        if not await library.delete(deck_id):
            raise HTTPException(status_code=404, detail="no such deck in the library")

    @app.post("/api/library/compare", response_model=DeckComparison)
    async def compare_decks(body: CompareDecks) -> DeckComparison:
        """Diff two saved versions, and compare the Gate results they carry.

        Both halves are answered here rather than in the browser for the same
        reason legality is: the diff is the refine job's diff function, and the
        verdict on two win rates is a statement about ADR-0003's bands. A second
        implementation in the UI would be a second answer to both.
        """
        try:
            return await compare(library, body.left, body.right)
        except KeyError as missing:
            raise HTTPException(
                status_code=404,
                detail=f"the library has no version {missing.args[0]}",
            ) from missing

    @app.post("/api/jobs/{job_id}/cancel", response_model=Job)
    async def cancel_job(job_id: str) -> Job:
        job = await store.request_cancel(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such job")
        return job

    return app


app = create_app()
