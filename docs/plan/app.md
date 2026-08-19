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
| 0 | Shell, seam, fake executor, durable job queue | Submit a fake refine job; watch it queue, run, finish; reload the page mid-job and it is still there | - | 1 |
| 1 | Deck input: paste a decklist, card search, legality + Masking preview | Paste a deck with 4 copies of a card and an out-of-pool card; both are flagged with reasons | #4 | 1.5 |
| 2 | Interests: the Constraint form that drives a build | Ask for a Cyberse deck under a card-count cap; get a legal deck that respects it | #4 | 1 |
| 3 | Refine job: submit, queue position, live progress, result | Submit a deck, watch swap-by-swap progress, see the final diff and which cards changed | #6, #7 | 2 |
| 4 | Test job: Gate evaluation vs the Gauntlet | Run a test, get a win rate with its matchup breakdown, labelled Gate fidelity | #3, #8 | 1.5 |
| 5 | Deck library: save, name, version, compare | Save two decks, diff them, see each one's last Gate result | - | 1.5 |
| 6 | Duel replay: watch one duel the deck played | Open a duel from a test result, step through the action log | #3 | 2 |
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
- **Deck import format.** YDK is the ecosystem standard; a paste box that accepts names needs a
  fuzzy matcher against the pool.

## Status

**Slice 0 is done.** `api/` and `ui/` are still uncommitted.

What landed:

- `api/src/ai_draw_api/executor.py` — the `DuelExecutor` Protocol and `FakeExecutor`. Every
  evaluation returns a win rate *and* its fidelity; the fake is `live = False` and says so.
- `api/src/ai_draw_api/store.py` — the durable single-slot queue over SQLite. Jobs survive the
  tab and the process; `recover_orphans()` re-queues anything left RUNNING by a crash.
- `api/src/ai_draw_api/refine.py` — the refine job. The swap proposer is a stand-in, not the
  Builder: it picks by hash, keeps positive Deltas, and never breaks legality.
- `api/src/ai_draw_api/main.py` — `GET /api/health`, `POST /api/jobs/refine`, `GET /api/jobs`,
  `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`.
- `ui/` — Tailwind v4 shell: the `live: false` header badge, a submit form, the job list with
  honest queue positions, and a job view with progress and the swap log.
- 20 tests in `api/tests/`, including the slice's manual test as `test_api.py`.

Running it:

```
cd api && uv venv && uv pip install -e ".[dev]" && .venv/bin/python -m pytest
.venv/bin/python -m uvicorn ai_draw_api.main:app --port 8000
cd ui && npm install && npm run dev      # http://localhost:5173, proxies /api to :8000
```

Known gaps, deliberately left for later slices:

- **Restart recovery re-runs a job from the start.** The job is never lost, but the swaps it had
  already made are. Checkpointing per swap belongs with slice 3's progress work.
- **Progress is polled at 700 ms**, not streamed. Fine at beta scale; slice 3 can revisit.
- **No auth.** Slice 8.
