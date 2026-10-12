import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Leftover fractions after placing the job.
    Lc = np.clip((rem[:, 0] - it[0]) / cap[0], 0.0, 1.0)
    Lm = np.clip((rem[:, 1] - it[1]) / cap[1], 0.0, 1.0)

    # Harmonic mean of leftovers: harshly penalises a near-empty dimension,
    # so it strongly avoids creating slivers (better than arithmetic area).
    harm = (2.0 * Lc * Lm) / np.maximum(Lc + Lm, 1e-9)

    # Fit: how tightly the item fills the binding residual dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Directional complementarity: item skew vs leftover skew.
    ic = it[0] / cap[0]
    im = it[1] / cap[1]
    comp = -np.abs((ic - im) - (Lc - Lm))

    # Keep the weaker dimension alive (future usability).
    weak = np.minimum(np.minimum(Lc, Lm) * 3.0, 1.0)

    base = 1.20 * harm + 0.85 * fit + 0.45 * comp + 0.35 * weak

    # Fresh-bin gate: damp only when the job is easy (small in BOTH dims).
    hardness = max(ic, im)          # big in one dim -> may need a fresh bin
    ease = 1.0 - min(max(0.5 * (ic + im), 0.0), 1.0)
    score = base.copy()
    score[-1] -= 0.22 * ease * (1.0 - hardness)

    # Oldest-bin tie-break to consolidate.
    k = rem.shape[0]
    if k > 1:
        score = score - 1e-6 * np.arange(k, dtype=float)

    return np.nan_to_num(score, nan=0.0, posinf=1e12, neginf=-1e12).reshape(-1)
