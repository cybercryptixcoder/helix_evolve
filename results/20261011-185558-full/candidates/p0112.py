import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Post-placement residual, normalised.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Unit demand direction of the arriving item.
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]
    nrm = np.sqrt(dc * dc + dm * dm) + 1e-12
    uc, um = dc / nrm, dm / nrm

    # Waste projected onto the item's own demand direction: how much of the
    # bin's leftover is "in the way" for jobs shaped like this one.
    proj = Lc * uc + Lm * um

    # Orthogonal leftover: room the item doesn't care about, mildly useful.
    orth = np.abs(Lc * um - Lm * uc)

    # Fit: binding-dimension tightness (prefer the bin the item nearly fills).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Usable: keep the weaker resource reasonably large for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # Corner-ness of the item: near-diagonal items deserve a fresh bin.
    corner = 1.0 - np.abs(dc - dm) / (dc + dm + 1e-12)

    score = (1.10 * fit
             - 1.05 * proj
             - 0.30 * orth
             + 0.35 * usable)

    # Penalise opening a new bin, less so for large or corner-like items.
    size = min(max(0.5 * (dc + dm), 0.0), 1.0)
    score[-1] -= (0.18 - 0.14 * size) * (1.0 - 0.4 * corner)

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
