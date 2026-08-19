# Fork ygo-agent's ygoenv as the duel executor

Duels are executed by our own fork of [`sbl1996/ygo-agent`](https://github.com/sbl1996/ygo-agent)'s `ygoenv` — a Gym-API environment wrapping `ygopro-core` via envpool — vendored as a git submodule. Nothing else in the ecosystem simulates a duel: the Pilot, the Gauntlet, Screening and Gate evaluation all run through this one component. We fork rather than depend because upstream's last push was 2024-08-16 and phase 2 requires patching its C++ bindings for a 2026 card pool.

## Considered options

- **WindBot / EDOPro scripted AI** — free deterministic opponents, but every deck needs a hand-written executor, so a Builder that invents a novel deck has nobody who can pilot it. Fatal for our purpose; still viable later as extra Gauntlet variety.
- **Write our own simulator** — full control, but re-implementing Yu-Gi-Oh!'s card-effect resolution is a multi-year project on its own.
- **Branching from a downstream fork instead of upstream** — see the fork survey below.

## Fork point

We branch from **upstream `sbl1996/ygo-agent`**, then cherry-pick. Surveyed 2026-08-19: upstream has 18 forks and has not moved since 2024-08-16, so every fork is `behind=0` and they are all cleanly composable onto the same base.

| Fork | Last push | Ahead | Cards | Brings |
| --- | --- | --- | --- | --- |
| `sbl1996/ygo-agent` (upstream) | 2024-08-16 | — | 13,472 | canonical base, 157★ |
| `Archangel252` | 2026-08-13 | 1 | — | LLM web duel harness (FastAPI + two frontends) |
| `EN1AK` | 2026-07-10 | 7 | — | WSL2 GPU training notes, asset refresh |
| `cjiang1209` | 2026-07-05 | 3 | 13,472 | eval/serving correctness fixes |
| `YGO-ExodAI` | 2026-04-26 | 22 | 13,472 | own ocgcore build + C++ fixes |
| `izzak98/ygo-env` | 2026-04-05 | 34 | 13,633 | extra decks, pendulum/obs-mask fixes, `edopro-migrate` branch |
| `KohakuBlueleaf/M-YGO-Agent` | 2025-07-30 | 18 | 13,991 | largest card pool, `src/` restructure, pyproject.toml |

None is maintained; all are personal snapshots. The decisive point against `M-YGO-Agent`, despite it having the largest card pool and the cleanest packaging, is that it relocated 155 files into `src/` in a single day's work and was never touched again — as a base it makes cherry-picking from the other four forks conflict on nearly every file.

**Merged before phase 1:** `cjiang1209`'s three commits (`0926e99`, `0f7820a`, `529e87f`; +19/-5 across `Dockerfile`, `scripts/battle.py`, `scripts/eval.py`, `ygoinf/ygoinf/features.py`). These are evaluation-correctness fixes — notably a `select_card`/tribute length mismatch that corrupts action predictions — and phase 1 stakes a six-week timebox on the evaluation stack telling a good deck from a bad one. Merging them is cheap insurance against the hill-climb fallback firing for the wrong reason.

**Banked for phase 2, not merged now:** `YGO-ExodAI` (already carries a chunk of the two-year C++ diff: an `edopro-core` build pin, a Lua `GetID` nil fix, `c_get_card_id` hardened against unknown codes, an ygoenv sync-mode `IndexError` fix, and xmake's Python pinned to 3.10.x because it auto-resolved to 3.14) and `M-YGO-Agent` (+519 cards, card-db makefile). `izzak98/ygo-env` is a secondary reference for deck assets and observation-mask sizing.

## Consequences

- The supported card pool is whatever `scripts/code_list.txt` supports (13,472 cards upstream), and the shipped Pilot checkpoint is narrower still (864 cards). Phase 1 lives inside that pool; widening it is phase 2 and requires a C++ diff two years wide.
- envpool ships prebuilt for Linux x86_64 only and the training path assumes CUDA, so the Mac is a development machine and cannot train. Training runs on the Linux + NVIDIA box (RTX 4070 Ti Super, 16 GB VRAM; Intel i7-14700KF, 20 cores / 28 threads).
- Duels run on CPU, so **cores, not VRAM, are the throughput ceiling** — 28 threads bounds the parallel-env count and therefore how many Screening duels per second the Builder's reward signal can consume.
