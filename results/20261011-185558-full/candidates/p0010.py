import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=np.float64)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)

    cap_safe = np.maximum(cap, 1.0)
    after = rem - it
    a = np.clip(after[:, 0], 0.0, None) / cap_safe[0]
    b = np.clip(after[:, 1], 0.0, None) / cap_safe[1]

    # Euclidean tightness: prefer bins whose post-placement leftover vector is short.
    tight = np.sqrt(a * a + b * b)

    # Item-direction weighting: leftover in the resource this job stresses most.
    tot = it[0] + it[1] + 1e-9
    p = it[0] / tot
    q = it[1] / tot
    dirw = p * a + q * b

    score = -(tight + 0.4 * dirw)

    # Discourage opening a fresh bin unless it truly packs tightest.
    score[-1] -= 0.03
    return score
