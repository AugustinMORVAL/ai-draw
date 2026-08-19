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

**Always pass the 864-card code list.** The card ids the env emits are line numbers in
`--code_list_file`, and the frozen Pilot's embedding table has room for 999 of them. With the
vendored 13,472-line `scripts/code_list.txt`, 552 of the 604 cards in the shipped decks land past
the end of that table, clamp, and reach the policy as the same zero "unknown" vector — a card-blind
Pilot that still scores ~0.50 against the greedy bot. See ADR-0001; the pool is 864 cards.

```bash
cd scripts
gh release download v0.1 --repo sbl1996/ygo-agent \
  -p '0546_22750M.flax_model' -p 'embed864.pkl' -D checkpoints
python -u eval.py --checkpoint checkpoints/0546_22750M.flax_model \
  --code_list_file ../../../data/pilot-864/code_list.txt \
  --num_episodes 1024 --num_envs 28 --env_threads 28 --seed 0
```

`~0.50 vs the greedy bot is not a passing result` — it is what a blind pilot scores. The Pilot is
correctly wired only if its win rate under the 864 code list is materially above its win rate under
the 13,472-line one. Run both and compare; that gap is the acceptance test for the fork.

## Measured throughput (i7-14700KF / RTX 4070 Ti Super, 28 threads)

**These numbers were measured card-blind** (13,472-line code list) and are pending re-measurement
under `data/pilot-864/code_list.txt` — a Pilot that can actually see its cards plays different, and
probably shorter, duels. Treat the shape of the curve as sound and the absolute duels/s as an
estimate until phase 0 re-closes.

`eval.py` with the frozen Pilot `0546_22750M`, all 33 shipped decks, `--env_threads 28`,
1024–4096 episodes per run. Duels/s = `SPS / mean episode length`.

| `--num_envs` | SPS | mean len | **duels/s** |
| --- | --- | --- | --- |
| 28 | 2751 | 87.7 | 31 |
| 56 | 3887 | 88.2 | 44 |
| 112 | 7877 | 87.7 | 90 |
| 224 | 10717 | 88.4 | 121 |
| 448 | 14080 | 87.0 | 162 |
| 672 | 15120 | 85.1 | **178** |

896 envs fails at construction (`RuntimeError: Resource temporarily unavailable`). Throughput
is model-bound below ~224 envs and env-bound above it; 672 is the practical ceiling.
