import numpy as np


def priority(item, bins, capacity):
    """Prefer the bin whose used profile best matches the arriving job's shape.

    Score = item . (capacity - bins) = dot of the job demand with the bin's
    already-used vector. A brand-new (empty) bin scores 0, so it is only
    chosen when every fitting bin scores 0 (i.e. nothing fitting is non-empty).
    """
    used = capacity - bins
    return (item * used).sum(axis=1)
