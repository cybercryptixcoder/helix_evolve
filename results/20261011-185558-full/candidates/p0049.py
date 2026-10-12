import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    left = np.clip(rem - it, 0.0, None) / cap
    lc, lm = left[:, 0], left[:, 1]
    mx = np.maximum(lc, lm)
    mn = np.minimum(lc, lm)

    # compactness: strongly prefer small max residual (fill the binding dimension)
    score = -1.0 * mx
    # usability: keep the min residual non-trivial, saturating
    score += 0.30 * np.minimum(mn / 0.3, 1.0)
    # balance: prefer bins whose two residuals are similar
    score += 0.5 * (-(mx - mn))

    return np.asarray(score, dtype=float)
