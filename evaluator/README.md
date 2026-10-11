# Evaluator: online 2D vector bin packing

The evaluator is the part of Helix that holds the problem and scores programs. You give it a candidate program; it runs that program on a fixed set of packing instances and returns one score, plus a per-family breakdown for the Researcher to reason from. It follows [`CONTRACT.md`](../CONTRACT.md) version 1.

## Who built what

| Part | Owner | Where |
|---|---|---|
| Problem choice, evaluator, baseline programs | **KRSaivikram1** | `evaluator/`, `programs/` |
| Evolution loop (Researcher, Coder, Mutator, sandbox) | **Shreyas Naik** (cybercryptixcoder) | `helix/` |
| Contract between the two | Agreed together | `CONTRACT.md` |

## The problem in one paragraph

Jobs arrive one at a time. Each needs some CPU and some memory, and must be placed straight away into a bin (a server) that has enough of **both** left. Nothing moves later and no job leaves. The aim is to use as few bins as possible. A candidate program is a single function, `priority(item, bins, capacity)`, that scores every bin the job fits in. The simulator puts the job in the top-scoring bin, which may be a brand-new one. Finding the best packing is NP-hard, and online you can't see future jobs, so every program here is a heuristic.

## Quick start

Needs Python and numpy (tested on Python 3.13 and numpy 2.5). Always run from the repo root.

```bash
# Score a program on the training split; the result goes to the --out file
python -m evaluator --program programs/code_zero.py --split train --out result.json
```

```python
from evaluator import evaluate
result = evaluate("programs/dot_product.py", split="train")
print(result["score"], result["families"]["anticorr"])
```

The loop doesn't import the evaluator. It runs it in its own process through `helix/sandbox.py`, which also handles timeouts:

```bash
python -m helix.sandbox programs/code_zero.py train
```

The exit code is 0 whenever a result file was written, including for a broken program. The full train split takes **about 0.3–0.7 s** per program, so LLM calls, not evaluation, decide how long a run takes.

## Writing a candidate program

```python
import numpy as np

def priority(item, bins, capacity):
    # item:     [cpu, mem] of the arriving job
    # bins:     remaining [cpu, mem] of each open bin the job fits in, oldest first;
    #           the LAST row is always a brand-new empty bin
    # capacity: [cpu, mem] of one full bin
    # return:   one finite score per row; the highest wins, ties go to the earlier row
    return np.zeros(len(bins))   # all equal -> oldest bin wins = First Fit
```

- Only `numpy` and `math` can be imported.
- Don't keep state between calls.
- The bins aren't always square (one held-out family uses `[100, 200]`), so divide by `capacity` rather than hard-coding 100.

## Splits

| Split | Used by | Families | Instances | Jobs each |
|---|---|---|---|---|
| `train` | The loop, every generation | 6 training families | 3 per family | 1,000 |
| `test` | Final report only | 6 training families (new seeds) + 2 held-out | 3 per family | 1,000 |
| `quick` | The loop, to fail broken programs fast | 6 training families | 1 per family | 100 |

| Family | Job sizes [cpu, mem] | Capacity | In train? |
|---|---|---|---|
| `uniform` | Each independent, 1–50 | 100 × 100 | yes |
| `correlated` | CPU 5–45; memory = CPU + noise (σ = 5) | 100 × 100 | yes |
| `anticorr` | Exactly half CPU-heavy (30–60, 5–20), half memory-heavy, shuffled | 100 × 100 | yes |
| `small` | Each 1–20 | 100 × 100 | yes |
| `large` | Each 15–60 | 100 × 100 | yes |
| `bimodal` | Each resource small (1–15) or large (35–60), 50/50 | 100 × 100 | yes |
| `lognormal` | Heavy-tailed, median 15, clipped to 1–80 | 100 × 100 | **held out** |
| `wide` | CPU 1–50, memory 1–100 | **100 × 200** | **held out** |

Instances are generated from fixed seeds (`train` = 1, `test` = 2, `quick` = 3, combined with the family and instance number), so the same split always produces the same jobs, and train and test never overlap.

## How the score works

- **Lower bound** per instance: total CPU ÷ bin CPU and total memory ÷ bin memory, each rounded up; take the larger. No packing can use fewer bins.
- **Excess** = bins used ÷ lower bound − 1. 0% would mean as good as the bound.
- A family's `excess_pct` is the mean over its instances; the overall `excess_pct` is the mean of the families, so every family counts equally.
- **`score` = −`excess_pct`.** Higher is better. This is the one number the loop ranks on.

The bound ignores the shapes of individual jobs, so 0% isn't reachable on any family. Expect it to be loosest on `large`, where only a few jobs fit in each bin.

## Baseline results

Excess over the lower bound, so lower is better. Columns after "Overall" are per family.

**Train**

