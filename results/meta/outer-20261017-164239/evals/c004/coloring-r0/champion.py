# Helix v3 policy: coloring, gap 13.321%, progress 76.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 saturation_scarcity_mix (wide): Saturation count times scarcity: how many distinct colours already block the candidate, weighted by how crowde
def _f003(neighbor_colors, adjacency, degree, color_sizes):
    """Saturation count times scarcity: how many distinct colours already block the candidate, weighted by how crowded those colours are."""
    k = neighbor_colors.shape[0]
    if neighbor_colors.size == 0:
        return np.zeros(k)
    c = neighbor_colors.shape[1]
    blocked = (neighbor_colors > 0).astype(float)          # (k, c) which colours are present among neighbours
    sat = blocked.sum(axis=1)                               # number of distinct colours already used by neighbours
    # scarcity of each colour: colours with few vertices are cheap to "waste", crowded ones expensive
    sizes = np.asarray(color_sizes, dtype=float)
    total = sizes.sum()
    if total <= 0:
        return sat / max(c, 1)
    scarcity = 1.0 - sizes / total                          # (c,)
    crowd = blocked @ scarcity                              # mass of scarce colours among the blocked set
    # normalise into a bounded range
    return (sat / max(c, 1)) - (crowd / max(c, 1))

# f005 dsatur_distinct_neighbor_colors (deep): Saturation degree: fraction of used colours present among a candidate's coloured neighbours.
def _f005(neighbor_colors, adjacency, degree, color_sizes):
    """Saturation degree: fraction of used colours present among a candidate's coloured neighbours."""
    k = neighbor_colors.shape[0]
    c = neighbor_colors.shape[1]
    if c == 0:
        return np.zeros(k)
    saturation = (neighbor_colors > 0).sum(axis=1)
    return saturation / max(c, 1)

# f007 colored_neighbor_fraction (deep): Fraction of each candidate's neighbours that are already coloured.
def _f007(neighbor_colors, adjacency, degree, color_sizes):
    """Fraction of each candidate's neighbours that are already coloured."""
    colored = neighbor_colors.sum(axis=1)
    return colored / np.maximum(degree, 1)

# f022 would_take_colour_neighbour_block_share (wide): For each candidate: how much its colouring would free up colours for its uncoloured neighbours: counts uncolou
def _f022(neighbor_colors, adjacency, degree, color_sizes):
    """For each candidate: how much its colouring would free up colours for its uncoloured neighbours: counts uncoloured neighbours whose would-be colour is absent from the candidate's palette, i.e. colouring here removes a blocking colour from them."""
    k = neighbor_colors.shape[0]
    if k == 0:
        return np.zeros(0)
    c = neighbor_colors.shape[1]
    if c == 0:
        # No colours used yet: colouring any candidate opens colour 0 for everyone.
        # Measure how many uncoloured neighbours each candidate has that would then be free
        # (all of them, since colour 0 becomes available). Use neighbour count normalized.
        nb = adjacency.sum(axis=1).astype(float)
        return nb / np.maximum(nb.max(), 1.0)

    # Palette of each candidate: colours absent among its coloured neighbours.
    palette = (neighbor_colors == 0)                      # (k, c) colours this candidate could take
    # The colour each candidate WOULD take = first available column index (or c).
    first_avail = np.argmax(palette, axis=1)              # 0..c-1, but if none available argmax=0 wrongly
    has_avail = palette.any(axis=1)
    would_take = np.where(has_avail, first_avail, c)      # (k,)

    # For each uncoloured neighbour j of candidate i, does j's palette include i's would-take colour?
    # If yes, colouring i removes that colour from j's palette (blocks a slot).
    # We want the opposite: count neighbours for whom i's action does NOT block their would-take colour,
    # i.e. i's would-take colour is outside j's palette.
    # Build a (k, c) indicator of "would-take colour == column t"
    take_col = np.zeros((k, c), dtype=float)
    in_range = would_take < c
    rows = np.nonzero(in_range)[0]
    if rows.size:
        take_col[rows, would_take[rows]] = 1.0

    # neighbours_palette_col_t: for each candidate i and colour t, how many of i's uncoloured
    # neighbours have colour t in their palette. That is adjacency @ palette.
    nb_palette = adjacency.astype(float) @ palette          # (k, c): count of uncoloured neighbours with t in palette
    # For each candidate i: number of uncoloured neighbours that have i's would-take colour in palette
    blocked_count = np.einsum('ij,ij->i', nb_palette, take_col)   # (k,)
    nbr_count = adjacency.sum(axis=1).astype(float)
    # Fraction of uncoloured neighbours whose palette includes i's would-take colour.
    frac = blocked_count / np.maximum(nbr_count, 1.0)
    return np.nan_to_num(frac, nan=0.0, posinf=1.0, neginf=0.0)

_TERMS = [(_f003, np.array([10.762297])), (_f005, np.array([3.36458])), (_f007, np.array([0.077777])), (_f022, np.array([-0.185551]))]

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
