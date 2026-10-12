def priority(item, bins, capacity):
    # bins: remaining
    # compute leftover after placement
    leftover = bins - item
    # balance ratio
    m = np.minimum(leftover[:,0], leftover[:,1]) / np.maximum(leftover[:,0], leftover[:,1])
    # piecewise linear for m<0.5 then constant?
    balance_score = np.where(m < 0.5, m, 0.5)  # or something
    # also consider total leftover
    total = leftover.sum(axis=1)
    return balance_score - total / capacity.sum()
