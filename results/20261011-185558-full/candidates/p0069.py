import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)

    # leftover after placement, normalized to capacity
    left = np.clip(rem - it, 0.0, None) / cap_safe
    lc = left[:, 0]
    lm = left[:, 1]

    # 1) Tight fill: how much of the bin's free room the item consumes,
    #    taking the weaker dimension (a bin only helps if it fits both).
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fill = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) Worst-case future fit: can a job of ~this item's size still go in?
    #    Look at leftover relative to the item's own dimensions.
    fut_c = np.minimum(lc * cap_safe[0] / max(it[0], 1e-9), 1.0)
    fut_m = np.minimum(lm * cap_safe[1] / max(it[1], 1e-9), 1.0)
    future = np.minimum(fut_c, fut_m)

    # 3) Balance of leftover: keeps the bin flexible for both job types.
    balance = -np.abs(lc - lm)

    # 4) Compactness: consolidate to leave fewer, better bins.
    compact = -(lc + lm)

    score = 1.0 * fill + 0.55 * future + 0.45 * balance + 0.30 * compact

    # Mild penalty for opening a fresh bin.
    score[-1] -= 0.045

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
