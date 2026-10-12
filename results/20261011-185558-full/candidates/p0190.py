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

    # Item aspect and leftover aspect (both normalised).
    ic = it[0] / cap[0]
    im = it[1] / cap[1]

    # Residual matching: reward leftovers whose aspect ratio mirrors the item's,
    # so bins fill with "similar" jobs and stay reusable.
    denom = Lc + Lm + 1e-9
    match = -np.abs(Lc / denom - ic / (ic + im + 1e-9))

    # Binding-resource tightness in raw units (Best-Fit flavour).
    bind = np.minimum(it[0] / rc, it[1] / rm)
    bind = np.clip(bind, 0.0, 1.0)

    # Complementarity: a CPU-heavy item likes a memory-heavy leftover.
    comp = (ic - im) * (Lm - Lc)

    # Fill area: prefer shrinking total free space (well-filled bin).
    fill = -(Lc + Lm)

    # Weak-dimension floor: penalise starving the scarcer resource.
    weak = np.minimum(Lc, Lm)

    # New-bin reluctance, softer for big jobs.
    used = 0.5 * (ic + im)
    used = min(max(used, 0.0), 1.0)

    score = ((1.15 + 0.20 * used) * bind
             + 0.55 * match
             + 0.30 * comp
             + 0.40 * fill
             + 0.35 * np.minimum(2.0 * weak, 1.0))

    score[-1] -= 0.14 - 0.10 * used
    return score
