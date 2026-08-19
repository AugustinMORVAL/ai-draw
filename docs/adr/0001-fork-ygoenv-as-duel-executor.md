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

## The phase-1 card pool is 864 cards, and the code list is not free to choose

Measured 2026-08-19, after the fork was already vendored. The env assigns each card an id equal to its **1-based line number in `--code_list_file`** (`init_module`: `card_ids_[code] = i`). The frozen Pilot `0546_22750M` carries a card-embedding table of exactly **1000 rows**, whose rows 1..864 are the vectors of the v0.1 release asset `embed864.pkl` in that pickle's insertion order (cosine similarity 1.000 for all 864; row 0 is "unknown", rows 865..999 are zero).

So the code list is not a knob — it is part of the checkpoint. Run the Pilot against the vendored 13,472-line `scripts/code_list.txt` and **552 of the 604 cards used by the shipped decks land beyond row 999**. That is not a graceful "unknown" fallback: an out-of-range index into a `nn.Embed` is an out-of-bounds gather, i.e. *undefined behaviour* under `jit`. Measured on this box it returns **NaN**, so 100% of decision rows carry NaN logits and `probs.argmax` — which never raises — returns 0. The "card-blind Pilot" is really a Pilot that always takes the first legal action, and that scores ~0.50 against the greedy bot: exactly the number the original smoke test accepted as proof the fork worked. It proved nothing.

**Nothing about this failure is loud, so the checks are the deliverable.** `tools/gen_code_list.py --check` decides statically what would otherwise abort a run hours in: it requires the code list to cover `cards.cdb` exactly (the three `ygopro.h` throw sites — `card_reader_callback`, `c_get_card_id`, `script_reader_callback` — all kill the process on a code or script the list omits) and that only the three preloaded shared Lua libs exist. `eval.py` and `battle.py` now raise on a NaN in the policy output rather than arg-maxing it. Measured: over 400 episodes across the 33 shipped decks, **no card id above 864 ever reaches the policy**, so the tail is a core-side concern only.

**The phase-1 supported pool is therefore the 864 codes of `embed864.pkl`, in that order**, committed as `data/pilot-864/code_list.txt` and regenerated by `tools/gen_code_list.py`. The committed file does not *stop* at 864: `init_module` populates `cards_data_` from the code list alone, and `card_reader_callback` aborts the process when a card script asks the core for a code the file never listed — an 864-line list dies mid-run on `[card_reader_callback] Card not found: 40005099`, a card no shipped deck plays but a Shiranui script references. So the file is the 864 pool codes first, then the remaining vendored codes in their original order. Only the first 864 lines are addressable by the Pilot's table; everything past line 999 gathers to a zero row, which is the correct treatment of an out-of-pool card. **Pool membership is a property of the first 864 lines, not of the file's length.** All 604 cards of the shipped decks are inside it; the remaining 260 are cards the Pilot understands but no shipped deck plays, and they are deliberately kept in the pool because that is where a Builder can out-build a human list. Masking, the Damaged deck's replacement draws, and Warm-start's decklist filter all range over these 864 and no others.

## Consequences

- The wiring is verified by a *paired* run, never an absolute number: measured 2026-08-19, 1024 episodes at seeds 0 and 1, the Pilot scores **0.974 / 0.976** against the greedy bot under `data/pilot-864/code_list.txt` and **0.496 / 0.481** under the vendored list. The ~0.49 gap is the acceptance test; parity means the Pilot is card-blind again.
- The supported card pool is **864 cards** — the Pilot's embedding table, not `scripts/code_list.txt`'s 13,472 lines. The 13,472 figure is the *executor's* ceiling and therefore a phase-2 target; reaching it means training a new Pilot, not just widening a file. Phase 1 lives inside the 864.
- envpool ships prebuilt for Linux x86_64 only and the training path assumes CUDA, so the Mac is a development machine and cannot train. Training runs on the Linux + NVIDIA box (RTX 4070 Ti Super, 16 GB VRAM; Intel i7-14700KF, 20 cores / 28 threads).
- Duels run on CPU, so **cores, not VRAM, are the throughput ceiling** — 28 threads bounds the parallel-env count and therefore how many Screening duels per second the Builder's reward signal can consume.
