# Helix v3 policy: backtrack, gap 33.949%, progress 66.0%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f007 basin_slack_tightness (deep): Tightness 1/(1+slo+shi) of the tightest basin each candidate belongs to, 0 if in none.
def _f007(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):
    """Tightness 1/(1+slo+shi) of the tightest basin each candidate belongs to, 0 if in none."""
    k = domain.shape[0]
    dom_min = np.argmax(domain, axis=1).astype(float)
    dom_max = (3 - np.argmax(domain[:, ::-1], axis=1)).astype(float)
    M = basins.astype(float)
    min_sum = M.T @ dom_min
    max_sum = M.T @ dom_max
    slo = np.maximum(basin_rest - min_sum, 0.0)
    shi = np.maximum(max_sum - basin_rest, 0.0)
    t = 1.0 / (1.0 + slo + shi)
    masked = np.where(basins, t[None, :], -1.0)
    best = masked.max(axis=1)
    return np.where(basins.any(axis=1), best, 0.0)

# f011 census_scarcity_basin_amplified (wide): Census scarcity weighted by basin tightness: how rare a candidate's feasible depths are in the census, amplifi
def _f011(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):
    """Census scarcity weighted by basin tightness: how rare a candidate's feasible depths are in the census, amplified when the candidate sits in a tight basin (small slack)."""
    k = domain.shape[0]
    # scarcity of each depth in [0,1]: rarer remaining census slot -> higher
    tot = float(max(census_left.sum(), 1))
    scarcity = (tot - census_left.astype(float)) / tot
    # candidate's scarcity-weighted domain mass
    mass = (domain.astype(float) * scarcity[None, :]).sum(axis=1)
    # basin tightness (same geometry as f007): tight basins amplify the census signal
    dom_min = np.argmax(domain, axis=1).astype(float)
    dom_max = (3 - np.argmax(domain[:, ::-1], axis=1)).astype(float)
    M = basins.astype(float)
    min_sum = M.T @ dom_min
    max_sum = M.T @ dom_max
    slo = np.maximum(basin_rest - min_sum, 0.0)
    shi = np.maximum(max_sum - basin_rest, 0.0)
    tight = 1.0 / (1.0 + slo + shi)
    masked = np.where(basins, tight[None, :], 0.0)
    best_tight = masked.max(axis=1)  # 0 if in no basin
    # combine: scarcity mass scaled up by tightness (candidates in tight basins matter more)
    amp = 1.0 + best_tight
    out = mass * amp / 4.0
    # normalise to roughly [-1,1] range
    return np.clip(out, -1.0, 1.0)

# f034 basin_stranding_tightness_weighted (wide): For each candidate: the fraction of its feasible depths that force a wipeout or completion in the tightest bas
def _f034(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):
    """For each candidate: the fraction of its feasible depths that force a wipeout or completion in the tightest basin it belongs to, scaled by how tight that basin is (bad -> negative)."""
    k = domain.shape[0]
    dom_size = domain.sum(axis=1).astype(float)
    safe_size = np.where(dom_size > 0, dom_size, 1.0)

    # basin geometry: slack of each basin given current domains (as in f007)
    dom_min = np.argmax(domain, axis=1).astype(float)
    dom_max = (3 - np.argmax(domain[:, ::-1], axis=1)).astype(float)
    M = basins.astype(float)
    min_sum = M.T @ dom_min          # (B,)
    max_sum = M.T @ dom_max          # (B,)
    slo = np.maximum(basin_rest - min_sum, 0.0)
    shi = np.maximum(max_sum - basin_rest, 0.0)
    tight = 1.0 / (1.0 + slo + shi)  # (B,) larger = tighter

    # For each basin, sum of the domains (as index sums) of its candidate members
    # so we can locate "the other open member(s)" for a candidate.
    idx = np.arange(k).astype(float)
    sum_idx = M.T @ idx               # (B,)
    cnt = M.sum(axis=0)               # (B,) members that are still candidates
    open_cnt = basin_open.astype(float)  # (B,) open members overall (== cnt for basins tracked)

    # partner set size per candidate per basin = open members of basin minus itself
    others = np.maximum(open_cnt[None, :] - M, 0.0)  # (k,B): count of other open members

    # For each candidate c, basin b, and own feasible depth v, check whether
    # EVERY other open member of the basin can still reach a depth making the
    # basin total exactly basin_rest. We approximate by requiring the residual
    # rest - v to be coverable by the other open members with their domains.
    rest_b = basin_rest[None, :, None]          # (1,B,1)
    v = np.arange(4)[None, None, :]             # (1,1,4)
    residual = rest_b - v                       # (1,B,4) -> broadcast
    lo = np.maximum(residual - 3.0 * others[:, :, None], 0.0)  # min each other could take
    hi = np.minimum(residual, 3.0 * others[:, :, None])        # max each other could take
    # residual must be between the min and max achievable by the others (others each in [0,3])
    coverable = (residual >= lo - 1e-9) & (residual <= hi + 1e-9) & (residual >= 0.0)

    # candidate's own feasible depths
    own_feas = domain[:, None, :].astype(bool)  # (k,1,4) -> broadcast to (k,B,4)
    # basin must have at least one other open member to be a "pair" situation
    has_other = (others > 0)[:, :, None]        # (k,B,1)

    bad = own_feas & (~coverable) & has_other   # (k,B,4): own depth would strand basin
    n_bad = bad.sum(axis=2).astype(float)       # (k,B)

    # only basins the candidate belongs to
    in_basin = basins  # (k,B)
    frac_b = np.where(in_basin, n_bad / safe_size[:, None], 0.0)  # (k,B)

    # weight by basin tightness, take the worst (max) over basins
    weighted = frac_b * tight[None, :]
    worst = weighted.max(axis=1)

    # normalise into roughly [-1,1]: bad is negative signal
    return np.clip(-worst, -1.0, 1.0)

