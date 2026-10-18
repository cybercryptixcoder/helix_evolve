# Helix v3 policy: coloring, gap 15.467%, progress 73.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 color_option_fraction (wide): Fraction of currently used colours that a candidate could legally take (conflict-free colour options).
def _f002(neighbor_colors, adjacency, degree, color_sizes):
    """Fraction of currently used colours that a candidate could legally take (conflict-free colour options)."""
    k, c = neighbor_colors.shape
    if c == 0:
        return np.zeros(k)
    # a colour is available to a candidate iff no neighbour uses it (count == 0)
    available = (neighbor_colors == 0)
    n_avail = available.sum(axis=1).astype(float)
    return n_avail / c

# f001 colored_neighbor_fraction_minus_open_fraction (wide): Fraction of a candidate's neighbours that are already coloured, i.e. how constrained (saturation) the vertex i
def _f001(neighbor_colors, adjacency, degree, color_sizes):
    """Fraction of a candidate's neighbours that are already coloured, i.e. how constrained (saturation) the vertex is."""
    k = neighbor_colors.shape[0]
    if k == 0:
        return np.zeros(0)
    n = k + int(color_sizes.sum())
    nc = neighbor_colors.sum(axis=1).astype(float)
    d = degree.astype(float)
    sat = np.divide(nc, np.maximum(d, 1.0), out=np.zeros(k), where=d > 0)
    # uncoloured-degree normalisation as well: how concentrated its remaining uncoloured neighbours are
    uncol_deg = adjacency.sum(axis=1).astype(float)
    frac_open = np.divide(uncol_deg, np.maximum(d, 1.0), out=np.zeros(k), where=d > 0)
    return np.clip(sat - frac_open, -1.0, 1.0)

# f016 degree_tiebreak_on_max_saturation (deep): Normalised degree, masked to candidates at maximum saturation (0 if not at max saturation).
def _f016(neighbor_colors, adjacency, degree, color_sizes):
    """Normalised degree, masked to candidates at maximum saturation (0 if not at max saturation)."""
    k, c = neighbor_colors.shape
    d = degree.astype(float)
    dn = d / max(d.max(), 1.0)
    if c == 0:
        return dn
    sat = (neighbor_colors > 0).sum(axis=1).astype(float)
    mask = (sat == sat.max()).astype(float)
    return mask * dn

# f010 relative_saturation_forced_crowding (wide): Saturation of a candidate relative to the most saturated candidate, weighted by how close it is to being force
def _f010(neighbor_colors, adjacency, degree, color_sizes):
    """Saturation of a candidate relative to the most saturated candidate, weighted by how close it is to being forced to open a new colour (crossover pressure)."""
    k = neighbor_colors.shape[0]
    if k == 0:
        return np.zeros(0)
    c = neighbor_colors.shape[1]
    d = degree.astype(float)

    # raw number of distinct colours among coloured neighbours (DSATUR saturation degree)
    distinct = (neighbor_colors > 0).sum(axis=1).astype(float)

    # relative saturation: how this candidate's saturation compares to the front-runner
    max_distinct = float(distinct.max()) if k > 0 else 0.0
    rel_sat = distinct / max_distinct if max_distinct > 0 else np.zeros(k)

    # closeness to being forced onto a new colour: fraction of used colours blocked
    if c == 0:
        blocked_frac = np.zeros(k)
    else:
        blocked = (neighbor_colors > 0).sum(axis=1).astype(float)
        blocked_frac = blocked / c

    # how tightly packed its uncoloured neighbourhood is: candidate is "crowded" when
    # few of its neighbours remain uncoloured but those few are highly interconnected
    uncol_deg = adjacency.sum(axis=1).astype(float)
    # density of the subgraph induced on this candidate's uncoloured neighbours
    # adjacency @ adjacency gives, per candidate, sum over neighbours of their uncoloured degree
    second = (adjacency.astype(float) @ adjacency.astype(float)).diagonal()
    crowd = np.divide(second, np.maximum(uncol_deg * np.maximum(uncol_deg - 1.0, 1.0), 1.0),
                      out=np.zeros(k), where=uncol_deg > 1)

    # combine: prefer saturated vertices that are near the "must open a colour" boundary,
    # and whose remaining neighbourhood is dense (colour choices will collapse quickly)
    val = 0.5 * rel_sat + 0.5 * blocked_frac + 0.25 * crowd
    return np.clip(val, -1.0, 1.0)

_TERMS = [(_f002, np.array([-6.489036])), (_f001, np.array([2.020273])), (_f016, np.array([2.564341])), (_f010, np.array([-5.151156]))]

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
