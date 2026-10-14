# Helix: the evolution loop

Two loops of LLM agents share one evaluator. The **deep** loop studies how the best policy loses and tests one idea at a time. The **wide** loop writes variations without seeing the research (the air gap). The problem and the evaluator are described in `../CONTRACT.md` and `../evaluator/README.md`.

There are two engines:

- **Feature engine** (the default): agents write *features*, small functions that measure a candidate bin. The policy is a weighted sum of them; an optimiser (CMA-ES) fits the weights on the training instances, and separate validation instances decide which features are kept. The Researcher sees the policy's packings next to near-optimal packings of the same jobs.
- **Program engine** (`--engine programs`, version 1): agents write whole `priority()` programs, numbers included, and a tune step polishes the numbers.

Why the switch: in runs 2 and 3, agents wrote whole programs, numbers included, and judged them by scores alone; the runs stalled at 27% and 19% of the way from Code Zero to the optimal packing. Agents are better at ideas than at numbers, and they were working blind. The feature engine gives each job to the part that's good at it.

Both engines start from the same place: **generation 0 is Code Zero and nothing else**. In the feature engine the library starts empty; an empty policy scores every bin 0, so each job goes into the oldest bin it fits, which is exactly Code Zero (the run checks this). Every gain after that is the search's own, so runs of both engines are compared fairly.

## Start here: the dashboard

```bash
pip install -r helix/requirements.txt
python -m helix.ui            # opens http://127.0.0.1:8765
```

1. **Connect:** pick Luminal Cloud or a local model, paste the URL, key and model, press **Test model**. MongoDB is optional. Everything is saved to `helix/.env`, which is gitignored.
2. **New run:** pick the engine, the mode and the number of generations, press **Start**. Tick *Offline test* to check the whole pipeline with a fake model at no cost.
3. **Watch:**
   - **Health:** whether the run, the model, the evaluator, MongoDB and the optimal-packing bounds are connected and working.
   - **Tiles:** progress to optimal, extra bins vs the optimal packing, the evaluator's own score (the unit of earlier runs), and the lead over the best classic heuristic.
   - **The loop:** a live flowchart of the current generation. The step that's running pulses, with counts (for example, Coder 3/4). Pick any past generation with the arrows. Click a step to see what it did in that generation. Feature engine: the library going in (each feature's weights and importance), the packing comparison the Researcher read, its feature ideas and their verdicts, each feature's code and its gain on train and validation, and what was kept or retired. Program engine: the hypotheses, each test's code diff, the Mutator's variants, tuned programs and the pool. Click a row for the code, or for an agent call's full prompt, reply and reasoning.
   - **Progress:** best program by generation or by minutes, in either unit, against the yardsticks (Code Zero, the best classic heuristic, an offline packer, the optimum). Markers show each generation's best deep and best Mutator result. Add up to three earlier runs to compare; a table lines them up at the same generation.
4. **Controls:** **Stop** finishes the current generation; **Kill** stops at once; **Resume** continues a stopped run; **Held-out check** scores the best program on the test split; **Publish** copies the trace into `results/`.

Runs are separate processes: closing the dashboard doesn't stop a run, and reopening it picks the run back up. Published runs in `results/` can be opened and compared too.

## Units: how good is a program?

The evaluator scores a program as **−(mean excess %)**: bins used above a simple lower bound (total demand ÷ capacity), averaged over the six families. That stays the score the search optimises, so every run is comparable with earlier ones (run 2 reached −6.79). But the simple bound ignores job shapes, so even a perfect packing can't reach 0, and the number alone doesn't say how close to the best possible a program is.

So the dashboard adds two units, measured against the **optimal packing**: the fewest bins any packing could use, even one that knows every job in advance.

- **Extra bins vs optimal:** extra bins per 100 the optimal packing needs, averaged over the families. 0 = optimal; lower is better.
- **Progress to optimal:** 0% = Code Zero (first fit), 100% = the optimal packing. Higher is better.

Both come from the per-family results the evaluator already reports, so they also apply to runs made before they existed. `helix/metrics.py` has the formulas.

