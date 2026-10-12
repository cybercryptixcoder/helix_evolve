import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    p = it[0] / cap[0]
    q = it[1] / cap[1]

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # tight fit / shape match
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)
    # closest residual
    dist = -np.sqrt(Lc * Lc + Lm * Lm)
    # dominant residual small (tight in binding dim)
    dom = -np.maximum(Lc, Lm)
    # versatile bin
    usable = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)
    # complementarity with skew-adaptive weight
    s = p - q
    comp = s * (Lm - Lc) * (0.5 + abs(s))

    scores = (
        1.0 * fit
        + 1.0 * dist
        + 0.8 * dom
        + 0.5 * usable
        + 0.4 * accept
        + 0.6 * comp
    )
    return np.asarray(scores, dtype=float)
