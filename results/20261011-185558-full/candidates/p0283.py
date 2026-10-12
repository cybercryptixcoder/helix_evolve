import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Tightness: smaller max-normal leftover is better (well-filled bin).
    tight = -np.maximum(Lc, Lm)

    # Imbalance, concave so near-balanced bins aren't over-rewarded.
    imb = np.sqrt(np.abs(Lc - Lm) + 1e-12)

    # Room in the weak dimension (concave, saturating) for future jobs.
    weak = np.minimum(Lc, Lm)
    room = np.sqrt(np.minimum(weak, 1.0))

    # Item demand normalised.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    used = min(max(0.5 * (d0 + d1), 0.0), 1.0)

    # Multiplicative shape match: tight and balanced and roomy.
    shape = (1.0 + 0.6 * tight) * (1.0 - 0.5 * imb) * (0.4 + 0.6 * room)

    # Directional complementarity: lopsided item -> oppositely lopsided bin.
    comp = np.clip(d0 - d1, -1.0, 1.0) * np.tanh(2.0 * (Lm - Lc))

    score = shape + 0.3 * comp

    # New-bin penalty, softer for large jobs.
    score[-1] -= 0.14 - 0.10 * used

    return score
