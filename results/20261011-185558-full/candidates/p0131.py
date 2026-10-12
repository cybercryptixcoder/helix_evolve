import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Best-fit: how completely the item fills its binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance of the resulting residual.
    bal = -np.abs(Lc - Lm)

    # Residual area (well-filled bin) and aggregate fill ratio.
    area = -Lc * Lm
    fr = np.minimum((it[0] + it[1]) / np.maximum(rc + rm, 1e-9), 1.0)

    # Keep some room in both resources for the future.
    usable = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    # NEW: complementarity.  A job that stresses one resource should land in
    # a bin that is rich in the other, so the leftover can absorb the opposite
    # (memory-heavy / cpu-heavy) jobs that appear in anticorrelated streams.
    d = it[0] / cap[0] - it[1] / cap[1]          # signed dominance of cpu
    comp = np.clip(d, -1.0, 1.0) * (Lm - Lc)     # >0 when residual opposes item

    score = (1.00 * fit
             + 0.55 * bal
             + 0.35 * area
             + 0.30 * fr
             + 0.30 * usable
             + 0.45 * comp)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.17 - 0.12 * used

    return np.asarray(score, dtype=float)
