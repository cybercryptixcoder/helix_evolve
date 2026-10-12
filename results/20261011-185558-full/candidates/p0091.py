import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=np.float64), 1.0)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # post-placement residual, normalized
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Best-fit: prefer the bin where the item binds tightly in its binding dim.
    # ratio in each dim (capped), take the min => how "exactly" the item fits.
    fc = np.minimum(it[0] / rc, 1.0)
    fm = np.minimum(it[1] / rm, 1.0)
    fit = np.minimum(fc, fm)

    # Residual shape: distance from the residual to the diagonal, superlinear.
    # A balanced residual keeps the bin open for both job types.
    bal = -((Lc - Lm) ** 2)

    # Geometric compactness: small residual area is good, but with a floor so
    # that "nearly full" bins aren't over-rewarded into becoming dead ends.
    geom = -np.sqrt(Lc * Lm + 1e-12)

    # Usability: the weaker residual side, saturating — reward bins that still
    # have meaningful room in BOTH dimensions.
    weaker = np.minimum(Lc, Lm)
    usable = np.minimum(3.0 * weaker, 1.0)

    # Diagonal closeness: how close residual is to a balanced (d, d) shape.
    diag = 1.0 - np.abs(Lc - Lm) / np.maximum(Lc + Lm, 1e-9)

    score = 1.10 * fit + 0.85 * bal + 0.45 * geom + 0.40 * usable + 0.35 * diag

    # New-bin penalty scaled by how small the job is: tiny jobs should squeeze
    # into existing bins; large jobs legitimately deserve a fresh bin.
    used_frac = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    pen = 0.18 - 0.14 * used_frac

    n = score.shape[0]
    is_new = np.zeros(n, dtype=bool)
    if n > 0:
        is_new[-1] = True
    score = score - pen * is_new

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
