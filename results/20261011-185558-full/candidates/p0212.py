import numpy as np

def priority(item, bins, capacity):
    # remaining after placement if item goes here
    rem = bins - item  # shape (k,2), non-negative for rows that fit

    cap = capacity.astype(float)
    # normalized leftovers
    rc = rem[:, 0] / cap[0]
    rm = rem[:, 1] / cap[1]

    # tight fit: how small the leftover is relative to what the item used
    # ratio in (0,1]; guard against zero remaining by adding a tiny epsilon
    eps = 1e-9
    use_c = item[0] / cap[0]
    use_m = item[1] / cap[1]
    fit_c = use_c / (rc + use_c + eps)   # 1 when rem=0, small when rem large
    fit_m = use_m / (rm + use_m + eps)
    fit = np.minimum(fit_c, fit_m)

    # leftover magnitude (L2) and imbalance
    l2 = np.sqrt(rc * rc + rm * rm)
    imb = np.abs(rc - rm)

    # cost to minimize; convert to a score (higher is better)
    cost = l2 + 0.5 * imb - 0.3 * fit

    # the last row is the fresh empty bin; nudge it slightly so it is only
    # chosen when no open bin is genuinely better
    score = -cost
    score[-1] -= 1e-6
    return score
