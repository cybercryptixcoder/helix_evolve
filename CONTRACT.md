# Contract: problem, evaluator, loop

Version 1. Change it only by agreement, and bump `contract_version` when you do.

Three parts, each owned by one side:

| Part | Folder | Does |
|---|---|---|
| Problem | `evaluator/` | Instances and the packing simulator. Lives inside the evaluator. |
| Evaluator | `evaluator/` | Loads a candidate program, runs it on the problem, returns a score. |
| Loop | `helix/` | Writes candidate programs with LLMs and calls the evaluator. Never imports evaluator internals. |

Candidate programs, including Code Zero and the baselines, are plain files in `programs/` that follow Level 1 below.

---

## Level 1: the problem

**Online 2D vector bin packing.** Every bin has the same capacity in two resources, CPU and memory. Jobs arrive one at a time, and each must be placed immediately and permanently. A job can go into an open bin only if it fits in both resources at once; otherwise it opens a new bin. The goal is to use as few bins as possible. Jobs never leave.

### Instance

```json
{
  "id": "anticorr-003",
  "family": "anticorr",
  "capacity": [100, 100],
  "items": [[37, 12], [5, 61], [44, 9]]
}
```

- `capacity`: two positive integers, `[cpu, mem]`, the same for every bin in the instance.
- `items`: listed in arrival order. Each is `[cpu, mem]`, with integers from 1 up to the capacity in each resource.

### Candidate program: what the LLMs write

A Python file that defines one function. It may import only `numpy` and `math`. It must not keep state between calls.

```python
import numpy as np

def priority(item, bins, capacity):
    """Score every bin the arriving job could go into. The highest score wins.

    item:     np.ndarray, shape (2,), int    the job's demand [cpu, mem]
    bins:     np.ndarray, shape (k, 2), int  remaining [cpu, mem] of each bin the job fits in,
                                             oldest bin first; the LAST row is always a brand-new
                                             empty bin (equal to capacity)
    capacity: np.ndarray, shape (2,), int    full capacity of one bin
    returns:  np.ndarray, shape (k,), float  one finite score per row of bins
    """
    return np.zeros(len(bins))   # Code Zero: every score is equal, so the oldest bin wins = First Fit
```

### Simulation rules

1. For each item in order, find the open bins it fits in (enough remaining CPU and enough remaining memory).
2. Build `bins` from those bins, oldest first, then add one new empty bin as the last row.
3. Call `priority(item, bins, capacity)` with copies, so the candidate can't change the simulator's state.
4. Pick the row with the highest score. On a tie, the earlier row wins, which is what `np.argmax` does.
5. If the last row wins, open a new bin. Otherwise subtract the item from the chosen bin.
6. If the return value has the wrong shape or contains NaN or infinity, the program is invalid.

### Reference implementation

This shows the rules exactly. It's correct but not fast, and the evaluator is free to optimise it.

```python
import math
import numpy as np

def run_instance(instance, priority):
    cap = np.asarray(instance["capacity"], dtype=np.int64)
    items = np.asarray(instance["items"], dtype=np.int64)
    remaining = np.empty((0, 2), dtype=np.int64)          # one row per open bin, oldest first

    for item in items:
        fit_idx = np.flatnonzero(np.all(remaining >= item, axis=1))
        candidates = np.vstack([remaining[fit_idx], cap[None, :]])
        scores = np.asarray(priority(item.copy(), candidates.copy(), cap.copy()), dtype=float)
        if scores.shape != (len(candidates),) or not np.all(np.isfinite(scores)):
            raise ValueError(f"priority returned shape {scores.shape}, expected ({len(candidates)},) of finite numbers")
        choice = int(np.argmax(scores))
        if choice == len(fit_idx):                           # last row = new bin
            remaining = np.vstack([remaining, cap - item])
        else:
            remaining[fit_idx[choice]] -= item

    bins_used = len(remaining)
    totals = items.sum(axis=0)
    lower_bound = max(math.ceil(totals[0] / cap[0]), math.ceil(totals[1] / cap[1]))
    return {
        "id": instance["id"],
        "family": instance["family"],
        "bins_used": bins_used,
        "lower_bound": lower_bound,
        "excess": bins_used / lower_bound - 1,             # 0 = as good as the lower bound
        "fill": (totals / (bins_used * cap)).tolist(),     # average utilisation [cpu, mem]
    }
```

