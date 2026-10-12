import numpy as np

def priority(item, bins, capacity):
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)

    v_c = it[0] / cap[0]
    v_m = it[1] / cap[1]

    rem_c = b[:, 0] / cap[0]
    rem_m = b[:, 1] / cap[1]

    # fractional usage AFTER placing this item (both <= 1 since the job fits)
    pc = (1.0 - rem_c) + v_c
    pm = (1.0 - rem_m) + v_m

    # best-fit: maximum total occupancy
    fill = pc + pm

    # complementary packing: post-placement usage balanced across resources
    bal = -np.abs(pc - pm)

    # room left in the binding resource (avoid sealing a bin too early)
    usable = np.minimum(1.0 - pc, 1.0 - pm)

    return fill + 1.0 * bal + 0.25 * usable
