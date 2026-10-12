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

    # Fit: how tightly the item fills the binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Balance and geometric leftover (well-filled, even bins preferred).
    bal = -np.abs(Lc - Lm)
    geom = -np.sqrt(Lc * Lm)

    # Usable / accept: keep the weaker resource alive for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # Residual slack: the largest remaining usable "square" after placing.
    slack = np.minimum(Lc, Lm)

    # Item shape.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]
    used = min(max(0.5 * (d0 + d1), 0.0), 1.0)

    # Complementarity: lopsided jobs prefer oppositely-lopsided bins.
    comp = np.clip(d0 - d1, -1.0, 1.0) * np.tanh(2.0 * (Lm - Lc))

    score = ((1.00 + 0.30 * used) * fit
             + 0.85 * bal
             + 0.55 * geom
             + 0.40 * usable
             + 0.15 * accept
             + (0.40 * np.abs(d0 - d1)) * comp)

    # ---- Explicit new-bin decision (opportunity cost) ----
    # Fresh bin has leftover = capacity, i.e. Lc=Lm=1. Opening it wastes the
    # whole bin if the job is small; if the job is large, filling an existing
    # bin's leftover with a big item leaves nothing usable anyway, so a fresh
    # bin is cheap. Also reward starting fresh when no existing bin leaves a
    # reasonably shaped remainder (slack too small to be useful).
    existing = score[:-1]
    if existing.size > 0:
        best_existing = float(np.max(existing))
        best_slack = float(np.max(slack[:-1]))
    else:
        best_existing = -1e9
        best_slack = 0.0

    # Cost of dedicating a fresh bin: grows with unused residue.
    # Large jobs -> smaller penalty; small jobs -> larger penalty.
    fresh_penalty = 0.32 - 0.30 * used

    # If the best existing bin wastes a lot (low slack), opening fresh is
    # comparatively attractive -> reduce the penalty further.
    fresh_penalty -= 0.10 * (1.0 - min(best_slack, 1.0))

    fresh_score = (1.00 + 0.30 * used) * fit[-1] + 0.85 * bal[-1] \
        + 0.55 * geom[-1] + 0.40 * usable[-1] + 0.15 * accept[-1] \
        + (0.40 * np.abs(d0 - d1)) * comp[-1] - fresh_penalty

    score = score.copy()
    score[-1] = fresh_score
    return score
