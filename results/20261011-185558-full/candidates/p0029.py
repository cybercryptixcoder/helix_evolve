import numpy as np


def priority(item, bins, capacity):
    """Score each candidate bin: tight pack + balanced leftover + shape alignment."""
    bins = np.asarray(bins, dtype=float)
    item = np.asarray(item, dtype=float)
    cap = np.asarray(capacity, dtype=float)

    c, m = item[0], item[1]
    C, M = cap[0], cap[1]

    # Leftover of each bin *after* placing the item (clamped: job is assumed to fit).
    lc = np.maximum(bins[:, 0] - c, 0.0)
    lm = np.maximum(bins[:, 1] - m, 0.0)

    # 1) Tightness: prefer small total leftover (normalised).
    tight = (lc + lm) / (C + M)

    # 2) Balance of the leftover: good pairing leaves a square-ish residue.
    bal = -np.abs(lc / C - lm / M)

    # 3) Shape alignment: cosine between pre-placement remaining and the item.
    rc = bins[:, 0]
    rm = bins[:, 1]
    dot = rc * c + rm * m
    denom = np.sqrt(rc * rc + rm * rm) * np.sqrt(c * c + m * m)
    cos = dot / np.maximum(denom, 1e-9)

    score = -1.0 * tight + 0.5 * bal + 0.3 * cos
    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
