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

    # 1) Fit quality: how much of the bin's remaining capacity the item uses.
    #    A bin whose remaining shape matches the item gets a near-exact fill.
    #    Measured as the ratio of item demand to pre-placement remaining.
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fill_c = np.minimum(it[0] / rc, 1.0)
    fill_m = np.minimum(it[1] / rm, 1.0)
    # reward bins where the item fills both dimensions well
    fit = np.minimum(fill_c, fill_m)

    # 2) Balance of leftover: keeps a bin able to accept both job types.
    balance = -np.abs(lc - lm)

    # 3) Usability floor on the weaker leftover side (avoid dead bins).
    weaker = np.minimum(lc, lm)
    usable = np.minimum(weaker * 2.0, 1.0)

    # 4) Compactness: consolidate small leftover.
    compact = -(lc + lm)

    score = 1.35 * fit + 0.9 * balance + 0.35 * usable + 0.30 * compact

    # New-bin penalty: discourage opening fresh bins unless clearly needed.
    score[-1] -= 0.05

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
