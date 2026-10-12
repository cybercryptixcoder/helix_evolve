import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rem_c = rem[:, 0]
    rem_m = rem[:, 1]
    cap_c = max(cap[0], 1.0)
    cap_m = max(cap[1], 1.0)
    it_c = max(it[0], 0.0)
    it_m = max(it[1], 0.0)

    # How much of each remaining resource this item would consume (best-fit tightness),
    # symmetric in CPU and memory; no need to pick a "binding" dimension.
    f_c = np.clip(it_c / np.maximum(rem_c, 1e-9), 0.0, 1.0)
    f_m = np.clip(it_m / np.maximum(rem_m, 1e-9), 0.0, 1.0)
    tight = f_c + f_m

    # Leftover after placement, expressed as fractions of one full bin.
    a = np.maximum(rem_c - it_c, 0.0) / cap_c
    b = np.maximum(rem_m - it_m, 0.0) / cap_m
    waste = a + b                 # consolidation: small leftover mass is good
    bal = 1.0 - np.abs(a - b)     # prefer bins whose leftovers stay proportional

    score = 0.9 * tight + 0.5 * bal - 0.8 * waste

    # Mild reluctance to open a fresh bin when an older one fits.
    score[-1] -= 0.02
    return score
