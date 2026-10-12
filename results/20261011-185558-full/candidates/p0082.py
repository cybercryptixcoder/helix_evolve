import numpy as np

def priority(item, bins, capacity):
    # Remaining resources after placing the item (bins already fit, so >= 0).
    rem = bins - item

    # Normalize leftovers by capacity so the score is scale-free.
    rc = rem[:, 0] / capacity[0]
    rm = rem[:, 1] / capacity[1]

    # Squared Euclidean norm of normalized leftovers:
    # small when the bin is tightly packed and balanced across both resources.
    score = -(rc * rc + rm * rm)

    # Penalize opening the brand-new empty bin so it is only chosen when
    # no existing bin offers a comparably tight fit.
    empty = np.all(bins == capacity, axis=1)
    score = score - empty * 0.5

    return score
