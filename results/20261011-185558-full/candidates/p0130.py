import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # leftover after placement, normalized by capacity
    Lc = np.clip(rc - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rm - it[1], 0.0, None) / cap[1]

    # best-fit: item nearly fills the dimension it stresses most
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # item asymmetry: +ve => CPU-heavy, -ve => memory-heavy
    s = (it[0] - it[1]) / (it[0] + it[1] + 1e-9)

    # complementarity: reward bins whose leftover is rich in the OTHER resource
    comp = -s * (Lc - Lm)

    # total leftover: prefer tighter packings (less waste)
    waste = Lc + Lm

    # new-bin bias: the last row is always a fresh empty bin
    k = rem.shape[0]
    is_new = np.zeros(k, dtype=float)
    if k > 0:
        is_new[-1] = 1.0

    score = 3.0 * fit + 1.5 * comp - 1.0 * waste + 0.02 * is_new
    return np.asarray(score, dtype=float)
