import numpy as np

def priority(item, bins, capacity):
    # residual after placing item
    residual = bins - item  # shape (k,2), non-negative for fitting bins
    # normalized residuals
    n_c = residual[:, 0] / capacity[0]
    n_m = residual[:, 1] / capacity[1]
    # base: minimize the maximum normalized residual (L-infinity)
    base = -np.maximum(n_c, n_m)
    # quadratic imbalance penalty (from best -7.893)
    imb = -0.5685 * (n_c - n_m) ** 2
    # alignment: cosine similarity between residual and item (from -8.021)
    # guard zero norms
    r_norm = np.sqrt(residual[:, 0] ** 2 + residual[:, 1] ** 2)
    r_norm = np.where(r_norm > 0, r_norm, 1.0)
    i_norm = np.sqrt(item[0] ** 2 + item[1] ** 2)
    if i_norm <= 0:
        i_norm = 1.0
    align = (residual[:, 0] * item[0] + residual[:, 1] * item[1]) / (r_norm * i_norm)
    # combine: quadratic + alignment
    score = base + imb + 0.5 * align
    # Dynamic new bin rule: if the best existing bin is poor, boost the new bin.
    # The last row is always a brand-new empty bin.
    # We identify it as the last row.
    if bins.shape[0] > 1:
        best_existing = np.max(score[:-1])
        # If best existing is below a threshold, add a bonus to the new bin.
        # Threshold: maybe -0.5? We can make it depend on item size.
        # A simple heuristic: if best_existing < -0.5, add 0.5 to new bin.
        # But to be smooth, add a bonus that grows as best_existing decreases.
        # Let's use a softplus-like: bonus = 0.2 * max(0, -0.5 - best_existing)
        # Actually, we want to encourage new bin when existing bins are bad.
        # But we must be careful not to hurt. We'll add a small bonus.
        bonus = 0.2 * max(0.0, -0.5 - best_existing)
        score[-1] += bonus
    return score
