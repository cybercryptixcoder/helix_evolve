import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it  = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised residual capacity left after this job is placed.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # 1) tightness: prefer bins this job nearly fills.
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) small leftover: gently discourages opening a fresh bin.
    tight = -(Lc + Lm)

    # 3) squareness of the leftover shape.
    bal = -np.abs(Lc - Lm)

    # 4) complementary reserve: bonus when the leftover block could still
    #    swallow the transposed job (mem-heavy job for a CPU-heavy one and
    #    vice versa). Maximal when the leftover matches that shape exactly.
    need_c = d1          # transposed CPU demand = this job's memory
    need_m = d0          # transposed memory demand = this job's CPU
    fits_c = Lc >= need_c
    fits_m = Lm >= need_m
    mismatch = np.abs(Lc - need_c) + np.abs(Lm - need_m)
    reserve = np.where(fits_c & fits_m, 1.0 - 0.5 * mismatch, 0.0)

    score = (1.4 * fit
             + 1.2 * tight
             + 0.9 * bal
             + 1.1 * reserve)

    return np.asarray(score, dtype=float).reshape(-1)
