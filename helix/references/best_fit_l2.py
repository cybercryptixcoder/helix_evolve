# Norm-based greedy (L2)
# Online form of the L2 heuristic of Panigrahy et al., "Heuristics for Vector Bin Packing"
# (Microsoft Research, 2011): the bin whose room after placing the job is smallest in Euclidean norm.
import numpy as np


def priority(item, bins, capacity):
    left = (bins - item) / capacity
    return -(left ** 2).sum(axis=1)
