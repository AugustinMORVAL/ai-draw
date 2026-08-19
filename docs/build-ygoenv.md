# Building the duel executor (vendor/ygo-agent)

`vendor/ygo-agent` is our fork of [sbl1996/ygo-agent](https://github.com/sbl1996/ygo-agent) —
upstream, plus cjiang1209's three evaluation fixes, plus our gcc-13 build fixes (see ADR-0001).
It is the duel executor every later phase runs on.

## Build it

Requires `xmake`, gcc 10+, and a Python 3.11 venv.

```bash
cd vendor/ygo-agent
uv venv --python 3.11 .venv
source .venv/bin/activate
pip install -U "jax[cuda12]<=0.4.28" "jaxlib<=0.4.28" flax distrax chex
make                                   # assets, ygopro-scripts, editable installs
export CMAKE_POLICY_VERSION_MINIMUM=3.5 # xmake's sqlite3/sqlitecpp recipes predate CMake 4
xmake f -y
xmake b ygopro_ygoenv                  # writes ygoenv/ygoenv/ygopro/ygopro_ygoenv.cpython-311-*.so
```

**Build from source; do not use the v0.1 prebuilt `ygopro_ygoenv.so`.** The prebuilt binary
predates upstream `dbf5142` ("Support announce_card") and calls `std::terminate` mid-duel on
`Unknown message announce_card` — decks like BlueEyes hit it within ~80 duels. If a prebuilt
`ygopro_ygoenv.so` is present next to the compiled `...cpython-311-*.so`, delete it.

`edopro-core` fails to build (its package recipe tracks git HEAD and its `extern "C"` patch no
longer applies). We made it an optional requirement; only the unused `edopro_ygoenv` target
needs it. Fixing it is phase-2 work — see `YGO-ExodAI/ygo-agent` in ADR-0001.

## Smoke test

**Always pass `data/pilot-864/code_list.txt`.** The card ids the env emits are line numbers in
`--code_list_file`, and the frozen Pilot's embedding table has room for 999 of them. With the
vendored 13,472-line `scripts/code_list.txt`, 552 of the 604 cards in the shipped decks land past
the end of that table, clamp, and reach the policy as the same zero "unknown" vector — a card-blind
Pilot that still scores ~0.50 against the greedy bot. See ADR-0001; the pool is 864 cards.

Our list is the Pilot's 864 codes in embedding-row order **followed by** the rest of the vendored
list. The tail is not optional: `init_module` builds `cards_data_` from this file alone, and
`card_reader_callback` calls `std::terminate` the moment a card script asks the core for a code the
file never listed. An 864-line file dies mid-run on `[card_reader_callback] Card not found:
40005099` ("Shiranui Style Synthesis" — a card no shipped `.ydk` plays, but a Shiranui script
references). Codes past line 999 gather to a zero row, which is what an out-of-pool card should be.
Regenerate with `python tools/gen_code_list.py`; `--check` fails if the committed file is stale.

```bash
cd scripts
gh release download v0.1 --repo sbl1996/ygo-agent \
  -p '0546_22750M.flax_model' -p 'embed864.pkl' -D checkpoints
python -u eval.py --checkpoint checkpoints/0546_22750M.flax_model \
  --code_list_file ../../../data/pilot-864/code_list.txt \
  --num_episodes 1024 --num_envs 28 --env_threads 28 --seed 0
```

`~0.50 vs the greedy bot is not a passing result` — it is what a blind pilot scores. The Pilot is
correctly wired only if its win rate under our code list is materially above its win rate under the
vendored one. Run both and compare; that gap is the acceptance test for the fork. Measured
2026-08-19, 1024 episodes, all 33 shipped decks, `--num_envs 28 --env_threads 28`:

| seed | `data/pilot-864/code_list.txt` | vendored `scripts/code_list.txt` |
| --- | --- | --- |
| 0 | **0.9736** (len 89.0, win_reason 0.993) | 0.4961 (len 87.7, win_reason 0.968) |
| 1 | **0.9756** (len 88.1, win_reason 0.989) | 0.4814 (len 87.9, win_reason 0.977) |

A ~0.49 point gap, stable across seeds, and `win_reason` ≈ 0.99 either way (duels end by an actual
win, not the step cap). The wired-up Pilot beats the greedy bot ~97.5% of the time; the blind one is
a coin flip. If a future run of this pair comes back at parity, the Pilot is unwired again — check
the code list before anything else.

## Measured throughput (i7-14700KF / RTX 4070 Ti Super, 28 threads)

Re-measured 2026-08-19 under `data/pilot-864/code_list.txt`, i.e. with the Pilot able to see its
cards. `eval.py` with the frozen Pilot `0546_22750M`, all 33 shipped decks, `--env_threads 28`,
`--seed 0`, 1024 episodes (4096 at 448+). Duels/s = `SPS / mean episode length`.

| `--num_envs` | SPS | mean len | **duels/s** |
| --- | --- | --- | --- |
| 28 | 3005 | 89.0 | 34 |
| 56 | 5739 | 88.7 | 65 |
| 112 | 8445 | 85.9 | 98 |
| 224 | 12079 | 83.9 | 144 |
| 448 | 16162 | 86.8 | 186 |
| 672 | 17240 | 85.2 | **202** |

896 envs still fails at construction (`RuntimeError: Resource temporarily unavailable`), so **~202
duels/s at 672 envs / 28 threads is the ceiling**. Throughput is model-bound below ~224 envs and
env-bound above it — the 28 physical threads, not the 4070 Ti Super, are what binds. The earlier
card-blind table (31 → 178 duels/s) understated every point by 10–20%: a wired-up Pilot wins faster
than it loses slowly, so episodes are no longer uniformly ~88 steps.

**What this buys ADR-0003:** a 100-duel Screening sample costs ~0.5 s and a 500-duel Gate
evaluation ~2.5 s of pure duel time — ~2 candidates/s, ~175k candidate evaluations per 24 h.
Screening throughput is *not* the binding constraint on phase 1, so the learned win-rate surrogate
stays shelved. Caveat: this is Pilot-vs-greedy-bot under `eval.py`; agent-vs-agent (`battle.py`)
doubles model time, which costs ~30–40% in the model-bound regime and little at 672 envs.
