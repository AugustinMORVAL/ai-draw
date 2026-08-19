# The Builder is an RL policy; the Archive is deferred to phase 3

The Builder is a PPO-trained policy over a construct-then-mutate MDP, not an evolutionary search. The published state of the art for automated deckbuilding is Deep Surrogate Assisted MAP-Elites (arXiv 2112.03534, Hearthstone) — a quality-diversity search with no learned builder — so choosing RL is a deliberate deviation from the strongest published result, taken because a learned policy is the project's actual goal and because a policy can later be *conditioned* on constraints, which a per-cell archive cannot.

## Consequences

- A single policy can mode-collapse onto one deck shape. The Archive (MAP-Elites over Constraint dimensions, with the Builder as its mutation operator) is the planned answer, and it arrives in phase 3 — not phase 1. Until then, one lineage per run, and diversity is not claimed.
- The construct stage cannot be trained from scratch on a flat reward over a 13k-card pool, so it is Warm-started by behavior-cloning human decklists before PPO fine-tunes. See ADR-0003 for how the reward itself is made cheap enough.
- The Builder's constraint input slot exists from phase 1 but is fed a fixed vector; Masking (hard removal of illegal picks from the action space) is what actually enforces constraints until Conditioning is trained in phase 3.
- If PPO underperforms, the pre-committed diagnostic is to run the mutation stage as a plain greedy hill-climber over Delta scores. That isolates "PPO is broken" from "the evaluation machinery is broken" — see the phase-1 gate issue.
