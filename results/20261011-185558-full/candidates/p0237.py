import numpy as np

def priority(item, bins, capacity):
    cap = float(capacity[0])
    leftover = bins - item          # (k, 2), both columns >= 0 since job fits
    Lc = leftover[:, 0]
    Lm = leftover[:, 1]
    # normalized skew of the arriving job: +1 => CPU-heavy, -1 => memory-heavy
    d = (float(item[0]) - float(item[1])) / cap
    # tightness (best fit on the sum of leftovers) vs. complementarity bonus
    return -(Lc + Lm) + 1.5 * d * (Lm - Lc)
