import numpy as np


def priority(item, bins, capacity):
    """Best-fit by normalized leftover: reward tight fits, weight the binding resource."""
    cap = capacity.astype(float)
    it = item.astype(float)

    rem = bins.astype(float)
    after = rem - it  # >= 0 in both resources for rows that fit

    # Normalized leftover fraction in each resource after placing.
    frac = after / cap
    np.clip(frac, 0.0, None, out=frac)

    # The tighter resource is the one with less relative slack; weight it more.
    # Weight per resource: smaller leftover fraction -> more important.
    w = 1.0 / (frac + 0.05)  # shape (k,2), large when a resource is nearly full
    # Score: prefer leaving small, balanced slack -> negative weighted leftover.
    score = -(w[:, 0] * frac[:, 0] + w[:, 1] * frac[:, 1])

    # Mild bonus for using a bin whose orientation matches the item's dominant demand,
    # so CPU-heavy jobs prefer CPU-tight bins and vice versa.
    item_dom = np.where(it[0] >= it[1], 0, 1)
    tight = np.argmin(frac, axis=1)
    score += 0.05 * (tight == item_dom)

    return score
