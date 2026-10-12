import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Fill quality: how much of the bin is now occupied, in the tighter direction.
    fill = 1.0 - np.maximum(Lc, Lm)

    # "Sliver" penalty: large residual in one resource but tiny in the other is
    # useless for future jobs. Penalize the mismatch nonlinearly.
    hi = np.maximum(Lc, Lm)
    lo = np.minimum(Lc, Lm)
    sliver = -hi * (1.0 - np.minimum(lo / (hi + 1e-9), 1.0))

    # Compactness: residual vector length (small = snug bin).
    dist = -np.sqrt(Lc * Lc + Lm * Lm)

    # Keep the weaker resource usable for the next job.
    usable = np.minimum(2.0 * lo, 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.10 * fill + 0.85 * dist + 0.55 * sliver + 0.30 * usable)

    # Fresh bin: penalize less for large jobs (they need a fresh bin anyway).
    score[-1] -= 0.18 - 0.14 * used

    return score
