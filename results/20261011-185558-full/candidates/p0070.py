import numpy as np


def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    cap_safe = np.maximum(cap, 1.0)

    # Leftover after placement, normalized to capacity.
    left = np.clip(rem - it, 0.0, None) / cap_safe
    lc = left[:, 0]
    lm = left[:, 1]

    # Total waste: how much of the bin is left idle after placement.
    waste = lc + lm

    # Bottleneck: the resource that ends up tightest (smaller leftover).
    # A near-zero bottleneck means the bin becomes nearly useless.
    bottleneck = np.minimum(lc, lm)

    # Item-shape alignment: does the item's resource mix match the bin's
    # pre-placement remaining mix? Cosine-like but cheap and stable.
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    align = (it[0] * rc + it[1] * rm) / np.sqrt(
        (it[0] ** 2 + it[1] ** 2) * (rc ** 2 + rm ** 2) + 1e-9
    )

    # Fill fraction: fraction of each remaining resource the item consumes.
    # Reward bins where the item genuinely uses up what's there.
    fill = np.minimum(
        np.minimum(it[0] / rc, 1.0), np.minimum(it[1] / rm, 1.0)
    )

    # Opposite-resource reserve: mildly reward keeping both sides alive so
    # the bin can still host the other job type later.
    reserve = np.minimum(bottleneck * 3.0, 1.0)

    score = (
        -1.00 * waste          # consolidate aggressively
        -0.60 * (1.0 - bottleneck)  # punish dead bottleneck resource
        + 0.45 * align         # match item shape to bin shape
        + 0.30 * fill          # actually use what's in the bin
        + 0.25 * reserve       # keep bin versatile
    )

    # Slight new-bin penalty so we prefer existing fits when comparable.
    score[-1] -= 0.03

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
