import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Leftover after placing, normalised, guarded against zero.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Normalised item demand.
    u = it[0] / cap[0]
    v = it[1] / cap[1]

    # Residual shape mismatch: how far leftover aspect is from item aspect.
    # Prefer leftover that is proportionally similar to the item, so future
    # jobs of the same shape still fit snugly.
    denom = np.maximum(Lc + Lm, 1e-9)
    aspect = np.abs(Lc - Lm) / denom          # 0 = balanced, 1 = lopsided
    item_aspect = np.abs(u - v) / max(u + v, 1e-9)

    # Waste: the larger normalised leftover fraction (binding waste).
    waste = np.maximum(Lc, Lm)

    # Tight-fill: prefer the bin the item fills well (small waste).
    tight = -waste

    # Shape match: prefer leftover aspect close to item aspect.
    shape = -np.abs(aspect - item_aspect)

    # Reward keeping the *smaller* leftover usable (avoid stranding a resource).
    weak = np.minimum(Lc, Lm)
    keep = np.minimum(weak * 4.0, 1.0)

    score = 1.30 * tight + 0.55 * shape + 0.30 * keep

    # Discourage opening a fresh bin; less so for large items.
    used = 0.5 * (u + v)
    used = min(max(used, 0.0), 1.0)
    score[-1] -= 0.20 - 0.16 * used

    return score
