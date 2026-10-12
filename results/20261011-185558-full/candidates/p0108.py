import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # normalized remaining fractions
    frac = rem / np.maximum(cap, 1.0)

    # dot product: item's demand weighted by how rich the bin is in that dim
    dot = (it * frac).sum(axis=1)

    # post-placement residual (only meaningful where it fits; bins given all fit)
    resid = rem - it
    resid_frac = resid / np.maximum(cap, 1.0)

    # prefer tighter fit in the item's heavy dimension: penalize leftover room
    # weighted by the item's own shape
    tight = -(it * resid_frac).sum(axis=1)

    # small bonus for balancing the two leftovers (avoid very lopsided bins)
    balance = -np.abs(resid_frac[:, 0] - resid_frac[:, 1])

    # brand-new empty bin sits in the last row; discourage opening it unless
    # it is genuinely the best option (it has frac == 1, so dot is largest there,
    # so we subtract a modest constant to keep old bins competitive)
    score = dot + 0.5 * tight + 0.2 * balance

    # penalize the last (empty) row a little so we pack existing bins first
    score = score.copy()
    score[-1] -= 0.05 * (it.sum())

    return score
