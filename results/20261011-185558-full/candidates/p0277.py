import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the job.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Normalised demand of the arriving job.
    d0 = it[0] / cap[0]
    d1 = it[1] / cap[1]

    # 1) fit: tightness in the binding dimension (a near-full bin wins).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # 2) balance: prefer an even leftover.
    bal = -np.abs(Lc - Lm)

    # 3) geom: prefer small leftover area (well-filled bin).
    geom = -np.sqrt(Lc * Lm)

    # 4) usable: keep the weaker resource alive for future jobs.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # 5) accept: reward both leftovers still being at least half a bin.
    accept = np.minimum(2.0 * Lc, 1.0) * np.minimum(2.0 * Lm, 1.0)

    # 6) open: penalise a big open dimension (thin sliver is a wasted bin).
    maxopen = -np.maximum(Lc, Lm)

    # 7) comp: complementarity -- a CPU-heavy job wants a memory-slack bin
    #    and vice versa, so leftover skew should oppose the job's skew.
    comp = np.clip((d0 - d1) * (Lm - Lc), -1.0, 1.0)

    # Adaptive fresh-bin discount: timid for small jobs, bolder for big ones.
    used = 0.5 * (d0 + d1)
    used = min(max(used, 0.0), 1.0)

    score = ((1.10 + 0.25 * used) * fit
             + 0.85 * bal
             + 0.55 * geom
             + 0.35 * usable
             + 0.15 * accept
             + 0.20 * maxopen
             + 0.25 * comp)

    score[-1] -= 0.16 - 0.12 * used

    return np.asarray(score, dtype=float).reshape(-1)
