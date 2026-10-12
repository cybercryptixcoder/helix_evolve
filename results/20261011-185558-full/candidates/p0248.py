import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip((rem[:, 0] - it[0]) / cap[0], 0.0, 1.0)
    Lm = np.clip((rem[:, 1] - it[1]) / cap[1], 0.0, 1.0)

    # Tight fit in the binding dimension (item nearly fills the tightest residual).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Shape complementarity: item skew vs residual skew.
    # If item is CPU-heavy (d0>d1), we want residual memory-heavy (Lm>Lc).
    item_skew = d0 - d1
    left_skew = Lc - Lm
    comp = -item_skew * left_skew

    # Stranding guard: punish leaving a small absolute leftover in either dim.
    # Floor scaled by capacity so it works for any size.
    floor_c = 0.12
    floor_m = 0.12
    strand = -np.minimum(np.minimum(Lc, floor_c) / floor_c, 1.0) \
             - np.minimum(np.minimum(Lm, floor_m) / floor_m, 1.0)

    # Balance of leftover (gentler than stranding).
    bal = -np.abs(Lc - Lm)

    # Reward keeping both residuals reasonably large for future jobs.
    weak = np.minimum(Lc, Lm)
    alive = np.minimum(2.0 * weak, 1.0)

    # Item size (binding dimension) drives the new-bin gate.
    binding = max(d0, d1)
    binding = min(max(binding, 0.0), 1.0)

    score = (1.10 * fit
             + 0.55 * comp
             + 0.60 * strand
             + 0.40 * bal
             + 0.30 * alive)

    # Prefer older bins for consolidation.
    idx = np.arange(len(score), dtype=float)
    score = score - 1e-6 * idx

    # New-bin gate: forbid opening a new bin for small jobs unless nothing
    # else fits (which the simulator handles separately); allow for big jobs.
    score[-1] -= 0.22 * (1.0 - binding) ** 2

    return np.nan_to_num(score, nan=-1e6, posinf=1e6, neginf=-1e6).reshape(-1)
