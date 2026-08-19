# The app is a queued job service over one duel farm, not a training service

ai-draw ships a user-facing app: people describe what they want, get a deck, and have the
Builder refine it. The load-bearing decision is that **no user ever trains a model**. A user
submits work to a queue; the Builder runs at inference and the duel farm scores candidates.
Training the Builder stays an offline, operator-only activity.

## Why

PPO training of the Builder is GPU-hours on a single box (RTX 4070 Ti Super; i7-14700KF,
28 threads). Duels run on CPU, so cores bound throughput (ADR-0001). Per-user training would
serialise days of work behind each request. Inference-time refinement does not: the Builder
proposes a card swap in milliseconds, and the cost is entirely in Screening the candidate.

Against the Stage-1 throughput target of **≥1,000 candidate evaluations/hour at 100 Screening
duels** (issue #3, a target — not yet measured):

| Job | Work | Wall clock |
| --- | --- | --- |
| Build a deck | Builder construct, Masked to the user's Constraints | seconds |
| Refine a deck | ~50 mutations x 100 Screening duels | ~3 min |
| Test a deck | Gate evaluation, 500+ duels vs the Gauntlet | ~20 s |

Those are servable. Per-user training is not.

## Consequences

- **The queue is single-slot.** The duel farm already saturates all 28 threads; two concurrent
  refine jobs halve each other's throughput and make both users wait longer than if they had
  queued. Users see queue position, not a spinner.
- **A job is the unit of work, and it is durable.** Refine and test jobs outlive the request,
  the browser tab, and an API restart. State lives in the database, not in process memory.
- **The duel executor sits behind one interface** (`DuelExecutor`), with a fake implementation
  used for all UI development. The app is built and manually testable before `vendor/ygo-agent`
  is wired in, and the real executor swaps in behind the same interface.
- **Every number the app displays is labelled with its fidelity.** Screening win rates appear
  only as refinement progress; anything presented as a deck's strength comes from Gate
  evaluation (ADR-0003). The UI carries this distinction because users will screenshot it.
- **"Based on their interest" is Masking until phase 3.** Constraints are enforced by removing
  picks from the Builder's action space; they do not yet steer the policy. A user asking for a
  Cyberse deck gets a legal Cyberse-only deck, not a deck the Builder *wanted* to build that
  way. Conditioning (ADR-0002) is what closes the gap, and it is phase 3.
- **Private beta only, until phase 2.** The supported pool is 864 cards from a 2024 checkpoint.
  Users searching for 2026 cards will find nothing and conclude the app is broken. Open signups
  wait for the card refresh.

## Not decided here

Auth, hosting, and the public-launch surface. The beta runs on a shared key for a known handful
of users; the queue and the job model are built to survive a later move to accounts.
