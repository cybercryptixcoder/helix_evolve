import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)
    k = rem.shape[0]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    Lc = np.clip((rem[:, 0] - it[0]) / cap[0], 0.0, 1.0)
    Lm = np.clip((rem[:, 1] - it[1]) / cap[1], 0.0, 1.0)

    # Usable square: a big min-leftover keeps room for a generic future job.
    weak = np.minimum(Lc, Lm)

    # Aspect match: bin residual aspect vs item aspect. Reward when the bin's
    # leftover shape mirrors the item's demand shape (complementary packing).
    s = Lc + Lm
    b_aspect = (Lc - Lm) / np.maximum(s, 1e-9)
    i_aspect = (it[0] - it[1]) / (it[0] + it[1] + 1e-9)
    aspect_match = -np.abs(b_aspect - i_aspect)

    # Tightness in the binding dimension (mild best-fit pressure).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Anti-sliver: penalize extreme imbalance strongly.
    bal = -np.abs(Lc - Lm)

    score = (0.95 * weak
             + 0.55 * aspect_match
             + 0.45 * fit
             + 0.40 * bal)

    # New-bin gate based on the *best open-bin match*: only open when no
    # existing bin offers a decent aspect fit and usable square.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(float(used), 0.0), 1.0)
    if k > 1:
        best_open = float(np.max(weak[:-1] + 0.5 * aspect_match[:-1]))
    else:
        best_open = 0.0
    need = 1.0 - min(best_open, 1.0)          # 0 => great match exists
    score[-1] -= (0.18 + 0.30 * need) * (1.0 - used) ** 1.5

    score = np.asarray(score, dtype=float).reshape(-1)
    score = np.nan_to_num(score, nan=0.0, posinf=1e12, neginf=-1e12)
    return score
