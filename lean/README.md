# Helix (lean)

The main version of Helix: v4's core, cleaned, with every other part added back only if a test shows it helps
(`docs/LEAN_PLAN.md`). About 1,000 lines; the model client, the sandbox and the loop each fit on a screen.

## The loop

```
each round:
  1 MUTATE   `mutations` programs: each takes a parent (the best program, or one sampled from all programs by rank)
             and the model writes a better version of it (optionally shown another strong program for ideas)
  2 PLAN     `planned` experiments: the planner sees the problem, the best program, the strongest programs and the
             notes of what was tried, and plans experiments, each on a base program it chooses; a coder writes each
  3 SCORE    every new program runs from its parent's result, under a CPU limit, in its own process; code checks
             and scores the result exactly (no model judges anything)
  4 NOTE     one line per program (what it tried, what it gave) is added to the notes the planner reads
  5 RESTART  (with --restart K) a line with no gain in K rounds is frozen; a new line starts from Code Zero
```

Every program is kept, with its code, parent, idea and result. Nothing is decided by a model except what to try.

## The switches (each one tested: see the experiments)

| Switch | What it does | Default |
|---|---|---|
| `--planned K` | planned experiments per round (0: no planner) | 3 |
| `--mutations K` | mutations per round | 3 |
| `--parents best\|population` | where mutations start | population |
| `--no-inspiration` | mutations don't see another strong program | off |
| `--no-notes` | the planner gets no notes | off |
| `--path` | the planner sees the best program's ancestry: each step from Code Zero, what it tried and gained (written by code) | off |
| `--restart K` | a line that hasn't gained (by `--restart-gain`, relative; 1e-5) in K rounds is frozen and a new one starts from Code Zero; parents and bases come only from the current line | 0 (off) |
| `--budget S` | CPU seconds per program | 30 |

## Files

| Path | What |
|---|---|
| `loop.py` | the loop, its settings (`Config`) and the agents' calls |
| `prompts.py` | every prompt, and the parsers for the replies |
| `sandbox.py` | runs a program in its own process under CPU, memory and time limits; checks and scores its result |
| `archive.py` | every program, as a tree |
| `llm.py` | the model client (any OpenAI-style endpoint; Luminal's DeepSeek V4.1 Flash by default) |
| `problems/` | one file per problem: what the agents are told, Code Zero, the exact checker and scorer. `circles` (n circles in a square, sum of radii), `ac1`, `ac2`, `ac3` (the three autocorrelation inequalities; AC3 signed), `erdos` (Erdős's minimum overlap) |
| `run.py` | one run from the command line |
| `bench.py` | an experiment: arms x seeds side by side, then a report |

Each run writes: `programs.jsonl` (every program, its code and result), `calls.jsonl` (every model call, prompt and
reply), `rounds.jsonl` (one line per round), `notes.jsonl`, `constructions/` (every result), `state.json` (resume
point), and at the end `summary.json`, `best.py`, `best.npy`.

## What changed from v4

- **Memory:** v4's Atlas (a graph of findings written by a Distiller, typed links, a navigation step) is replaced by
  plain notes, written by code: one line per program. v4's journal compactor (a model call) is replaced by a rule:
  past a size limit, the oldest rounds keep only their gains. Whether a model-written memory does better is a
  separate test.
- **Fixed:**
  - the step limit was written into the problem text (200,000) whatever the run's limit was; it is now one
    parameter, used everywhere;
  - the planner read the archive while mutations were writing to it; it now reads under a lock;
  - coders saw base programs clipped at 12,000 characters, so long programs were rewritten blind; now 30,000.
- **Kept as they were:** the sandbox and machine-wide evaluation slots, rank-based parent sampling, duplicate
  detection.
- **Not carried over** (tested later, one at a time, or dropped): the "alternative" result (v4.7), side tracks and
  races (v7), the register of hills (v8), the design map (v9), the field's ideas as options and the invariant audit
  (v10), builds from nothing (v10.2).

## Running it

```bash
python -m lean.run --problem circles --out runs/lean/try --rounds 20 --budget 10
python -m lean.run --problem ac2 --param max_n=50000 --out runs/lean/ac2 --rounds 50 --budget 60
python -m lean.bench experiments/lean/e1_core.json
python -m pytest tests/test_lean.py          # crash tests (fake model); results come only from live runs
```

The key goes in `.env` at the repo root (`LUMINAL_API_KEYS=...`).
