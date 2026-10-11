"""Online 2D vector bin packing: the simulator.

Follows CONTRACT.md Level 1 exactly; only the bookkeeping is faster
(a preallocated array instead of growing one with vstack).
"""
import math

import numpy as np


# ---------------------------------------------------------------- instances
# Each generator takes (rng, n) and returns an (n, 2) int array of [cpu, mem].

def _uniform(rng, n):
    return rng.integers(1, 51, (n, 2))

def _correlated(rng, n):
    cpu = rng.integers(5, 46, n)
    mem = np.clip(np.rint(cpu + rng.normal(0, 5, n)), 1, 100)
    return np.stack([cpu, mem], 1)

def _anticorr(rng, n):
    heavy = rng.integers(30, 61, n)
    light = rng.integers(5, 21, n)
    cpu_heavy = rng.permutation(np.arange(n) < n // 2)  # exactly half, shuffled
    return np.stack([np.where(cpu_heavy, heavy, light), np.where(cpu_heavy, light, heavy)], 1)

def _small(rng, n):
    return rng.integers(1, 21, (n, 2))

def _large(rng, n):
    return rng.integers(15, 61, (n, 2))

def _bimodal(rng, n):
    big = rng.random((n, 2)) < 0.5
    return np.where(big, rng.integers(35, 61, (n, 2)), rng.integers(1, 16, (n, 2)))

def _lognormal(rng, n):  # held out: heavy-tailed
    return np.clip(np.rint(np.exp(rng.normal(math.log(15), 0.8, (n, 2)))), 1, 80)

def _wide(rng, n):  # held out: bins are [100, 200], not square
    return np.stack([rng.integers(1, 51, n), rng.integers(1, 101, n)], 1)

# family -> (generator, capacity)
FAMILIES = {
    "uniform": (_uniform, [100, 100]),
    "correlated": (_correlated, [100, 100]),
    "anticorr": (_anticorr, [100, 100]),
    "small": (_small, [100, 100]),
    "large": (_large, [100, 100]),
    "bimodal": (_bimodal, [100, 100]),
    "lognormal": (_lognormal, [100, 100]),
    "wide": (_wide, [100, 200]),
}

TRAIN_FAMILIES = ["uniform", "correlated", "anticorr", "small", "large", "bimodal"]
HELD_OUT_FAMILIES = ["lognormal", "wide"]

# split -> (seed, families, instances per family, items per instance)
SPLITS = {
    "train": (1, TRAIN_FAMILIES, 3, 1000),
    "test": (2, TRAIN_FAMILIES + HELD_OUT_FAMILIES, 3, 1000),
    "quick": (3, TRAIN_FAMILIES, 1, 100),
}


def make_instance(family, split_seed, index, n_items):
    gen, capacity = FAMILIES[family]
    rng = np.random.default_rng([split_seed, list(FAMILIES).index(family), index])
    items = gen(rng, n_items).astype(np.int64).tolist()
    return {
        "id": f"{family}-{index:03d}",
        "family": family,
        "capacity": list(capacity),
        "items": items,
        # Worked out here, before any candidate code runs, so a program can't change it.
        "lower_bound": lower_bound(items, capacity),
    }


def load_split(split):
    """All instances of a split, in a fixed order. Same split -> same instances, always."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}, expected one of {list(SPLITS)}")
    seed, families, per_family, n_items = SPLITS[split]
    return [make_instance(f, seed, i, n_items) for f in families for i in range(per_family)]


# ---------------------------------------------------------------- simulator
def lower_bound(items, cap):
    """No packing can use fewer bins: total demand / capacity, per resource, rounded up.
    Plain integer arithmetic, so it is exact and doesn't depend on numpy or math."""
    totals = [sum(int(item[d]) for item in items) for d in range(2)]
    return max(-(-totals[d] // int(cap[d])) for d in range(2))


def run_instance(instance, priority):
    cap = np.asarray(instance["capacity"], dtype=np.int64)
    items = np.asarray(instance["items"], dtype=np.int64)
    remaining = np.empty((len(items), 2), dtype=np.int64)  # one row per open bin, oldest first
    n_open = 0

    for item in items:
        fit_idx = np.flatnonzero(np.all(remaining[:n_open] >= item, axis=1))
        candidates = np.vstack([remaining[fit_idx], cap[None, :]])
        scores = np.asarray(priority(item.copy(), candidates.copy(), cap.copy()), dtype=float)
        if scores.shape != (len(candidates),):
            raise ValueError(f"priority returned shape {scores.shape}, expected ({len(candidates)},)")
        if not np.all(np.isfinite(scores)):
            raise ValueError(f"priority returned NaN or infinity: {scores.tolist()[:10]}")
        choice = int(np.argmax(scores))
        if choice == len(fit_idx):  # last row = new bin
            remaining[n_open] = cap - item
            n_open += 1
        else:
            remaining[fit_idx[choice]] -= item

    totals = items.sum(axis=0)
    lb = instance.get("lower_bound") or lower_bound(instance["items"], instance["capacity"])
    return {
        "id": instance["id"],
        "family": instance["family"],
        "bins_used": n_open,
        "lower_bound": lb,
        "excess": n_open / lb - 1,
        "fill": (totals / (n_open * cap)).tolist(),
    }
