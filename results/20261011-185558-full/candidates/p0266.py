import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Normalised demand of the arriving item.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    # Binding-dimension tightness: prefer the bin the item nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Leftover balance (prefer even leftover).
    bal = -np.abs(Lc - Lm)

    # Small leftover area (well-filled bin).
    geom = -np.sqrt(Lc * Lm)

    # Keep the weaker resource usable for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # --- The new idea: resource-aware complementarity. ---
    # If the item is CPU-heavy (d0 > d1), it should go where memory is the
    # slack resource; if memory-heavy, where CPU is slack.  This matches the
    # item's skew against the bin's leftover skew instead of just penalising
    # imbalance, which is what strands resources on anticorr/bimodal.
    item_skew = d0 - d1
    bin_skew = Lm - Lc  # positive when memory is the larger leftover
    comp = np.clip(item_skew * bin_skew, -1.0, 1.0)

    # Discount the fresh bin more strongly for small jobs, weakly for big ones.
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.05 + 0.25 * used) * fit
             + 0.85 * bal
             + 0.45 * geom
             + 0.35 * usable
             + 0.30 * comp)

    score[-1] -= 0.16 - 0.12 * used

    return score
