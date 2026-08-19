# Fork ygo-agent's ygoenv as the duel executor

Duels are executed by our own fork of [`sbl1996/ygo-agent`](https://github.com/sbl1996/ygo-agent)'s `ygoenv` — a Gym-API environment wrapping `ygopro-core` via envpool — vendored as a git submodule. Nothing else in the ecosystem simulates a duel: the Pilot, the Gauntlet, Screening and Gate evaluation all run through this one component. We fork rather than depend because upstream's last push was 2024-08-16 and phase 2 requires patching its C++ bindings for a 2026 card pool.

## Considered options

- **WindBot / EDOPro scripted AI** — free deterministic opponents, but every deck needs a hand-written executor, so a Builder that invents a novel deck has nobody who can pilot it. Fatal for our purpose; still viable later as extra Gauntlet variety.
- **Write our own simulator** — full control, but re-implementing Yu-Gi-Oh!'s card-effect resolution is a multi-year project on its own.
- **`KohakuBlueleaf/M-YGO-Agent`** — a fork of the same base. Check which of the two is more alive before choosing the fork point; this ADR records the *base*, not which mirror we branch from.

## Consequences

- The supported card pool is whatever `scripts/code_list.txt` supports (13,472 cards upstream), and the shipped Pilot checkpoint is narrower still (864 cards). Phase 1 lives inside that pool; widening it is phase 2 and requires a C++ diff two years wide.
- envpool ships prebuilt for Linux x86_64 only and the training path assumes CUDA, so the Mac is a development machine and cannot train. Training runs on the Linux + NVIDIA box (RTX 4070 Ti Super, 16 GB VRAM; Intel i7-14700KF, 20 cores / 28 threads).
- Duels run on CPU, so **cores, not VRAM, are the throughput ceiling** — 28 threads bounds the parallel-env count and therefore how many Screening duels per second the Builder's reward signal can consume.
