# Helix v3 policy: tsp, gap 8.177%, progress 98.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f007 nearest_neighbour_distance (deep): Next-step Euclidean distance to each candidate as a fraction of the two-leg path current->candidate->start (ne
def _f007(current, candidates, tour, start):
    """Next-step Euclidean distance to each candidate as a fraction of the two-leg path current->candidate->start (near-now but far-from-start scores high)."""
    d = np.linalg.norm(candidates - current, axis=1)
    d_back = np.linalg.norm(candidates - start, axis=1)
    return -(d / (d + d_back + 1e-9))

# f002 nearest_gap_savings (wide): Savings of visiting now: distance from candidate to its nearest other unvisited city minus distance from curre
def _f002(current, candidates, tour, start):
    """Savings of visiting now: distance from candidate to its nearest other unvisited city minus distance from current to it (normalised)."""
    k = len(candidates)
    d = np.linalg.norm(candidates[:, None, :] - candidates[None, :, :], axis=-1)
    np.fill_diagonal(d, np.inf)
    nearest_other = d.min(axis=1) if k > 1 else np.full(k, np.inf)
    dcur = np.linalg.norm(candidates - current, axis=1)
    saving = nearest_other - dcur
    # k == 1 (or degenerate) fallback: pure closeness
    saving = np.where(np.isfinite(saving), saving, -dcur)
    scale = np.max(np.abs(saving)) + 1e-9
    return saving / scale

# f021 mean_isolation_savings (wide): Savings of visiting now under mean isolation: mean distance from each candidate to the other unvisited cities 
def _f021(current, candidates, tour, start):
    """Savings of visiting now under mean isolation: mean distance from each candidate to the other unvisited cities minus the distance from current to it (normalised)."""
    k = len(candidates)
    dcur = np.linalg.norm(candidates - current, axis=1)
    if k <= 1:
        saving = -dcur
        scale = np.max(np.abs(saving)) + 1e-9
        return saving / scale
    # pairwise distances between candidates (self-distance is 0)
    d = np.linalg.norm(candidates[:, None, :] - candidates[None, :, :], axis=-1)
    mean_other = d.sum(axis=1) / (k - 1)
    saving = mean_other - dcur
    scale = np.max(np.abs(saving)) + 1e-9
    return saving / scale

# f037 gated_home_contrast_endgame (deep): Gate-weighted distance-to-start contrast measured per unit leg: (1-k/n)^2 * (mean(dh)-dh)/(||c-current||+1e-9)
def _f037(current, candidates, tour, start):
    """Gate-weighted distance-to-start contrast measured per unit leg: (1-k/n)^2 * (mean(dh)-dh)/(||c-current||+1e-9), clipped to [-gate, gate]."""
    k = candidates.shape[0]
    if k <= 1:
        return np.zeros(k)
    dh = np.linalg.norm(candidates - start, axis=1)
    leg = np.linalg.norm(candidates - current, axis=1)
    n = tour.shape[0] + k
    gate = (1.0 - k / n) ** 2
    vals = gate * (dh.mean() - dh) / (leg + 1e-9)
    out = np.clip(vals, -gate, gate)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)

# f043 path_clearance_outward (wide): Distance from each candidate to the already-walked path (excluding the latest leg), normalised by the largest 
def _f043(current, candidates, tour, start):
    """Distance from each candidate to the already-walked path (excluding the latest leg), normalised by the largest such distance: high = the candidate lies in open, not-yet-swept territory."""
    k = candidates.shape[0]
    m = tour.shape[0]
    if k == 0 or m <= 2:
        return np.zeros(k)
    # segments of the path strictly before the current city: tour[0..m-2]
    a = tour[:-2]      # (s, 2)
    b = tour[1:-1]     # (s, 2)
    seg = b - a
    seg_len2 = np.einsum('ij,ij->i', seg, seg)
    seg_len2 = np.where(seg_len2 < 1e-12, 1e-12, seg_len2)

    rel = candidates[:, None, :] - a[None, :, :]            # (k, s, 2)
    t = np.einsum('ksj,sj->ks', rel, seg) / seg_len2[None, :]
    t = np.clip(t, 0.0, 1.0)
    closest = a[None, :, :] + t[:, :, None] * seg[None, :, :]  # (k, s, 2)
    d = np.linalg.norm(candidates[:, None, :] - closest, axis=-1)  # (k, s)
    mind = d.min(axis=1)

    scale = mind.max()
    if not np.isfinite(scale) or scale < 1e-9:
        return np.zeros(k)
    return mind / scale

_TERMS = [(_f007, np.array([1.501666])), (_f002, np.array([6.953105])), (_f021, np.array([6.462188])), (_f037, np.array([-5.121117])), (_f043, np.array([0.454154]))]

def priority(current, candidates, tour, start):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(current, candidates, tour, start), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(candidates))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
