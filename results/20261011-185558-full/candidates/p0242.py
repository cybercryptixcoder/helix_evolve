import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # leftover fractions after placing
    Lc = np.clip((rem[:, 0] - it[0]) / cap[0], 0.0, 1.0)
    Lm = np.clip((rem[:, 1] - it[1]) / cap[1], 0.0, 1.0)

    # item fractions
    ic = it[0] / cap[0]
    im = it[1] / cap[1]

    # 1. Tight fit in the binding dimension: the item nearly fills what's left.
    fit = np.minimum(it[0] / rc, it[1] / rm)

    # 2. Sliver penalty: harshly punish leaving a tiny leftover in either dim,
    #    because such a bin can accept almost nothing else.
    sliver = np.minimum(np.minimum(Lc, Lm) * 4.0, 1.0)

    # 3. Balance: prefer leftover even across the two resources.
    bal = -np.abs(Lc - Lm)

    # 4. Directional complementarity: if the item is CPU-heavy, a bin whose
    #    leftover is memory-heavy becomes balanced and remains useful.
    skew_item = ic - im
    skew_left = Lc - Lm
    comp = -skew_item * skew_left

    # 5. Future-fit proxy: leftover aligned with a typical future job's shape
    #    (roughly equal in both dims) is more reusable than a lopsided one.
    future = -np.abs(Lc - Lm) - 0.35 * (Lc + Lm)

    # 6. New-bin gate keyed on the item's *binding* size, not its average:
    #    a job that is huge in one dimension rarely fits old bins well anyway.
    binding = max(ic, im)
    binding = min(max(binding, 0.0), 1.0)

    score = (1.15 * fit
             + 0.55 * sliver
             + 0.65 * bal
             + 0.45 * comp
             + 0.55 * future)

    # suppress opening a fresh bin for small jobs; allow it for big ones
    score[-1] -= 0.20 * (1.0 - binding) ** 2

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
