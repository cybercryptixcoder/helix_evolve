import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    cap = np.where(cap > 0.0, cap, 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = rem[:, 0]
    rm = rem[:, 1]

    # 1) snugness: how completely the item plugs the binding dimension
    fc = it[0] / np.maximum(rc, 1e-9)
    fm = it[1] / np.maximum(rm, 1e-9)
    tight = np.minimum(np.minimum(fc, fm), 1.0)

    # residual left behind, normalised
    Lc = np.maximum(rc - it[0], 0.0) / cap[0]
    Lm = np.maximum(rm - it[1], 0.0) / cap[1]

    # 2) complementarity: a CPU-heavy item should leave memory-rich residue
    a = it[0] / cap[0]
    b = it[1] / cap[1]
    tilt = -(Lc - Lm) * (a - b)

    # 3) overall fullness: tighter bins are more "done"
    load = Lc + Lm

    score = 1.0 * tight + 0.8 * tilt - 0.2 * load

    # discourage opening a fresh bin, less so for big jobs that need one
    pen = 0.30 - 0.55 * (0.5 * (a + b))
    pen = min(max(pen, 0.02), 0.35)
    score[-1] -= pen

    return score
