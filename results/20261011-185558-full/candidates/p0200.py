import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placement.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Bottleneck after placement: the resource that will bind next.
    weak = np.minimum(Lc, Lm)

    # Tightness of fit in the binding dimension (as before).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Anti-alignment: item heavy on cpu wants bin rich on mem, etc.
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]
    anti = (dc - dm) * (Lm - Lc)

    # Balance: even leftovers are more reusable.
    bal = -np.abs(Lc - Lm)

    # Preserve the bottleneck: this is the key resource for the lower bound.
    # Concave in weak so a bin with tiny weak is heavily penalised.
    keep = np.sqrt(np.clip(weak, 0.0, None))

    # Loose-bin penalty: a bin whose larger leftover is huge is wasted space.
    loose = -np.maximum(Lc, Lm)

    # New-bin penalty scaled by how good the best open bin's bottleneck is.
    used = 0.5 * (dc + dm)
    used = min(max(used, 0.0), 1.0)
    open_weak = keep[:-1].max() if bins.shape[0] > 1 else 0.0
    new_pen = (0.22 - 0.14 * used) * (1.0 - open_weak)

    score = (1.10 * fit
             + 0.55 * keep
             + 0.45 * anti
             + 0.40 * bal
             + 0.30 * loose)

    score[-1] -= new_pen

    return score
