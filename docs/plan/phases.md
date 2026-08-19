# Phases 0–4: the grill record

What the grilling sessions decided, rejected, and left open, phase by phase. Decisions that met the
ADR bar live in [`docs/adr/`](../adr/); the vocabulary lives in [`CONTEXT.md`](../../CONTEXT.md);
issue-level work lives in GitHub Issues. This file holds the rest — the rationale, the rejected
options, the traps, the superseded choices, and the questions each phase still has open — so none of
it has to be re-derived from a chat log.

**Provenance.** All of it comes from four sessions on 2026-08-19: the ecosystem grill (16 decisions,
5 phases, ~12 questions), the phase-1 re-grill via `/grill-with-docs` (which wrote the glossary and
corrected the gate), the phase-2 grill (**opened and abandoned after its first question**), and the
app grill (which produced ADR-0005 and [`app.md`](app.md)). A fork survey and a hardware/OS thread
ran alongside them.

## Cross-phase decisions

The ecosystem grill froze 16 decisions. Those with an ADR are recorded properly; the rest exist only
here.

| Decision | Choice | Recorded |
| --- | --- | --- |
| Duel executor | Fork ygo-agent's `ygoenv` (ygopro-core + envpool) | ADR-0001 |
| Builder formulation | RL policy over construct-then-mutate; Archive deferred | ADR-0002 |
| Evaluation | Two fidelities — Screening for reward, Gate for claims | ADR-0003 |
| Candidate injection | Hidden `_candidate` deck slot, swapped between batches | ADR-0004 |
| User surface | Queued job service over one duel farm | ADR-0005 |
| Compute | Windows box: RTX 4070 Ti Super (16 GB VRAM), i7-14700KF (20c/28t), 32 GB RAM | ADR-0001 |
| OS | WSL2 Ubuntu, code on the WSL ext4 filesystem, dual-boot as fallback | here (phase 0) |
| Frameworks | Pilot stays JAX (upstream's cleanba/PPO+LSTM); Builder in PyTorch; no Rust in the loop | here |
| Card representation | Upstream's LLM text embeddings (`scripts/card/embedding.py` → `embed*.pkl`), plus structured features and a learned residual when the pool is regenerated | here (phase 2) |
| Format | Master Duel Bo1, main + extra, forced 50/50 first/second, MD banlist | here — **unverified against the shipped assets** |
| License | AGPLv3, fully open source | here (phase 4) |
| Data | Monorepo, fork as a git submodule; SQLite for run metadata + Parquet for duel results | here — partly superseded by whatever `api/` ends up using |
| Pilot/Builder training | Co-trained by **alternating epochs** (freeze one, train the other) | here (phase 3) |
| Gauntlet | Fixed meta anchors now, evolving league later (`scripts/torch/ppo_osfp.py` is already in-repo) | here (phase 3) |

### Superseded, and why the correction matters

The phase-1 re-grill overrode four earlier choices. Each override fixed a claim that could not fail
or could not be honoured:

1. **Uniform-random baseline → Damaged deck.** A random legal pile loses to anything, so beating it
   by 15 points proved nothing. The Damaged deck (a shipped meta deck with ~10/40 main-deck cards
   replaced) is hurt but pilotable, so the gate can actually fail.
2. **"Common random numbers" → Paired evaluation.** The original phrasing implied candidate decks
   could share hands. They cannot — a different decklist draws a different order. The Environment
   set (opponent deck order, going-first assignment, pilot seeds) is what is genuinely shared.
3. **Racing / successive halving → two named fidelities.** Same goal, but ADR-0003's split makes it
   impossible to quote a Screening number as a deck's strength by accident.
4. **Repair gate → Build gate.** The re-grill drifted from *stress-testing the machinery* into
   *redefining the mission*, and landed on a Builder that repairs Damaged decks. The mission is
   building decks. Repair survives only as a diagnostic smoke test of the mutation stage, and
   construct-then-mutate was restored. Worth remembering as a failure mode of re-grilling: a
   rechallenge is allowed to fix a measurement, not to replace the goal.

## Phase 0 — build the executor and prove the wiring

**Closed** ([#2](https://github.com/AugustinMORVAL/ai-draw/issues/2)). The substance — the 864-card
pool, the silent-NaN trap, the paired acceptance test, `tools/gen_code_list.py --check` — is in
ADR-0001 and [`docs/build-ygoenv.md`](../build-ygoenv.md). What is only here is the platform
reasoning, because it will be re-litigated every time the project moves machines.

**macOS is three separate ports, not one.** `ygoenv/core/async_envpool.h` uses `cpu_set_t`,
`CPU_ZERO`, `CPU_SET` and `pthread_setaffinity_np` with no `#ifdef` guards, and those symbols do not
exist on macOS; `xmake.lua` passes `-march=native`, which Apple clang rejects on arm64; and
`jax<=0.4.28` caps out at Python 3.12. The Mac is a development and driving machine, nothing more.

**Native Windows is a multi-week port of envpool's threading and mmap layer with no upside.** WSL2 +
Ubuntu with NVIDIA passthrough gets ~95% of native throughput for CPU-bound duel simulation. Docker
Desktop on the WSL2 backend is the same kernel with more isolation; upstream ships a `Dockerfile`
and `cjiang1209`'s cherry-picked commits touch it.

**WSL2 gotchas that specifically bite this project.**

1. Keep the repo in the WSL filesystem (`~/ai-draw`), never `/mnt/c/...` — cross-boundary I/O is an
   order of magnitude slower and this project hammers card DBs and checkpoints.
2. `nproc` must report 28 and `free -g` must not show ~16 GB. WSL2 defaults to half the host RAM and
   can under-allocate cores; set `processors=28` and `memory=24GB` in `.wslconfig`. A default-capped
   WSL2 silently halves the Screening budget ADR-0003 depends on.
3. The GPU needs only the Windows-side NVIDIA driver — nothing installed inside the distro. Verify
   with `nvidia-smi` in WSL before anything else.
4. `EN1AK/ygo-agent` (fork survey, ADR-0001) has a commit titled "Add WSL2 GPU training support
   notes" — free reconnaissance.

**Run the agent inside WSL2, not over `ssh` from the Mac.** Driving it as `ssh box "cmd"` degrades
every file operation into a heredoc and pays a round trip per read. If the box must be reached
remotely, WSL2's NAT'd IP changes on every reboot, so `netsh portproxy` needs constant redoing:
use Tailscale on both machines (stable hostname, works off-LAN, ~10 min) or
`networkingMode=mirrored` in `.wslconfig` (Windows 11 22H2+, conflicts with some VPN clients).

**Two hardware notes.** 13th/14th-gen Raptor Lake had the documented voltage-degradation issue, and
multi-day RL training at sustained full load is exactly the workload that exposed it — confirm the
0x12B microcode and the Intel Default power profile before a long run. And envpool assumes
homogeneous workers, so the i7-14700KF's 12 E-cores will straggle behind its 8 P-cores; if
throughput looks lumpy that is the cause, and the fix is affinity pinning, not a rewrite.

**Sizing that came out of the thread:** ~24 actor threads, 64–128 parallel envs, 2–4 threads left for
the learner and the OS. Past ~256 envs RAM becomes the ceiling before CPU does, and env construction
is already known to fail outright at 896 envs (`Resource temporarily unavailable`, ADR-0004).

## Phase 1 — the Build gate

The gate, the six-week timebox (hard stop **2026-09-30**, hill-climb fallback through **2026-10-07**)
and the stage decomposition are in [#1](https://github.com/AugustinMORVAL/ai-draw/issues/1) and
[#3–#8](https://github.com/AugustinMORVAL/ai-draw/issues/3). What the grill established around them:

- **The gate is well-powered, not just falsifiable.** At 2000 paired duels the standard error on a
  win-rate *difference* is ~1.5 points, so a 15-point gate is a >5σ detection. The number was chosen
  to be both meaningful and measurable on one box.
- **Phase 1 deliberately proves the machinery on decks nobody asked for.** `assets/deck` ships ~30
  tested 2024 meta decks (Snake-Eye, Branded, Labrynth, Sky Striker, Shaddoll, Tenyi,
  Floowandereeze, CenturIon, Chimera…) and **zero Cyberse decks**, and the frozen Pilot has never
  seen a Cyberse deck. The project's actual target — a constrained Cyberse build — is not reachable
  until a Pilot is retrained. Accepting that is what keeps phase 1 six weeks long instead of six
  months.
- **The binding constraint is the Pilot, not the pool file.** The executor's `code_list.txt` covers
  13,472 cards; the shipped checkpoint's embedding table covers 864. Widening the pool means
  training a new Pilot. This is the single most common wrong turn available in this project.
- **The hill-climber is built before PPO on purpose** ([#6](https://github.com/AugustinMORVAL/ai-draw/issues/6)).
  It separates "PPO is broken" from "the evaluation machinery is broken". The same logic is why
  `cjiang1209`'s three eval-correctness commits were cherry-picked before the timebox started: with
  the `select_card`/tribute length mismatch in place, action predictions corrupt silently, the
  fallback fires, and a week goes into blaming PPO for four lines in `features.py`.
- **Budget is stated in candidates per hour, not duels per second** (≥1,000/hr end to end, ADR-0003)
  because the tempting fix for a plumbing shortfall — shrinking the Screening batch — moves the
  noise band and changes what the gradient means.

**Open in phase 1:** which single fixed Constraint the gate run uses as its test case; and whether
Screening throughput turns out to be the binding constraint, which is ADR-0003's stated trigger for
revisiting the rejected learned surrogate.

## Phase 2 — the 2026 card pool (highest risk, barely grilled)

**This is the least-examined branch in the project, and the grill that was supposed to fix that
stopped after its first question.** Nothing in the repo defines phase 2's goal. Resume here.

**Q1, unanswered: what is phase 2's single load-bearing claim?** "2026 C++ core update" describes
work, not a goal. Three framings were put up:

1. **Pool expansion enabler** — grow the supported pool beyond 864 so phase 3 has room to discover
   decks. Gate: N new cards playable end to end.
2. **Correctness/parity update** — take the newer core while proving nothing observable changed for
   the existing 864. Gate: behavioural parity with the frozen Pilot.
3. **Infrastructure unblock** — the old core cannot be built or maintained. Gate: green build, and
   phase-1 results reproduce.

**Recommended: framing 2, parity-first**, with expansion layered on afterwards as phase 2b. The
entire measurement chain — Pilot, Build gate, Paired evaluation — assumes the frozen checkpoint's
behaviour is stable. A core update that quietly changes a ruling, a card script, or the observation
encoding invalidates every phase-1 number with no visible symptom, and phase 0 already showed how
silent this class of failure is (a card-blind Pilot scoring a plausible 0.50). Making expansion the
goal is what tempts you to skip the parity proof.

**Q2–Q6 were never asked.** Roughly: how parity is measured and what tolerance counts as passing;
what gets version-pinned (core, CardScripts, BabelCDB, xmake's Python) and how; whether a new Pilot
is trained inside phase 2 or split into 2b; and how the regression harness proves phase-1 results
still reproduce.

**Facts already banked for whoever resumes it.**

- All four Project Ignis repos are actively maintained — `ygopro-core` and `CardScripts` were pushed
  on 2026-08-19. The 2026 refresh is a real path: pull latest `cards.cdb`, scripts, and core.
- The cost sits in `ygoenv/ygopro/ygopro.cpp`, one large C++ binding written against a **2024** core
  API. Two years of core changes will break it — budget days-to-weeks of C++ debugging, not hours.
- Card embeddings must be regenerated for the new pool (`scripts/card/embedding.py`), and the
  embedding order *is* the card-id order, so regeneration is a checkpoint-compatibility event.
- **`YGO-ExodAI` is the highest-value reference** — 22 commits of exactly this work: its own
  `edopro-core` build pin, a Lua `GetID` nil fix, `c_get_card_id` hardened to return 0 on unknown
  codes, an ygoenv sync-mode `IndexError` fix, and xmake's Python pinned to 3.10.x because it was
  auto-resolving to 3.14. `M-YGO-Agent` is the reference for the card-db makefile (+519 cards).
- **`izzak98/ygo-env` is the sharpest "not now"**: its observation-mask sizing changes the
  observation layout, which invalidates the shipped Pilot checkpoint outright. Its extra decks
  (Live Twin, Race, Sylvans, VV) are Gauntlet variety, not worth that.
- **Retraining a Pilot is the dominant cost.** Upstream's own multi-deck runs used 8×4090 and 128
  cores for days; this project has one 16 GB GPU and 28 threads.
- **The Rust question is settled but has a revisit trigger.** `ocgcore-ffi` (v0.1.4, ~122 downloads,
  one maintainer) genuinely binds the *current* core, and duel simulation is CPU-bound and
  embarrassingly parallel, so a Rust harness is defensible in principle. It loses because
  `ygopro.cpp`'s value is not the FFI, it is thousands of lines of state encoding — chains,
  materials, positions, zones → tensors. Rewriting that is redoing the hardest part of the project
  for zero modelling gain. Revisit only if simulation throughput is *provably* the bottleneck.

## Phase 3 — co-training, Conditioning, the Archive

- **Co-training is the honest formulation; alternating epochs is the tractable schedule.** A deck has
  no win rate on its own — only a deck + Pilot pair does — so freezing the Pilot forever caps deck
  quality at what that Pilot can express. But a non-stationary reward on a one-GPU box is how these
  projects die at month three. Freeze one, train the other, alternate. The open question was never
  *whether* to co-train, only the schedule granularity — and that is still open.
- **Conditioning is what turns a filter into an intent.** Until it is trained, a user's stated
  interest is enforced by Masking only: the deck is legal and respects the Constraint, but the
  Builder was never steered toward it. [`app.md`](app.md) puts it correctly — the gap between
  "filtered" and "intended" is the gap between a demo and a product. The policy's constraint input
  slot exists from phase 1 and is fed a fixed vector until here.
- **The Archive answers mode collapse** (ADR-0002): MAP-Elites over Constraint dimensions with the
  Builder as the mutation operator. Before phase 3 there is exactly one lineage per run and
  diversity is not claimed. Which dimensions the cells range over is open; **budget is just another
  Constraint dimension**, which is what makes a collection/budget optimiser a phase-3 by-product
  rather than a separate product.
- **The Gauntlet becomes a league.** Fixed meta anchors stay as comparability anchors; the evolving
  opponent population arrives here, and `scripts/torch/ppo_osfp.py` (Online Self-Fictitious Play) is
  already in-repo, so this is a wiring job, not a research one.
- **This is where the project's actual goal becomes reachable** — a constrained Cyberse build, which
  needs both a Pilot that knows Cyberse cards (phase 2) and a Builder that can be told to want them
  (here).

## Phase 4 — the ecosystem

Decided in ADR-0005 and planned slice-by-slice in [`app.md`](app.md). The grill insights behind it:

- **The pivot was console → product.** A research console can be a Streamlit page in a weekend; a
  product cannot. Choosing "product" is what forced multi-user, persistence, and a job queue.
- **Nobody trains a model on demand.** PPO training is GPU-hours on one box; ten users training would
  queue for days. Users *run* the Builder — express interests (inference, seconds), refine a deck
  (mutation loop, ~3 min at 1,000 candidates/hr), test a deck (Gate evaluation, ~5–30 min). That is
  a render farm, not a training service.
- **Launch is gated on phases 2 and 3, not on frontend effort.** An 864-card 2024 pool makes the app
  look broken to anyone searching for a real card, and Masking-without-Conditioning makes "I want a
  Sky Striker deck" return a filtered generic pile. Stated plainly because slices 0–6 build a
  complete, clickable, fake-backed app: **do not let a working demo create pressure to open signups**.
- **Every displayed number carries its fidelity label**, or Screening noise (±4–6 points) reads as
  the deck getting worse half the time.
- **The licence decides the ecosystem's business shape.** `ygopro-core` is AGPLv3 (WindBot too);
  ygo-agent is MIT but links the core; envpool is Apache-2.0. AGPL is *network* copyleft: run a
  public service on that engine and you must offer corresponding source to its users. The decision
  taken was to be fully open source, which makes this a non-issue rather than a surprise later.
  (Standard reading, not legal advice.)

**Open, carried from [`app.md`](app.md):** where the API runs (the duel farm is a desktop box, not a
server); whether live Screening win rates are shown during a job; and the deck import format (YDK is
the ecosystem standard, a name-paste box needs a fuzzy matcher against the pool).

## Keeping this file honest

Add to a phase's section when a grill closes; when something here becomes hard to reverse,
surprising, and the result of a real trade-off, promote it to an ADR and leave a pointer behind.
The one live gap is phase 2: it has no defined claim, and it is the phase most able to invalidate
everything upstream of it.
