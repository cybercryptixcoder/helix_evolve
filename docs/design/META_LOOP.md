> **Scrapped (October 20, 2026).** Meta-evolution was dropped: too expensive and slow for the compute available. Kept as history; see docs/WORKLOG.md.

# Meta loop: evolving Helix itself

**Status: specification, not built yet.** Written October 16, 2026, so whoever picks this up can build it without the conversation it came from.

## The idea

Helix improves programs. The meta loop improves **Helix**: the thing being evolved is the search loop itself (`helix/`), and its fitness is *how well it improves programs* across many problems.

- **Shreyas's part: the meta-evaluator.** It takes a candidate version of Helix, runs it on a suite of verifiable problems, and returns one score plus a detailed breakdown. This is the only piece that has to be built carefully, because everything else is judged by it.
- **The rest is one agent, not a full Helix.** A single coding agent (the expendable long-running agent we already use) edits a copy of Helix and submits it to the meta-evaluator. It reads the feedback and tries again, keeping the best version so far. No separate Mutator, Researcher or Coder is needed at this level.

```
 coding agent ──edits──► candidate Helix ──► META-EVALUATOR ──► score + per-problem report
      ▲                                       (runs the candidate on                 │
      └───────────────────── feedback ───────  every problem, from Code Zero) ◄─────┘
```

## What the meta-evaluator does

For each problem in the suite, and each repeat:

1. Start the candidate's own `python -m helix.run` from that problem's **Code Zero**, with nothing added.
2. Hold the generation count, time limit and model calls to the current **stage** budget (below).
3. When it ends, score its best program on the problem's **held-out test split** with the problem's own evaluator. The candidate never runs this step and never sees the test split.
4. Record progress per generation, held-out progress, cost (LLM calls, tokens, wall minutes), and any crash.

Then it combines everything into one result: a JSON file, plus a short human-readable report.

### Interface (proposed)

```bash
python -m meta.evaluate --candidate path/to/candidate_repo --stage 1 --out result.json
```

- **The candidate** is a full copy of the repo (or a git ref), so the agent may change anything in `helix/`.
- **Off-limits:** the agent may not change `meta/` itself, any problem folder, or `evaluator/`. The meta-evaluator uses its own pinned copies of those.
- **Problem swapping already exists**, via the environment variables `HELIX_EVALUATOR_CMD`, `HELIX_PROMPTS_DIR`, `HELIX_BOUNDS_MODULE` and `HELIX_FUNC_NAME`. `problems/tsp/README.md` shows a working example. Every problem must provide:
  - a Code Zero seed;
  - an evaluator CLI with `train` and `test` splits;
  - a lower bound or best-known value, so progress can be normalised;
  - prompts.
- **Runs are independent,** so problems and repeats run in parallel. Each run has a hard wall-clock limit; a run that crashes or times out scores 0 progress for that problem and is reported.

## The problem suite

Start with **3-4 problems** and grow to **6-8** once the evaluator is trusted. More than that multiplies cost.

| Problem | Status |
|---|---|
| Online 2D vector bin packing (`evaluator/`) | Exists, with optimal-packing bounds |
| Travelling salesman (`problems/tsp/`) | Exists, with lower bounds |
| Online 1D bin packing (the FunSearch problem) | To add |
| Scheduling, e.g. makespan on parallel machines | To add |
| 0/1 knapsack or graph colouring | To add |
| **One or two held-out problems the agent never sees** | To add; used only to check that improvements generalise |

Each problem needs instances from fixed seeds, a train/test split, and scores where higher is better, normalised to progress: 0% = Code Zero, 100% = the bound. That way problems can be averaged.

## The score

- **Main score: mean held-out progress across problems** after the stage's generations. That's the share of the way from Code Zero to the bound each problem got, averaged so every problem counts equally.
- **Speed matters too:** also report the area under the progress-by-generation curve, so a Helix that gets there sooner scores higher. Pick one as the official number before starting; the mean is the simpler choice.
- **Cost is a budget, not a score.** Every candidate gets the same generations, time and model-call caps. Report cost; refuse candidates that exceed it.
- **Noise:** one Helix run is noisy, because LLM replies vary. Use **2-3 repeats per problem** and compare each candidate with the current best on the *same* problems and seeds. A candidate counts as better only if it wins by more than the spread between repeats.

## Staged budgets: start small, then check the gain scales

We can't afford 30-generation runs for every candidate. So:

| Stage | Generations per run | Who gets it |
|---|---|---|
| 1 | 5 | Every candidate |
| 2 | 10 | Candidates that beat the incumbent at stage 1 by more than the noise |
| 3 | 20-30 | Candidates that also win at stage 2 |

A candidate is **promoted to the new incumbent only if its advantage holds or grows** as the budget grows. A version that wins at 5 generations but loses at 10 is tuned for short runs, not better. Keep a ledger of every candidate: the change made, the score at each stage, the cost, and the verdict.

## Rules learned the hard way (see HANDOFF.md §10)

- **No head starts:** every run starts from Code Zero with nothing added. A candidate that ships hand-written knowledge about a problem (built-in features, prompt hints) is invalid. The held-out problems catch this.
- **The meta-evaluator owns** problems, seeds, splits, bounds and budgets. The candidate controls only how it searches.
- **Never trust the candidate's self-reported score.** Rescore its best program with the problem's own evaluator, on the test split.
- **The offline fake model (`--fake-llm`) only proves a candidate runs.** It says nothing about quality; use it as a cheap crash check before spending real model calls.

## Rough cost

One 10-generation feature-engine run on bin packing costs about 100-250 model calls and roughly 5-50 minutes of wall time, depending on the version and the machine. Stage 1 with 4 problems × 2 repeats × 5 generations is 8 short runs per candidate: well under an hour if they run in parallel.

## Open questions

- Mean progress or area under the curve as the official score?
- How large a win counts as real, given the noise? Measure the spread of the current Helix first, with 3 repeats on each problem.
- Should the agent see per-problem traces, or only the scores? More detail helps it improve, but risks fitting to specific problems; the held-out problems are the guard.
