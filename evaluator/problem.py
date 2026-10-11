"""Online 2D vector bin packing: the simulator.

Follows CONTRACT.md Level 1 exactly; only the bookkeeping is faster
(a preallocated array instead of growing one with vstack).
"""
import math

import numpy as np


def lower_bound(items, cap):
    """No packing can use fewer bins: total demand / capacity, per resource, rounded up."""
    totals = items.sum(axis=0)
    return max(math.ceil(totals[0] / cap[0]), math.ceil(totals[1] / cap[1]))


def run_instance(instance, priority):
    cap = np.asarray(instance["capacity"], dtype=np.int64)
    items = np.asarray(instance["items"], dtype=np.int64)
    remaining = np.empty((len(items), 2), dtype=np.int64)  # one row per open bin, oldest first
    n_open = 0

    for item in items:
        fit_idx = np.flatnonzero(np.all(remaining[:n_open] >= item, axis=1))
        candidates = np.vstack([remaining[fit_idx], cap[None, :]])
        scores = np.asarray(priority(item.copy(), candidates.copy(), cap.copy()), dtype=float)
        if scores.shape != (len(candidates),) or not np.all(np.isfinite(scores)):
            raise ValueError(
                f"priority returned shape {scores.shape}, expected ({len(candidates)},) of finite numbers"
            )
        choice = int(np.argmax(scores))
        if choice == len(fit_idx):  # last row = new bin
            remaining[n_open] = cap - item
            n_open += 1
        else:
            remaining[fit_idx[choice]] -= item

    totals = items.sum(axis=0)
    lb = lower_bound(items, cap)
    return {
        "id": instance["id"],
        "family": instance["family"],
        "bins_used": n_open,
        "lower_bound": lb,
        "excess": n_open / lb - 1,
        "fill": (totals / (n_open * cap)).tolist(),
    }
