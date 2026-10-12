import numpy as np
import math

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    mc = rc / cap[0]
    mm = rm / cap[1]

    # leftovers after placing, fractions
    Lc = np.clip(mc - d0, 0.0, None)
    Lm = np.clip(mm - d1, 0.0, None)

    # best-fit: how fully the item occupies the tightest residual dimension
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # balance of leftover
    bal = -np.abs(Lc - Lm)

    # consolidation: prefer bins that end up well filled (small leftover area)
    geom = -np.sqrt(np.maximum(Lc * Lm, 0.0))

    # keep the weaker resource alive so the bin stays reusable
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # complementarity for skewed items: pair CPU-heavy with memory-heavy leftovers
    skew_item = d0 - d1
    skew_left = Lc - Lm
    comp = -skew_item * skew_left

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.00 + 0.40 * used) * fit
             + 0.95 * bal
             + 0.55 * geom
             + 0.30 * usable
             + 0.50 * abs(skew_item) * comp)

    # Gate on opening a fresh bin: cheaper for big / skewed jobs.
    binding = max(d0, d1)
    binding = min(max(binding, 0.0), 1.0)
    score[-1] -= 0.17 - 0.12 * used - 0.05 * binding

    # mild oldest-bin preference
    idx = np.arange(rem.shape[0], dtype=float)
    score = score - 1e-6 * idx

    return np.nan_to_num(score, nan=-1e6, posinf=1e6, neginf=-1e6).reshape(-1)
