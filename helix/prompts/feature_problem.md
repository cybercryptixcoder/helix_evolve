# The problem: online 2D vector bin packing

Jobs arrive one at a time. Each job needs some CPU and some memory. Every bin (think of it as a machine) has the same capacity in both resources. Each job must be placed immediately and permanently, before the next job is seen: either into an open bin that still has enough CPU **and** enough memory, or into a new bin. Jobs never leave. The goal is to use as few bins as possible.

For each arriving job the simulator scores the candidate bins and puts the job in the highest-scoring one (on a tie, the oldest bin). The score is a **weighted sum of features**:

    priority(bin) = w1 * feature1(bin) + w2 * feature2(bin) + ...

Agents write the features. An optimiser fits the weights, including their signs, on the training instances. A new feature is tried by searching its own weight with the rest of the policy fixed, and kept only if the policy then also does better on separate validation instances and the gain doesn't just repeat what other kept features already give. Your job is never to choose numbers: it is to find **measurements of a candidate bin that tell the optimiser something it can't yet see**.

## A feature

```python
import numpy as np

def feature(item, bins, capacity):
    """One line: what this measures."""
    ...
    return values   # np.ndarray, shape (k,): one number per row of bins
```

- `item`: shape (2,), int, the arriving job's [cpu, mem]. `bins`: shape (k, 2), int, the remaining [cpu, mem] of every open bin the job fits in, oldest first; **the last row is always a brand-new empty bin** (equal to capacity). `capacity`: shape (2,), int.
- Return one finite number per row, roughly between -1 and 1 (normalise by `capacity`; the optimiser rescales anyway). Guard every division and log: `bins - item` can be 0.
- Import only `numpy` and `math`. No state between calls, no randomness, don't modify the inputs, no Python loops over bins (it's called about 18,000 times per evaluation; keep it vectorised).
- Capacity is [100, 100] in training but other capacities exist: always work from `capacity`.
- A feature can be conditional: for example, nonzero only for lopsided jobs, or only for bins that would end up nearly full. Conditions are how a linear sum expresses "do this in that situation".

## How policies are scored

- Six families of instances, 1,000 jobs each: `uniform` (CPU and memory independent, 1-50), `correlated`, `anticorr` (half the jobs CPU-heavy, half memory-heavy), `small` (1-20), `large` (15-60), `bimodal` (each resource either small or large).
- Excess = bins used ÷ a simple lower bound − 1, averaged per family; score = −(mean excess across families, in %). Higher is better.
- The simple bound ignores job shapes. The best packing that could exist is only a little above it (about 2.4% on anticorr, under 1% elsewhere), so almost all of the excess is avoidable.
