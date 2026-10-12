import numpy as np

def priority(item, bins, capacity):
    # Leftover space in each bin after placing the arriving job (clipped at 0).
    left = np.maximum(bins - item, 0.0)
    a = left[:, 0]
    c = left[:, 1]

    cap_min = float(np.min(capacity))
    half = 0.5 * cap_min if cap_min > 0.0 else 1.0

    mx = np.maximum(a, c)
    mn = np.minimum(a, c)

    # 1) balance: strong penalty on the dominant leftover, reward for the
    #    weaker leftover (favours bins whose residual is balanced).
    balance = -1.55 * mx + 0.90 * mn

    # 2) compactness: mild reward for consuming total space.
    compact = -0.15 * (a + c)

    # 3) usable room: saturating reward for keeping a useful amount of slack,
    #    capped at half the tighter capacity so huge slack is not over-valued.
    usable = np.minimum(mn, half) / half

    # 4) discourage opening a brand-new bin (always the last row).
    penalty = np.zeros(bins.shape[0])
    penalty[-1] = -7.5

    return balance + compact + usable + penalty