### The optimum, and the yardsticks

`helix/bounds.json` holds, for every train and test instance, bounds on the optimal number of bins (`python -m helix.bounds` prints them by family):

- **lower:** the configuration-LP bound (Gilmore–Gomory), computed by column generation with 2D-knapsack pricing, the classic bound behind exact bin-packing solvers. No packing can use fewer bins.
- **upper:** a real packing, built by diving on the LP solution, or by offline best-fit decreasing if that's better.

"Optimal" in the units above means the lower bound, so a program is never flattered. Recompute the bounds with `pip install highspy` and `python -m helix.bounds --compute` (minutes per instance). This is only needed if the evaluator's instances change; a fingerprint of each instance is checked, so stale bounds are never used.

The other yardsticks:

- **Classic online heuristics** (`helix/references/`): Best Fit (L1, L2, L∞), Best Fit with balance, and dot product / alignment (Panigrahy et al. 2011; the Tetris scheduler, Grandl et al. 2014). The best of them is the bar a search should clear.
- **Offline best-fit decreasing** (`helix/reference.py`): sorts all jobs biggest first. It's not online, so it's a strong practical reference, not a limit.

## The same things from the command line

Run everything from the repo root.

| Command | What it does |
|---|---|
| `python -m helix.llm` | Check the model connection |
| `python -m helix.diagnose` | Probe the model: does it answer, does it slip into hidden reasoning |
| `python -m helix.run --generations 30` | The full algorithm (feature engine) |
| `python -m helix.run --engine programs --generations 30` | The program engine (version 1) |
| `python -m helix.run --fake-llm --generations 3` | Offline test of the whole pipeline, no keys needed |
| `python -m helix.run --mode wide-only` / `deep-only` | Controls: one loop only |
| `python -m helix.run --mode zero-shot --n 40` | Control: best of N plain answers, no search |
| `python -m helix.run --resume helix/runs/<run> --generations 40` | Continue a stopped run up to generation 40 |
| `python -m helix.analyze [helix/runs/<run>]` | Diagnose a run: cut-off calls, what each branch contributed, headroom by family |
| `python -m helix.peek [helix/runs/<run>]` | Text snapshot of a run |
| `python -m helix.report helix/runs/<run> [more runs]` | Held-out check, charts, research log |
| `python -m helix.publish helix/runs/<run> [--report] [--push]` | Copy the trace into `results/<run>/` |
| `python -m helix.bounds [--compute] [--packings]` | The optimal-packing bounds by family; recompute them, or the near-optimal packings |
| `python -m helix.reference` | The offline packer's score on train and test |
| `python -m helix.sandbox programs/code_zero.py` | Score one program by hand |

Main options (defaults in brackets):
- **Both engines:** `--hypotheses 4` Researcher ideas per generation; `--variants` Mutator outputs per generation (4 features / 6 programs), of which `--fresh` are fresh ideas (1 / 2); `--max-minutes`, `--workers 12` agent calls in parallel, `--pro-every 10`.
- **Feature engine:** `--trial-evals 24` evaluations searching a new feature's own weights; `--trial-refit-evals 24` evaluations for each of its two paired refits; `--champion-refit-evals 24` evaluations refitting the champion's weights each generation; `--refit-evals 64` for the joint refit when features are kept; `--accept-margin 0.03` validation gain a feature needs (one bin saved on one of the 24 validation instances is worth about 0.017); `--max-columns 60` most weights the policy may have; `--fit-workers` CPU cores for fitting (all but one); `--no-inspect` gives the Researcher no packing comparison.
- **Program engine:** `--epsilon 0.05` smallest score change judged supported or refuted; `--jump 0.15`, `--stall 3`, `--judge-tune-evals 16`; `--tune/--no-tune`, `--tune-evals 48`, `--tune-targets 2`; `--pool-size 8`, `--max-siblings 3`, `--top-x 4`.

To stop a command-line run cleanly, create a file called `STOP` in its run folder.

## One generation of the feature engine

