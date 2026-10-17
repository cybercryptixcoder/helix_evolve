## What a candidate is here: an edit to the strategy

The incumbent is a strategy folder. Its "parts" are its files and settings; the sensitivity of a part is what the run digests show about it (e.g. how often the Mutator's features are duplicates, how often predictions hold, whether the deep or the wide loop wins). Read the inner runs' digests the way a researcher reads lab notes: what did the search actually do, and where did it waste effort?

- `change` describes one edit precisely: which file, what to change, and how (for prompts: the sentence or section to add, remove or rewrite; for config: the key and value; for hooks.py: the behaviour).
- A `probe` edit changes one thing to learn whether it matters (for example, thinking on for one role only).
- `prediction.family` is a problem name or `all`; `prediction.metric` is one of the diagnostics.
