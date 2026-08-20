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
| 2 ✓ | Interests: the Constraint form that drives a build | Ask for a themed deck under a card-count cap; get a legal deck that respects it. Ask for a Cyberse one and get the reason no deck can be built | #4 | 1 |
| 3 ✓ | Refine job: submit, queue position, live progress, result | Submit a deck, watch swap-by-swap progress, see the final diff and which cards changed | #6, #7 | 2 |
| 4 ✓ | Test job: Gate evaluation vs the Gauntlet | Run a test, get a win rate with its matchup breakdown, labelled Gate fidelity | #3, #8 | 1.5 |
| 5 ✓ | Deck library: save, name, version, compare | Save two decks, diff them, see each one's last Gate result | - | 1.5 |
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
   Slice 2 makes this visible rather than hiding it — a build is a uniform draw inside the mask,
   and the Interests panel says as much on screen.

## Open questions

- **Hosting.** The duel farm is the Linux box; it is not a server. Slice 8 needs a decision on
  whether the API runs on that box or on a small VPS that dispatches to it.
- **What a user sees while a job runs.** Screening win rates are noisy by design (+/-4-6 points,
  ADR-0003). Showing them live is honest but will read as the deck getting worse half the time.
- **An interest is a card count, not an archetype.** "A Labrynth deck" is a set of named cards
  a human recognises; a Constraint can only say "at least 20 Fiends". Archetype membership is in
  the card text (`desc`) and in nothing structured the index carries, so naming one would mean
  matching strings in card names. Worth revisiting once users say which they meant.
- **One shelf, no owners.** The deck library is a single shared list because there
  is no auth until slice 8. At five to twenty known users that is a feature -- the
  beta can look at each other's decks -- and it is also how someone deletes a deck
  they did not save. Whether the shelf becomes per-user or stays shared with
  attribution is the same decision as accounts.
- **Name matching is exact, not fuzzy.** Slice 1 folds accents, quote styles and spacing, but a
  misspelling still resolves to nothing. Good enough while the paste box is mostly `.ydk`; a
  typo-tolerant matcher is worth revisiting if users type more than they paste.

## Status

**Slices 0 to 5 are done. Slice 6 is done against the fake executor.**

### Slice 5 -- the deck library: save, name, version, compare

The manual test passes: two decks are saved, the library diffs them card for card
(4 out, 4 in, 36 unchanged), and each one carries the last Gate result that measured
it -- 52.6% +/-4.4 against 58.6% +/-4.3, six points apart and reported as *not* a
difference, because two 500-duel measurements earn a +/-6.1 band between them.

Until this slice a deck was the contents of a text box: one deck in `localStorage`,
kept across a reload, and every deck before it gone. `api/.../library.py` is the
whole slice, and three decisions carry it.

- **The name is the identity.** Saving under a name the library already holds adds a
  version to that deck, matched case-insensitively -- someone who typed "shaddoll"
  today and "Shaddoll" last week meant one deck both times. There is no second
  "Shaddoll" and no rename-to-fork.
- **A version is immutable, and content-addressed.** Saving a list identical to the
  one already on the shelf writes nothing and says so: a version number records a
  change, not a click. Judged against the *newest* version and only that one, so A,
  then B, then A again is v1, v2, v3 -- folding the third save back onto v1 would be
  claiming the deck never went to B and came back.
- **A saved deck is joined to its Gate result by the decklist itself**, not by a
  stored pointer. This is the decision the slice is built on. A pointer would have to
  be written when the job was submitted, which would leave a deck saved *after* its
  own test with no result, and the same list saved twice with two disconnected
  histories. Matching on content instead means the ordinary order -- test a deck, like
  the number, then save it -- works, and it is the order a user will actually use.

That last one is why the library lives in the job database on the job store's
connection: its central query is a join against `jobs`. Only **test** jobs are
joined. A refine job also finishes with a win rate, but it is a Screening number
ADR-0003 forbids quoting, and attaching one to a saved deck would publish the number
the two fidelities have separate names to keep apart.

Four more things this slice decided:

- **A version carries two content addresses, because two questions are asked of it.**
  `fingerprint` covers the whole list and decides whether a save is a new version at
  all. `main_key` covers the main deck alone and is what a Gate result is matched on
  -- a job carries a main deck and nothing else (`Deck.main`), so a win rate cannot
  be attributed to an Extra Deck the executor was never handed. Two versions
  differing only in their Extra Deck therefore share a Gate result, and the
  comparison screen says as much rather than hiding it. It is also why the deck saved
  from a finished job saves 40 cards and no Extra Deck, with the caption saying why.
