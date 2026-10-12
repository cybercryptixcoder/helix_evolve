import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)

    left = np.clip(rem - it, 0.0, None) / cap_safe
    lc = left[:, 0]
    lm = left[:, 1]

    # Geometric mean: collapses to ~0 if either resource is nearly exhausted,
    # unlike a linear floor which still rewards a one-sided bin.
    geo = np.sqrt(np.maximum(lc * lm, 0.0))

    # Balance: keep residual shape near-square so both job types fit.
    balance = -np.abs(lc - lm)

    # Compactness: prefer filling bins up (mild, avoid over-consolidation).
    compact = -(lc + lm)

    # Shape match: how well does this bin's residual direction align with the
    # item's shape? Reward bins whose remaining profile resembles the item.
    itn = it / cap_safe
    itn = itn / np.maximum(itn[0] + itn[1], 1e-9)
    remn = np.stack([lc, lm], axis=1)
    remn = remn / np.maximum(remn[:, 0] + remn[:, 1], 1e-9)[:, None]
    align = -(remn[:, 0] - itn[0]) ** 2 - (remn[:, 1] - itn[1]) ** 2

    score = 1.10 * balance + 0.50 * compact + 0.90 * geo + 0.25 * align

    # New-bin penalty: cheap when the item is large (new bin gets used well),
    # expensive when the item is tiny (we would waste a fresh bin).
    fill_frac = (it[0] + it[1]) / (cap_safe[0] + cap_safe[1])
    score[-1] -= 0.06 + 0.35 * (1.0 - min(fill_frac, 1.0))

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
