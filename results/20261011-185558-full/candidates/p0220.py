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

    # Binding-dimension tightness.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance of leftover.
    bal = -np.abs(Lc - Lm)

    # Small leftover area (well filled).
    geom = -np.sqrt(Lc * Lm)

    # Keep the weaker resource usable.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Reward both leftovers being at least half a bin.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # NEW: directional complementarity. If the item is CPU-heavy it leaves
    # memory behind (good for future memory-heavy jobs), so reward leaving
    # the *other* resource large. sign = which resource the item stressed.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = np.clip(d0 - d1, -1.0, 1.0)
    comp = skew * (Lm - Lc)          # heavy in cpu -> want big Lm

    # Also value a residual that is itself balanced but not tiny:
    # a "breathing room" term peaking near half a bin in both resources.
    breath = (1.0 - np.abs(2.0 * Lc - 1.0)) * (1.0 - np.abs(2.0 * Lm - 1.0))

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit
             + 0.90 * bal
             + 0.50 * geom
             + 0.35 * usable
             + 0.15 * accept
             + 0.40 * np.abs(skew) * comp
             + 0.20 * breath)

    # Fresh-bin penalty: strong for narrow jobs (should reuse), weak for
    # wide jobs that barely fit anywhere.
    score[-1] -= (0.20 - 0.16 * used)

    return score
