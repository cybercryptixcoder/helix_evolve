import numpy as np

# Non-LLM bar: a fixed formula whose 6 numbers were picked by random search
# (120 tries) on the train split. If the evolved programs can't beat this,
# the loop is only tuning numbers, not finding new ideas.
FILL, BALANCE, MAX_LEFT, NEAR_FULL_BONUS, NEAR_FULL, NEW_BIN_PENALTY = 0.298, 1.945, 1.78, 1.645, 0.144, 0.081


def priority(item, bins, capacity):
    left = (bins - item) / capacity
    scores = (
        -FILL * left.sum(axis=1)
        - BALANCE * np.abs(left[:, 0] - left[:, 1])
        - MAX_LEFT * left.max(axis=1)
        + NEAR_FULL_BONUS * (left.max(axis=1) <= NEAR_FULL)
    )
    scores[-1] -= NEW_BIN_PENALTY
    return scores
