import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)
    k = rem.shape[0]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # leftover fractions after placing
    Lc = np.clip((rem[:, 0] - it[0]) / cap[0], 0.0, 1.0)
    Lm = np.clip((rem[:, 1] - it[1]) / cap[1], 0.0, 1.0)

    # best-fit tightness in the binding dimension
    fit = np.minimum(it[0] / rc, it[1] / rm)

    # minimize the larger leftover (avoid wasting either dimension)
    linf = -np.maximum(Lc, Lm)

    # balance between the two leftovers
    bal = -np.abs(Lc - Lm)

    # total waste
    waste = -(Lc + Lm)

    # keep a floor of usable space in the weaker dimension
    weak = np.minimum(Lc, Lm)
    room = np.minimum(2.0 * weak, 1.0)

    score = (1.20 * fit
             + 0.70 * linf
             + 0.60 * bal
             + 0.25 * waste
             + 0.20 * room)

    # tiny tie-break: prefer the oldest, most-filled bin (earlier row) so the
    # brand-new empty bin is only chosen when it is genuinely the best fit.
    idx = np.arange(k, dtype=float)
    score = score - 1e-6 * idx

    score = np.asarray(score, dtype=float).reshape(-1)
    score = np.nan_to_num(score, nan=0.0, posinf=1e12, neginf=-1e12)
    return score
