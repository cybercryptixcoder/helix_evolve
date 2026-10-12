import numpy as np


def priority(item, bins, capacity):
    """
    item:     np.ndarray, shape (2,), int
    bins:     np.ndarray, shape (k, 2), int   (last row = brand-new empty bin)
    capacity: np.ndarray, shape (2,), int
    returns:  np.ndarray, shape (k,), float
    """
    a0 = float(item[0])
    a1 = float(item[1])
    C0 = float(capacity[0]) if capacity[0] > 0 else 1.0
    C1 = float(capacity[1]) if capacity[1] > 0 else 1.0

    rc = bins[:, 0].astype(float)
    rm = bins[:, 1].astype(float)

    # leftover if the job is placed here (all rows fit, so >= 0)
    lc = rc - a0
    lm = rm - a1

    # normalised leftover per resource
    u = lc / C0
    v = lm / C1

    # best-fit: prefer a small total leftover
    fit = -(u + v)

    # balanced residual: avoid leaving one dimension starved
    bal = -np.abs(u - v)

    # tightness of the binding dimension (smaller leftover -> higher score)
    tight = -np.minimum(u, v)

    # geometric utilisation of the resulting bin (fuller -> higher)
    geom = (1.0 - u) * (1.0 - v)

    score = fit + 0.35 * bal + 0.60 * tight + 0.30 * geom

    # --- shape-adaptive new-bin penalty on the last (empty) row ---
    k = bins.shape[0]
    frac = (a0 / C0 + a1 / C1) * 0.5          # 0 for tiny jobs, ~1 for huge
    pen = (0.10 + 0.06 * np.log1p(k)) * (1.0 - 0.5 * frac)
    pen = min(pen, 0.5)
    score[-1] -= pen

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
