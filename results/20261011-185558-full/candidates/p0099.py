import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)

    k = b.shape[0]
    eps = 1e-9

    # Residuals after placing the item in each bin
    rem = b - it
    rem = np.maximum(rem, 0.0)

    # Normalized residuals
    nc = rem[:, 0] / (cap[0] + eps)
    nm = rem[:, 1] / (cap[1] + eps)

    # Aggregate scarcity of each resource across currently open bins
    # (lower mean residual => scarcer resource)
    ac = float(np.mean(b[:, 0])) / (cap[0] + eps)
    am = float(np.mean(b[:, 1])) / (cap[1] + eps)

    # Weights: scarce resource gets more weight so we avoid stranding it
    wc = 1.0 + (1.0 - ac)
    wm = 1.0 + (1.0 - am)
    s = wc + wm
    wc /= s
    wm /= s

    # Weighted residual "left over" — smaller is better
    waste = wc * nc + wm * nm

    # Balance term: penalize imbalance in the leftover bin
    balance = np.abs(nc - nm)

    # Fit tightness: how much of the bin's remaining capacity we consume
    # (only meaningful for bins that actually fit; others won't be chosen
    # since simulator only passes fitting bins, but guard anyway)
    used_c = it[0] / (b[:, 0] + eps)
    used_m = it[1] / (b[:, 1] + eps)
    tight = wc * (1.0 - used_c) + wm * (1.0 - used_m)

    # The last row is the fresh empty bin; give it a mild bonus so we prefer
    # opening a new bin over badly fragmenting an existing one.
    fresh_bonus = np.zeros(k)
    fresh_bonus[-1] = 0.02

    score = -(waste + 0.35 * balance + 0.25 * tight) + fresh_bonus

    # Ensure finite
    score = np.where(np.isfinite(score), score, -1e9)
    return score
