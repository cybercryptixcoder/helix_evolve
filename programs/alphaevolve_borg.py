import numpy as np


def priority(item, bins, capacity):
    """Baseline: the heuristic AlphaEvolve discovered for Google's Borg scheduler
    (Novikov et al., "AlphaEvolve", 2025, Figure 6), which frames online job
    placement as two-resource vector bin packing.

    The formula is unchanged: residual = required / free per resource.
    Borg places jobs on existing machines and never opens one, so here the new
    bin is ranked last and only used when nothing fits. Borg optimised for
    stranded resources, not for the number of bins, so this is a reference
    point, not the bar to beat."""
    cpu_residual = item[0] / bins[:, 0]
    mem_residual = item[1] / bins[:, 1]
    scores = -1.0 * (cpu_residual + mem_residual
                     + mem_residual / cpu_residual
                     + cpu_residual / mem_residual)
    scores[-1] = scores.min() - 1.0
    return scores
