import numpy as np


def priority(item, bins, capacity):
    """Baseline: Best Fit. Choose the bin with the least space left over after
    placing the job, measured as a fraction of capacity in each resource.
    A new bin always has the most left over, so it is only used when nothing fits."""
    leftover = (bins - item) / capacity
    return -leftover.sum(axis=1)
