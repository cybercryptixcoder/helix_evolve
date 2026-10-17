# Helix v3 policy: coloring, gap 20.311%, progress 64.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 neighbour_saturation_pressure (wide): Fraction of uncoloured neighbours that would be forced into a new colour if this candidate is coloured now (sa
def _f002(neighbor_colors, adjacency, degree, color_sizes):
    """Fraction of uncoloured neighbours that would be forced into a new colour if this candidate is coloured now (saturation pressure on the neighbourhood)."""
    k = neighbor_colors.shape[0]
    if k == 0:
        return np.zeros(0)
    c = neighbor_colors.shape[1]
    # A neighbour is "blocked" on colour j if it already has a neighbour (anywhere) with colour j.
    # We approximate using the candidate's own row: colours present in its neighbourhood.
    used = (neighbor_colors > 0).astype(float)  # (k, c) which colours touch each candidate
    # For each candidate, count how many of its uncoloured neighbours are already blocked on every colour
    # Blocked on colour j for neighbour v ~ (colours present among v's coloured neighbours) OR (candidate's own used colours, since candidate would take a colour).
    # Approximate: a neighbour loses a free colour j if it has colour j among its own used colours OR the candidate takes colour j.
    # Candidate takes colour = first zero column. Compute that colour index per candidate.
    if c == 0:
        # No colours yet: colouring any candidate forces neighbours? No, first colour only affects itself.
        return np.zeros(k)
    first_zero = np.argmax(neighbor_colors == 0, axis=1).astype(float)
    has_zero = (neighbor_colors == 0).any(axis=1)
    take = np.where(has_zero, first_zero, float(c))  # colour each candidate would take
    # Count free colours per candidate (columns that are zero in its row)
    free_self = (neighbor_colors == 0).sum(axis=1).astype(float)
    # Estimate pressure: neighbours adjacent to candidate that have few free colours -> being forced.
    # For neighbour v (an uncoloured vertex adjacent to candidate), if candidate takes colour t,
    # v loses colour t if v had t free. So v's free count drops by 1 when t is among v's zeros.
    # We can't see arbitrary v's zeros; approximate via adjacency-weighted propagation:
    # Each candidate's row of zeros vs its neighbours' rows is not available, so use degree-normalised
    # pressure: candidate's own scarcity plus adjacency to many constrained candidates.
    # Use adjacency to sum neighbours' (c - free) = used count, i.e. saturation of neighbours.
    used_count = used.sum(axis=1)  # colours used among each candidate's coloured neighbours
    sat = used_count / max(c, 1)
    neigh_sat = adjacency.astype(float) @ sat
    neigh_deg = adjacency.sum(axis=1).astype(float)
    avg_neigh_sat = neigh_sat / np.maximum(neigh_deg, 1.0)
    # Candidate that takes a NEW colour (no zero column) wastes resources; penalise via sat
    takes_new = (~has_zero).astype(float)
    val = 0.5 * avg_neigh_sat + 0.3 * sat - 0.4 * takes_new
    return val.astype(float)

# f045 target_class_two_hop_affinity (deep): Fraction of a candidate's uncoloured neighbours adjacent to at least one member of the colour class the candid
def _f045(neighbor_colors, adjacency, degree, color_sizes):
    """Fraction of a candidate's uncoloured neighbours adjacent to at least one member of the colour class the candidate would join (0 if it would open a new colour)."""
    k, c = neighbor_colors.shape
    if c == 0:
        return np.zeros(k)
    used = neighbor_colors > 0
    free = ~used
    t = np.where(free.any(axis=1), np.argmax(free, axis=1), c)
    ts = np.minimum(t, max(c - 1, 0))
    vals = neighbor_colors[:, ts]  # (k, k): vals[u, v] = # colour-t(v) vertices adjacent to u
    raw = (adjacency * (vals > 0).T).sum(axis=1)
    out = raw / (1.0 + adjacency.sum(axis=1))
    out[t >= c] = 0.0
    return out

_TERMS = [(_f002, np.array([11.718303])), (_f045, np.array([0.036276]))]

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
