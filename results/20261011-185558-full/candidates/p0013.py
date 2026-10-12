import numpy as np

def priority(item, bins, capacity):
    cap0 = float(capacity[0])
    cap1 = float(capacity[1])
    a = float(item[0])
    b = float(item[1])

    rem0 = bins[:, 0].astype(float)
    rem1 = bins[:, 1].astype(float)

    # Normalised residual after placing the item (0 = exactly full, 1 = empty bin).
    f0 = np.maximum(rem0 - a, 0.0) / cap0
    f1 = np.maximum(rem1 - b, 0.0) / cap1

    sum_f = f0 + f1
    max_f = np.maximum(f0, f1)

    # Normalised item shape.
    sh0 = a / cap0
    sh1 = b / cap1

    # Best-fit: small total and small bottleneck residual is good.
    # Complement: reward leaving residual in the resource this job uses little,
    # so memory-heavy / CPU-heavy jobs can still be packed later.
    score = -sum_f - 0.4 * max_f + 0.15 * (sh0 * f1 + sh1 * f0)
    return score
