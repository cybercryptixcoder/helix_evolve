# Helix v3: design

Written October 17, 2026, at the start of the rebuild. It records why each part of v2 didn't do what it was meant to do (traced to the line of code or prompt that causes it), and what v3 does instead. The two-loop structure stays: a Mutator that goes wide, a Researcher that goes deep, one shared evaluator. What changes is everything around them.

The vision this is built against: `docs/next-concept/README.md` (two loops; improvement as a search space; a ledger; effort follows evidence; only a proof prunes).

---

## 1. Why v2 doesn't do what it was meant to do

Each row: the intent, what run 8 showed, and where it comes from. "Structure" means the flow of information or control in `helix/evolve.py`; "prompt" means `helix/prompts/` or `helix/roles.py`; "config" means a default.

| # | Intent | What happens | Cause |
|---|---|---|---|
| 1 | The Mutator goes **wide** | 7 of 9 variants were of one feature; it re-proposed a whole feature a generation later | **Structure:** `wide()` picks variant targets as `targets[(gen + i) % len(targets)]`, and `targets` is only the champion's own features, so with one feature every variant has the same parent. **Information:** it sees only the champion's code and score, never the scores of anything it tried, so it can't avoid repeats. **Prompt:** "keep what that feature is about" asks for narrow variants by design. |
| 2 | The Researcher goes **deep**, learning from how earlier hypotheses scored | It adapts a little (generation 2) but works from thin evidence | **Structure:** the log line is the claim truncated to ~150 characters and a verdict word. A probe rejection is logged as "refuted" with no number (`verdict()`). The log records the *claim*, never what the code measured or the sign the optimiser gave it. **Config:** thinking off (`reasoning_effort: none`). |
| 3 | The deep loop **cashes in** on the Mutator's luck | Impossible | **Structure:** the Researcher never sees a Mutator feature unless it was kept. Near-misses from the wide loop vanish. |
| 4 | Hypotheses are tested by **probe programs** that change one thing or **exaggerate one aspect**, to learn rather than to win | No probe step exists | **History:** the exaggeration probes of runs 1-2 were whole programs competing in the pool, so they always lost and crowded it out (HANDOFF §9). The fix then was to remove them. The real problem was that probes competed for selection. |
| 5 | A hypothesis's **prediction is checked** | Never | **Structure:** `record_hypotheses()` stores the `target` text; nothing reads it again. |
| 6 | Results go **back and forth** between evaluator, Researcher and Mutator | One way only: Fit → Accept → Library | **Structure.** The two loops share nothing but kept features. |
| 7 | The search **orients itself** and stops repeating | A fixed rotation of three "lenses", plus extra slots after two stalled generations | **Structure:** `FOCUS_LENSES[gen % 3]`; nothing models what has been tried. |
| 8 | Repeated ideas are noticed | Three of eight features in generation 1 were the same ranking | **Structure:** features have no identity beyond their id. |
| 9 | Ideas that only help **in combination** get a chance | Each feature is judged alone; 30 of 40 died at the probe | **Config:** pair trials and revisits exist but are off (`--pairs 0`, `--revisit 0`). |
| 10 | Credit goes to the **idea** | The biggest gain was argued as one thing and measured another; one kept feature had its sign flipped | **Structure:** the verdict attaches to the claim; nothing compares claim, code and fitted sign. |
| 11 | "Stuck" means stuck | Told "the small refinements are used up" with no features yet | **Prompt:** `roles.py` adds that sentence at `stuck >= 1`; the extra slots start at `stuck >= 2`. |
| 12 | Readable units | Scores are negative (−9.181 → −6.774) | The evaluator's score is −(excess %). |

---

## 2. v3 in one picture

```
                         ┌──────────────── Navigator (LLM, thinks) ────────────────┐
                         │ reads the approach tree + the ledger + last generation   │
                         │ brainstorms approaches, assigns effort, asks for proofs  │
                         └───────┬───────────────────────┬──────────────────┬──────┘
                    assignments  │                       │ parents to vary  │ prune requests
                                 ▼                       ▼                  ▼
  Inspect + sensitivity ─► Researcher ─► Coder     Mutator (code + scores   Prover ─► certificate
  (probes: knock out,       (deep: probe or          only; blind to          (checked by code;
   amplify, half)            improve experiments,     hypotheses)             prune only if it holds)
                             each with a prediction)        │
                                 │                          │
                                 └──────────► Novelty check (fingerprint) ◄─┘
                                                     │ duplicates are not re-evaluated
                                                     ▼
                                 Fit: probe → trial (with vs without) → prediction check
                                                     │
                                                     ▼
                                 Accept: greedy combination + near-miss pairs
                                                     │
                                                     ▼
                         Ledger + approach tree (every feature, its fingerprint, result,
                         prediction outcome, approach node, node state)
```

**How the loops and the search space fit together** (the open question in the concept doc): the approach tree **sits above both loops and decides where they search**, and the deep loop is **how a branch gets explored**. The Mutator stays blind to hypotheses: the Navigator chooses *which code* it varies, not what it should think.

---

## 3. The parts

### Ledger and approach tree (`helix3/ledger.py`)
- Every feature ever written is in the ledger: its code, origin (deep, wide, combination), approach node, fingerprint, probe curve, trial result, fitted sign, the Coder's reading, prediction and outcome, verdict.
- An **approach** is a node in a tree: a title, a description, a parent, and a **state**:
  - `untried`: added by brainstorming, waiting its turn;
  - `promising`: one of its features gained on validation;
  - `unproven`: tried, no gain yet; retried at lower priority;
  - `pruned`: a checked certificate shows it can't beat what's kept.