- **The comparison refuses to call the difference a Delta score.** A Delta score is a
  win rate difference between a deck and its own mutation under one Environment set,
  and it is sharp precisely because parent and child share 39 of 40 cards
  (CONTEXT.md). Two library decks were measured by two separate jobs, so what is on
  offer is the difference of two *absolute* win rates and the band on it is the two
  bands added in quadrature -- +/-6.2 points at 500 duels each. Most deck changes are
  smaller than that. The verdict (`separated`) is drawn as two bars standing on their
  bands on one scale, so overlapping bands are visible and not only stated.
- **A fake win rate is never compared with a real one.** Slice 7 swaps `FakeExecutor`
  for `YgoenvExecutor`, so one library will hold results from both. The comparison
  refuses that pair outright and names which side was fabricated, because the two
  differ by however much the fake felt like. Worth knowing today: the fake's win rate
  is a hash of the decklist, so two decks one card apart land 18 points apart and
  every comparison in the app currently says "separated". Real duels will not do that.
- **The shelf refuses nothing the queue would.** Legality gates the queue because an
  illegal deck kills the worker (#4); a shelf has no worker, and a 32-card deck
  someone is halfway through building is exactly what a library is for. A 61-card
  deck saves too. The lengths on the save body bound what a stray paste can write and
  are not the rulebook.

The diff is `refine.diff_codes` -- the refine job's own counting function, generalised
from decks to card lists so an Extra Deck can go through it -- and it is drawn by one
component shared with the duel farm. The library comparing two saved decks and the
farm comparing a refined deck against the one it was given now agree by construction
rather than by inspection.

Known gaps, deliberate. **The shelf is shared and unowned**: there is no auth yet
(slice 8), so the beta's users write to one library and can delete each other's decks.
**The Baseline comparison is still missing**: the Build gate is "beats the
Damaged-deck Baseline by >=15 points" (#8), and this slice can compare any two Gate
results but the API container ships no Damaged deck to compare against. Building one
needs a shipped Seed deck, which is slice 7's territory. And the library **reloads
rather than streams**: a finished test job changes what the shelf says without
anything on the shelf being touched, so the browser re-reads it when the count of
finished test jobs changes.

### Slice 4 -- the test job: Gate evaluation vs the Gauntlet

The manual test passes: a deck goes to the farm as a test, faces all ten Gauntlet
decks 50 duels each, and comes back at 66.2% +/-4.1 with the ten numbers that
average to it -- 80% into Sky Striker Ace, 56% into Chimera -- labelled `gate`.

`gate.py` is the whole job and it is deliberately thin: no mutations, no proposals,
no Masking, because a test has no pick to mask. What it adds over one call to
`executor.gate()` is the three things a queued job owes a user -- progress while it
runs, a place to stop, and a result that carries its own provenance.

The slice's real work was deciding what makes a number quotable, and then making the
code unable to publish one that is not:

- **The headline is summed out of the breakdown, never carried beside it.**
  `FakeExecutor` could trivially state both and let them drift; then the app would be
  showing ten rows nobody could check against the number above them. A test asserts
  `sum(wins) / sum(duels) == win_rate`.
- **500 duels is a floor, not a default.** `POST /api/jobs/test` refuses
  `gate_duels` below 500 with a 422. ADR-0003 gives the two fidelities separate names
  precisely so a Gate-labelled win rate cannot have been measured over a
  Screening-sized batch, and a knob a user can turn down to 100 would hand that back.
- **Every rate arrives with the band its duel count earns**, from one formula
  (`models.wald_margin`), as a computed field so it cannot be forgotten: +/-4.4 points
  at 500 duels, +/-13.9 at the 50 one matchup gets. That is why the breakdown is
  drawn as bars against the 50% line with the band behind each one, and why the panel
  says to read the ordering rather than the digits -- the band is wider than most of
  the bars.
- **Screening carries no breakdown at all.** At 100 duels a matchup row is ten
  duels, a +/-31 point band under a number ADR-0003 already forbids quoting. The seam
  returns `matchups: []` from `screen()` and says why.
- **The Gauntlet is shown in its fixed order**, not sorted best-to-worst. It is fixed
  within a phase so two decks' rows line up (CONTEXT.md); re-sorting per deck would
  spend that to make one column look tidier.

Three smaller decisions:

- **Each opponent's duels are split 50/50 on the play and on the draw**, and the row
  carries both. ADR-0004 forces the seat, and in Master Duel Bo1 the seat is often
  worth more than the decklist -- one averaged number would hide a deck that only
  wins going first.
- **A test job stops between matchups and nowhere else.** That is not a shortcut: a
  candidate deck may only be swapped at a batch boundary (ADR-0004), so "stop now"
  has to mean "stop after this matchup" or it means racing the core. The seam's
  `on_matchup` hook is the same boundary the progress line is written on.
- **One submit panel, two kinds.** The deck, the interests and the legality that
  decide whether anything may be queued are identical for a refine and a test, so
  `_deck_to_run` in `main.py` is the one place both refusals live -- an illegal deck
  and an unsatisfiable Constraint -- and the panel switches only the fidelity and its
  knobs. A test job keeps the Constraint as the record of what the deck was asked to
  be, and the caption says so rather than repeating the refine job's "masked into
  every swap", which for a test would be a lie.

Known gaps, deliberate: **a test job is not checkpointed.** A restart re-runs its
duels, because there is no half of one win rate worth keeping -- but a cancelled test
therefore keeps only its last progress line, not the matchups it did finish. And it
reports **no Baseline comparison**: the Build gate is "beats the Damaged-deck
Baseline by >=15 points" (#8), which needs a Damaged deck built from a shipped Seed
deck the API container does not carry. Slice 5's library compares two Gate results
and is still missing the one deck worth comparing against.

### Slice 3 -- the refine job, watched while it runs

The manual test passes: a pasted deck goes to the farm, the swap log fills in
mutation by mutation while the job runs, and the finished job says which cards
changed.

One thing carries the slice: **the checkpoint**. After every mutation the worker
writes what it has -- the best deck so far, its win rate, every swap tried, and the
diff against the deck that was submitted -- in the same statement that writes
progress, so the two can never disagree. Two readers want exactly that record, and
before this slice each would have got its own half-answer:

- **The browser**, which now shows the swap log building up instead of a bar that
  turns into 30 mutations when the job ends.
- **The worker after a restart**, which resumes at the mutation it reached. Slice 0
  left this as a known gap: the job was never lost, but the swaps it had already
  paid for were. Resuming is safe because a mutation is a pure function of the deck
  and the step number -- the job re-derives the swap it was about to make and carries
  on, rather than re-running the ones a user already watched.

Four more things this slice decided:

- **A diff is not a swap log.** `RefineResult` carries the deck that was submitted
  beside the final one, and the diff between them: 30 mutations, 4 accepted, and 4
  cards changed is the common shape, but a card cut at step 3 and picked back up at
  step 17 is two swaps and no change. The log says what was *tried*; the diff says
  what a user takes away. Both are on screen and they are labelled as the different
  things they are.
- **A result supersedes the checkpoint that built it**; a cancelled or failed job
  keeps its checkpoint, because that is the only record of the work that did happen.
- **`GET /api/jobs` is summaries now.** It is polled every 700 ms and a refine result
  holds six full duel logs, so the list carries where each job stands and nothing it
  carries; `GET /api/jobs/{id}` carries the params, the checkpoint and the result,
  and is polled only for the one job on screen -- and stops the moment that job is
  finished. The replay picker still knows which jobs are watchable because the kept
  duels are counted in SQL (`json_array_length`), so no log crosses the wire to draw
  a list of ids.
- **The job database migrates in place.** `make down` keeps the volume on purpose,
  so the file a user has is older than the code reading it, and
  `CREATE TABLE IF NOT EXISTS` will not add a column to a table that exists. A
  checkpoint written by an older build that no longer validates is not a reason to
  fail a job: the job starts over, which is exactly where this app was before
  checkpoints existed.

Progress messages name cards now (`Mutation 9/40: rejected Shaddoll Dragon -> Prayers
of the Voiceless Voice`) rather than passcodes. A line a person reads should be
readable by that person.

Still deliberately polled, not streamed. At beta scale, with the payload split off
the list, 700 ms costs one small row per job and the checkpoint of the single job
being watched.

### Slice 2 -- Interests, the Constraint that drives a build

The manual test passes, in the form the pool allowed it to: asking for 20+
Spellcasters in 40 cards with at most 4 Traps builds a legal deck that holds them.
Asking for a **Cyberse** deck -- the wording in the row above, before the pool was
counted -- is refused, with the reason.

`api/.../constraints.py` is the whole slice. One function, `action_space`, answers
"what may be picked into this deck" for the three callers that must not disagree: the
Masking preview the editor shows, deck construction, and every swap a refine job
proposes. A preview that counted picks the Builder would not make would be a lie
told in a screenshot.

- A **Constraint** is `main_size` plus up to 8 clauses, each a bound (`at least` /
  `at most`), a count, and a facet value: race, attribute, card type or subtype.
  `GET /api/constraints/facets` lists every value with the ceiling the pool sets on
  it, so the form offers only what exists and says how much of it there is.
- `POST /api/decks/build` constructs under a Constraint and answers with the same
  `DeckReport` a paste gets, so one screen renders both. `POST /api/decks/parse` and
  `POST /api/jobs/refine` both take a Constraint too.
- **A Constraint never makes a deck illegal.** `legal` stays a statement about the
  rules, because that is the field that decides whether the queue may see the deck.
  Conformance is reported beside it and stops nothing.
- **`main_size` is optional.** A user who never chose 40 is not told their 42-card
  deck is the wrong size; legality's 40-to-60 already holds and already reports.

Three facts this slice surfaced:

- **The pool can build no Cyberse deck.** It knows 34 Cyberse cards and every one is
  a Token or an Extra Deck monster -- 14 Link monsters, 4 Synchros, 16 Tokens, zero
  main-deck cards. The slice's own manual test asked for the one archetype the Pilot cannot be
  handed, which is the pool being the Pilot's *vocabulary* rather than a list of
  buildable cards, arriving as a product problem. So an unsatisfiable Constraint is
  refused at the door with its ceiling spelled out ("the pool can supply at most 0
  such copies to a main deck"), like an illegal deck and for the same reason: there
  is no work to queue.
- **The floor has to be paid first, or a cap steals its slots.** Draw filler first
  under "at least 20 Spellcasters, at most 22 monsters" and 22 non-Spellcaster
  monsters can land before the floor is touched, leaving a perfectly satisfiable
  Constraint unsatisfiable. Construction pays floors first and the at-least mask --
  when the empty slots run down to the cards still owed, nothing else may be picked
  -- makes a feasible minimum hold by construction rather than by luck.
- **A refine job pulls toward a Constraint without promising to arrive.** Masking
  decides what may be *proposed*; the Delta score decides what is *kept*. Every
  masked swap pays down an unmet floor, but only accepted swaps land, so a
  non-conformant deck moves toward the Constraint at the pace the win rate allows.
  Building under the Constraint is the only thing that guarantees it, and the submit
  panel says so rather than implying the job will fix it.

### The interface: a deck editor, not a form

The app was a form with a paste box beside a job list. It is now three surfaces built
the way the clients these users already have are built (EDOPro, MDPro3, Master Duel):

- **Deck** -- a left card inspector carrying the printed card text, a centre grid of
  card art with one slot per copy, and a right card browser with the filter strip.
  Cards are added and removed by clicking; the `.ydk` text is still the deck's one
  definition and is still parsed server-side, so a visual edit rewrites the text
  rather than forking a second answer to "what is in this deck".
- **Duel farm** -- the queue and one job, with each mutation drawn as the two cards it
  traded rather than as two passcodes, above the interests the job ran under: a
  result read months later has to say what it was asked for, or the deck cannot be
  explained.
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

145 tests in `api/tests/`, including every slice's manual test.

Running it:

```
make up          # build and start both containers -> http://localhost:8080
make down        # stop, keeping every queued and finished job
make clean       # stop and delete the job database volume
make test        # the 145 tests, inside the API image
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

- ~~**Restart recovery re-runs a job from the start.**~~ Closed by slice 3: the worker
  checkpoints after every mutation and resumes from it.
- **Progress is polled at 700 ms**, not streamed. Still true after slice 3, which
  split the payload off the polled list instead. Fine at beta scale.
- **Side decks are parsed and then dropped.** Phase 1 has no use for one.
- **No auth.** Slice 8.

`data/pilot-864/cards.json` is committed, so nothing above needs the network.
`python tools/gen_card_index.py --check` re-derives it from its two pinned sources and
fails if the committed copy is stale; it downloads them, so it is not part of the test
run.
