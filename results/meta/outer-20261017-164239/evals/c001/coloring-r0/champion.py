# Helix v3 policy: coloring, gap 20.073%, progress 65.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 saturation_with_new_color_flag (wide): Saturation-style score: how many distinct colours already touch a candidate, relative to its uncoloured neighb
def _f004(neighbor_colors, adjacency, degree, color_sizes):
    """Saturation-style score: how many distinct colours already touch a candidate, relative to its uncoloured neighbours."""
    k, c = neighbor_colors.shape
    if c == 0:
        return np.zeros(k)
    touched = (neighbor_colors > 0).sum(axis=1).astype(float)
    uncolored_deg = adjacency.sum(axis=1).astype(float)
    total_deg = np.maximum(degree.astype(float), 1.0)
    frac_uncol = uncolored_deg / total_deg
    # combine distinct-colour pressure with how many uncoloured neighbours it constrains
    raw = touched * (1.0 + frac_uncol)
    norm = np.maximum(c, 1.0)
    return raw / (norm + 1.0)

# f012 forced_new_colour_neighbour_pressure (wide): For candidates that would open a new colour, how many uncoloured neighbours they block; else 0.
def _f012(neighbor_colors, adjacency, degree, color_sizes):
    """For candidates that would open a new colour, how many uncoloured neighbours they block; else 0."""
    k, c = neighbor_colors.shape
    if c == 0:
        # everyone opens a new colour at the first decision: use uncoloured neighbourhood size
        uncolored_deg = adjacency.sum(axis=1).astype(float)
        return uncolored_deg / (k + 1.0)
    blocked = (neighbor_colors > 0).any(axis=1)
    opens_new = ~blocked
    uncolored_deg = adjacency.sum(axis=1).astype(float)
    n = k + color_sizes.sum()
    return np.where(opens_new, uncolored_deg / (n + 1.0), 0.0)

_TERMS = [(_f004, np.array([5.435213])), (_f012, np.array([-5.333652]))]

def priority(neighbor_colors, adjacency, degree, color_sizes):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(neighbor_colors, adjacency, degree, color_sizes), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(neighbor_colors))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
