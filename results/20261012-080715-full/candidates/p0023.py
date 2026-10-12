import numpy as np


def priority(item, bins, capacity):
    """Fresh idea: 'free-dimension' fit.

    Instead of scoring bins by their leftover capacity, score them by how
    much of the *scarce* resource they free up relative to the item's shape.
    A bin is good if, after placing the job, its residual stays as far as
    possible from the item's own aspect ratio in normalized units, i.e. the
    bin is left "complementary" to the job so that a job of the opposite
    shape can still land there later.

    Concretely: normalize residual by capacity, compute its direction, and
    reward bins whose leftover direction is most unlike the item direction
    (dot product most negative), while penalizing total wasted space.
    """
    res = (bins - item) / capacity                      # (k,2) >= 0
    item_dir = item / capacity                          # (2,)
    item_norm = np.sqrt(item_dir[0] ** 2 + item_dir[1] ** 2) + 1e-12
    res_norm = np.sqrt(res[:, 0] ** 2 + res[:, 1] ** 2) + 1e-12
    # cosine between leftover direction and item direction
    cos = (res[:, 0] * item_dir[0] + res[:, 1] * item_dir[1]) / (res_norm * item_norm)
    # reward complementarity (small cos) and small leftover magnitude
    return -cos - 0.5 * res_norm