1. **Library:** the champion policy: the features kept so far and their fitted weights. It's written out as an ordinary `priority()` program (`features.compose`), which the unchanged evaluator scores, so both engines are compared on the same score.
2. **Inspect:** for one training instance per family, the champion's packing next to a near-optimal packing of the same jobs (`instruments.py`, from `optimal_packings.json`): jobs per bin, the most common bin make-ups by job size class, bins stranded with one resource full, room left.
3. **Deep:** the Researcher reads that comparison, the room left per family, each feature's weight and importance, and the research log. It proposes features aimed at specific structural differences, each with the number in the comparison that should move. A Coder writes each one as `feature(item, bins, capacity)`.
4. **Wide**, at the same time: the Mutator sees only the policy's code and its score. It writes variants of the policy's features (a different form, a condition, a combination) and fresh ones.
5. **Fit (started while the agents are still writing — `--overlap`, default on):** first the champion's own weights are refitted (no new feature), so fitting keeps improving the policy and that gain is credited to fitting, never to a feature. Then, as each feature is written, it is checked (it runs, returns finite values of the right shape, isn't much slower; one repair if not) and tried: a quick probe at a few strong weights of both signs (±2.0, ±0.4, ±0.1) rejects candidates that lose everywhere for a handful of evaluations; the rest get the full trial — their own weights searched with the rest fixed (a line search for a single value, CMA-ES for several, on the 12-instance `train-fast` fit set by default), then all the weights refitted twice from there with the same budget and random seed, once with the feature and once with it switched off. The feature is credited only with the difference, on the fit set and on the validation instances, which fitting never sees: 48 instances (two seeds × 4 per training family) from the evaluator's own generator.
6. **Accept:** features that gain at least `--accept-margin` on validation (and anything on train) are combined greedily, best first (`--max-combine` caps the attempts; a near-joining feature first gets a small refit with the kept set — `--combine-refit`). Then all the weights are refitted together. Features that just missed the bar get a second chance next to the kept set (`--combo`), and up to `--revisit` near-miss features from past generations are re-fitted against the new champion. Features whose removal would score better on validation are retired — but never when removal trades train away for a small validation win. The new champion is scored by the evaluator; each idea's verdict goes into the research log.

Generation 0 is Code Zero and nothing else: no agent is called and nothing is fitted. The fitting runs the evaluator's simulation in-process on a pool of worker processes, with the evaluator's own restricted builtins; features may only import `numpy` and `math`.

**Short runs are the unit of work.** A 10-generation run takes roughly ten minutes on a two-core machine; most generations are under a minute. Fit budgets (`--trial-evals 8`, `--trial-refit-evals 8`, `--champion-refit-evals 8`, `--refit-evals 16`, `--combo-evals 8`) and the fit set (`--fit-split train-fast`) are sized for that cadence. For slower, higher-fidelity runs raise those budgets and use `--fit-split train`. If a run is still climbing at generation 10, `--resume <run> --generations N` continues it with the same configuration.

**The air gap is enforced in code.** `roles.feature_mutator_message` (and `mutator_message` in the program engine) only accepts a `Scored(code, score)` object and raises an error on anything else, so the Mutator can't see the packings, the hypotheses or the research log.

## One generation of the program engine

The branches run at the same time, from the same pool.

1. **Pool:** the best `--pool-size` programs found so far, with at most `--max-siblings` children of one parent. Selection is (μ+λ).
2. **Deep:** the Researcher studies the champion (what changed from its parent, knock-out results, the room per family, the research log) and proposes cause tests (knock-outs) and improve tests. The Coder writes each test; an improve test's new numbers are tuned before it's judged.
3. **Wide:** from only the top programs' code and scores, the Mutator writes variants and a few fresh ideas.
4. **Tune:** a local search over the numeric constants of the champion and of the best untuned newcomer.
5. **Merge** into the next pool.

### Keeping calls short and reliable

