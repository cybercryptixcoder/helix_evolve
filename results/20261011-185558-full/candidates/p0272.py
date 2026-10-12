import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing this job.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # 1) Tightness in the binding dimension: prefer nearly-filled bins.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) Residual square: the largest cube-shaped job the bin could still take.
    #    A big square residual means the bin stays broadly useful; a sliver
    #    (one dim tiny) is penalised hard. This is the key new signal.
    square = np.minimum(Lc, Lm)

    # 3) Directional complementarity: a CPU-heavy job wants memory slack and
    #    vice versa, so the leftover skew opposes the item skew.
    comp = np.clip((d0 - d1) * (Lm - Lc), -1.0, 1.0)

    # 4) Shape balance: discourage extremely lopsided residuals.
    bal = -np.abs(Lc - Lm)

    # 5) Fresh-bin toll: small jobs should avoid opening bins; large jobs may.
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.30 + 0.30 * used) * fit
             + 1.00 * square
             + 0.60 * comp
             + 0.25 * bal)

    score[-1] -= 0.30 - 0.22 * used

    return np.asarray(score, dtype=float).reshape(-1)
