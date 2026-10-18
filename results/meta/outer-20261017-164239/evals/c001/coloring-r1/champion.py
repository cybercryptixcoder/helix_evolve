# Helix v3 policy: coloring, gap 17.266%, progress 70.0%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f012 blocked_uncolored_neighbor_count (wide): For each candidate, how many of its uncoloured neighbours are themselves blocked: neighbours that cannot take 
def _f012(neighbor_colors, adjacency, degree, color_sizes):
    """For each candidate, how many of its uncoloured neighbours are themselves blocked: neighbours that cannot take any existing colour (all columns nonzero), normalised by k."""
    k = adjacency.shape[0]
    if k == 0:
        return np.zeros(0)
    c = neighbor_colors.shape[1]
    if c == 0:
        return np.zeros(k, dtype=float)
    # blocked vertex: has a neighbour of every used colour (no zero entry)
    free = (neighbor_colors == 0).any(axis=1)  # True if it can take an existing colour
    blocked = (~free).astype(float)
    # count blocked among uncoloured neighbours (exclude self via adjacency which is False on diagonal)
    nb = adjacency.astype(float)
    return (nb @ blocked) / max(k, 1)

# f019 blocked_neighbor_share_times_own_saturation_defi (wide): For each candidate, the fraction of its uncoloured neighbours that are blocked (cannot take any existing colou
def _f019(neighbor_colors, adjacency, degree, color_sizes):
    """For each candidate, the fraction of its uncoloured neighbours that are blocked (cannot take any existing colour), weighted by how pressured the candidate's own colour options are: blocked-neighbour share times the candidate's own saturation deficit (1 - free_colours/c)."""
    k = adjacency.shape[0]
    if k == 0:
        return np.zeros(0)
    c = neighbor_colors.shape[1]
    if c == 0:
        return np.zeros(k, dtype=float)
    # blocked vertex: has a neighbour of every used colour (no zero entry across columns)
    free = (neighbor_colors == 0).any(axis=1)
    blocked = (~free).astype(float)
    nb = adjacency.astype(float)
    blocked_share = (nb @ blocked) / np.maximum(nb.sum(axis=1), 1.0)  # fraction of uncoloured nbrs blocked
    # candidate's own saturation: fraction of used colours it cannot take
    distinct = (neighbor_colors > 0).sum(axis=1).astype(float)
    own_deficit = distinct / max(c, 1)  # 0 = all colours open, 1 = fully blocked
    return blocked_share * own_deficit

# f030 blocked_region_depth (deep): Mean over candidate i's uncoloured neighbours j of blocked_j * (share of j's uncoloured neighbours that are bl
def _f030(neighbor_colors, adjacency, degree, color_sizes):
    """Mean over candidate i's uncoloured neighbours j of blocked_j * (share of j's uncoloured neighbours that are blocked), scaled by 1/k."""
    k = adjacency.shape[0]
    if k == 0:
        return np.zeros(0)
    c = neighbor_colors.shape[1]
    if c == 0:
        return np.zeros(k)
    blocked = (~(neighbor_colors == 0).any(axis=1)).astype(float)
    deg_u = adjacency.sum(axis=1).astype(float)
    depth = (adjacency.astype(float) @ blocked) / max(k, 1)
    raw = (adjacency.astype(float) @ (blocked * depth)) / np.maximum(deg_u, 1.0)
    return raw / max(k, 1)

# f039 saturation_local_peak_contrast (deep): (present_i - mean present over uncoloured neighbours) / c, 0 if no uncoloured neighbours or c==0.
def _f039(neighbor_colors, adjacency, degree, color_sizes):
    """(present_i - mean present over uncoloured neighbours) / c, 0 if no uncoloured neighbours or c==0."""
    k = adjacency.shape[0]
    c = neighbor_colors.shape[1]
    if c == 0:
        return np.zeros(k)
    present = (neighbor_colors != 0).sum(axis=1).astype(float)
    adj_f = adjacency.astype(float)
    deg_u = adj_f.sum(axis=1)
    nb_sum = adj_f @ present
    nb_mean = nb_sum / np.maximum(deg_u, 1.0)
    val = (present - nb_mean) / float(c)
    val = np.where(deg_u > 0, val, 0.0)
    return val

_TERMS = [(_f012, np.array([33.922856])), (_f019, np.array([-3.152582])), (_f030, np.array([-909.765343])), (_f039, np.array([0.110176]))]

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
