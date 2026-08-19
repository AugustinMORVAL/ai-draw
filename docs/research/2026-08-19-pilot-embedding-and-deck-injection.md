# The Pilot's embedding table, the code list, and what a duel actually costs

Measured 2026-08-19 on the Linux box (i7-14700KF, 20 cores / 28 threads; RTX 4070 Ti Super),
against `vendor/ygo-agent` at `ec8002a` and the frozen Pilot `0546_22750M`. This note closes
phase 0 (#2) — it is the evidence behind ADR-0001's pool section and the throughput table in
`docs/build-ygoenv.md`.

## 1. The code list is part of the checkpoint

`init_module` (`ygoenv/ygoenv/ygopro/ygopro.h`) walks `--code_list_file` line by line and does
`card_ids_[code] = i` with `i` the 1-based line number. Nothing else assigns card ids. The Pilot's
card-embedding table has exactly 1000 rows: row 0 is "unknown", rows 1..864 are the vectors of the
v0.1 release asset `embed864.pkl` in that pickle's insertion order (cosine similarity 1.000 for all
864 against the checkpoint's rows), rows 865..999 are zero.

So the id a card gets is a function of the *file*, and the vector it gets is a function of the
*checkpoint*. They agree only when the file starts with those 864 codes in that order. Under the
vendored 13,472-line `scripts/code_list.txt`, 552 of the 604 cards used by `assets/deck/*.ydk`
land past line 999. The consequence is sharper than "the model sees a generic unknown card":
`nn.Embed` is a gather, and an out-of-range index under `jit` is undefined behaviour. See §5.

## 2. Why the pool file is 13,473 lines and not 864

The first attempt at a corrected list was 864 lines. It ran 128 episodes clean and then died at
episode ~500 of a 1024-episode batch:

```
[card_reader_callback] Card not found: 40005099
terminate called after throwing an instance of 'std::runtime_error'
```

`40005099` is "Shiranui Style Synthesis". It is in no shipped `.ydk` — a Shiranui card script asks
the core for it. `cards_data_` is populated *only* from the code list, and `card_reader_callback`
throws (and `std::terminate`s the process) on a miss. `preload_deck` exists but `init_module` for
`YGOPro-v1` never calls it, and there is no `assets/deck/_tokens.ydk`, so `preload_tokens=True`
is not an escape either.

The fix keeps the pool and the file distinct: `tools/gen_code_list.py` emits the 864 embedded codes
first, then every remaining vendored code in its original order (13,473 lines total). Lines 1..864
carry the Pilot's vectors; nothing past 864 was ever observed reaching the policy (§5). **The pool is the first 864 lines. The tail is
there so the C++ core can answer a script's question without killing the run.**

This also means an 864-length code list can never be used for the "does the model see its cards"
comparison — the blind arm of the experiment has to be the vendored file.

## 3. The paired acceptance test

`eval.py`, frozen Pilot vs the greedy bot, all 33 shipped decks, 1024 episodes,
`--num_envs 28 --env_threads 28`, one run per code list per seed.

| seed | `data/pilot-864/code_list.txt` | vendored `scripts/code_list.txt` |
| --- | --- | --- |
| 0 | **win_rate 0.9736**, len 89.0, win_reason 0.993 | win_rate 0.4961, len 87.7, win_reason 0.968 |
| 1 | **win_rate 0.9756**, len 88.1, win_reason 0.989 | win_rate 0.4814, len 87.9, win_reason 0.977 |

The gap is ~0.49 and stable across seeds; `win_reason` ≈ 0.99 in every arm, so duels end by an
actual win rather than the step cap in both. This is the falsifiable result the original phase-0
smoke test lacked: 0.50 was never evidence of a working fork, because 0.50 is exactly what a
card-blind Pilot scores.

An incidental consequence worth carrying into phase 3: **the Pilot beats the greedy bot ~97.5% of
the time.** The greedy bot is a near-floor opponent for a correctly wired Pilot, so Damaged-deck
calibration (#5) cannot expect much headroom from bot win rate alone — a damaged deck has to be bad
enough to move a number that starts at 0.975.

## 4. Throughput, re-measured non-blind

Same setup, `--seed 0`, 1024 episodes (4096 at 448 envs and above). Duels/s = `SPS / mean len`.

| `--num_envs` | SPS | mean len | **duels/s** |
| --- | --- | --- | --- |
| 28 | 3005 | 89.0 | 34 |
| 56 | 5739 | 88.7 | 65 |
| 112 | 8445 | 85.9 | 98 |
| 224 | 12079 | 83.9 | 144 |
| 448 | 16162 | 86.8 | 186 |
| 672 | 17240 | 85.2 | **202** |

896 envs fails at construction (`RuntimeError: Resource temporarily unavailable`), so ~202 duels/s
is the ceiling. Below ~224 envs the run is model-bound (model time > env time), above it env-bound:
the 28 threads bind, not the GPU. Every point is 10–20% above the card-blind table it replaces
(31 → 178 duels/s), because a wired-up Pilot ends duels sooner.

**For ADR-0003:** 100-duel Screening ≈ 0.5 s, 500-duel Gate ≈ 2.5 s of pure duel time — ~2
candidates/s, ~175k candidate evaluations per 24 h. Screening throughput is not the phase-1
constraint, so the learned win-rate surrogate stays shelved. Caveat: `battle.py` (agent-vs-agent)
roughly doubles model time, costing ~30–40% in the model-bound regime and little at 672 envs.

## 5. The blind arm was not "blind" — it was NaN

Re-measured after phase 0 closed, because "clamps to a zero row" was an assumption, not a
measurement. It is wrong.

`nn.Embed` gathers row `id` from a `(1000, 1024)` table. An out-of-range index under `jit` is
undefined behaviour. Measured directly on this box (`jax[cuda12]`, RTX 4070 Ti Super):

| index | 0 | 864 | 999 | 1000 | 13472 |
| --- | --- | --- | --- | --- | --- |
| result | learned "unknown" row | learned row | zero row | **NaN** | **NaN** |

And in a real run, instrumenting the policy output over 200 decision steps × 28 envs:

| code list | max action card id | policy rows containing NaN |
| --- | --- | --- |
| `data/pilot-864/code_list.txt` | 864 | 0 / 5600 |
| vendored `scripts/code_list.txt` | 13420 | **5598 / 5600 (100%)** |

So the 0.496 baseline is not a card-blind Pilot making uninformed-but-real decisions. It is a Pilot
whose logits are entirely NaN, where `probs.argmax(axis=1)` returns 0 without raising — **the
"blind" arm always plays the first legal action**, and that is worth ~0.50 against the greedy bot.

Two consequences worth carrying:

- **There is no graceful degradation at the pool boundary.** A single out-of-pool id does not
  cost a little accuracy; it NaNs that env's entire decision. Any future widening of the pool,
  deck injection of an out-of-pool card, or checkpoint swap is a hard error, not a soft one.
- **`argmax` over NaN is the silent part.** Nothing in the stack complains. `eval.py` and
  `battle.py` now raise on a NaN policy row, naming the max card id and the table size. That guard
  fires in ~2 seconds on the vendored list; it would have caught phase 0's original close.

### Where card ids actually enter the model

Worth recording because it is not obvious from the feature layout: `_set_obs_cards` computes a
`card_id` per card but calls `_set_obs_card_(f_cards, offset, c, hide)` *without* it, so columns
0–1 of `cards_` are always zero and the per-card `x_id` embedding is always the "unknown" row.
Card identity reaches the policy only through `actions_` and `h_actions_` (`action.cid_`, set by
`c_get_card_id`), gathered from the same table. This is upstream behaviour (`04e61b9`), not a
cherry-pick artifact. It means the pool boundary is enforced at *action* construction — which is
also where `c_get_card_id` throws — and that an id probe should read `actions_`, not `cards_`.

## 6. Why the tail can no longer bite

The three abort sites in `ygopro.h` all fire on something the code list omits:
`card_reader_callback` (card data for a script-requested code), `c_get_card_id` (an id for a card
being acted on or announced), `script_reader_callback` (a Lua path never preloaded). All three are
now decidable before a duel runs, and `tools/gen_code_list.py --check` decides them:

- the committed code list covers `cards.cdb` **exactly** — 13,473 codes, 0 missing, 0 extra — so no
  code in the database can be requested and missed;
- all 203 distinct `Duel.CreateToken` codes in `vendor/ygopro-scripts` are in the database;
- `vendor/ygopro-scripts` contains no `Duel.LoadScript` calls and exactly three shared libraries
  (`constant.lua`, `utility.lua`, `procedure.lua`) — the three `init_module` preloads;
- every `has_script` flag matches whether `c<code>.lua` exists (0 mismatches both ways).

The residual risk is a *new* database or script bundle: both are submodule bumps, and `--check`
fails on them.

## Reproducing

Build per `docs/build-ygoenv.md`, then from `vendor/ygo-agent/scripts` with that venv active:

```bash
python tools/gen_code_list.py --check          # from the repo root: pre-flights the executor
python -u eval.py --checkpoint checkpoints/0546_22750M.flax_model \
  --code_list_file ../../../data/pilot-864/code_list.txt \
  --num_episodes 1024 --num_envs 28 --env_threads 28 --seed 0
python -u eval.py --checkpoint checkpoints/0546_22750M.flax_model \
  --code_list_file code_list.txt \
  --num_episodes 1024 --num_envs 28 --env_threads 28 --seed 0
```
