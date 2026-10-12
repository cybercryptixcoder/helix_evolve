import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # normalised demand of the arriving item
    d = it / cap
    dc, dm = d[0], d[1]
    dmax = max(dc, dm)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # residual after placement, normalised
    Rc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Rm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # bottleneck and volume of leftover
    hi = np.maximum(Rc, Rm)
    lo = np.minimum(Rc, Rm)
    vol = Rc + Rm

    # tightness: how full the resulting bin is in its binding dimension
    tight = 1.0 - hi

    # fit ratio of the item into the remaining stock (both resources)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # usable capacity left for future jobs (both resources)
    usable = np.minimum(2.0 * lo, 1.0)

    # balance: penalise lopsided leftovers
    bal = 1.0 - np.abs(Rc - Rm)

    score = 0.9 * tight + 0.7 * fit + 0.6 * bal + 0.35 * usable - 0.25 * vol

    # adaptive new-bin penalty: if existing bins are still roomy, avoid
    # opening a fresh bin; big items are excused because they fit nowhere well
    leftovers = (rem[:, 0] + rem[:, 1]) / (cap[0] + cap[1])
    frag = float(np.mean(leftovers))
    new_pen = 0.15 + 0.9 * frag * (1.0 - min(max(dmax, 0.0), 1.0))

    k = rem.shape[0]
    penalty = np.zeros(k, dtype=float)
    penalty[-1] = new_pen

    out = score - penalty
    out = np.where(np.isfinite(out), out, -1e6)
    return out
