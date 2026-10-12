import numpy as np

def priority(item, bins, capacity):
    # Complementarity: reward bins whose remaining resources align with the
    # item's demands (item's heavy dim meets bin's leftover heavy dim).
    rem = bins.astype(float)
    it = item.astype(float)
    cap = capacity.astype(float)

    dot = rem[:, 0] * it[0] + rem[:, 1] * it[1]

    # Prefer bins that leave a balanced leftover after placing the item,
    # so future items can still be paired.
    left = rem - it
    left = np.clip(left, 0.0, None)
    balance = -np.abs(left[:, 0] - left[:, 1])

    # Penalize opening a brand-new bin (last row) so we fill existing bins first.
    is_new = np.zeros(rem.shape[0])
    is_new[-1] = 1.0
    new_penalty = -is_new * (2.0 * cap[0] * cap[1])

    # Slight preference for tighter leftovers (best-fit flavor).
    tightness = -np.abs(left[:, 0] + left[:, 1] - (cap[0] + cap[1]))

    score = dot + 0.5 * balance + 0.3 * tightness + new_penalty
    return score
