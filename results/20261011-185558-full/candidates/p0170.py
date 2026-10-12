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

    # Tightness of the binding dimension: prefer the bin the item nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Directional alignment: item's resource mix vs. the bin's leftover mix.
    # A CPU-heavy job prefers a bin whose leftover is CPU-heavy (can still absorb).
    iw = it[0] / (it[0] + it[1] + 1e-9)
    lw = Lc / (Lc + Lm + 1e-9)
    align = 1.0 - np.abs(iw - lw)          # in [0,1], peaks when shapes match

    # Future-fit: how much "room" the leftover offers as a fractional bin.
    # Use the geometric mean of leftovers, capped, so a bin with one dead
    # resource is penalised even if the other is huge.
    weak = np.minimum(Lc, Lm)
    geom = np.sqrt(Lc * Lm)
    future = 0.6 * weak + 0.4 * geom

    # Balance reward: even leftovers are reusable by both job shapes.
    bal = -np.abs(Lc - Lm)

    # Fresh-bin tax, weaker for large jobs (which need a fresh bin anyway).
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.10 * fit + 0.55 * align + 0.90 * future
             + 0.35 * bal + 0.25 * geom)

    score[-1] -= 0.17 - 0.13 * used

    return score
