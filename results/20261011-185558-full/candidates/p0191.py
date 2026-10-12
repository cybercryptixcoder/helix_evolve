import numpy as np

def priority(item, bins, capacity):
    cap = capacity.astype(np.float64)
    it = item.astype(np.float64)
    rem = bins.astype(np.float64)

    # Remaining capacity if this item were placed (bins rows all fit, so >= 0)
    rem_after = rem - it
    nc = np.clip(rem_after[:, 0] / cap[0], 0.0, None)
    nm = np.clip(rem_after[:, 1] / cap[1], 0.0, None)

    # Core: prefer the fullest bin that still fits (best-fit -> less leftover)
    tight = -(nc + nm)

    # Mild convexity: discourage leaving a huge leftover in the worst resource
    worst = -np.maximum(nc, nm)

    # Keep the resulting bin flexible: prefer balanced leftovers
    balance = -np.abs(nc - nm)

    score = tight + 0.3 * worst + 0.1 * balance
    return np.asarray(score, dtype=np.float64)
