import numpy as np


def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=np.float64), 1.0)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Post-placement leftover, normalized by capacity.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # --- Residual-shape matching: cosine alignment between item and residual ---
    # A bin whose residual points the same way as the item will be drained
    # efficiently; misaligned residuals leave a sliver that nothing fits.
    ni = np.sqrt(it[0] * it[0] + it[1] * it[1]) + 1e-9
    nr = np.sqrt(rc * rc + rm * rm)
    align = (rc * it[0] + rm * it[1]) / (nr * ni + 1e-9)

    # --- Bottleneck fill (min ratio), capped ---
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # --- "Usable residual": geometric mean of leftovers, small is good ---
    # Rewards bins that become nearly-full after placement.
    waste = np.sqrt(Lc * Lm + 1e-12)

    # --- Future acceptance proxy: could a small uniform job (say 25% cap)
    #     still fit? Penalize bins that become dead to medium jobs. ---
    med = 0.25
    accept = np.minimum(Lc / med, 1.0) * np.minimum(Lm / med, 1.0)

    # --- Balance of residual: keep the bin able to take both job types ---
    bal = 1.0 - np.abs(Lc - Lm) / (Lc + Lm + 1e-9)

    score = (1.05 * fit + 0.55 * align + 0.75 * bal
             + 0.55 * (1.0 - waste) + 0.30 * accept)

    # New-bin penalty: opening fresh is cheaper for large jobs, so penalize
    # small jobs more strongly to force them into existing bins.
    used_frac = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    pen = 0.14 - 0.10 * used_frac

    n = score.shape[0]
    is_new = np.zeros(n, dtype=bool)
    if n > 0:
        is_new[-1] = True
    score = score - pen * is_new

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
