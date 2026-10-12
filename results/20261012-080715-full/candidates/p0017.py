import numpy as np


def priority(item, bins, capacity):
    """Tightest-fit (min residual) scoring, with a penalty on opening a new bin.

    Score = -((bins - item).sum(axis=1)), and the last row (the always-empty
    new bin) is penalised by 0.1 * capacity.sum() so a fresh bin only wins
    when every existing bin leaves a worse total residual.
    """
    residual = bins - item
    score = -residual.sum(axis=1).astype(float)
    score[-1] -= 0.1 * float(capacity.sum())
    return score
