import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Normalised demand of the arriving job.
    d = it / cap

    # Normalised residual after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # 1) Waste: prefer the bin where total leftover is smallest (best fill).
    waste = -(Lc + Lm)

    # 2) Fit: how tightly the item fills the binding dimension.
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 3) Match: align the job's weaker resource with the bin's larger residual,
    #    so a CPU-heavy job prefers a memory-rich leftover bin and vice versa.
    skew_item = d[0] - d[1]
    skew_bin = Lc - Lm
    match = -np.abs(skew_item - skew_bin)

    # 4) Usable: keep the weaker residual reasonably large for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # 5) Balance: even leftovers are easier to fill later.
    bal = -np.abs(Lc - Lm)

    score = 1.20 * waste + 0.55 * fit + 0.45 * match + 0.30 * usable + 0.20 * bal

    # New-bin handling: only open a fresh bin when the best open bin leaves
    # dangerously little headroom in the weaker resource.
    used = 0.5 * (d[0] + d[1])
    used = min(max(used, 0.0), 1.0)
    if bins.shape[0] > 1:
        best_open_weak = np.max(weak[:-1]) if bins.shape[0] > 1 else 0.0
    else:
        best_open_weak = 0.0
    # If no good open bin exists, don't punish the new bin.
    gate = 1.0 if best_open_weak < 0.15 * used else 0.0
    score[-1] -= (1.0 - gate) * (0.22 - 0.15 * used)

    return score
