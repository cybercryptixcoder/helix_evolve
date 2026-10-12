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

    # Residual (post-placement) utilisation in each resource.
    Uc = np.clip(rem[:, 0] / cap[0], 0.0, 1.0)
    Um = np.clip(rem[:, 1] / cap[1], 0.0, 1.0)

    # 1) Alignment: item shape vs. the bin's free shape (cosine-like).
    #    A bin whose remaining room is shaped like the item absorbs it cleanly.
    dot = (it[0] / cap[0]) * Uc + (it[1] / cap[1]) * Um
    nrm = np.sqrt((it[0] / cap[0]) ** 2 + (it[1] / cap[1]) ** 2 + 1e-12) \
        * np.sqrt(Uc ** 2 + Um ** 2 + 1e-12)
    align = dot / nrm

    # 2) Tightness: the item should nearly saturate at least one dimension.
    tight = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 3) Balance of the *resulting* leftover (prefer even residue).
    bal = -np.abs(Lc - Lm)

    # 4) Sealing bonus: reward making the bin's tighter resource nearly full.
    seal = 1.0 - np.minimum(np.minimum(Lc, Lm) / 0.25, 1.0)

    # 5) Reserve: don't leave a large chunk of the untouched resource unused
    #    if the item is very skewed (avoid stranding capacity).
    skew = np.abs(it[0] / cap[0] - it[1] / cap[1])
    reserve = -skew * (1.0 - np.minimum(np.maximum(Lc, Lm) / 0.5, 1.0))

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.10 * tight + 0.55 * align + 0.85 * bal
             + 0.45 * seal + 0.30 * reserve)

    # New-bin penalty: strong when the item is small (should pack into old bins),
    # weak when the item is big and would seal a fresh bin anyway.
    score[-1] -= 0.22 - 0.18 * used

    return score
