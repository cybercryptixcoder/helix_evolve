import numpy as np

def priority(item, bins, capacity):
    residual = bins - item
    nc = residual[:, 0] / capacity[0]
    nm = residual[:, 1] / capacity[1]
    fc = item[0] / capacity[0]
    fm = item[1] / capacity[1]

    # Core idea: "best AREA fit" -- minimize the leftover free rectangle area.
    # (Fully packed bin -> area 0, the max score; brand-new bin -> area ~1.)
    area = -nc * nm

    # Balance guard: do not create lopsided leftovers that are unusable later.
    imb = -0.60 * (nc - nm) ** 2

    # Fit both resources: reward bins that also leave a small residual in the
    # looser resource (tie-break that pushes toward fuller bins).
    tight = -0.15 * np.minimum(nc, nm)

    # Finish-off bonus: strongly reward a nearly-closed bin.
    close = 0.30 * np.exp(-9.0 * np.maximum(nc, nm))

    # Aspect match: prefer residual aligned with the arriving item's shape.
    align = 0.12 * (nc * fc + nm * fm)

    return area + imb + tight + close + align
