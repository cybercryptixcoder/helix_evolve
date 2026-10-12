import numpy as np

def priority(item, bins, capacity):
    # residual free space after placing the job in each candidate bin
    residual = bins - item
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    f_c = item[0] / capacity[0]
    f_m = item[1] / capacity[1]

    # how demanding the item is (its binding dimension fraction)
    binding = np.maximum(f_c, f_m)

    # --- bald change #1: base fit is no longer pure L-infinity.
    # We still prefer the bin whose tighter leftover dimension is smallest
    # (best-fit in the binding resource), but we add a mild L1 pull so that
    # the *other* dimension is also kept tight. This breaks ties toward bins
    # that are compact in both resources rather than lopsided.
    base = -np.maximum(n_c, n_m) - 0.30 * np.minimum(n_c, n_m)

    # --- bald change #2: replace the "shape drift" penalty with an explicit
    # leftover-area term. Minimising the residual rectangle's area (n_c*n_m)
    # directly discourages wasting a big free corner that no future job fits.
    # The imbalance term is kept but folded in as the squared-difference term.
    imb = -0.52 * (n_c - n_m) ** 2
    area = -0.24 * (n_c * n_m)

    # alignment reward: leftover should point along the item's aspect ratio,
    # scaled up for demanding items (they decide the bin count).
    align = 0.32 * (n_c * f_c + n_m * f_m) * (0.5 + binding)

    return base + imb + area + align
