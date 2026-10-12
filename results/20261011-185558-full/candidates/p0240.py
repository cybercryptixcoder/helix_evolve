import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Normalised leftover after placing the job.
    Lc = np.clip((rem[:, 0] - it[0]) / cap[0], 0.0, 1.0)
    Lm = np.clip((rem[:, 1] - it[1]) / cap[1], 0.0, 1.0)

    # 1) Area of leftover: prefer a well-filled bin (small leftover area).
    area = -(Lc * Lm)

    # 2) Weak dimension: don't starve the smaller leftover completely.
    weak = np.minimum(Lc, Lm)

    # 3) Squareness: leftover should be balanced, not a long thin sliver.
    s = Lc + Lm
    square = 1.0 - np.abs(Lc - Lm) / np.maximum(s, 1e-9)

    # 4) Tight fit in the binding dimension (prefer near-filling the tight side).
    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    base = 1.30 * area + 0.45 * weak + 0.35 * square + 0.55 * fit

    # Job size drives the new-bin gate: small jobs should almost always reuse.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    # Damp fresh bin for small jobs, leave it nearly free for big jobs.
    score = base.copy()
    score[-1] -= 0.20 * (1.0 - used) ** 2

    # Mild oldest-bin tie-break so we pack existing bins before opening new ones.
    k = rem.shape[0]
    if k > 1:
        idx = np.arange(k, dtype=float)
        score = score - 1e-6 * idx

    return np.nan_to_num(score, nan=0.0, posinf=1e12, neginf=-1e12).reshape(-1)
