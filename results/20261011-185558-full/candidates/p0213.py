import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Normalised fractions of the arriving job.
    d = it / cap                      # shape (2,)
    d0, d1 = d[0], d[1]

    # Leftover after placement, normalised.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Residual waste: prefer leaving a small total leftover (tight packing).
    waste = Lc + Lm

    # Complementary matching: a CPU-heavy job should land in a memory-rich bin.
    skew = d0 - d1
    comp = skew * (Lm - Lc)

    # Balance leftover shape: penalise very lopsided residuals.
    lopsided = np.abs(Lc - Lm)

    # Prefer bins that were already fairly full (leftover small before arrival).
    pre = (rem[:, 0] / cap[0]) + (rem[:, 1] / cap[1])

    score = (-1.6 * waste
             + 0.9 * comp
             - 0.5 * lopsided
             - 0.25 * pre)

    # Fresh-bin penalty: weaker for large jobs, stronger for small ones.
    size = 0.5 * (d0 + d1)
    score[-1] -= 0.30 * (1.0 - min(max(size, 0.0), 1.0)) + 0.05

    return score
