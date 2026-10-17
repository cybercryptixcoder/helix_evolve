# The problem: improving how Helix searches

Helix is an LLM-driven evolutionary search that improves decision policies on verifiable problems (packing, routing, scheduling, colouring...). Each run starts from Code Zero (a policy that knows nothing) and runs a few generations: a Navigator plans, a Researcher runs experiments (deep loop), a Mutator makes blind variations (wide loop), Coders write features, and a fitter judges every feature.

**A candidate here is a strategy**: the folder that controls *how* Helix searches. Its files:

- `config.json`: budgets per generation, thinking levels (`effort`: none, low, medium, high, max), temperatures, probe weights, margins, novelty thresholds;
- `prompts/<role>.md`: the **method** prompt of each role (researcher, mutator, coder, navigator, prover): how it should think and what it should reply. Replies are parsed by code, so keep each role's reply format (the JSON fields, the code block) intact;
- `prompts/features/<role>.md`: what a candidate is for the inner level (a feature), per role;
- `hooks.py`: `allocate(view)`, the rule-based plan used when the Navigator is off or fails.

**How a strategy is scored.** The inner engine runs with it on several problems, from Code Zero, for a fixed number of generations, with repeats. Per run: final progress on a held-out test split (0% = Code Zero, 100% = the reference) and the area under the validation progress curve (rewards getting there sooner). score = 0.6 × final + 0.4 × AUC, both measured beyond a hidden textbook baseline for each problem (0 = the baseline rule, 100 = the reference: progress from Code Zero saturates where doing nothing is catastrophic), averaged over repeats, then over problems. A strategy is promoted only if it beats the incumbent by more than the noise between repeats, and doesn't get worse on held-out problems you never see.

**Rules.**
- No knowledge of any particular problem: no heuristics, formulas or hints for packing, routing or anything else. Strategies that only work because they leak a known solution fail on the held-out problems, and the rule is checked.
- The budget is fixed: Researcher experiments + Mutator slots per generation add up to at most 8 (you may move slots between the loops, not add them), and fit evaluation budgets are at most 48. A strategy wins by searching better, not by spending more.
- A strategy that crashes the inner engine scores 0 on that run.

**Diagnostics** (per problem, the incumbent's mean, for predictions): `final`, `auc`, `plateau` (generation reaching 90% of the final gain), `flat_tail`, `duplicates`, `invalid`, `probe_rejected`, `kept_deep`, `kept_wide`, `predictions_held`, `calls`.
