import numpy as np
import math

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)

    # Remaining resources after hypothetically placing the item.
    rem_cpu = bins[:, 0] - it[0]
    rem_mem = bins[:, 1] - it[1]

    # Normalized residual fractions (guard against zero capacity).
    inv_cap = 1.0 / np.maximum(cap, 1.0)
    r_cpu = np.maximum(rem_cpu, 0.0) * inv_cap[0]
    r_mem = np.maximum(rem_mem, 0.0) * inv_cap[1]

    # Prefer bins that fit tightly: small total residual.
    compact = -(r_cpu + r_mem)

    # Prefer the residual to match the item's shape (best-fit in 2D).
    it_frac = it * inv_cap
    shape_cpu = it_frac[0]
    shape_mem = it_frac[1]
    # Alignment term: reward when residual proportions match item proportions.
    item_ratio = shape_cpu / (shape_cpu + shape_mem + 1e-12)
    rem_ratio = r_cpu / (r_cpu + r_mem + 1e-12)
    align = -np.abs(rem_ratio - item_ratio)

    # Mild balance bonus: square residuals pack better.
    balance = -np.abs(r_cpu - r_mem)

    # Penalize leaving a bin with small residual in EITHER resource heavily used;
    # prefer to consume the scarcer resource's slack first.
    scarcity = -(np.minimum(r_cpu, r_mem))

    score = 1.6 * compact + 0.5 * align + 0.35 * balance + 0.2 * scarcity

    # Slight nudge to prefer older bins on near-ties is automatic via tie-break,
    # so no extra term needed.

    return score
