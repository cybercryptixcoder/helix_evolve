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

    score = 1.1 * fit + 0.9 * balance + 0.35 * usable + 0.30 * compact

    # New-bin penalty: discourage opening fresh bins unless clearly needed.
    score[-1] -= 0.05

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
