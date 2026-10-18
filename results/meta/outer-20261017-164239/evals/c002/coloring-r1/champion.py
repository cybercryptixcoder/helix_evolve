# Helix v3 policy: coloring, gap 15.745%, progress 72.7%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 saturation_and_blocking_pressure (wide): Three columns per candidate: fraction of existing colours already present among its neighbours (saturation), t
def _f004(neighbor_colors, adjacency, degree, color_sizes):
    """Three columns per candidate: fraction of existing colours already present among its neighbours (saturation), the fraction of its uncoloured neighbours that would lose the colour it is about to take if it were coloured now (future blocking), and its degree normalised by the largest degree in the candidate set."""
    nc = np.asarray(neighbor_colors, dtype=float)
    adj = np.asarray(adjacency, dtype=float)
    deg = np.asarray(degree, dtype=float)
    k, c = nc.shape
    if k == 0:
        return np.zeros((0, 3))

    # saturation: how many distinct colours its coloured neighbours already use
    sat = (nc > 0).sum(axis=1) / float(max(c, 1))

    # would-be colour: first colour column that is free (a brand-new colour counts as free)
    free_ext = np.concatenate([nc <= 0, np.ones((k, 1), dtype=bool)], axis=1)
    j = np.argmax(free_ext, axis=1)                     # first free colour, always exists
    # free_ext[p, col] = 1 iff candidate p could still take colour col
    reach = adj @ free_ext.astype(float)                # (k, c+1): for each candidate,count of its uncoloured neighbours free at each colour
    would_block = reach[np.arange(k), j]                # neighbours that lose their option if this candidate takes colour j
    rowsum = adj.sum(axis=1)
    blocking = would_block / np.maximum(rowsum, 1.0)    # fraction of its uncoloured neighbours blocked

    dmax = max(float(deg.max()) if k else 1.0, 1.0)
    degn = deg / dmax

    return np.stack([sat, blocking, degn], axis=1)

# f005 saturation_forward_gain_degree (wide): Per candidate: DSATUR-style saturation, a forward-looking constraint gain (how many still-uncoloured neighbour
def _f005(neighbor_colors, adjacency, degree, color_sizes):
    """Per candidate: DSATUR-style saturation, a forward-looking constraint gain (how many still-uncoloured neighbours would lose the candidate's would-be colour), and whole-graph degree."""
    neighbor_colors = np.asarray(neighbor_colors)
    k = neighbor_colors.shape[0]
    c = neighbor_colors.shape[1]
    deg = np.asarray(degree, dtype=float).reshape(k)
    if k == 0:
        return np.zeros((0, 3))

    has_col = neighbor_colors > 0                 # (k, c) colours already used by neighbours
    sat = has_col.sum(axis=1).astype(float)       # saturation degree

    # Would-be colour of each candidate: first colour column that is zero, else a new colour (index c).
    has_zero = ~has_col                           # (k, c) colours still available in the neighbourhood
    any_zero = has_zero.any(axis=1)               # (k,)
    if c > 0:
        would_be = np.where(any_zero, has_zero.argmax(axis=1), c)
    else:
        would_be = np.full(k, c, dtype=int)

    # Forward gain: number of uncoloured neighbours for which that colour is still available,
    # i.e. neighbours that would be forced to give it up once this candidate takes it.
    gain = np.zeros(k)
    if c > 0:
        idx = np.arange(k)
        jj = np.where(any_zero, would_be, 0)
        gv = has_zero[idx, jj].astype(float)
        gv[~any_zero] = 0.0                        # opening a brand-new colour: neutral here
        gain = adjacency.astype(float) @ gv        # (k,)

    denom_c = float(max(c, 1))
    maxdeg = float(max(deg.max(), 1.0)) if k else 1.0

    sat_norm = sat / denom_c
    gain_norm = gain / (deg + 1.0)
    deg_norm = deg / maxdeg

    out = np.stack([sat_norm, gain_norm, deg_norm], axis=1)
    return np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=-1.0)

# f006 dsatur_saturation_frac (deep): DSATUR saturation: number of distinct colours among a candidate's coloured neighbours, divided by the colours 
def _f006(neighbor_colors, adjacency, degree, color_sizes):
    """DSATUR saturation: number of distinct colours among a candidate's coloured neighbours, divided by the colours used so far."""
    k = neighbor_colors.shape[0]
    c = neighbor_colors.shape[1]
    if c == 0:
        return np.zeros(k, dtype=float)
    distinct = (neighbor_colors > 0).sum(axis=1).astype(float)
    return distinct / float(c)

_TERMS = [(_f004, np.array([11.781179, -1.635835, 2.622024])), (_f005, np.array([9.473975, -6.885879, 1.333156])), (_f006, np.array([6.155658]))]

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
