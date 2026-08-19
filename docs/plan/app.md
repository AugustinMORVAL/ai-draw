# The app: build plan

A user-facing app where people describe the deck they want, get one built, and have the Builder
refine it against simulated duels. Built slice by slice, each slice manually testable the day it
lands. Decisions in [ADR-0005](../adr/0005-app-is-a-queued-job-service.md).

**Audience:** private beta, ~5-20 known users, shared key. No open signups before phase 2.
**Stack:** FastAPI (`api/`) + React / Vite / Tailwind / shadcn (`ui/`).
**Method:** every slice ships behind the `DuelExecutor` interface with a fake implementation, so
the app is finished and clickable before `vendor/ygo-agent` is wired in.

## The seam

```
ui/  React            ->  api/  FastAPI  ->  DuelExecutor (Protocol)
                              |                 |- FakeExecutor    <- every slice is built on this
                              |                 '- YgoenvExecutor  <- lands with Stage 1 (#3)
                              '- JobQueue (single-slot, durable)
```

One interface, two implementations. The UI never learns which one it is talking to, except
through a `live: true|false` flag it displays in the header so no screenshot is ambiguous.

## Slices

Each slice is done when its manual test passes by hand in a browser. Estimates are working days.

| # | Slice | Manual test | Backs issue | Est. |
| --- | --- | --- | --- | --- |
| 0 ✓ | Shell, seam, fake executor, durable job queue | Submit a fake refine job; watch it queue, run, finish; reload the page mid-job and it is still there | - | 1 |
| 1 ✓ | Deck input: paste a decklist, card search, legality + Masking preview | Paste a deck with 4 copies of a card and an out-of-pool card; both are flagged with reasons | #4 | 1.5 |
| 2 | Interests: the Constraint form that drives a build | Ask for a Cyberse deck under a card-count cap; get a legal deck that respects it | #4 | 1 |
| 3 | Refine job: submit, queue position, live progress, result | Submit a deck, watch swap-by-swap progress, see the final diff and which cards changed | #6, #7 | 2 |
| 4 | Test job: Gate evaluation vs the Gauntlet | Run a test, get a win rate with its matchup breakdown, labelled Gate fidelity | #3, #8 | 1.5 |
| 5 | Deck library: save, name, version, compare | Save two decks, diff them, see each one's last Gate result | - | 1.5 |
| 6 ~ | Duel replay: watch one duel the deck played | Open a duel from a refine result, step through the action log | #3 | 2 |
| 7 | Real executor: swap `FakeExecutor` for `YgoenvExecutor` | Every slice above still passes its manual test, now against real duels | #3 | 1.5 |
| 8 | Beta hardening: shared-key access, rate limit, queue fairness | Two users submit at once; both see honest queue positions | - | 1 |

