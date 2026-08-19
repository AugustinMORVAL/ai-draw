# ai-draw

RL-driven Yu-Gi-Oh! deckbuilding ecosystem: a Builder that constructs and refines decks, evaluated by simulated duels piloted by an RL agent, under user-supplied constraints.

## Language

### Constraints

**Constraint**:
A user-supplied restriction on deck composition (e.g. "max 20 Cyberse-type cards", "budget ≤ N"). Distinct from *Legality* — banlist, copy limits, and deck-size rules are not Constraints, they are always enforced.
_Avoid_: rule, filter

**Masking**:
Hard enforcement: illegal or constraint-violating card picks are removed from the Builder's action space. Guarantees valid decks. Present from phase 1.

**Conditioning**:
Feeding the Constraint vector into the Builder policy as input so one trained model serves any constraint at inference. A phase-3 training feature; the policy's constraint input slot is reserved from phase 1 but fed a fixed vector until then.
_Avoid_: constraint-aware (vague — could mean either Masking or Conditioning)

### Evaluation

**Damaged deck**:
A shipped meta deck with ~10 of 40 main-deck cards replaced by random legal cards from the supported pool — hurt but still pilotable. Serves as the phase-1 Baseline: strong enough that a bad Builder loses to it, weak enough that a working Builder beats it.
_Avoid_: random deck, random-legal deck (unfalsifiable — uniform-random piles lose to anything)

**Build gate**:
The phase-1 pass/fail test: a deck the Builder **built** (constructed and refined, under Masking) must beat the Damaged-deck Baseline by ≥15 win-rate points under Paired evaluation. Win rate vs the undamaged seed deck is reported alongside but does not gate.
_Avoid_: repair gate (a demoted diagnostic: seeding the Builder with a Damaged deck to smoke-test the mutation stage), success metric (say which gate)

**Pilot**:
The RL policy that plays duels with a given deck. Phase 1 uses a *frozen* pilot (the shipped 864-card ygo-agent checkpoint); a deck's measured strength is always relative to its pilot.
_Avoid_: bot, player AI (WindBot-style scripted executors are not Pilots)

**Builder**:
The trained RL policy that **builds decks**: constructs a decklist from the card pool (masked card-adds) and refines it by mutation (card swaps). Distinct from the Pilot; the Builder never plays a duel. The Builder is a learned policy, not an evolutionary search — diversity comes later from the Archive, not from replacing the Builder.
_Avoid_: deck AI, generator, repairer (repair is a diagnostic use of the Builder, never its purpose)

**Archive**:
The phase-3 population of elite decks kept per cell of the Constraint dimensions (e.g. Cyberse count), MAP-Elites style, with the Builder acting as its mutation operator. Not a phase-1 concept; before phase 3 there is exactly one lineage per run.
_Avoid_: population, league (the League is opponent decks; the Archive is candidate decks)

**Screening**:
The training-time evaluation fidelity: a small paired-duel batch (order 100 duels) whose noisy win rate is the Builder's reward sample. Noise is accepted; averaging is the optimizer's job. Never quoted as a deck's strength.
_Avoid_: evaluation (say which fidelity), quick eval

**Gate evaluation**:
The high-fidelity fidelity (order 500+ duels) used only to decide the Build gate and to report results. The only numbers allowed in claims like "beats Baseline by 15 points".
_Avoid_: full eval, final eval

**Paired evaluation**:
Evaluating decks under a fixed *Environment set* — frozen opponent deck orders, going-first assignments, and pilot sampling seeds — so two decks differ only in what they can control. A candidate's own draw order is NOT pairable across different decklists and is never claimed to be.
_Avoid_: common random numbers (overpromises — implies candidate hands are shared)

**Delta score**:
A mutated deck's fitness in phase 1: its win rate minus its parent's win rate under the same Environment set. Valid only because parent and child share ~39/40 cards; meaningless between unrelated decks.
_Avoid_: fitness, reward (ambiguous with the Pilot's in-duel reward)

**Warm-start**:
Behavior-cloning the Builder's construct stage on human decklists (restricted to the supported card pool) before RL fine-tuning, so construction starts in plausible-deck space instead of a flat-reward desert. Distinct from Seed decks, which warm-start *mutation*, not construction.
_Avoid_: pretraining (ambiguous with Pilot pretraining)

**Seed deck**:
A known-good decklist (phase 1: a shipped ygo-agent meta deck) used to warm-start the mutation stage and as the reference for report-only metrics. Seeds accelerate the Builder; they never replace construction.
_Avoid_: starter deck, template

**Gauntlet**:
The fixed set of opponent decks (each driven by the Pilot) that a candidate deck is evaluated against. Fixed within a phase so win rates stay comparable across runs.
_Avoid_: meta, league (the League is the *evolving* opponent population, a later-phase concept)
