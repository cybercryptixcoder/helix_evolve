import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # fractions of remaining that the item consumes
    fc = np.minimum(it[0] / rc, 1.0)
    fm = np.minimum(it[1] / rm, 1.0)
    fit = np.minimum(fc, fm)          # binding-dimension tightness

    # balance of leftovers
    bal = -np.abs(Lc - Lm)

    # fill: want the worst leftover small (binding dim used well)
    fill = -np.maximum(Lc, Lm)

    # usable: keep weaker resource healthy
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0*weak, 1.0)

    # complementarity: skew of item should oppose skew of leftover
    d0 = it[0]/cap[0]; d1 = it[1]/cap[1]
    skew_item = d0 - d1
    skew_left = Lm - Lc
    comp = skew_item * skew_left

    used = 0.5*(d0 + d1)

    score = (1.0 + 0.3*used)*fit + 0.85*bal + 0.6*fill + 0.35*usable + 0.3*comp
    score[-1] -= 0.12 - 0.10*used
    return score
