import numpy as np

def priority(item, bins, capacity):
    """
    item:     np.ndarray, shape (2,), int    demand of the arriving job, [cpu, mem]
    bins:     np.ndarray, shape (k, 2), int  remaining [cpu, mem] of every open bin the job fits in,
                                             oldest bin first. The LAST row is always a brand-new
                                             empty bin (equal to capacity).
    capacity: np.ndarray, shape (2,), int    full capacity of one bin
    returns:  np.ndarray, shape (k,), float  one finite score per row of bins.
    """
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    cap0 = cap[0] if cap[0] > 0 else 1.0
    cap1 = cap[1] if cap[1] > 0 else 1.0

    # Remaining room AFTER placing the item, normalised by capacity.
    left = np.asarray(bins, dtype=np.float64) - it
    lc = left[:, 0] / cap0
    lm = left[:, 1] / cap1

    # Base penalty: Euclidean norm squared -> prefers bins that end up nearly full.
    base = lc * lc + lm * lm

    # Adaptive balance penalty: how lopsided is the leftover shape.
    balance = (lc - lm) * (lc - lm)

    # Item-normalised size: small arriving jobs suggest small future jobs, so a
    # versatile balanced bin is worth more; big jobs just need the tightest fit.
    s = max(it[0] / cap0, it[1] / cap1)
    if s < 0.0:
        s = 0.0
    elif s > 1.0:
        s = 1.0
    w = 1.0 - s

    score = -(base + w * balance)

    # Guard against any non-finite value creeping in.
    score = np.nan_to_num(score, nan=-1e18, posinf=-1e18, neginf=-1e18)
    return score
