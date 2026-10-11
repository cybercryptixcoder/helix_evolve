# Helix: the evolution loop

Two loops share one evaluator. The **deep** loop forms hypotheses about why programs score well and tests each one with a single-aspect change. The **wide** loop mutates the best programs with no direction, to keep the search from narrowing too early. The problem and the evaluator are described in `../CONTRACT.md` and `../evaluator/README.md`.

## Start here: the dashboard

```bash
pip install -r helix/requirements.txt
python -m helix.ui            # opens http://127.0.0.1:8765
```

1. **Connect:** pick Luminal Cloud or a local model, paste the URL, key and model names, then press **Test model**. MongoDB is optional; paste a URI and press **Test MongoDB**. Everything is saved to `helix/.env`, which is gitignored.
2. **Run:** choose the settings and press **▶ Run**. Tick *Offline test* first to check the whole pipeline with a fake model at no cost.
3. **Watch:** the page refreshes every 3 seconds. It shows:
   - the current generation and what each branch is doing right now;
   - the best score and whether it beats the bar to beat, plus LLM calls and tokens;
   - a live chart;
   - the Researcher's latest reasoning and hypotheses, and the research log with verdicts;
   - every agent call: click one for its full prompt, reply and reasoning;
   - programs, the best program, and console output.

   **Copy snapshot** copies a text summary you can paste into a chat.
4. **Selected run:**
   - **Stop after this generation** finishes cleanly; **Kill now** stops immediately.
   - **Resume** continues a stopped run.
   - **Held-out check** scores the best program against Code Zero and the baselines on the test split.
   - **Publish & push** commits the trace to `results/`.

Runs are separate processes: closing the dashboard doesn't stop a run, and reopening it picks the run back up.

## The same things from the command line

Run everything from the repo root.

| Command | What it does |
|---|---|
| `python -m helix.llm` | Check the model connection |
| `python -m helix.run --generations 20` | The full algorithm |
| `python -m helix.run --fake-llm --generations 3` | Offline test of the whole pipeline, no keys needed |
| `python -m helix.run --mode wide-only` | Control: conventional single-mutator evolution |
| `python -m helix.run --mode deep-only` | Control: research loop only |
| `python -m helix.run --mode zero-shot --n 40` | Control: best of N plain answers, no search |
| `python -m helix.run --resume helix/runs/<run> --generations 30` | Continue a stopped run up to generation 30 |
| `python -m helix.peek [helix/runs/<run>]` | Text snapshot of a run (the newest by default) |
| `python -m helix.report helix/runs/<run> [more runs]` | Held-out check, charts, research log |
| `python -m helix.publish helix/runs/<run> [--report] [--push]` | Copy the trace into `results/<run>/` |
| `python -m helix.sandbox programs/code_zero.py` | Score one program by hand |

Main options: `--top-x 4` survivors per branch, `--variants 6` Mutator programs per generation, `--hypotheses 4` per generation, `--pro-every 10` (every Nth call uses the Pro model), `--epsilon 0.4` (smallest score change counted as supported or refuted), `--schedule parallel|alternate`, `--max-minutes`, `--workers 8`. To stop a command-line run cleanly, create a file called `STOP` in its run folder.

## Model providers

- **Luminal Cloud** (default): `LUMINAL_BASE_URL`, `LUMINAL_API_KEY`, `HELIX_FLASH_MODEL`, optional `HELIX_PRO_MODEL`. Any OpenAI-style `/chat/completions` endpoint works.
- **Local model** (`HELIX_PROVIDER=local`): runs the same loop on your own machine through Ollama, LM Studio or llama.cpp. For example, `ollama pull qwen2.5-coder:7b`, then set `LOCAL_MODEL=qwen2.5-coder:7b`. Slower and weaker than a hosted model, but the loop, evaluator and logs are identical.

If a model returns its reasoning separately (`reasoning_content`), it's saved with every call and shown on the dashboard.

## One generation

1. Rank the current pool.
2. **Deep** (`researcher` then `coder`): the Researcher sees the ranked programs, their excess in each family, and the research log, and proposes hypotheses. The Coder writes one program per hypothesis, changing only that aspect of its base program. Each result is judged against its base: supported (more than `--epsilon` better), refuted, flat, invalid, or unchanged.
3. **Wide** (`mutator`): the Mutator gets only the top X programs' code and scores, and writes variants.
4. Merge the top X of each branch, plus the best program ever found, into the next pool.

Generation 0 is Code Zero plus one wide batch. With `--schedule parallel` (the default) both branches run at once from the same ranking; with `alternate`, deep runs on odd generations and wide on even ones. Each candidate is checked on the evaluator's tiny `quick` split before the full `train` split, and a failed program gets one repair attempt with its error.

**The air gap is enforced in code.** `roles.mutator_message` only accepts `Scored(code, score)` objects and raises an error on anything else, so the Mutator can't see hypotheses or the research log.

## Traces and published results

Every run writes everything as it happens to `helix/runs/<run>/` (gitignored):

| File | Contents |
|---|---|
| `llm_calls.jsonl` | Every prompt and reply, the model's reasoning, model, tokens and seconds |
| `programs.jsonl` | Every program: code, scores per family, branch, parent, hypothesis |
| `hypotheses.jsonl` | The research log, with verdicts and which families moved |
| `generations.jsonl` | Each generation's survivors, best score and LLM usage |
| `status.json` | Live state: generation, current phase, best score, errors (read by the dashboard) |
| `best_program.py`, `candidates/` | The best program so far, and every candidate as a `.py` file |
| `console.log` | Console output when started from the dashboard |

Real runs also keep **`results/<run>/`** (committed to the repo, for reviewers) up to date after every generation:
- `summary.json` with Code Zero, best score, gain and LLM usage;
- the trace files above, plus every agent call compressed into `llm_calls.jsonl.gz`;
- `snapshot.txt` and `progress.png`.

At the end of the run, the held-out report (`report.md`, `heldout.json`) is added. `results/README.md` lists every published run. Commit with **Publish & push** on the dashboard, or `python -m helix.publish <run> --push`.

With `MONGODB_URI` set, every program, hypothesis, generation and the run's status are also mirrored into MongoDB (collections `runs`, `programs`, `hypotheses`, `generations`). Writes happen in the background, so an unreachable database never slows the run; the dashboard shows the mirror's state.

## Files

| File | Purpose |
|---|---|
| `ui.py`, `dashboard.html` | The dashboard: local server and its single page |
| `run.py` | The loop, the controls, live status, stop and resume |
| `roles.py` | Builds each agent's message and parses its reply |
| `prompts/*.md` | The system prompts: `mutator`, `researcher`, `coder`, `zeroshot`, and the shared `problem` statement appended to each |
| `llm.py` | Model client: Luminal or local, Flash by default, Pro every Nth call, retries, call log, offline fake |
| `sandbox.py` | Runs the evaluator on a candidate in its own process, with a timeout |
| `population.py` | Programs, hypotheses, and the run folder on disk |
| `mongo.py` | Optional MongoDB mirror |
| `peek.py` | Reads a run's live state; text snapshots |
| `report.py` | Held-out check, report and charts |
| `publish.py` | Copies a run's trace into `results/` and optionally pushes it |
