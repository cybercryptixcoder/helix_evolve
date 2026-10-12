import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item in each axis.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Fit: how tightly the item fills the bin's binding dimension.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # --- Core change: multiplicative "waste" objective. ---
    # A bin is good if the leftover it leaves is small in BOTH axes; taking the
    # product punishes a bin that is tight in one axis but loose in the other,
    # which the additive sums above reward. Normalised so it stays in [0,1].
    waste = 1.0 - np.sqrt(Lc * Lm) - 0.5 * np.abs(Lc - Lm)

    # --- Directional complementarity. ---
    # Item skew (dc-dm) times opposite bin skew (Lm-Lc): a CPU-heavy job loves a
    # memory-rich bin. Scaled by the item's own skew so balanced jobs ignore it.
    dc = it[0] / cap[0]
    dm = it[1] / cap[1]
    skew = np.clip(dc - dm, -1.0, 1.0)
    comp = skew * (Lm - Lc)

    # Weak-resource floor: never strand a bin with one axis near empty.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    used = min(max(0.5 * (dc + dm), 0.0), 1.0)

    score = ((1.15 + 0.35 * used) * fit
             + 1.10 * waste
             + 0.45 * np.abs(skew) * comp
             + 0.30 * usable)

    # New-bin penalty: charge it when the arriving job would leave a fresh bin
    # mostly idle (i.e. the job is small), refund it for jobs that fill a bin.
    idle = 1.0 - min(max(0.5 * (dc + dm), 0.0), 1.0)
    score[-1] -= 0.20 * idle

    return score
