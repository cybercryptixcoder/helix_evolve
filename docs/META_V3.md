# The meta loop: Helix evolving how Helix searches

Built October 17, 2026. It supersedes the specification in `META_LOOP.md` in one respect: the outer level is **not** a single coding agent but the same kind of evolutionary loop as the inner one (Navigator, Researcher, Coder, Mutator), and the winning strategy is swapped into the outer loop itself.

## The two levels

| | Inner level (`helix3/`) | Outer level (`meta/`) |
|---|---|---|
| A candidate is | a feature (a measurement in a decision) | a **strategy**: the folder `helix3/strategy/` |
| The incumbent is | the champion policy | the incumbent strategy |
| Evaluated by | the fitter, on the problem's instances | the **meta-evaluator**: inner runs on several problems |
| What the Researcher reads | packings/solutions vs a reference, sensitivity probes | the digests of the incumbent's inner runs (traces), per-problem behaviour stats |
| Role prompts | the strategy's method prompts + `prompts/features/` | the **outer strategy's** method prompts + `meta/space/` |

## The recursion

The strategy folder holds the **method** prompts of every role (`prompts/<role>.md`: how to research, mutate, navigate) separately from what a candidate is at a given level (`prompts/features/<role>.md` for the inner level, `meta/space/<role>.md` for the outer one). The outer roles run on the outer strategy's method prompts and settings. When a candidate strategy is promoted, it becomes:

1. the incumbent: from then on, inner runs are judged against it;
2. **the outer loop's own strategy**: its method prompts and settings now drive the outer Navigator, Researcher, Coder and Mutator.

So an improvement to *how a Researcher should research* improves the inner Researcher and the outer one. If a swapped-in strategy breaks the outer roles (two failures in a row), the outer loop swaps back.

## The meta-evaluator (`meta/evaluate.py`)

For each problem and repeat, the inner engine runs from Code Zero with the candidate strategy, in its own process, with a wall-clock limit. Per run:

| Measure | What it rewards |
|---|---|
| `final` | held-out test progress at the end (degree of improvement) |
| `auc` | mean validation progress over the generations (getting there sooner) |
| `plateau` | the generation by which 90% of the final gain was reached |
| `flat_tail` | generations at the end without gain (flatlining) |
| cost | model calls, tokens, minutes, crashes |

`run score = 0.6 × final + 0.4 × auc`; a problem's score is the mean over repeats; the strategy's score is the mean over the search problems. **Held-out problems** are scored the same way but their traces are never shown to the outer agents; a candidate is promoted only if it beats the incumbent by more than the noise between repeats (or `--margin`) *and* doesn't get worse on the held-out problems. Budgets are capped (`meta/strategies.py`, `CAPS`) so a strategy can't win by spending more.

The **supervisor**: when a candidate strategy crashes inner runs, the outer Coder gets the errors and the strategy and repairs it once, and the candidate is re-evaluated.

## Running it (on your machine; it's long)

```bash
# score one strategy (the current default) on four problems, one held out
python -m meta.evaluate --problems binpack1d,knapsack,tsp,scheduling --held-out coloring \
    --generations 5 --repeats 2 --parallel 4

# the meta loop: 10 outer generations; each candidate costs problems × repeats inner runs
python -m meta.outer --problems binpack1d,knapsack,tsp,scheduling --held-out coloring \
    --inner-generations 5 --repeats 2 --outer-generations 10 --deep 2 --wide 2 --parallel 4
```

Rough cost: one inner run of 5 generations is about 60-90 model calls and 3-10 minutes, depending on the problem and the machine. An outer generation with 4 candidates × 5 problems × 2 repeats is 40 inner runs: about an hour with `--parallel 4` on an 8-core machine, about 3,000 model calls. With several Luminal keys in `.env`, the key pool spreads the calls.

Everything lands in `meta_runs/outer-<timestamp>/`: `state.json` (every candidate, its edit, score, verdict), `candidates/<id>/` (each strategy), `evals/<id>/` (its inner runs, with digests), `outer_strategy/` (what the outer loop runs on now), `trace.jsonl`. The dashboard's Meta loop page reads it.

## Running it unattended, with a live page

```bash
cp .env.example .env              # put your Luminal key in LUMINAL_API_KEYS (gitignored)
HOURS=5 scripts/run_meta.sh       # budgeted run; on exit it commits and pushes results/meta/<run>
python -m ui                      # then open http://localhost:8765/meta
```

`scripts/run_meta.sh` takes `HOURS`, `INNER_GENS`, `REPEATS`, `DEEP`, `WIDE`, `PARALLEL`, `PROBLEMS`, `HELD_OUT`, `PUSH=0` (keep results local). `--hours` stops new outer generations and new candidate evaluations once the budget is used; the one in flight finishes, so allow up to an hour extra. The `/meta` page shows the incumbent's score over outer generations, the inner runs in flight and per-problem scores, and can start or stop a run.
