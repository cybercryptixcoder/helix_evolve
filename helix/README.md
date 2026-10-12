# Helix: the evolution loop

Two loops of LLM agents share one evaluator. The **deep** loop works out why the best program wins and tests one idea at a time. The **wide** loop writes variants of the best programs, plus a few fresh ideas, without seeing the research (the air gap). A **tune** step polishes the numbers in the programs, so the agents can spend their effort on structure. The problem and the evaluator are described in `../CONTRACT.md` and `../evaluator/README.md`.

## Start here: the dashboard

```bash
pip install -r helix/requirements.txt
python -m helix.ui            # opens http://127.0.0.1:8765
```

1. **Connect:** pick Luminal Cloud or a local model, paste the URL, key and model, press **Test model**. MongoDB is optional. Everything is saved to `helix/.env`, which is gitignored.
2. **New run:** pick the mode and the number of generations, press **Start**. Tick *Offline test* to check the whole pipeline with a fake model at no cost.
3. **Watch:**
   - **Health:** whether the run, the model, the evaluator, MongoDB and the optimal-packing bounds are connected and working.
   - **Tiles:** progress to optimal, extra bins vs the optimal packing, the evaluator's own score (the unit of earlier runs), and the lead over the best classic heuristic.
   - **The loop:** a live flowchart of the current generation. The step that's running pulses, with counts (for example, Coder 3/4). Pick any past generation with the arrows. Click a step to see what it did in that generation: the Researcher's hypotheses, each test's verdict and code diff, the Mutator's variants, tuned programs, everything scored, and the pool going in and out. Click a row for the program's code, or for an agent call's full prompt, reply and reasoning.
   - **Progress:** best program by generation or by minutes, in either unit, against the yardsticks (Code Zero, the best classic heuristic, an offline packer, the optimum). Add up to three earlier runs to compare; a table lines them up at the same generation.
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
| `python -m helix.run --generations 30` | The full algorithm |
| `python -m helix.run --fake-llm --generations 3` | Offline test of the whole pipeline, no keys needed |
| `python -m helix.run --mode wide-only` / `deep-only` | Controls: one loop only |
| `python -m helix.run --mode zero-shot --n 40` | Control: best of N plain answers, no search |
| `python -m helix.run --resume helix/runs/<run> --generations 40` | Continue a stopped run up to generation 40 |
| `python -m helix.analyze [helix/runs/<run>]` | Diagnose a run: cut-off calls, whether wide makes variants, whether deep's tests move the score, pool memory, headroom by family |
| `python -m helix.peek [helix/runs/<run>]` | Text snapshot of a run |
| `python -m helix.report helix/runs/<run> [more runs]` | Held-out check, charts, research log |
| `python -m helix.publish helix/runs/<run> [--report] [--push]` | Copy the trace into `results/<run>/` |
| `python -m helix.bounds [--compute]` | The optimal-packing bounds, by family |
| `python -m helix.reference` | The offline packer's score on train and test |
| `python -m helix.tune programs/tuned_params.py` | Tune one program's numbers |
| `python -m helix.sandbox programs/code_zero.py` | Score one program by hand |

Main options (defaults in brackets):
- **Wide:** `--variants 6` Mutator programs per generation, of which `--fresh 2` are fresh ideas; `--top-x 4` programs the Mutator works from.
- **Deep:** `--hypotheses 4` per generation; `--epsilon 0.05` smallest score change judged supported or refuted; `--jump 0.15` gain that earns a new champion knock-out tests; `--stall 3` generations without progress before the search pushes for bigger changes; `--judge-tune-evals 16` evaluations spent tuning a test's new numbers before it's judged.
- **Tune:** `--tune/--no-tune` (on in full mode), `--tune-evals 48`, `--tune-targets 2`, `--tune-seconds 40`.
- **Pool:** `--pool-size 8`, `--max-siblings 3`.
- **Run:** `--max-minutes`, `--workers 12`, `--pro-every 10`.

To stop a command-line run cleanly, create a file called `STOP` in its run folder.

## One generation

The branches run at the same time, from the same pool.

