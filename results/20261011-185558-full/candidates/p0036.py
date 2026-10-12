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

    score = 1.0 * balance + 0.75 * compact + 0.35 * usable

    # New-bin penalty scaled by how badly we'd waste the fresh bin.
    score[-1] -= 0.04

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
