import numpy as np

def priority(item, bins, capacity):
    cap = capacity.astype(float)
    rem = bins.astype(float)
    load = cap - rem
    it = item.astype(float)

    # complementarity: prefer bins whose current load is opposite to the item
    dot = (load * it).sum(axis=1)

    # leftover after placing, normalized by capacity
    left = rem - it
    a = np.clip(left[:, 0], 0.0, None) / cap[0]
    b = np.clip(left[:, 1], 0.0, None) / cap[1]

    # tightness: reward leaving a balanced, small remainder (consolidation)
    mx = np.maximum(a, b)
    mn = np.minimum(a, b)
    tight = -(mx + mn)          # more negative = tighter/better packed
    bal = -np.abs(a - b)        # reward balance

    # scale dot into a comparable range using total item demand
    scale = max(it.sum(), 1.0)
    comp = -dot / (scale * (cap.sum() / 2.0))

    # combine: consolidation dominates, complementarity breaks ties
    return tight + 0.5 * bal + 0.3 * comp
