# Candidate decks are injected by mutating ygoenv's deck map, not by respawning envs

The Builder produces a new candidate deck for every Screening batch, but `ygoenv` learns its decks
once: `init_module(db_path, code_list_file, decks)` reads a name → `.ydk` map into static
`main_decks_` / `extra_decks_`, and the env config selects one by *name* (`deck1`, `deck2`).

We add a `register_deck(name, main, extra)` binding to our fork that writes those static maps
directly, and keep the Builder's candidate in a **hidden deck slot** named `_candidate`. Both halves
exploit machinery that already exists: `load_deck()` re-reads `main_decks_.at(deck_name)` at *every
episode reset*, so a deck swapped between batches takes effect on the next duel with no env
teardown; and `init_module` already excludes `_`-prefixed names from `deck_names_` (upstream uses
`_tokens` for exactly this).

## Considered options

- **Re-call `init_module` with a fresh `.ydk` directory per candidate** — needs no C++, but re-parses
  the whole card database and card scripts on every candidate, and `init_module` appends to
  `deck_names_` without ever clearing it, so deck names accumulate and per-deck win-rate logging
  degrades over a long run.
- **Tear down and rebuild the envpool per candidate** — no fork divergence at all, but pays the full
  construction cost thousands of times per training run, and env construction is already known to be
  expensive enough to fail outright at 896 envs (`Resource temporarily unavailable`).

We already fork ygoenv precisely so we can patch its C++ (ADR-0001), and this patch is roughly fifteen
lines. Neither alternative is cheaper in anything except fork divergence.

## Consequences

- **Swaps happen only when every env is quiescent** — between Screening batches, never mid-batch.
  envpool runs envs on worker threads that read the same static maps, so a mid-batch write is a data
  race and, worse, would silently mix two decks' duels into one win rate. This is enforced with an
  assertion in the evaluation harness, not a comment in the code.
- The candidate is invisible to `deck_names_`, so `info:deck` reports it as id 0. That field feeds
  per-deck logging in the `cleanba*` scripts only and is never an input to the policy, so the Pilot
  sees no out-of-distribution signal from the hidden slot; only the logs need to know.
- Candidate decks still have to satisfy `ygopro-core`, which aborts the process on a malformed deck.
  Masking must produce a legal deck *before* injection; the harness never discovers illegality at
  duel time.
