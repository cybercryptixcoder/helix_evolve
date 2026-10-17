# Helix v3

An LLM-driven evolutionary search for decision policies, with two loops (a Researcher that goes deep, a Mutator that goes wide) steered by a Navigator over a map of approaches. Why it is built this way, and what was wrong with v2: [docs/V3_DESIGN.md](../docs/V3_DESIGN.md).

## Run it

```bash
pip install -r helix3/requirements.txt          # numpy, cma, certifi
cp .env.example .env                            # then put your Luminal key(s) in it (LUMINAL_API_KEYS=k1,k2,...)
python -m helix3.run binpack2d -g 5             # one run, from Code Zero
python -m ui                                    # the dashboard: http://localhost:8765
python -m suite.check --all                     # check every problem in the suite
python -m helix3.run knapsack -g 2 --fake       # crash test without model calls
python -m helix3.run --resume runs/<problem>/<run>   # continue an interrupted run from its last generation
python -m helix3.keeper --list                  # every run, and whether it is alive; the keeper resumes dead ones
```

Every run checkpoints after each generation (`checkpoint.json`, written atomically). `scripts/install_keeper.sh`
starts the keeper at login so interrupted runs resume by themselves.

A run writes `runs/<problem>/<timestamp>[-label]/`:

| File | What |
|---|---|
| `checkpoint.json`, `status.json` | the state to resume from; the live phase and process id |
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

## One generation

1. **Inspect** (code): diagnostics of the champion against the reference, and sensitivity (each kept feature knocked out).
2. **Refit** the champion's weights (CMA-ES), starting at once. Every 4th generation is a **perturbation**
   generation: the fit also restarts from randomly kicked weights, kept only if better on search and validation.
3. **Navigator** (one call): reads the approach tree, the ranking of approaches by recent gains (the direction of
   fastest improvement), near-misses and the ledger; assigns the Researcher to approaches, picks the Mutator's
   parents (two slots always go to kept features), proposes combinations and prune requests. Approaches that fail
   3 generations in a row are **benched** (hidden from it) and come back at random later.
4. **Deep loop**: the Researcher designs experiments (hypothesis, the quantity to measure, a prediction on a named
   diagnostic); Coders write each as a feature. **Wide loop**, at the same time: the Mutator writes variants and
   fresh features from code and scores only.
5. **Fit lane**: each feature is checked, certified (inert, duplicate or spanned by the kept features: not
   evaluated), **probed** (added to the champion at a few weights) and, if the probe gains, **trialled** (a full refit
   with and without it, credited on train and validation), as soon as it is written. The Researcher's predictions
   are checked against the diagnostics.
6. **Accept** the winners greedily (they must also gain on validation), refit jointly, retire any feature the policy
   is better without, and update the tree; the Prover tries to certify prune requests.

**Thinking.** Each role has an effort level in `strategy/config.json` (the Researcher thinks at `low`; the others don't).
Every 5th generation is a **breakthrough** generation: the Navigator and the Researcher think at `max`. A role without
hidden thinking writes a short `Reasoning:` before its JSON; a thinking model isn't asked to, and gets output room for
its reasoning (a reply cut off by the limit is retried with double room).

**Speed.** Feature values are cached per decision state (a hash chain of the choices made so far), in workers that
each keep the same instances; feature inputs are read-only views; the fit lane overlaps the agents' writing.

## The meta loop

`meta/` evolves the strategy folder with the same kind of loop. See [docs/META_V3.md](../docs/META_V3.md).