**Lower bound:** take the total demand in each resource divided by one bin's capacity, round up, and use the larger of the two. No packing can use fewer bins than that, so `excess` is how far a heuristic is above an unbeatable floor.

---

## Level 2: the evaluator

### Entry points

The loop only ever uses the command line. The Python function is there for convenience.

```
python -m evaluator --program PATH --split train --out RESULT.json
```

```python
evaluate(program_path: str, split: str = "train") -> dict
```

- Run from the repo root.
- The result goes to `--out`, not to stdout, because candidate programs may print things.
- Exit code 0 whenever a result file was written, including for an invalid program. Non-zero only if the evaluator itself is broken.

### Splits

| Split | Used by | Contents |
|---|---|---|
| `train` | The loop, every generation | The families below, with the train seeds. |
| `test` | Only the final report | The same families with different seeds, **plus at least one family that isn't in `train`**. The loop never calls this split. |
| `quick` (optional) | The loop, before `train` | One small instance per family, so broken programs fail in under a second. |

### Instance set: starting proposal

Three instances per family, 1,000 items each, capacity `[100, 100]`. The evaluator owner can tune these values.

| Family | Demands |
|---|---|
| `uniform` | CPU and memory independent, each uniform in 1–50 |
| `correlated` | CPU uniform in 5–45; memory = CPU + noise (σ = 5), clipped to 1–100 |
| `anticorr` | Half CPU-heavy (CPU 30–60, memory 5–20), half memory-heavy (swapped), shuffled together |
| `small` | Both uniform in 1–20 |
| `large` | Both uniform in 15–60 |
| `bimodal` | Each resource independently drawn from small (1–15) or large (35–60), 50/50 |

For the held-out family in `test`, use something heavy-tailed (for example lognormal demands clipped to 1–80) or bins that aren't square (for example capacity `[100, 200]`).

### Output

```json
{
  "contract_version": 1,
  "split": "train",
  "valid": true,
  "error": null,
  "score": -6.37,
  "excess_pct": 6.37,
  "families": {
    "uniform":  {"excess_pct": 5.90, "bins_used": 838, "lower_bound": 791, "fill": [0.93, 0.94], "instances": 3},
    "anticorr": {"excess_pct": 6.84, "bins_used": 922, "lower_bound": 863, "fill": [0.92, 0.92], "instances": 3}
  },
  "runtime_s": 1.2
}
```

(Only two families are shown here. A real result lists every family in the split.)

- Family `excess_pct` = 100 × the mean of `excess` over that family's instances. `bins_used` and `lower_bound` are totals; `fill` is the mean.
- Top-level `excess_pct` = the mean of the family values, so each family counts equally.
- **`score` = −`excess_pct`.** Higher is better and 0 is perfect. This is the one number the loop ranks on.
- The per-family breakdown is what the Researcher reasons from, so it should always be filled in for a valid program.

An invalid program returns:

```json
{
  "contract_version": 1,
  "split": "train",
  "valid": false,
  "error": "ValueError: priority returned shape (3, 2), expected (4,) of finite numbers\n  File \"candidate.py\", line 12, in priority",
  "score": null,
  "excess_pct": null,
  "families": {},
  "runtime_s": 0.4
}
```

The program is invalid if it fails to import, defines no `priority`, raises an exception, or returns a bad value on any instance. Keep `error` to the last ~20 lines of the traceback, because it gets shown to the LLM so it can fix the problem.

### Determinism and speed

- Instances come from fixed seeds, and the `train` and `test` seeds never overlap. The same program must always get the same score.
- The whole `train` split should take under about 10 seconds for an ordinary numpy heuristic, so the LLM calls, not evaluation, decide how long a run takes.
- The evaluator doesn't need to handle timeouts. The loop kills the process if it runs too long and records the program as invalid with the error `timeout`.

---

## What the loop promises

- It only sends files that define `priority` as in Level 1.
- It ranks on `score`, treats `valid: false` and timeouts as the worst possible score, and passes `error` back to the LLM.
- It never reads the `test` split during a run.
