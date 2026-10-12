import numpy as np

def priority(item, bins, capacity):
    # Remaining capacities
    rem = bins.astype(float)
    Lc = rem[:, 0]
    Lm = rem[:, 1]
    cap_c = float(capacity[0])
    cap_m = float(capacity[1])

    it_c = float(item[0])
    it_m = float(item[1])

    # Tightness: how snugly the item fits in each resource (1 = exact fit)
    a = it_c / cap_c if cap_c > 0 else 0.0
    b = it_m / cap_m if cap_m > 0 else 0.0
    # Fraction used after placement
    uc = np.clip(1.0 - (Lc - it_c) / cap_c, 0.0, 1.0) if cap_c > 0 else np.zeros_like(Lc)
    um = np.clip(1.0 - (Lm - it_m) / cap_m, 0.0, 1.0) if cap_m > 0 else np.zeros_like(Lm)

    # Leftovers after placement
    rc = np.maximum(Lc - it_c, 0.0)
    rm = np.maximum(Lm - it_m, 0.0)

    # Fit quality: prefer bins where the item's demand mirrors remaining space
    fit = 1.0 - np.abs(Lc / cap_c - a) - np.abs(Lm / cap_m - b) if cap_c > 0 and cap_m > 0 else np.zeros_like(Lc)

    # Even-fill: minimize the larger leftover (fill the looser dimension)
    even = -np.maximum(rc, rm) / (cap_c + cap_m)

    # Balance: reward equal leftover proportions
    bal = -np.abs(rc / cap_c - rm / cap_m) if cap_c > 0 and cap_m > 0 else np.zeros_like(Lc)

    # Load-fill: prefer fuller bins (smaller total leftover)
    fill = -(rc + rm) / (cap_c + cap_m)

    score = 1.10 * fit + 0.55 * even + 0.45 * bal + 0.35 * fill

    # New-bin penalty: adaptive to item magnitude and how poorly it fits anywhere
    used = 1.0 - (Lc + Lm) / (cap_c + cap_m)
    mag = 0.5 * (a + b)
    penalty = 0.45 * (1.0 - used) + 0.25 * (1.0 - mag)
    is_fresh = (Lc >= cap_c - 1e-9) & (Lm >= cap_m - 1e-9)
    score = score - np.where(is_fresh, penalty, 0.0)

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