Slices 0-6 are frontend-and-fake work and do not touch the phase-1 critical path. Slice 7 is the
join, and it cannot start before Stage 1 (#3) lands.

## What gates a public launch

Neither is app work; both are already on the roadmap — see [phases.md](phases.md) for the reasoning
behind each phase.

1. **Phase 2 — the 2026 card pool.** Today: 864 cards from the frozen Pilot checkpoint. Users
   will search for cards that do not exist in it. ADR-0001 calls this a C++ diff two years wide.
2. **Phase 3 — Conditioning.** Until then, a user's stated interest is enforced by Masking only:
   the deck is legal and respects the Constraint, but the Builder was not steered toward it. The
   quality gap between "filtered" and "intended" is the difference between a demo and a product.

## Open questions

- **Hosting.** The duel farm is the Linux box; it is not a server. Slice 8 needs a decision on
  whether the API runs on that box or on a small VPS that dispatches to it.
- **What a user sees while a job runs.** Screening win rates are noisy by design (+/-4-6 points,
  ADR-0003). Showing them live is honest but will read as the deck getting worse half the time.
- **Name matching is exact, not fuzzy.** Slice 1 folds accents, quote styles and spacing, but a
  misspelling still resolves to nothing. Good enough while the paste box is mostly `.ydk`; a
  typo-tolerant matcher is worth revisiting if users type more than they paste.

## Status

**Slices 0 and 1 are done. Slice 6 is done against the fake executor.**

### The interface: a deck editor, not a form

The app was a form with a paste box beside a job list. It is now three surfaces built
the way the clients these users already have are built (EDOPro, MDPro3, Master Duel):

- **Deck** -- a left card inspector carrying the printed card text, a centre grid of
  card art with one slot per copy, and a right card browser with the filter strip.
  Cards are added and removed by clicking; the `.ydk` text is still the deck's one
  definition and is still parsed server-side, so a visual edit rewrites the text
  rather than forking a second answer to "what is in this deck".
- **Duel farm** -- the queue and one job, with each mutation drawn as the two cards it
  traded rather than as two passcodes.
- **Replays** -- the duel mat, life point bars, a transport, and the action log. All
  four read from a single index into the log, so they cannot disagree.

Two things carry the look, and both are honest about where they come from:

- **Card art is fetched by the browser** from `images.ygoprodeck.com`, falling back to
  the mycard host and then to a frame-coloured plate with the card's name on it. The
  API never touches the network and neither do the tests; a box with no egress runs
  the whole app on plates.
- **Card text is now in the index.** `tools/gen_card_index.py` reads `texts.desc` out
  of the same pinned `cards.cdb`, for pool cards only (`cards.json` grows 670 KB to
  928 KB). Carrying it for all 12,384 known cards would quadruple the file to buy
  nothing: the inspector never opens a card the Pilot cannot see.

Fonts are self-hosted in `ui/public/fonts` (92 KB), so the container needs no CDN.

### Slice 6 -- duel replay, on the fake executor

`DuelExecutor` grew one method, `replays(deck, count)`, and `FakeExecutor` implements
it by writing a duel log out of the deck's own cards: real passcodes, real Gauntlet
opponent names, life points that only fall and that reach zero on the turn the winner
takes. It is fabricated, it says so on every replay (`live: false`) and in a banner
above the mat, and `YgoenvExecutor` will implement the same method against real duels.

- A refine job keeps `REPLAY_SAMPLE = 6` duels of its *final* deck, in its result.
  Sampled, never complete: a refine job screens thousands and storing every log would
  dwarf the job database.
- `GET /api/jobs/{id}/replays` lists them without logs; `/{index}` returns one with
  its log. A job that has not finished answers 409, not an empty list.
- `GET /api/pool` returns all 864 cards in one response, so the editor filters
  locally instead of asking the server on every keystroke. Cards *outside* the pool
  stay a server question: `/api/cards?q=` still answers it, and still answers with the
  card marked rather than missing.

### One bug this slice found

**A four-digit passcode could not be pasted.** `_CODE` in `decklist.py` required five
to nine digits, and "Labrynth Cooclock" is code `2511`. A `.ydk` carrying it came back
one card short, with "no card is named '2511'" against it -- and Labrynth is one of the
33 decks the executor ships with. The floor is gone. It also made
`test_the_random_deck_the_app_submits_is_legal` fail about one run in twelve, which is
how it surfaced.

### Slice 1 — deck input, legality, Masking preview

The manual test passes: pasting a deck with 4 copies of a card and an out-of-pool card
flags both, each with a sentence saying which rule and why.

- `data/pilot-864/cards.json` — the card index, generated by `tools/gen_card_index.py`
  from the same pinned `cards.cdb` the ygoenv build fetches, plus `lflist.conf`. Three
  tiers, matching the domain: the 864 **supported pool** with full metadata; the other
  12,384 cards the C++ core knows but the Pilot cannot see, name only; and 225 alt-art
  aliases that fold onto the printing the index carries.
- `api/.../cards.py`, `decklist.py`, `legality.py` — the index, the paste-box parser
  (`.ydk` and typed names with counts), and the legality + Masking engine.
- `GET /api/cards?q=`, `GET /api/cards/{code}`, `POST /api/decks/parse`.
- `POST /api/jobs/refine` now refuses an illegal deck with 422 and the same report the
  UI shows. `ygopro-core` kills the process on a malformed deck rather than refusing
  it (#4), so the queue must never see one.
- `ui/` — paste box, card search, per-card flags with reasons, and the Masking preview.

Two facts this slice surfaced, both load-bearing:

- **Only 411 of the 864 pool cards are main-deck cards** — 232 are Tokens and 221 are
  Extra Deck monsters. The pool is the Pilot's *vocabulary*, not a list of buildable
  cards. 408 remain once the banlist takes three. `random_deck()` was drawing from all
  864, which would have handed the real executor a deck containing Tokens; it now draws
  from the 408, and so does the swap proposer.
- **The banlist is 2024.7**, the OCG list in force when the Pilot's pool was frozen
  (upstream last pushed 2024-08-16, ADR-0001) — not today's. Judging a 2024 pool against
  a 2026 list would forbid cards these decks were built to play. The list name is in
  `cards.json`, in `/api/health`, and on screen, so it is never ambiguous. One constant
  in `tools/gen_card_index.py` changes it.

The 33 decks the executor ships with are the fixture: `Shaddoll.ydk` parses to 42 main
and 14 extra, and comes back legal. If our rules reject a deck a human built for this
exact pool, our rules are wrong.

### Slice 0 — shell, seam, fake executor, durable queue

- `api/src/ai_draw_api/executor.py` — the `DuelExecutor` Protocol and `FakeExecutor`. Every
  evaluation returns a win rate *and* its fidelity; the fake is `live = False` and says so.
- `api/src/ai_draw_api/store.py` — the durable single-slot queue over SQLite. Jobs survive the
  tab and the process; `recover_orphans()` re-queues anything left RUNNING by a crash.
- `api/src/ai_draw_api/refine.py` — the refine job. The swap proposer is a stand-in, not the
  Builder: it picks by hash, keeps positive Deltas, and never breaks legality.
- `api/src/ai_draw_api/main.py` — the job endpoints and `GET /api/health`.
- `ui/` — Tailwind v4 shell: the `live: false` header badge, the job list with honest queue
  positions, and a job view with progress and the swap log.

62 tests in `api/tests/`, including both slices' manual tests.

Running it:

```
make up          # build and start both containers -> http://localhost:8080
make down        # stop, keeping every queued and finished job
make clean       # stop and delete the job database volume
make test        # the 62 tests, inside the API image
```

`make up` publishes the UI on 8080 and the API on 8000; both are overridable
(`make up UI_PORT=3000`). nginx serves the built bundle and proxies `/api` to the API
container, so the browser talks to one origin. The job database is a named volume:
`down` keeps it, `clean` is the only thing that throws it away.

For hot reload, run the two halves on the host instead:

```
cd api && uv venv && uv pip install -e ".[dev]" && .venv/bin/python -m pytest
.venv/bin/python -m uvicorn ai_draw_api.main:app --port 8000 --reload
cd ui && npm install && npm run dev      # http://localhost:5173, proxies /api to :8000
```

Known gaps, deliberately left for later slices:

- **Restart recovery re-runs a job from the start.** The job is never lost, but the swaps it had
  already made are. Checkpointing per swap belongs with slice 3's progress work.
- **Progress is polled at 700 ms**, not streamed. Fine at beta scale; slice 3 can revisit.
- **Side decks are parsed and then dropped.** Phase 1 has no use for one.
- **No auth.** Slice 8.

`data/pilot-864/cards.json` is committed, so nothing above needs the network.
`python tools/gen_card_index.py --check` re-derives it from its two pinned sources and
fails if the committed copy is stale; it downloads them, so it is not part of the test
run.
