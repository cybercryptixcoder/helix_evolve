import numpy as np


def priority(item, bins, capacity):
    """Best Fit: negate the total leftover [cpu, mem] after placing the job,
    so the fullest bin that still fits scores highest."""
    return -((bins - item).sum(axis=1))
