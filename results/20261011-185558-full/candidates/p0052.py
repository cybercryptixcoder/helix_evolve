import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)

    # remaining capacity after placing the item (clip at 0 for safety)
    left = np.maximum(b - it, 0.0)
    lx = left[:, 0] / cap[0]
    ly = left[:, 1] / cap[1]
    mx = np.maximum(lx, ly)   # worst leftover dimension (binding)
    mn = np.minimum(lx, ly)   # best leftover dimension

    # item size relative to capacity: how "large" is this job overall
    size = (it[0] / cap[0] + it[1] / cap[1]) / 2.0
    size = np.clip(size, 0.0, 1.0)

    # For small items: strongly prefer tight fits (best-fit on max leftover)
    # and reward a decent min leftover. For large items: relax the fit
    # pressure since choice is limited by feasibility.
    A = 1.55 * (1.0 - 0.4 * size) + 0.1
    B = 0.55 * (1.0 - 0.3 * size) + 0.05

    score = -A * mx + B * mn

    # small tie-break: prefer fuller bins overall (smaller total leftover)
    score -= 0.05 * (lx + ly)

    # never let the brand-new empty bin dominate unfairly; keep finite
    score = np.nan_to_num(score, nan=-1e9, posinf=1e9, neginf=-1e9)
    return score
