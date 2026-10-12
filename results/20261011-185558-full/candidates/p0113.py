import numpy as np

def priority(item, bins, capacity):
    bins = np.asarray(bins, dtype=float)
    item = np.asarray(item, dtype=float)
    cap = np.asarray(capacity, dtype=float)

    a, b = item[0], item[1]
    Lc = bins[:, 0]
    Lm = bins[:, 1]

    # Pre-placement capacity of each bin (remaining + item).
    x = Lc + a
    y = Lm + b

    # Fit term: how much of the bin's capacity the item consumes in its
    # tighter resource. 1 = perfectly snug, small = item is negligible.
    fit = np.minimum(a / np.maximum(x, 1e-9),
                     b / np.maximum(y, 1e-9))

    # Balance term: reward residuals that are close to square, so the bin
    # stays useful for both CPU-heavy and memory-heavy arrivals.
    hi = np.maximum(Lc, Lm)
    lo = np.minimum(Lc, Lm)
    bal = lo / np.maximum(hi, 1e-9)

    # Product of experts, kept at a stable scale via geometric mean.
    score = np.sqrt(np.maximum(fit, 0.0) * np.maximum(bal, 0.0))

    # Small tie-breaker: prefer snugger fits when products are equal, and
    # give the empty bin a tiny nudge so it is never chosen needlessly.
    score = score + 1e-6 * fit

    return score
