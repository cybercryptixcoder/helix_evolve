import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised residual after placing this item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Normalised demand of the arriving item.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    # 1) Tightness: prefer the bin this item nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) Small leftover area (well-filled bin) - gentle.
    geom = -np.sqrt(Lc * Lm)

    # 3) Balance: prefer leftover that is even across resources.
    bal = -np.abs(Lc - Lm)

    # 4) NEW: residual utility. How well does the leftover block serve the
    #    most likely future jobs? We reward a leftover that can still host a
    #    small job, a medium job, the "transposed" shape, and a corner job.
    #    Each probe returns 1 if both dims fit, scaled by how snugly.
    def host(need_c, need_m):
        ok = (Lc >= need_c) & (Lm >= need_m)
        snug = 1.0 - 0.5 * (np.abs(Lc - need_c) + np.abs(Lm - need_m))
        return np.where(ok, np.clip(snug, 0.0, 1.0), 0.0)

    # Probes sized relative to capacity: tiny, medium, transposed, corner.
    util = (0.9 * host(0.10, 0.10)          # still hosts small jobs
            + 0.7 * host(0.30, 0.30)         # hosts medium jobs
            + 0.6 * host(d1, d0)             # hosts the transposed shape
            + 0.4 * host(0.45, 0.45))        # hosts a big corner job

    # 5) Complementarity: CPU-heavy item prefers a memory-rich bin.
    comp = np.clip((d0 - d1) * (Lm - Lc), -1.0, 1.0)

    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = (1.10 * fit
             + 0.55 * geom
             + 0.70 * bal
             + 0.85 * util
             + 0.35 * comp)

    # Fresh-bin penalty: strong for small jobs, weak for big ones.
    score[-1] -= 0.18 - 0.13 * used

    return np.asarray(score, dtype=float).reshape(-1)
