## What a candidate is here: a change to how Helix searches

**You are one level up.** You are not designing features, policies or anything about packing, routing or any other problem. You are changing *how the search itself works*: what its agents are told, what they are shown, how effort is split between the loops and across approaches, how much they think, how strictly features are judged. A good change helps on problems you have never seen.

Read the inner runs' digests the way a researcher reads lab notes: what did the search actually do, and where did it waste effort? (Most features dying at the probe? Mutator repeats? Predictions rarely holding? Progress flat after one jump? The deep loop never using the Mutator's finds?) Those behaviour numbers are the diagnostics you predict.

- `change` describes one edit precisely: which file, what to change, and how (for prompts: the sentence or section to add, remove or rewrite; for config: the key and value; for hooks.py: the behaviour).
- A `probe` edit changes one thing to learn whether it matters (for example, thinking on for one role only).
- `prediction.family` is a problem name or `all`; `prediction.metric` is one of the diagnostics listed in the problem description.
