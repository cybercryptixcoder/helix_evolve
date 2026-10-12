import numpy as np

def priority(item, bins, capacity):
    # remaining space in each dimension after placing the item (>= 0 for fit rows)
    leftover = bins - item

    # best fit: prefer the bin whose post-placement leftover is smallest
    score = -(leftover[:, 0] + leftover[:, 1]).astype(float)

    # best-fit already prefers existing bins (their leftover <= new bin's),
    # but keep a tiny nudge so a tie never opens a fresh bin
    score[-1] -= 1e-6

    return score
