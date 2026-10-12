import numpy as np

def priority(item, bins, capacity):
    # Remaining capacity after placing the item in each candidate bin.
    rem = bins - item  # shape (k, 2), guaranteed >= 0 for feasible rows
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    k = bins.shape[0]

    # Normalized leftover per resource (guard against zero capacity).
    rem_n = rem / np.where(cap > 0, cap, 1.0)

    # Core idea: best-fit on the looser resource -> minimize max leftover.
    max_left = np.maximum(rem_n[:, 0], rem_n[:, 1])

    # Balance / anti-stranding: penalize large |leftover_c - leftover_m|.
    bal = np.abs(rem_n[:, 0] - rem_n[:, 1])

    # Reward keeping both resources usable (min leftover large).
    mn = np.minimum(rem_n[:, 0], rem_n[:, 1])

    # Slight preference to fill bins that are already fairly full in the item's
    # dominant resource direction, encouraging tight packing.
    dom = 0 if it[0] >= it[1] else 1
    fill = 1.0 - rem_n[:, dom]

    score = -max_left - 0.30 * bal + 0.20 * mn + 0.05 * fill

    # The last row is always a fresh empty bin; nudge it down so we only open
    # a new bin when no open bin is clearly better.
    if k > 0:
        score[-1] -= 0.02

    return score
