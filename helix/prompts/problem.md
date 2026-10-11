# The problem: online 2D vector bin packing

Jobs arrive one at a time. Each job needs some CPU and some memory. Every bin (think of it as a machine) has the same capacity in both resources. Each job must be placed immediately and permanently, before the next job is seen: either into an open bin that still has enough CPU **and** enough memory, or into a new bin. Jobs never leave. The goal is to use as few bins as possible.

You don't write the packing loop. You write one function that scores the candidate bins for the arriving job, and the simulator puts the job in the highest-scoring bin.

```python
import numpy as np

def priority(item, bins, capacity):
    """
    item:     np.ndarray, shape (2,), int    demand of the arriving job, [cpu, mem]
    bins:     np.ndarray, shape (k, 2), int  remaining [cpu, mem] of every open bin the job fits in,
                                             oldest bin first. The LAST row is always a brand-new
                                             empty bin (equal to capacity).
    capacity: np.ndarray, shape (2,), int    full capacity of one bin
    returns:  np.ndarray, shape (k,), float  one finite score per row of bins. The highest score
                                             wins; on a tie the earlier row wins.
    """
```

## Rules

- Import only `numpy` and `math`. Anything else, including `typing` and `from __future__ import annotations`, makes the program invalid, so don't add type-hint imports. No file access, no randomness, no state kept between calls.
- Return exactly one finite number per row of `bins`: no NaN, no infinity. `bins - item` can be 0 in either resource, so guard any division.
- Picking the last row opens a new bin. Opening a new bin even when an old one fits is allowed, and is sometimes the right call.
- The function is called about 18,000 times per evaluation, so keep it vectorised with numpy and avoid Python loops over bins.
- Capacity is [100, 100] in training, but other capacities exist. Always work from `capacity`; never hard-code 100.

## How programs are scored

- Each program packs six families of instances, several instances per family, 1,000 jobs each:
  - `uniform`: CPU and memory independent, each 1–50
  - `correlated`: CPU and memory move together
  - `anticorr`: half the jobs are CPU-heavy, half memory-heavy
  - `small`: both 1–20
  - `large`: both 15–60
  - `bimodal`: each resource is either small or large
- For each instance, excess = bins used ÷ lower bound − 1. The lower bound is the total demand in the tighter resource divided by capacity, rounded up. No packing can beat it, but it isn't always reachable.
- **score = −(mean excess across families, in %).** Higher is better; 0 would be perfect.
