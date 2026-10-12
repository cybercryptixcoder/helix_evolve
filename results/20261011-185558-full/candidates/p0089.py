import numpy as np
import math

def priority(item, bins, capacity):
    item = np.asarray(item, dtype=float)
    bins = np.asarray(bins, dtype=float)
    cap = np.asarray(capacity, dtype=float)

    # Remaining room after placing the item (guard against zero/negative).
    rem = bins - item
    rem = np.maximum(rem, 0.0)

    # Dot-product best fit: weight each dimension by how heavily the item
    # uses it, so the tighter (heavier) resource dominates the score.
    # score = (item . rem) / (capacity . capacity)  -> prefers bins whose
    # leftover aligns with the item's heavy dimension (tight fit there).
    dot = (rem * item).sum(axis=1)
    denom = float((cap * cap).sum())
    if denom <= 0.0:
        denom = 1.0

    # Balance term: prefer leftovers that are even in the two resources,
    # which tends to leave bins "square" and reusable.
    bal = -np.abs(rem[:, 0] - rem[:, 1]) / (float(cap.sum()) + 1e-9)

    # Small term rewarding bins that actually get well-filled by the item.
    fill = (item.sum()) / (float(cap.sum()) + 1e-9)

    score = dot / denom + 0.5 * bal + 0.01 * fill
    return score
