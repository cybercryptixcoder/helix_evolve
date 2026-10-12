import numpy as np

def priority(item, bins, capacity):
    C = np.maximum(np.asarray(capacity, dtype=np.float64), 1.0)
    it = np.asarray(item, dtype=np.float64)
    rem = np.asarray(bins, dtype=np.float64)
    a = it[0]; b = it[1]
    x = a / C[0]
    y = b / C[1]

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    u = np.clip((rem[:,0] - a) / C[0], 0.0, 1.0)
    v = np.clip((rem[:,1] - b) / C[1], 0.0, 1.0)

    fill = np.minimum(np.minimum(a / rc, b / rm), 1.0)
    bal = 1.0 - np.abs(u - v)
    weak = np.minimum(u, v)
    usable = np.minimum(2.0 * weak, 1.0)
    comp = (x - y) * (v - u)

    score = (2.0 * fill + 1.5 * bal + 0.5 * usable + 1.0 * comp)
    ...
