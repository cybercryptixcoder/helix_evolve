import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # job's own resource skew, normalized to [-1, 1]
    d = (it[0] / cap[0] - it[1] / cap[1])
    # leftover skew: which resource we still have plenty of
    ls = (Lc - Lm)

    # Alignment: a CPU-heavy job (d>0) wants memory leftover (ls<0).
    align = -d * ls

    # Best-fit in the binding dimension: prefer leftover near zero there.
    tight = -(Lc + Lm)

    # Sliver guard: leftover should not be tiny in the weaker resource.
    weak = np.minimum(Lc, Lm)
    alive = np.minimum(3.0 * weak, 1.0)

    # Very-tight bonus when the binding leftover is nearly empty.
    bind = np.minimum(Lc, Lm)
    perfect = np.exp(-18.0 * bind)

    score = 1.40 * align + 0.85 * tight + 0.30 * alive + 0.55 * perfect

    # New-bin gate: strongly discourage fresh bin for small jobs only.
    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    score[-1] -= 0.24 * (1.0 - used) ** 2

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
