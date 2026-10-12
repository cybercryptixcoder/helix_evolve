import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # post-placement residuals (guarded against negatives from float noise)
    post = rem - it
    post = np.maximum(post, 0.0)

    # normalized residuals
    rc = post[:, 0] / cap[0]
    rm = post[:, 1] / cap[1]

    # bottleneck residual: how tight the tighter dimension is after placing
    bottleneck = np.minimum(rc, rm)

    # balance: prefer bins whose post-placement residuals are similar (square leftover)
    balance = 1.0 - np.abs(rc - rm)

    # shape complementarity: item's heavy dimension should land where bin has room
    ic = it[0] / cap[0]
    im = it[1] / cap[1]
    dot = ic * rc + im * rm

    # how much usable slack remains overall
    usable = rc + rm

    score = 1.05 * bottleneck + 0.90 * balance + 0.50 * dot + 0.35 * usable

    # strongly prefer the fresh empty bin only when it's genuinely better shaped
    score = np.where(score != score, 0.0, score)
    return score
