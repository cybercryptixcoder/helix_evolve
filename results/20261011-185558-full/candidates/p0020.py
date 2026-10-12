import numpy as np


def priority(item, bins, capacity):
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap = np.asarray(capacity, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)

    after = np.maximum(rem - it, 0.0)

    # Normalized post-placement leftover per resource.
    a = after[:, 0] / cap_safe[0]
    b = after[:, 1] / cap_safe[1]

    # Tightness: small leftover is good (both resources).
    tight = np.maximum(a, b) + 0.35 * (a + b)

    # Alignment: leftover shape parallel to the item's demand direction is good,
    # because future similar jobs can slot in without wasting the other resource.
    nd = np.sqrt(a * a + b * b) + 1e-9
    if it[0] + it[1] > 0:
        ixn = it[0] / (it[0] + it[1])
        iyn = it[1] / (it[0] + it[1])
    else:
        ixn = iyn = 0.5
    align = (a * ixn + b * iyn) / nd

    score = -(tight + 0.45 * (1.0 - align))

    # Mild penalty for opening a fresh bin so we consolidate when possible.
    score[-1] -= 0.04

    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return score
