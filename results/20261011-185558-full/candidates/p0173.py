import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    a, b = it[0], it[1]
    rc = rem[:, 0]
    rm = rem[:, 1]

    # leftover after placing
    lc = rc - a
    lm = rm - b
    # guard: only feasiable bins matter, but keep finite
    lc_safe = np.maximum(lc, 0.0)
    lm_safe = np.maximum(lm, 0.0)

    # balance of resulting bin (smaller = better)
    balance = np.abs(lc_safe - lm_safe)

    # tightness: prefer bins whose leftover is small (best-fit-like),
    # normalized by capacity so it scales with capacity.
    tight = (lc_safe + lm_safe) / (cap[0] + cap[1])

    # pairing term: for a CPU-heavy item (a>b), prefer CPU-rich bins
    # (rc large relative to rm); for memory-heavy, prefer memory-rich bins.
    skew = (rc - rm) / (cap[0] + cap[1])
    item_skew = (a - b) / (cap[0] + cap[1])
    pair = -np.abs(skew - item_skew)

    # base score: tight fit + balance + pairing
    score = -1.0 * tight - 0.5 * balance / (cap[0] + cap[1]) + 0.3 * pair

    # penalty for opening a new bin, decreasing with item size
    used_frac = (a + b) / (cap[0] + cap[1])
    new_penalty = 0.16 - 0.12 * used_frac

    # the last row is the brand-new empty bin
    score = score.copy()
    score[-1] -= new_penalty

    # ensure finite
    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    return score