# f037 census_hall_infeasible_depth_fraction (deep): Fraction of a candidate's feasible depths that break the census Hall condition.
def _f037(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):
    """Fraction of a candidate's feasible depths that break the census Hall condition."""
    k = domain.shape[0]
    # 16 subsets as bitmasks 0..15; in_S[s, d] = 1 if depth d is in subset s
    s_idx = np.arange(16)
    in_S = ((s_idx[:, None] >> np.arange(4)[None, :]) & 1).astype(np.float64)  # (16,4)

    # A_S = number of candidates whose domain meets subset S
    meets = (domain.astype(np.float64) @ in_S.T) > 0  # (k,16) bool
    A_S = meets.sum(axis=0).astype(np.float64)  # (16,)

    # dem_S = sum of census_left over depths in S
    dem_S = in_S @ census_left.astype(np.float64)  # (16,)

    base = dem_S - A_S  # (16,)

    # v_in_S[v, s] = 1 if depth v in subset S
    v_in_S = in_S.T  # (4,16)

    # inter[i, s] = 1 if candidate i meets subset S
    inter = meets.astype(np.float64)  # (k,16)

    # feasible[i, v] = all_S base[s] - v_in_S[v,s] + inter[i,s] <= 1e-9
    # shape (k,4,16)
    val = base[None, None, :] - v_in_S[None, :, :] + inter[:, None, :]
    feasible = np.all(val <= 1e-9, axis=2) & domain  # (k,4)

    dsize = np.maximum(domain.sum(axis=1), 1).astype(np.float64)
    return 1.0 - feasible.sum(axis=1) / dsize

# f080 basin_second_order_tightness (deep): Tightness 1/(1+W) of each candidate's second-tightest basin with >=2 open members, 0 if none.
def _f080(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):
    """Tightness 1/(1+W) of each candidate's second-tightest basin with >=2 open members, 0 if none."""
    k = domain.shape[0]
    B = basins.shape[1]
    dmin = np.argmax(domain, axis=1).astype(float)
    dmax = (3 - np.argmax(domain[:, ::-1], axis=1)).astype(float)
    M = basins.astype(float)
    W = (M.T @ dmax) - (M.T @ dmin)  # (B,) window width of each basin's open members
    mask = basins & (basin_open[None, :] >= 2)
    Wm = np.where(mask, W[None, :], np.inf)
    if B > 1:
        order = np.argsort(Wm, axis=1)
        second = Wm[np.arange(k), order[:, 1]]
    else:
        second = np.full(k, np.inf)
    return np.where(np.isfinite(second), 1.0 / (1.0 + second), 0.0)

# f082 basin_bottleneck_multi_constraint_tightness (wide): Basin 'bottleneck tightness': for each candidate, the tightest basin it is in, but discounted by how many othe
def _f082(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):
    """Basin 'bottleneck tightness': for each candidate, the tightest basin it is in, but discounted by how many other tight basins it also shares (multi-constraint pressure)."""
    k = domain.shape[0]
    B = basins.shape[1]
    dmin = np.argmax(domain, axis=1).astype(float)
    dmax = (3 - np.argmax(domain[:, ::-1], axis=1)).astype(float)
    M = basins.astype(float)
    min_sum = M.T @ dmin
    max_sum = M.T @ dmax
    slo = np.maximum(basin_rest - min_sum, 0.0)
    shi = np.maximum(max_sum - basin_rest, 0.0)
    W = slo + shi  # (B,) total slack/overshoot width
    tight = 1.0 / (1.0 + W)  # (B,)
    mask = basins & (basin_open[None, :] >= 2)
    tight_masked = np.where(mask, tight[None, :], 0.0)  # (k,B)
    best = tight_masked.max(axis=1)  # (k,)
    # number of basins the candidate shares that are at least moderately tight
    share = (tight_masked > 0.2).sum(axis=1).astype(float)
    # discount: more shared tight basins -> less unique pressure from the single tightest
    out = best * (1.0 + np.log1p(share)) / 4.0
    return np.clip(out, -1.0, 1.0)

_TERMS = [(_f007, np.array([4.400485])), (_f011, np.array([-0.256523])), (_f034, np.array([-3.279182])), (_f037, np.array([-42.784483])), (_f080, np.array([2.458985])), (_f082, np.array([0.132202]))]

def priority(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(domain, links, assigned_links, basins, basin_open, basin_rest, wipeouts, census_left, depth), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(domain))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
