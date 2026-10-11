# Helix: the evolution loop

Two loops share one evaluator. The **deep** loop forms hypotheses about why programs score well and tests each one with a single-aspect change. The **wide** loop mutates the best programs with no direction, to keep the search from narrowing too early. The problem and the evaluator are described in `../CONTRACT.md`.

## Setup

Requires Python 3.10+ and numpy; matplotlib is optional and only used for report charts.

```bash
cp helix/.env.example helix/.env      # then fill in the Luminal URL, key and model names
python -m helix.llm                   # checks the connection: sends one tiny request per model
```

`helix/.env` is gitignored, so keys never get committed.

## Run

Run everything from the repo root.

| Command | What it does |
|---|---|
| `python -m helix.run --generations 20` | The full algorithm |
| `python -m helix.run --fake-llm --generations 3` | Offline test of the whole pipeline, no keys needed |
| `python -m helix.run --mode wide-only` | Control: conventional single-mutator evolution |
| `python -m helix.run --mode deep-only` | Control: research loop only |
| `python -m helix.run --mode zero-shot --n 40` | Control: best of N plain answers, no search |
| `python -m helix.run --resume helix/runs/<run>` | Continue a stopped run |
| `python -m helix.report helix/runs/<run> [more runs]` | Held-out check, charts, research log |
| `python -m helix.sandbox programs/code_zero.py` | Score one program by hand |

Main options: `--top-x 4` survivors per branch, `--variants 6` Mutator programs per generation, `--hypotheses 4` per generation, `--pro-every 10` (every Nth call uses the Pro model), `--schedule parallel|alternate`, `--max-minutes`, `--workers 8`.

## One generation

1. Rank the current pool.
2. **Deep** (`researcher` then `coder`): the Researcher sees the ranked programs, their excess in each family, and the research log, and proposes hypotheses. The Coder writes one program per hypothesis, changing only that aspect of its base program. Each result is judged against its base: supported, refuted, flat, invalid or unchanged.
3. **Wide** (`mutator`): the Mutator gets only the top X programs' code and scores, and writes variants.
4. Merge the top X of each branch, plus the best program ever found, into the next pool.

Generation 0 is Code Zero plus one wide batch. With `--schedule parallel` (the default) both branches run at once from the same ranking; with `alternate`, deep runs on odd generations and wide on even ones.

**The air gap is enforced in code.** `roles.mutator_message` only accepts `Scored(code, score)` objects and raises an error on anything else, so the Mutator can't see hypotheses or the research log.

## Files

| File | Purpose |
|---|---|
| `run.py` | The loop, the controls, and resume |
| `roles.py` | Builds each agent's message and parses its reply |
| `prompts/*.md` | The system prompts: `mutator`, `researcher`, `coder`, `zeroshot`, and the shared `problem` statement appended to each |
| `llm.py` | Luminal client: Flash by default, Pro every Nth call, retries, call log, offline fake |
| `sandbox.py` | Runs the evaluator on a candidate in its own process, with a timeout |
| `population.py` | Programs, hypotheses, and the run folder on disk |
| `report.py` | Report and charts after a run |

## What a run leaves behind

Each run gets a folder in `helix/runs/` (gitignored):

| File | Contents |
|---|---|
| `llm_calls.jsonl` | Every prompt and reply, with model, tokens and seconds |
| `programs.jsonl` | Every program: code, scores per family, branch, parent, hypothesis |
| `hypotheses.jsonl` | The research log, with verdicts and which families moved |
| `generations.jsonl` | Each generation's survivors, best score and LLM usage |
| `best_program.py` | The best program so far |
| `candidates/` | Every candidate program as a `.py` file |
| `report.md`, `progress.png`, `compare.png` | Written by `helix.report` |