- Effort follows evidence: the Navigator sees each node's tries, best gain and age. A rule-based fallback (`strategy/hooks.py`) does the same when the Navigator is off or fails.

### Identity: fingerprints
- At the start of a run, decision states are sampled from Code Zero's own runs (and topped up from each champion's).
- A feature's **fingerprint** is its within-decision rank of every candidate, over those states.
- Two features whose fingerprints correlate at |ρ| ≥ 0.98 rank candidates the same way (up to sign, which the optimiser fits anyway): the second is a **duplicate**. It isn't evaluated again; it inherits the first's result, and its author is told.

### The prover (only a proof prunes)
- The Navigator may ask for an approach to be pruned. The Prover (LLM) must answer with a **certificate**, not an argument:
  - `duplicate`: this feature ranks the same as that one;
  - `span`: this feature is a linear combination of the kept features within every decision (so adding it can only re-weight what's there).
- The engine checks the certificate numerically (fingerprint correlation; R² of a within-decision regression ≥ 0.995). An approach is pruned only when every feature tried under it is certified. Otherwise it stays `unproven`.

### Sensitivity probes ("exaggerate one aspect")
- Before the Researcher runs, every kept feature is probed mechanically: knocked out (×0), halved, doubled, quadrupled. One line per feature: "doubling closing_bin_penalty: +0.12". A gain from amplifying means the policy under-uses that direction: a lead for the deep loop.
- These never compete for the champion's place, which was the failure of runs 1-2.

### Researcher (deep)
- Gets: the problem; the champion's features (what each code measures, its weight and sign, its importance); the champion's diagnostics next to the reference; the sensitivity table; the ledger for its assigned approaches (what was measured, probe curve, result, prediction outcome); **the Mutator's best recent finds** (to cash in on luck); its assignments.
- Proposes experiments, each with a `kind`:
  - `probe`: written to learn (change one thing, exaggerate one aspect). Judged by whether its prediction held, not by score. If it happens to win, it can still be kept;
  - `improve`: written to win.
- Every experiment has a structured **prediction**: a family, a named diagnostic metric, a direction. The engine checks it.
- Thinking on (`low` by default).

### Mutator (wide)
- Gets: the champion's code and score; a **scoreboard** of evaluated features (code and scores, never hypotheses), and a parent to vary chosen by the Navigator from the *whole ledger*, or a fresh slot.
- Its output goes through the novelty check; a duplicate earns one retry with the fact that it repeated something.

### Navigator
- One call per generation, with thinking. Reads the tree, the ledger summary, the last generation and the sensitivity table. Writes a JSON plan: new approaches, Researcher assignments (approach and mode: explore, exploit, probe), Mutator parents, combinations to retry, prune requests, and a short note on its reasoning.

### Fit and accept
- As in v2 (probe at four weights; trial = refit with vs without, on train and validation; greedy combination), plus:
  - prediction checks for every deep experiment (diagnostics with the feature at its best probe weight, compared with the champion's);
  - a near-miss backlog (helped alone but not enough; or probe-rejected by a small margin) that the Navigator can pair with new features.

### Units
- **Gap %**: how far above the instance's reference the solution is (lower is better, never negative for a bound).
- **Progress %**: 0% = Code Zero, 100% = the reference (for 2D bin packing, the optimal packings). This is what the dashboard shows. The evaluator's own score is kept in the records.

---

## 4. Generality: the problem interface (`helix3/problem.py`)

Every problem is a **priority problem**: a solution is built one decision at a time, and at each decision a policy scores the candidates; the highest score wins (ties: the first candidate). Code Zero is the policy that scores everything 0. A problem module provides:

| Member | What |
|---|---|
| `name`, `title` | ids |
| `description` | markdown for the prompts: the problem, what one decision is, how solutions are scored |
| `signature`, `signature_doc` | e.g. `feature(item, bins, capacity)`, and what each argument holds; the last line says what to return |
| `families` | instance families (the train families; held-out families may exist on test) |
| `instances(split)` | deterministic instances for `train`, `valid`, `test` |
| `run(instance, priority)` | builds a solution with the policy; returns `{"gap": %, ...}` |
| `floor(family)` | the best gap achievable (0 for an optimum, >0 when the reference is a loose bound) |
| `diagnose(instance, priority)` | named metrics of the solution (optional), for the Researcher and for prediction checks |
| `reference_metrics(instance)` | the same metrics for the reference solution (optional) |
| `n_candidates(args)` | how many candidates a decision has |

The problems themselves live in `suite/`.

---

## 5. The strategy surface, and the meta loop

Everything about *how* Helix searches that the meta loop may change is in one folder, `helix3/strategy/`:
- `config.json`: budgets, thinking levels, temperatures, probe weights, margins;
- `prompts/*.md`: the role prompts (problem-agnostic: the problem is injected);
- `hooks.py`: the rule-based allocation used when the Navigator is off or fails.

The meta loop evolves that folder. Its candidates are strategies; its evaluator runs the inner engine with a candidate strategy on several suite problems for a few generations and scores final progress, area under the progress curve, generations to plateau, generality (the worst problem) and cost. The outer loop uses the same roles (Researcher, Mutator, Navigator) with the prompts of the **current outer strategy**; when a candidate strategy beats the incumbent, it replaces the outer strategy too. That is the recursion. Details: `docs/META_V3.md`.
