import numpy as np


def priority(item, bins, capacity):
    """Dot-product fit with a "match the item's shape" bonus.

    Core idea kept from the norm program: measure the leftover after placing
    the job, but instead of just shrinking its squared norm, reward bins whose
    leftover *shape* matches the arriving item's shape.  Placing an item into a
    bin whose residual is proportional to the item's demand keeps both
    resources draining at the same rate, which packs tightly without stranding
    a bin that has one resource fully used up.

    score = -(scaled leftover norm)  -  w * (alignment penalty)
    where the alignment term compares the leftover direction to the item's
    demand direction (normalised, so no hard-coded capacity).
    """
    residual = bins - item                      # >= 0 by construction
    cap = capacity.astype(float)

    rc = residual[:, 0] / cap[0]                # normalised leftover
    rm = residual[:, 1] / cap[1]

    # 1) Shrink the joint leftover (keeps the tightest-fitting bin).
    core = -(rc * rc + rm * rm)

    # 2) Shape-matching bonus: prefer leftovers whose ratio mirrors the item.
    ic = item[0] / cap[0]
    im = item[1] / cap[1]
    # normalised item direction (guard zero demand)
    inorm = np.sqrt(ic * ic + im * im)
    inorm = inorm if inorm > 0 else 1.0
    icn, imn = ic / inorm, im / inorm

    rnorm = np.sqrt(rc * rc + rm * rm)
    rnorm = np.where(rnorm > 0, rnorm, 1.0)
    rcn, rmn = rc / rnorm, rm / rnorm

    # cosine similarity in [0, 1]; 1 means leftover points the same way as item
    align = rcn * icn + rmn * imn

    return core + 0.5 * align