1. **Pool:** the best `--pool-size` programs found so far, with at most `--max-siblings` children of one parent. Selection is (μ+λ): the old pool and everything new compete on score, so good programs aren't forgotten.
2. **Deep** (`researcher`, then `coder`):
   - The Researcher studies the **champion** (the best program). It sees:
     - what changed from the champion's parent;
     - knock-out results on the champion and its ancestors;
     - where the real room is: each family's excess minus the optimum's;
     - the other pool programs and the research log.
   - It proposes **cause** tests (knock-outs, only on a champion that jumped by `--jump` and only on its new parts) and **improve** tests (one new mechanism each).
   - The Coder writes each test. An improve test's new numbers are tuned before it's judged (**tune-then-judge**), so a new idea is compared at a good weight, not at a guessed one. In run 2, five of the eight near-miss tests on the stuck champion would have beaten it this way.
   - After `--stall` generations without a structural gain, the Researcher is told small edits are exhausted, and the Mutator gets an extra fresh-idea slot.
3. **Wide** (`mutator`): from only the top programs' code and scores, the Mutator writes **variants** (keep the core, make one or two bold changes) and a few **fresh ideas**.
4. **Tune:** a local search over the numeric constants of the champion and of the best untuned newcomer. A tuned program joins the pool if it gains `--tune-margin`.
5. **Merge** into the next pool.

Generation 0 is Code Zero plus one wide batch. Each candidate is checked on the evaluator's tiny `quick` split before the full `train` split, and a failed program gets one repair attempt with its error.

**The air gap is enforced in code.** `roles.mutator_message` only accepts `Scored(code, score)` objects and raises an error on anything else, so the Mutator can't see hypotheses or the research log.

### Keeping calls short and reliable

Run 2 lost most of its LLM time to replies that never answered: with thinking switched off, the model still slipped into hidden reasoning in 102 of 186 Mutator calls and ran to the token limit. Now:

- Every role has its own output limit (Mutator 4,000 tokens, Coder 4,000, Researcher 6,000).
- A streamed reply that has produced only hidden reasoning for too long is cut short at once.
- The Mutator and Coder write code first. A reply without a program gets one retry asking for only the code, showing the agent what it had written so the idea isn't lost.
- The Researcher writes its JSON first. Hypotheses it finished are kept even if the reply is cut off, and a reply with none gets one JSON-only retry.
- Overload (HTTP 429/503) halves the number of calls in flight and recovers gradually; a model that isn't answering is waited for before a generation is spent on it.

`python -m helix.analyze` shows how often each of these still happens in a run.

## Traces and published results

Every run writes everything as it happens to `helix/runs/<run>/` (gitignored):

| File | Contents |
|---|---|
| `llm_calls.jsonl` | Every prompt and reply, the model's reasoning, tokens, seconds, why it ended, and the generation, program and hypothesis it belongs to |
| `programs.jsonl` | Every program: code, scores per family, branch, parent, hypothesis |
| `hypotheses.jsonl` | The research log, with verdicts, score change as written and after tuning, and which families moved |
| `generations.jsonl` | Each generation's pool, best program, branch results, timing and LLM usage |
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
| `run.py` | The loop, the controls, live status, stop and resume |
| `roles.py` | Builds each agent's message and parses its reply |
| `prompts/*.md` | The system prompts: `mutator`, `researcher`, `coder`, `zeroshot`, and the shared `problem` statement |
| `llm.py` | Model client: Luminal or local, per-role limits, streaming, retries, call log, offline fake |
| `tune.py` | Finds a program's tunable numbers and runs the local search |
| `bounds.py`, `bounds.json` | Bounds on the optimal packing of every instance |
| `metrics.py` | The readable units and the yardsticks |
| `reference.py`, `references/` | The offline packer, and the classic online heuristics |
| `analyze.py` | Run diagnostics |
| `sandbox.py` | Runs the evaluator on a candidate in its own process, with a timeout |
| `population.py` | Programs, hypotheses, and the run folder on disk |
| `mongo.py` | Optional MongoDB mirror |
| `peek.py` | Reads a run's live state; text snapshots |
| `report.py` | Held-out check, report and charts |
| `publish.py` | Copies a run's trace into `results/` and optionally pushes it |
