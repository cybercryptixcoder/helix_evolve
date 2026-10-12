import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # How much of each remaining resource the job consumes (0..1).
    uc = np.minimum(it[0] / rc, 1.0)
    um = np.minimum(it[1] / rm, 1.0)

    # Binding resource: the one the job fills more tightly.
    binding = np.maximum(uc, um)

    # Skew of the arriving job.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    skew = abs(d0 - d1)

    # 1) Tighten the binding dimension (best-fit on the tighter resource).
    fit = binding

    # 2) Prefer well-packed bins: reward small pre-placement slack.
    pre_c = np.clip(rem[:, 0] / cap[0], 0.0, 1.0)
    pre_m = np.clip(rem[:, 1] / cap[1], 0.0, 1.0)
    filled = 1.0 - np.sqrt(np.maximum(1.0 - pre_c, 0.0) *
                           np.maximum(1.0 - pre_m, 0.0))

    # 3) Balance leftover, but only mildly.
    bal = -np.abs(Lc - Lm)

    # 4) Complementarity: skewed jobs want a bin rich in the opposite resource.
    comp = (d0 - d1) * (Lm - Lc)

    # 5) Keep the weaker leftover usable for future jobs.
    usable = np.minimum(2.0 * np.minimum(Lc, Lm), 1.0)

    score = (1.10 * fit
             + 0.55 * filled
             + 0.70 * bal
             + (0.45 * skew + 0.10) * comp
             + 0.30 * usable)

    # New-bin penalty: weaker when the job is big, and weaker when no existing
    # bin offers a decent binding fit (so opening a bin is justified).
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)
    best_fit = float(np.max(fit[:-1])) if len(fit) > 1 else 0.0
    need = max(0.0, 0.75 - best_fit)
    score[-1] -= (0.20 - 0.14 * used) - 0.25 * need

    return score
