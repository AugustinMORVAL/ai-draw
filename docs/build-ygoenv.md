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

```bash
cd scripts
gh release download v0.1 --repo sbl1996/ygo-agent -p '0546_22750M.flax_model' -D checkpoints
python -u eval.py --checkpoint checkpoints/0546_22750M.flax_model \
  --num_episodes 1024 --num_envs 28 --env_threads 28 --seed 0
```

Expect `win_rate` near 0.50 against the greedy bot and no abort.

## Measured throughput (i7-14700KF / RTX 4070 Ti Super, 28 threads)

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
