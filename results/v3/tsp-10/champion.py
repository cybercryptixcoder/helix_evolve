# Helix v3 policy: tsp, gap 10.397%, progress 98.0%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 current_minus_centroid_distance (wide): Distance from each candidate to the centroid of all unvisited cities, minus its distance to the current city, 
def _f001(current, candidates, tour, start):
    """Distance from each candidate to the centroid of all unvisited cities, minus its distance to the current city, normalised."""
    if len(candidates) == 0:
        return np.zeros(0)
    centroid = candidates.mean(axis=0)
    d_cent = np.linalg.norm(candidates - centroid, axis=1)
    d_cur = np.linalg.norm(candidates - current, axis=1)
    diff = d_cur - d_cent
    scale = diff.std()
    if scale < 1e-9:
        return np.zeros(len(candidates))
    return diff / (scale + 1e-9)

# f004 distance_ratio_to_start (wide): Ratio of distance-to-current over distance-to-start: prefers cities near the end of the tour.
def _f004(current, candidates, tour, start):
    """Ratio of distance-to-current over distance-to-start: prefers cities near the end of the tour."""
    d_cur = np.linalg.norm(candidates - current[None, :], axis=1)
    d_start = np.linalg.norm(candidates - start[None, :], axis=1)
    ratio = d_cur / (d_start + 1e-9)
    # squash to roughly [-1, 1]
    return (ratio - 1.0) / (1.0 + ratio)

# f014 progress_blended_inverse_distance (wide): Ratio of distance-to-start over distance-to-current, weighted by how far the walk has progressed (fraction of 
def _f014(current, candidates, tour, start):
    """Ratio of distance-to-start over distance-to-current, weighted by how far the walk has progressed (fraction of cities visited): late in the tour strongly prefers returning near the start."""
    d_cur = np.linalg.norm(candidates - current[None, :], axis=1)
    d_start = np.linalg.norm(candidates - start[None, :], axis=1)
    m = len(tour)
    k = len(candidates)
    # progress in (0,1): fraction of cities already visited
    progress = m / float(m + k) if (m + k) > 0 else 0.0
    # early: prefer near-current (small d_cur); late: prefer near-start (small d_start)
    # combine with a progress-dependent blend
    near_cur = 1.0 / (d_cur + 1e-9)
    near_start = 1.0 / (d_start + 1e-9)
    score = (1.0 - progress) * near_cur + progress * near_start
    # squash via tanh-like normalisation to roughly [-1, 1]
    return np.tanh(score - np.median(score) if len(score) else score)

# f025 exact_tail_gate (deep): Negative exact optimal tail cost (current -> perm -> start) for the first city of the best permutation, gated 
def _f025(current, candidates, tour, start):
    """Negative exact optimal tail cost (current -> perm -> start) for the first city of the best permutation, gated to k <= 4, normalised."""
    k = len(candidates)
    if k > 4:
        return np.zeros(k)
    d_cur = np.linalg.norm(candidates - current, axis=1)
    d_start = np.linalg.norm(candidates - start, axis=1)
    best = np.full(k, np.inf)
    # enumerate permutations without itertools
    perms = [[]]
    for i in range(k):
        perms = [p + [i] for p in perms for i in range(k) if i not in p]
    for perm in perms:
        cost = d_cur[perm[0]]
        for i in range(k - 1):
            cost += np.linalg.norm(candidates[perm[i]] - candidates[perm[i + 1]])
        cost += d_start[perm[-1]]
        if cost < best[perm[0]]:
            best[perm[0]] = cost
    v = -best
    return v / (np.max(np.abs(v)) + 1e-9)

# f042 exact_tail_k5_to_7 (deep): Negative exact optimal tail cost (current -> candidate -> all remaining -> start), Held-Karp, only for k = 5..
def _f042(current, candidates, tour, start):
    """Negative exact optimal tail cost (current -> candidate -> all remaining -> start), Held-Karp, only for k = 5..7."""
    n = len(candidates)
    if n < 5 or n > 7:
        return np.zeros(n)
    P = np.vstack([candidates, start[None, :]])                 # index n is the start
    D = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2)   # (n+1, n+1)
    Dc = D[:n, :n]
    INF = 1e18
    R = np.full((1 << n, n), INF, dtype=float)                  # R[mask, j] = best cost j -> (mask) -> start
    for j in range(n):
        R[1 << j, j] = D[j, n]
    bit = (1 << np.arange(n))
    for size in range(2, n + 1):
        masks = np.array([msk for msk in range(1, 1 << n) if bin(msk).count('1') == size], dtype=int)
        prev = masks[:, None] ^ bit[None, :]                    # (M, n) mask without j
        vals = Dc[None, :, :] + R[prev, :]                      # (M, n, n): [m, j, i]
        R[masks] = vals.min(axis=2)
    full = (1 << n) - 1
    dcur = np.linalg.norm(candidates - current[None, :], axis=1)
    tail = dcur + R[full, :]
    if not np.all(np.isfinite(tail)):
        return np.zeros(n)
    return -(tail / (np.mean(tail) + 1e-12))

# f049 held_karp_tail_k8_to_10 (deep): Negative Held-Karp exact tail cost (current -> candidate -> all remaining -> start), standardised, for k in [8
def _f049(current, candidates, tour, start):
    """Negative Held-Karp exact tail cost (current -> candidate -> all remaining -> start), standardised, for k in [8,10]; zeros otherwise."""
    k = candidates.shape[0]
    if k < 8 or k > 10:
        return np.zeros(k)

    # Pairwise distances between candidates
    diff = candidates[:, None, :] - candidates[None, :, :]
    D = np.sqrt(np.sum(diff * diff, axis=2))  # (k, k)

    # Distance from each candidate to start (sink)
    ds = np.sqrt(np.sum((candidates - start[None, :]) ** 2, axis=1))  # (k,)

    full = (1 << k) - 1
    INF = 1e18
    # f[S][i]: min cost starting at i, visiting all of S (i in S), ending at start
    f = np.full((1 << k, k), INF)

    # Base: f[1<<i][i] = ||cand_i - start||
    for i in range(k):
        f[1 << i, i] = ds[i]

    # DP over subsets by increasing popcount
    for S in range(1, full + 1):
        # iterate bits i in S
        bits = S
        while bits:
            low = bits & (-bits)
            i = low.bit_length() - 1
            bits ^= low
            if S == (1 << i):
                continue
            rest = S ^ (1 << i)
            # min over j in rest of D[i,j] + f[rest][j]
            best = INF
            rbits = rest
            while rbits:
                rlow = rbits & (-rbits)
                j = rlow.bit_length() - 1
                rbits ^= rlow
                val = D[i, j] + f[rest, j]
                if val < best:
                    best = val
            f[S, i] = best

    # tail(c) = ||current - cand_c|| + f[full][c]
    dc = np.sqrt(np.sum((candidates - current[None, :]) ** 2, axis=1))  # (k,)
    tail = dc + f[full, :]

    vals = -tail
    mu = vals.mean()
    sd = vals.std()
    if sd < 1e-12:
        return np.zeros(k)
    return (vals - mu) / sd

_TERMS = [(_f001, np.array([-0.343433])), (_f004, np.array([-1.018398])), (_f014, np.array([0.262886])), (_f025, np.array([203.463299])), (_f042, np.array([105.127638])), (_f049, np.array([6.015059]))]

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
