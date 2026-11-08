# Helix (lean)

The main version of Helix: v4 with its Atlas memory, cleaned, at least as good as v4 by construction. Every difference from v4 is
listed in `docs/LEAN_V4.md`, with why each one is safe. About 900 lines; the model client, the sandbox and the loop
each fit on a screen.

## The loop

```
each generation:
  1 MUTATE   3 parents sampled from every earlier program (by rank, favouring programs with few children); the
             mutator writes an improved version of each, shown one other strong program for ideas
  2 PLAN     meanwhile, the planner sees the problem, the best program (code, result, last 6 steps of ancestry) and
             the Atlas's map (the tree of attempts, the findings, the last generation in full), opens up to 6 items,
             and plans 3 experiments, each on a base it chooses; a coder writes each
  3 SCORE    every new program runs from its base's result, in its own process, under CPU, memory and time limits;
             code checks and scores it (no model judges anything)
  4 DISTIL   the Distiller records what the generation taught as findings citing their programs; each finding's
             status is computed by code from its evidence's measured gains
```

The Atlas starts empty in every run. `Config(memory="none")` is v4's Control: no map, the 6 strongest programs
instead.

Every program is kept, with its code, parent, idea and result. Nothing is decided by a model except what to try.

## Problems are adapters

The core never changes per problem. A problem file (`problems/`) supplies the statement, Code Zero and the evaluator,
and may reword the system prompts for its domain (`problems/__init__.py` lists every field and its default). The
built-in problems:
- `circles`: n circles in a unit square, sum of radii, checked exactly;
- `ac1`, `ac2`, `ac3`: the three autocorrelation inequalities;
- `erdos`: Erdős's minimum overlap.

An adapter can also live outside this repository (the private VRP plug-in does): `--problem package.module`.

## Files

| Path | What |
|---|---|
| `loop.py` | the loop and its settings (`Config`) |
| `atlas.py` | the Atlas: findings, the map, the Navigator's openings, the Distiller |
| `prompts.py` | every prompt (v4's text) and the parsers for the replies |
| `sandbox.py` | runs a program in its own process under limits; checks and scores its result |
| `archive.py` | every program, as a tree |
| `llm.py` | the model client (any OpenAI-style endpoint; Luminal's DeepSeek V4.1 Flash by default) |
| `problems/` | one file per problem |
| `run.py` | one run from the command line |
| `bench.py`, `publish.py`, `recheck.py` | experiments (setups × seeds), their reports, and re-checks |

Each run writes:
- `programs.jsonl` (every program, its code and result);
- `calls.jsonl` (every model call, prompt and reply);
- `rounds.jsonl` (one line per generation);
- `constructions/` (every result);
- `state.json` (the resume point);
- at the end, `summary.json`, `best.py` and `best.npy`.

## Running it

```bash
python -m lean.run --problem ac2 --param max_n=50000 --out runs/lean/ac2 --rounds 50 --budget 30
python -m lean.run --out runs/lean/ac2 --rounds 80            # resumes, runs to generation 80
python -m pytest tests/test_lean.py tests/test_lean_v4.py     # crash tests, and lean against helix4's own code
```

The key goes in `.env` at the repo root (`LUMINAL_API_KEYS=...`).

The experiments of Nov 5-7 (`docs/LEAN_RESULTS.md`) ran on an earlier version with extra switches (notes, restarts,
the best program's path). That version is at commit `bc7475a5`.
