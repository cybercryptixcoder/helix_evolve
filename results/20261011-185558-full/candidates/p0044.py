import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)

    # leftover after placement, normalized
    left = np.clip(rem - it, 0.0, None) / cap_safe
    lc = left[:, 0]
    lm = left[:, 1]

    # 1) Balance: reward leftover vectors that are equal in both resources.
    #    A bin that stays balanced can accept both CPU-heavy and mem-heavy jobs.
    balance = -np.abs(lc - lm)

    # 2) Compactness: prefer leaving little total room (consolidate).
    compact = -(lc + lm)

    # 3) Usability floor: a bin is valuable only if it keeps a workable amount
    #    of BOTH resources (not one near zero). Penalize the weaker side.
    weaker = np.minimum(lc, lm)
    usable = np.minimum(weaker * 2.0, 1.0)  # saturates; avoids over-reward

    score = 1.0 * balance + 0.0 * compact + 0.35 * usable

    # New-bin penalty scaled by how badly we'd waste the fresh bin.
    score[-1] -= 0.04

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
