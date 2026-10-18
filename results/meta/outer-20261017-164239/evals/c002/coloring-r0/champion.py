# Helix v3 policy: coloring, gap 13.598%, progress 76.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 saturation_uncoloured_degree_blocking (wide): Per candidate: fraction of used colours already touching it, fraction of its neighbours still uncoloured, and 
def _f005(neighbor_colors, adjacency, degree, color_sizes):
    """Per candidate: fraction of used colours already touching it, fraction of its neighbours still uncoloured, and how many of those uncoloured neighbours could still take the colour it would itself take."""
    k, c = neighbor_colors.shape
    if k == 0:
        return np.zeros((0, 3))
    dmax = max(float(degree.max()), 1.0)

    # saturation: how many distinct colours already sit on its neighbours
    sat = (neighbor_colors > 0).sum(axis=1).astype(float)
    sat_frac = sat / max(c, 1)

    # remaining (uncoloured) degree: how much freedom is left in its local subgraph
    uncol = adjacency.sum(axis=1).astype(float)
    uncol_frac = uncol / dmax

    # the colour this candidate would take: first zero column, else a new colour c
    avail = neighbor_colors == 0                      # (k, c)
    if c == 0:
        first = np.zeros(k, dtype=np.intp)            # no colours yet -> new colour 0
        avail_full = np.ones((k, 1), dtype=bool)
    else:
        any_free = avail.any(axis=1)
        first = np.where(any_free, avail.argmax(axis=1), c).astype(np.intp)
        avail_full = np.concatenate([avail, np.ones((k, 1), dtype=bool)], axis=1)

    # lose[i, j] = True if colour that candidate i would take is still free for candidate j
    lose = avail_full[:, first].T.astype(float)
    impact = (adjacency.astype(float) * lose).sum(axis=1)
    impact_frac = impact / dmax

    return np.column_stack([sat_frac, uncol_frac, impact_frac])

# f028 min_free_colour_contention (wide): Per candidate: fraction of used colours already touching it, the share of its own degree that is still uncolou
def _f028(neighbor_colors, adjacency, degree, color_sizes):
    """Per candidate: fraction of used colours already touching it, the share of its own degree that is still uncoloured, and (over its free colours) the smallest number of uncoloured neighbours that could also take that colour, as a share of its uncoloured neighbours."""
    k, c = neighbor_colors.shape
    if k == 0:
        return np.zeros((0, 3))

    adjf = adjacency.astype(float)
    uncol = adjf.sum(axis=1)                      # uncoloured neighbours (remaining degree)
    deg = np.maximum(degree.astype(float), 1.0)

    # 1) first-order saturation: distinct used colours on its neighbours
    sat = (neighbor_colors > 0).sum(axis=1).astype(float)
    sat_frac = sat / max(c, 1)

    # 2) relative remaining freedom: what share of its OWN degree is still uncoloured
    #    (per-candidate normalisation, not a global max-degree normalisation)
    uncol_frac = uncol / deg

    # 3) flexibility of colour choice: for every colour still free at this candidate,
    #    count the uncoloured neighbours that could also take it; take the minimum
    #    (the least contested free colour) as a share of its uncoloured neighbours.
    if c == 0:
        contention = np.ones(k)                   # no colours yet: everyone opens a new class
    else:
        avail = (neighbor_colors == 0).astype(float)   # (k, c) colours still free here
        contention_mat = adjf @ avail                  # (k, c) neighbours that share each colour
        blocked = np.where(avail > 0, contention_mat, np.inf)
        min_cont = blocked.min(axis=1)
        has_free = avail.any(axis=1)
        # no free colour -> must open a new class: maximal contention
        min_cont = np.where(has_free, min_cont, uncol)
        contention = min_cont / np.maximum(uncol, 1.0)

    return np.column_stack([sat_frac, uncol_frac, contention])

_TERMS = [(_f005, np.array([-0.244686, 11.904671, -8.970868])), (_f028, np.array([-0.669695, -0.796818, -0.579632]))]

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
