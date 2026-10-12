import numpy as np

def priority(item, bins, capacity):
    # Remaining capacity after placing the item in each bin.
    rem = bins - item  # shape (k, 2), guaranteed >= 0 for feasible bins

    cap = capacity.astype(float)
    d = item.astype(float)

    # Normalised leftovers.
    Lc = rem[:, 0] / cap[0]
    Lm = rem[:, 1] / cap[1]

    # Balance: penalise leaving one resource much tighter than the other.
    bal = -np.abs(Lc - Lm)

    # Complementarity: after placement, prefer the bin to become rich in the
    # resource the item is poor in.  A CPU-heavy item (d0 > d1) should end up
    # memory-rich (Lm > Lc), so reward Lm - Lc scaled by the item's skew.
    skew = (d[0] - d[1]) / (d[0] + d[1] + 1e-9)
    comp = skew * (Lm - Lc)

    # Best-fit: mildly prefer bins whose leftover matches the item's shape,
    # to avoid wasting the scarce dimension.
    fit = -(Lc * (d[0] / (d[0] + d[1] + 1e-9)) +
            Lm * (d[1] / (d[0] + d[1] + 1e-9)))

    # Total item size relative to capacity: large items care more about fit,
    # small items care more about balance/complementarity.
    size = (d[0] + d[1]) / (cap[0] + cap[1])
    w_comp = 0.45 * abs(skew)
    w_bal = 0.90 * (1.0 - size)
    w_fit = 0.35 + 0.40 * size

    score = w_bal * bal + w_comp * comp + w_fit * fit

    # Prefer using an existing bin over opening a fresh one when scores are
    # close: give a small bonus to non-empty bins (i.e. not the last row).
    k = bins.shape[0]
    if k > 1:
        score[:-1] += 1e-3

    return score