Run 2 lost most of its LLM time to replies that never answered, and run 3 failed outright: the model kept slipping into hidden reasoning and running to the token limit. On Luminal, only `reasoning_effort: "none"` switches that off (a probe: 3 of 3 Mutator calls answered in about 5 s, against 0 of 3 with every other setting), so Helix sends it by default (`HELIX_THINKING=on` turns reasoning back on). Also:

- Every role has its own output limit, and a streamed reply that has produced only hidden reasoning for too long is cut short at once.
- Coders and the Mutator write code first; a reply without code gets one code-only retry.
- The Researcher writes its JSON first; finished ideas are kept even if the reply is cut off, and a reply with none gets one JSON-only retry.
- Overload (HTTP 429/503) halves the number of calls in flight and recovers gradually.

`python -m helix.analyze` shows how often each of these still happens in a run.

## Traces and published results

Every run writes everything as it happens to `helix/runs/<run>/` (gitignored):

| File | Contents |
|---|---|
| `llm_calls.jsonl` | Every prompt and reply, the model's reasoning, tokens, seconds, why it ended, and the generation, program and hypothesis it belongs to |
| `programs.jsonl` | Every program: code, scores per family, branch, parent, hypothesis. In the feature engine: each champion, and each feature's trial (the champion plus that feature, refitted; marked `trial`, never the best) |
| `features.jsonl` | Feature engine: every feature, with its code, author, verdict, gain on train and validation, weights and importance |
| `hypotheses.jsonl` | The research log, with verdicts, score change as written and after tuning, and which families moved |
| `generations.jsonl` | Each generation's best program, branch results, timing and LLM usage; in the feature engine also the library, the packing comparison and the champion's weights (which is what `--resume` continues from) |
| `status.json` | Live state: generation, what each step of the loop is doing, best score, errors |
| `best_program.py`, `candidates/` | The best program so far, and every candidate as a `.py` file |
| `console.log` | Console output when started from the dashboard |

Real runs also keep **`results/<run>/`** (committed to the repo) up to date after every generation:
- `summary.json`, including the share of the gap to the offline packer that was closed;
- the trace files above, with every agent call compressed into `llm_calls.jsonl.gz`;
- `snapshot.txt` and `progress.png`.

At the end of the run, the held-out report (`report.md`, `heldout.json`) is added.

With `MONGODB_URI` set, every program, hypothesis, generation and the run's status are also mirrored into MongoDB, in the background, so an unreachable database never slows the run.

## Files

| File | Purpose |
|---|---|
| `ui.py`, `dashboard.html` | The dashboard: local server and its single page |
| `run.py` | The program engine, the controls, live status, stop and resume |
| `evolve.py` | The feature engine's loop |
| `features.py` | Features: checking an agent's code, composing a policy into a `priority()` program |
| `fit.py` | Fitting: parallel scoring of weight vectors, CMA-ES, validation, importance |
| `instruments.py` | The packing comparison the Researcher reads |
| `roles.py` | Builds each agent's message and parses its reply |
| `prompts/*.md` | The system prompts: `feature_*` for the feature engine; `mutator`, `researcher`, `coder`, `zeroshot` and `problem` for the program engine |
| `llm.py` | Model client: Luminal or local, per-role limits, streaming, retries, call log, offline fake |
| `diagnose.py` | Probes the model connection and its reasoning settings |
| `tune.py` | Finds a program's tunable numbers and runs the local search (program engine) |
| `bounds.py`, `bounds.json`, `optimal_packings.json` | Bounds on the optimal packing of every instance, and near-optimal packings of the diagnostic instances |
| `metrics.py` | The readable units and the yardsticks |
| `reference.py`, `references/` | The offline packer, and the classic online heuristics |
| `analyze.py` | Run diagnostics |
| `sandbox.py` | Runs the evaluator on a candidate in its own process, with a timeout |
| `population.py` | Programs, hypotheses, and the run folder on disk |
| `mongo.py` | Optional MongoDB mirror |
| `peek.py` | Reads a run's live state; text snapshots |
| `report.py` | Held-out check, report and charts |
| `publish.py` | Copies a run's trace into `results/` and optionally pushes it |
