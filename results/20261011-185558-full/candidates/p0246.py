import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Item and residual as fractions of capacity
    ic = it[0] / cap[0]
    im = it[1] / cap[1]

    rc = np.maximum(rem[:, 0], 1e-9) / cap[0]
    rm = np.maximum(rem[:, 1], 1e-9) / cap[1]

    Lc = np.clip(rc - ic, 0.0, None)
    Lm = np.clip(rm - im, 0.0, None)

    # --- Residual usefulness: what does this bin offer future jobs? ---
    # A generic future job wants a leftover that is (a) large and (b) balanced.
    bal = 1.0 - np.abs(Lc - Lm) / np.maximum(Lc + Lm, 1e-9)
    mag = np.sqrt(Lc * Lc + Lm * Lm)
    useful = mag * (0.5 + 0.5 * bal)

    # --- Sliver veto: if either leftover is tiny, the bin is nearly dead. ---
    # Typical jobs are ~0.25 of capacity; below that a bin can hold little.
    sliver_veto = np.minimum(np.minimum(Lc, Lm) / 0.20, 1.0)

    # --- Tightness: prefer filling the binding residual dimension. ---
    fit = np.minimum(np.minimum(ic / rc, im / rm), 1.0)

    # --- Complementarity: skewed item pairs well with oppositely skewed bin. ---
    comp = -(ic - im) * (Lc - Lm)

    # --- Current-job reward: a bin the item nearly fills is a good close. ---
    close = -(Lc + Lm)

    base = (0.55 * useful
            + 0.70 * sliver_veto
            + 0.80 * fit
            + 0.35 * comp
            + 0.55 * close)

    # New-bin gate keyed on the binding dimension of the item.
    binding = min(max(ic, im), 1.0)
    score = base.copy()
    score[-1] -= 0.22 * (1.0 - binding) ** 2

    # Mild oldest-first tie-break to consolidate.
    k = rem.shape[0]
    if k > 1:
        idx = np.arange(k, dtype=float)
        score = score - 1e-6 * idx

    return np.nan_to_num(score, nan=-1e6, posinf=1e6, neginf=-1e6).reshape(-1)
