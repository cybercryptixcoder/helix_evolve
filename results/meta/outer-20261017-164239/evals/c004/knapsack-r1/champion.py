# Helix v3 policy: knapsack, gap 0.047%, progress 99.6%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f003 density_vs_best_remaining (wide): Density (value per unit weight) relative to the average density of the candidates still fitting.
def _f003(values, weights, remaining, capacity, taken):
    """Density (value per unit weight) relative to the average density of the candidates still fitting."""
    eps = 1e-9
    dens = values / (weights + eps)
    mean_dens = np.mean(dens) + eps
    return np.clip(dens / mean_dens - 1.0, -1.0, 1.0)

# f006 raw_weight_signal (deep): Candidate weight divided by the knapsack's total capacity.
def _f006(values, weights, remaining, capacity, taken):
    """Candidate weight divided by the knapsack's total capacity."""
    return weights / max(capacity, 1)

# f027 pair_fill_leftover_endgame (deep): Gated negative leftover after the best-fitting partner item (endgame pair-fill signal).
def _f027(values, weights, remaining, capacity, taken):
    """Gated negative leftover after the best-fitting partner item (endgame pair-fill signal)."""
    w = np.asarray(weights, dtype=float)
    k = w.size
    if k == 0:
        return np.zeros(0)
    rem = float(remaining)
    res = rem - w
    mask = (w[None, :] <= res[:, None])
    np.fill_diagonal(mask, False)
    pw = np.where(mask, w[None, :], 0.0).max(axis=1)
    left = res - pw
    mean_w = np.mean(w) + 1e-9
    gate = np.clip(1.0 - res / (4.0 * mean_w), 0.0, 1.0)
    return np.clip(-gate * left / (4.0 * mean_w), -1.0, 1.0)

# f025 residue_vs_lightest_penalty (deep): Negative scaled deficit of each candidate's residue below the lightest other fitting item's weight.
def _f025(values, weights, remaining, capacity, taken):
    """Negative scaled deficit of each candidate's residue below the lightest other fitting item's weight."""
    w = np.asarray(weights, dtype=float)
    k = w.size
    if k == 0:
        return np.zeros(0)
    rem = float(remaining)
    res = rem - w
    order = np.argsort(w, kind='stable')
    sw = w[order]
    L = np.full(k, sw[0])
    if k >= 2:
        L[order[0]] = sw[1] if sw[1] > sw[0] else sw[0]
    pen = np.clip((L - res) / np.maximum(L, 1.0), 0.0, 1.0)
    return -pen

# f030 pair_fill_densest_partner_gated (wide): Residual room left after pairing the candidate with the highest-value fitting partner, scaled by the partner's
def _f030(values, weights, remaining, capacity, taken):
    """Residual room left after pairing the candidate with the highest-value fitting partner, scaled by the partner's own density."""
    w = np.asarray(weights, dtype=float)
    v = np.asarray(values, dtype=float)
    k = w.size
    if k == 0:
        return np.zeros(0)
    rem = float(remaining)
    res = rem - w
    # candidates fitting in each candidate's residue
    mask = (w[None, :] <= res[:, None])
    np.fill_diagonal(mask, False)
    # partner chosen by density (value per weight), not raw value
    dens = v / (w + 1e-9)
    dens = np.where(mask, dens, -1e9)
    best_dens = dens.max(axis=1)
    has_partner = np.isfinite(best_dens) & (best_dens > -1e8)
    # residual gap after that densest fitting partner
    pw = np.where(mask, w[None, :], 0.0).max(axis=1)
    left = res - pw
    mean_w = np.mean(w) + 1e-9
    # gate: only matters when the candidate uses a large share of remaining room
    gate = np.clip(res / (2.0 * mean_w + rem + 1e-9), 0.0, 1.0) * has_partner
    # density advantage of the partner over the candidate itself
    adv = np.clip((np.where(has_partner, best_dens, 0.0) - dens.diagonal()) / (np.abs(best_dens) + 1e-9), -1.0, 1.0)
    return np.clip(-gate * (left / (2.0 * mean_w + 1e-9)), -1.0, 1.0) + 0.5 * np.clip(adv, -1.0, 1.0)

# f018 scarcity_dominance_count (deep): Fraction of other candidates that do NOT dominate the candidate (1 - dominators/(k-1)).
def _f018(values, weights, remaining, capacity, taken):
    """Fraction of other candidates that do NOT dominate the candidate (1 - dominators/(k-1))."""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    k = v.shape[0]
    if k == 0:
        return np.zeros(0)
    dom = (v[None, :] >= v[:, None]) & (w[None, :] <= w[:, None]) & \
          ((v[None, :] > v[:, None]) | (w[None, :] < w[:, None]))
    cnt = dom.sum(axis=1).astype(float)
    return 1.0 - cnt / max(k - 1, 1)

_TERMS = [(_f003, np.array([2.493249])), (_f006, np.array([2.975961])), (_f027, np.array([5.457085])), (_f025, np.array([-1.097128])), (_f030, np.array([0.094632])), (_f018, np.array([4.029748]))]

def priority(values, weights, remaining, capacity, taken):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(values, weights, remaining, capacity, taken), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(values))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
