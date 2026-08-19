# Two evaluation fidelities: noisy Screening for reward, Gate evaluation for claims

A deck's win rate is measured at two distinct fidelities. **Screening** (~100 paired duels) is the Builder's per-candidate reward sample during training: deliberately noisy, ±4–6 win-rate points, on the premise that averaging over noisy rewards is PPO's job. **Gate evaluation** (500+ paired duels) is run only to decide the Build gate and to report results, and is the only fidelity whose numbers may be quoted.

## Considered options

- **A learned win-rate surrogate**, as in the Hearthstone MAP-Elites work — 10–100× cheaper per sample, but it adds a model that can drift and be reward-hacked, i.e. a second research problem nested inside phase 1. Revisit if Screening throughput turns out to be the binding constraint.
- **Large batches with successive halving** — the cleanest signal per sample, but the sample count PPO needs makes each update take weeks on one box. Only viable with rented burst compute.

## Consequences

- Any win-rate number that appears in a claim, a report, or a commit message must come from Gate evaluation. Screening numbers are training internals and are never a deck's stated strength.
- Screening batches are small enough that a candidate's measured advantage is often inside the noise band. This is tolerable for a gradient signal and intolerable for a decision, which is exactly why the two fidelities have separate names.
- The Builder's compute budget is stated in **candidates per hour, not duels per second**. Phase-1 target: **≥1,000 candidate evaluations/hour**, measured end to end — deck swap, env quiescence, and 100 Screening duels — which at 100 duels per candidate is ~28 sustained duels/s. Missing that target is a plumbing bug to fix, not a licence to shrink the Screening batch, because shrinking it moves the noise band and silently changes what the gradient signal means.
- Both fidelities use Paired evaluation — a fixed Environment set of opponent deck orders, going-first assignments, and pilot seeds. The candidate's own draw order is not pairable across different decklists and is never claimed to be.