| Program | Overall | uniform | correlated | anticorr | small | large | bimodal |
|---|---|---|---|---|---|---|---|
| `code_zero` (First Fit) | **9.18%** | 5.3 | 3.7 | 19.3 | 3.8 | 15.3 | 7.7 |
| `best_fit` | **8.77%** | 4.4 | 3.5 | 18.7 | 3.8 | 15.0 | 7.4 |
| `dot_product` | **8.42%** | 4.7 | 3.5 | 17.6 | 3.1 | 14.3 | 7.4 |
| `tuned_params` | **8.01%** | 4.2 | 3.6 | 15.9 | 3.8 | 13.3 | 7.2 |

**Test** (new seeds, plus the two held-out families)

| Program | Overall | uniform | correlated | anticorr | small | large | bimodal | lognormal | wide |
|---|---|---|---|---|---|---|---|---|---|
| `code_zero` (First Fit) | **8.91%** | 6.4 | 3.9 | 18.9 | 3.4 | 14.5 | 8.4 | 10.3 | 5.5 |
| `best_fit` | **8.77%** | 5.6 | 3.7 | 19.2 | 3.8 | 14.7 | 7.8 | 10.1 | 5.2 |
| `dot_product` | **7.99%** | 5.9 | 3.9 | 18.3 | 1.9 | 13.7 | 7.9 | 7.0 | 5.3 |
| `tuned_params` | **7.39%** | 5.5 | 3.9 | 15.2 | 3.1 | 13.4 | 7.0 | 6.6 | 4.6 |

What the baselines are:

- `code_zero.py`: the contract's Code Zero. All scores are equal, so it behaves as First Fit. Every run starts here.
- `best_fit.py`: the bin with the least space left over, measured as a fraction of capacity.
- `dot_product.py`: the bin whose free space points the same way as the job's demand (Panigrahy et al., *Heuristics for Vector Bin Packing*, 2011).
- `tuned_params.py`: a fixed formula (fill, balance between CPU and memory, a near-full bonus, a small penalty for opening a new bin) whose six weights were picked by a 120-try random search on `train`. No LLM was involved.

**`tuned_params` is the bar to beat.** If evolved programs don't beat it, the loop is only tuning numbers, not finding new ideas. It also improves on both held-out families, which shows the training mix has real room to improve and that gains can carry over to unseen job types. The biggest gaps are in `anticorr` and `large`.

## Safety and failure handling

A program is marked **invalid** (`valid: false`, `score: null`) instead of crashing the evaluator when it:

- imports anything other than `numpy` or `math`, including through `__import__`;
- uses `open`, `exec`, `eval`, `compile`, `input` or `breakpoint` (these are removed);
- fails to load, has a syntax error, or defines no `priority`;
- raises an exception, or calls `exit()`;
- returns the wrong shape, or any NaN or infinity.

Other behaviour:

- Anything a program prints is discarded.
- The `error` field keeps the last 20 lines of the traceback, so it can be shown to the LLM. A wrong shape and NaN/infinity give different messages, so the model can tell which to fix.
- The program is reloaded for every instance, so nothing it stores can carry over from one instance to the next. The same program always gets the same score; this was checked by running it twice.
- Timeouts are handled by the loop (`helix/sandbox.py`, 60 s by default), not here, as the contract says.

## Files

| File | What's in it |
|---|---|
| `evaluator/problem.py` | Instance families, splits and seeds; the packing simulator; the lower bound. The simulator gives the same results as the contract's reference code. |
| `evaluator/evaluate.py` | `evaluate(program_path, split)`: loads the program safely, runs every instance, builds the result. |
| `evaluator/__main__.py` | The `python -m evaluator` command line. |
| `evaluator/__init__.py` | Exposes `evaluate`. |
| `programs/*.py` | Code Zero and the three baselines above. |

## Changing the instance set

The evaluator owner can tune the instance set (the contract allows it). Families are defined in `FAMILIES`, and split sizes in `SPLITS`, at the top of `evaluator/problem.py`. Keep the `train` and `test` seeds different, and keep at least one family in `test` that isn't in `train`. If the shape of the result JSON ever changes, bump `contract_version` in both `CONTRACT.md` and `evaluate.py`.

## Reproducing the tables

```bash
python -c "
from evaluator import evaluate
for p in ['code_zero', 'best_fit', 'dot_product', 'tuned_params']:
    print(p, *(evaluate(f'programs/{p}.py', s)['excess_pct'] for s in ['train', 'test']))
"
```

## Notes

- The commit that added `tuned_params.py` says 7.97% on train. That was before its weights were rounded to three decimals; the committed program scores 8.01%, as in the table above.
- Running the evaluator directly creates `evaluator/__pycache__/`. Don't commit it. The sandbox sets `PYTHONDONTWRITEBYTECODE`, so loop runs don't create it.
