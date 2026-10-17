## What a candidate is here: a feature

The incumbent is a policy: a weighted sum of **features** (measurements of a candidate in one decision). An optimiser fits the weights and their signs, so never choose numbers or signs: choose *what to measure*. The parts in the sensitivity probes are the kept features; amplifying one means multiplying its weight.

- `change` is the exact measurement, per candidate, in terms of the arguments, so a Coder can write it without guessing. Say what it is for the last or special candidates when that matters.
- **It must rank candidates differently.** A value that is the same for every candidate in a decision, or a monotone copy of a feature the policy already has, tells the optimiser nothing. Prefer comparisons between normalised quantities; use a hard threshold only when the condition is the idea.
- A `probe` feature changes one thing, or exaggerates one aspect (a sharper threshold, a stronger form, one condition only).

A feature may apply only under a condition (only in some decisions, or for some candidates, when a quantity crosses a threshold) and be zero otherwise. The policy is one weighted sum, so a condition is the only way it can treat different cases differently.
