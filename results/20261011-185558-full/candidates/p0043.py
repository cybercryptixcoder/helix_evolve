import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)

    left = np.clip(rem - it, 0.0, None) / cap_safe
    lc = left[:, 0]
    lm = left[:, 1]

    # Fit: how well the item's shape matches the bin's remaining shape.
    # A bin rich in the resource the item needs most is preferred.
    itn = it / cap_safe
    need = itn / np.maximum(itn.sum(), 1e-9)  # item's resource mix, sums to 1
    fit = need[0] * lc + need[1] * lm

    # Balance: penalize very lopsided residuals (hard to reuse later).
    balance = -np.abs(lc - lm)

    # Consolidation: prefer leaving less total room.
    compact = -(lc + lm)

    # Usability: saturating reward for a workable weaker side.
    weaker = np.minimum(lc, lm)
    usable = np.minimum(weaker * 2.0, 1.0)

    score = 1.10 * fit + 0.85 * balance + 0.70 * compact + 0.35 * usable

    # New-bin penalty: scale with how much of a fresh bin the item would leave
    # unused (waste). Small items shouldn't force new bins; big ones may.
    waste = 1.0 - (itn.sum() * 0.5)
    score[-1] -= 0.05 + 0.15 * waste

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
