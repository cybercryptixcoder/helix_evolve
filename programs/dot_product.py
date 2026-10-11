import numpy as np


def priority(item, bins, capacity):
    """Baseline: dot-product alignment (Panigrahy et al., "Heuristics for Vector
    Bin Packing", 2011). Prefer the bin whose free space points in the same
    direction as the job's demand, so CPU-heavy jobs go where CPU is free.
    The new bin is ranked last, so it is only used when nothing fits."""
    demand = item / capacity
    free = bins / capacity
    scores = free @ demand / (np.linalg.norm(free, axis=1) * np.linalg.norm(demand))
    scores[-1] = scores.min() - 1.0
    return scores
