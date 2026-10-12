import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)

    Cc, Cm = cap[0], cap[1]
    xc, xm = it[0], it[1]

    # leftover space after placing the item
    rc = np.maximum(b[:, 0] - xc, 0.0)
    rm = np.maximum(b[:, 1] - xm, 0.0)
    nrc = rc / Cc
    nrm = rm / Cm

    # 1) tightness: reward bins that end up densely packed
    tight = -(nrc + nrm)
    # 2) balance: reward equal leftovers (keeps flexibility for opposite jobs)
    bal = -np.abs(nrc - nrm)
    # 3) flexibility: keep a decent minimum leftover
    flex = np.minimum(nrc, nrm)
    # 4) prefer bins that are already in use over a fresh empty bin
    fill = 1.0 - 0.5 * (b[:, 0] / Cc + b[:, 1] / Cm)

    # adapt to the arriving job's size: small jobs -> pack tight,
    # large jobs -> preserve balance / flexibility
    size = max(xc / Cc, xm / Cm)
    w_tight = 2.0 - size
    w_bal = 0.5 + 1.5 * size
    w_flex = 0.3
    w_fill = 0.4

    score = w_tight * tight + w_bal * bal + w_flex * flex + w_fill * fill
    return np.asarray(score, dtype=float)
