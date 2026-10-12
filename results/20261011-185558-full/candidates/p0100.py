import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float).reshape(-1, 2)

    # normalized demands
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]
    d = dc - dm            # +1 => CPU-heavy, -1 => memory-heavy

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Directional best fit: weight the resource the item stresses more.
    w = 0.5 + 0.5 * d      # in [0,1]
    directional = -(w * Lc + (1.0 - w) * Lm)

    # Pairing: reward residual skew that complements the item (a CPU-heavy
    # item leaves a memory-rich bin, ready for the next memory-heavy job).
    pair = d * (Lm - Lc)

    # Balance: square items prefer square leftovers.
    bal = -np.abs(Lc - Lm)

    # Keep both leftovers breathing a little.
    small = np.minimum(Lc, Lm)
    room = np.minimum(3.0 * small, 1.0)

    score = 1.0*directional + 0.35*pair + 0.30*bal + 0.10*room

    score = np.nan_to_num(np.asarray(score, dtype=float).reshape(-1),
                          nan=0.0, posinf=1e12, neginf=-1e12)
    return score
