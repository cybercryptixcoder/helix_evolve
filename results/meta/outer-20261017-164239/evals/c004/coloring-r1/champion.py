# Helix v3 policy: coloring, gap 7.134%, progress 87.6%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f008 free_colour_count (deep): Fraction of existing colours still free, weighted by how rare each free colour is among candidates.
def _f008(neighbor_colors, adjacency, degree, color_sizes):
    """Fraction of existing colours still free, weighted by how rare each free colour is among candidates."""
    k, c = neighbor_colors.shape
    if c == 0:
        return np.zeros(k)
    free = (neighbor_colors == 0).astype(float)          # (k, c) which colours are free per candidate
    # scarcity of each colour: 1 / (number of candidates that can still take it)
    avail = free.sum(axis=0)                              # (c,) candidates able to take each colour
    scarcity = 1.0 / np.maximum(avail, 1.0)               # (c,)
    weighted = free @ scarcity                            # (k,) sum over free colours of scarcity
    total = scarcity.sum()                                # normaliser: all colours free for one candidate
    return weighted / max(total, 1e-12)

# f005 dsatur_saturation (deep): Saturation pressure: distinct colours among coloured neighbours, weighted by how scarce those colours are glob
def _f005(neighbor_colors, adjacency, degree, color_sizes):
    """Saturation pressure: distinct colours among coloured neighbours, weighted by how scarce those colours are globally."""
    k, c = neighbor_colors.shape
    if c == 0:
        return np.zeros(k, dtype=float)
    present = (neighbor_colors > 0).astype(float)          # (k, c) which used colours touch the candidate
    sat = present.sum(axis=1)                              # distinct colours among coloured neighbours
    # scarcity of each colour: colours used by few vertices are the ones a candidate can still take,
    # so a candidate blocking many *rare* colours is more constrained than one blocking common ones.
    sizes = np.asarray(color_sizes, dtype=float)
    n = sizes.sum() + k
    scarcity = 1.0 / (sizes + 1.0)                         # in (0, 1], larger for rare colours
    weighted = present @ scarcity                          # (k,)
    # normalise both parts to [0, 1] and combine: saturation level plus rarity-weighted pressure
    sat_norm = sat / max(c, 1)
    w_norm = weighted / max(scarcity.sum(), 1e-12)
    return sat_norm + w_norm

# f033 residual_hub_tightness (deep): Residual degree times mean neighbourhood tightness (1/(1+free colours)), both normalised.
def _f033(neighbor_colors, adjacency, degree, color_sizes):
    """Residual degree times mean neighbourhood tightness (1/(1+free colours)), both normalised."""
    k = adjacency.shape[0]
    if k == 0:
        return np.zeros(0)
    # free colours per candidate: colours not yet used by any of its coloured neighbours
    if neighbor_colors.shape[1] == 0:
        nf = np.zeros(k)
    else:
        nf = (neighbor_colors == 0).sum(axis=1).astype(float)
    tight = 1.0 / (1.0 + nf)
    R = adjacency.sum(axis=1).astype(float)
    T = adjacency.astype(float) @ tight
    meanT = T / np.maximum(R, 1.0)
    R_norm = R / max(R.max(), 1.0)
    meanT_norm = meanT / max(meanT.max(), 1e-9)
    return R_norm * meanT_norm

_TERMS = [(_f008, np.array([-7.262397])), (_f005, np.array([1.459495])), (_f033, np.array([3.19223]))]

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
