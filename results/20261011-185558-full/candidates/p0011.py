import numpy as np


def priority(item, bins, capacity):
    """
    Cross-dot pairing score.

    For an arriving job (p, q) = (cpu, mem) and a candidate bin with
    remaining (rem_cpu, rem_mem), score

        -(q * rem_cpu + p * rem_mem)

    Because leftover_cpu = rem_cpu - p and leftover_mem = rem_mem - q,
    this equals

        -(p * leftover_mem + q * leftover_cpu + 2*p*q),

    so maximising the score means minimising the demand-weighted leftover.
    A cpu-heavy job (large p) therefore cares about eating up the bin's
    spare *memory* and is happy with a bin that already holds a
    memory-heavy job, and vice versa: complementary jobs get paired and a
    bin whose leftovers will be small wins over the empty new bin.
    """
    rem = bins.astype(float)
    rem_cpu = rem[:, 0]
    rem_mem = rem[:, 1]

    p = float(item[0])  # cpu demand of the arriving job
    q = float(item[1])  # memory demand of the arriving job

    score = -(q * rem_cpu + p * rem_mem)

    # Tie-breaker only: values above are integers, so this 1e-6 term can
    # never flip a real decision; it just prefers the fuller / older bin.
    score = score - 1e-6 * (rem_cpu + rem_mem)

    return score
