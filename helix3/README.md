# Helix v3

An LLM-driven evolutionary search for decision policies, with two loops (a Researcher that goes deep, a Mutator that goes wide) steered by a Navigator over a map of approaches. Why it is built this way, and what was wrong with v2: [docs/V3_DESIGN.md](../docs/V3_DESIGN.md).

## Run it

```bash
pip install numpy scipy cma                     # the only dependencies
cp .env.example .env                            # then put your Luminal key(s) in it (LUMINAL_API_KEYS=k1,k2,...)
python -m helix3.run binpack2d -g 5             # one run, from Code Zero
python -m ui                                    # the dashboard: http://localhost:8765
python -m suite.check --all                     # check every problem in the suite
python -m helix3.run knapsack -g 2 --fake       # crash test without model calls
```

A run writes `runs/<problem>/<timestamp>[-label]/`:

| File | What |
|---|---|
| `trace.jsonl` | every event: each model call (prompt, reply, hidden thinking), plans, experiments, probes, trials, predictions, the approach tree |
| `ledger.json` | every feature and approach, with results |
| `history.json` | the champion per generation |
| `summary.json` | the end: progress on train, validation and the held-out test, cost |
| `champion.py` | the policy written out as an ordinary program |
| `strategy/` | the exact strategy the run used |

`python -m helix3.digest runs/<problem>/<run>` prints a short digest of what the search did.

## Units

- **Gap %**: how far a solution is above the instance's reference (lower is better).
- **Progress %**: 0% = Code Zero (the policy that knows nothing), 100% = the reference. Gains are shown in **progress points (pts)**.

## The parts

| File | Role |
|---|---|
| `engine.py` | the generation loop |
| `ledger.py` | features, the approach tree, fingerprints and certificates |
| `fitter.py` | parallel scoring and weight fitting (CMA-ES); no LLM |
| `policy.py` | compiling features safely, composing a policy |
| `roles.py` | the messages each agent gets |
| `llm.py` | the Luminal client (several keys, both rate limits per key) |
| `problem.py` | the problem interface; the problems are in `suite/` |
| `strategy/` | **how Helix searches**: `config.json`, `prompts/` (method) + `prompts/features/` (what a feature is), `hooks.py`. The meta loop evolves this folder |
| `digest.py` | a run's trace, digested |

## The meta loop

`meta/` evolves the strategy folder with the same kind of loop. See [docs/META_V3.md](../docs/META_V3.md).
