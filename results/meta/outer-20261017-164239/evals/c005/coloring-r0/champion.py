# Helix v3 policy: coloring, gap 14.773%, progress 74.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 dsatur_saturation_and_crowding (wide): DSATUR-style: number of distinct colours already present among a candidate's coloured neighbours, plus saturat
def _f001(neighbor_colors, adjacency, degree, color_sizes):
    """DSATUR-style: number of distinct colours already present among a candidate's coloured neighbours, plus saturation pressure from colour class sizes."""
    k, c = neighbor_colors.shape
    if c == 0:
        return np.zeros(k)
    sat = (neighbor_colors > 0).sum(axis=1).astype(float)  # distinct colours blocked
    # free colours = colours not blocked; scarcity of free colours raises urgency
    free = (neighbor_colors == 0).sum(axis=1).astype(float)
    # weight blocked colours by how crowded those colour classes are (blocking a big class is worse)
    crowded = (neighbor_colors * color_sizes[None, :]).sum(axis=1)
    denom = crowded + degree + 1.0
    val = sat / (free + 1.0) + 0.5 * (crowded / denom)
    return val

# f004 static_degree (deep): Degree of each candidate divided by the maximum degree among candidates.
def _f004(neighbor_colors, adjacency, degree, color_sizes):
    """Degree of each candidate divided by the maximum degree among candidates."""
    degree = np.asarray(degree, dtype=float)
    denom = max(float(degree.max()) if degree.size else 0.0, 1.0)
    return degree / denom

# f003 colored_neighbor_fraction (wide): Fraction of already-coloured neighbours of each candidate, i.e. how 'saturated' the candidate's surroundings a
def _f003(neighbor_colors, adjacency, degree, color_sizes):
    """Fraction of already-coloured neighbours of each candidate, i.e. how 'saturated' the candidate's surroundings are."""
    k = neighbor_colors.shape[0]
    n = k + int(color_sizes.sum())
    if k == 0:
        return np.zeros(0)
    # coloured neighbours = degree - uncoloured neighbours
    uncolored_deg = adjacency.sum(axis=1).astype(float)
    colored_deg = np.maximum(degree.astype(float) - uncolored_deg, 0.0)
    denom = np.maximum(degree.astype(float), 1.0)
    return colored_deg / denom

_TERMS = [(_f001, np.array([2.830696])), (_f004, np.array([2.895284])), (_f003, np.array([2.813392]))]

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
