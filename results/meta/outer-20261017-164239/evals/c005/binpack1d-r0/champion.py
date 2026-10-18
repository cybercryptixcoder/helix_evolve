# Helix v3 policy: binpack1d, gap 3.417%, progress 39.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f001 residual_fraction_after_placement (wide): Fraction of the bin's remaining room that would be left after placing the item (empty bin = 1).
def _f001(item, bins, capacity):
    """Fraction of the bin's remaining room that would be left after placing the item (empty bin = 1)."""
    after = (bins - item) / capacity
    return np.clip(after, -1.0, 1.0)

# f010 gated_residual_tightness (wide): Post-placement residual fraction, gated so it only fires when the item nearly fills or overfills the bin; othe
def _f010(item, bins, capacity):
    """Post-placement residual fraction, gated so it only fires when the item nearly fills or overfills the bin; otherwise a mild preference for the fullest bin still fit."""
    # normalized item size
    s = item / capacity
    after = np.clip((bins - item) / capacity, -1.0, 1.0)
    # gate: strong signal when placement leaves very little room (tight fit) or overflows slack
    tight = 1.0 / (1.0 + np.exp(-(0.05 - np.abs(after)) * 40.0))  # ~1 when |after| small
    # near-full preference: bins whose remaining room is close to the item size get boosted
    near = np.exp(-((bins - item) / capacity) ** 2 / 0.02)
    # combine: tight fits pushed down (good for first-fit-decreasing-like behavior), empty bin mildly penalized
    val = -after * (0.5 + 0.5 * tight) + 0.15 * near * (1.0 - tight) - 0.1 * s * tight
    return np.clip(val, -1.0, 1.0)

# f012 tight_fit_gated_residual (wide): Post-placement residual fraction, gated by how tight the fit is relative to the item (sharp best-fit signal).
def _f012(item, bins, capacity):
    """Post-placement residual fraction, gated by how tight the fit is relative to the item (sharp best-fit signal)."""
    after = (bins - item) / capacity
    # tightness: how small the leftover is compared to the item size (0 = exact fit, 1 = lots of slack)
    slack_ratio = np.clip((bins - item) / max(item, 1), -1.0, 1.0)
    # sharp gate: exact fits get strongly boosted, loose fits suppressed
    gated = np.tanh(3.0 * (1.0 - np.abs(slack_ratio)))
    return np.clip(after * gated, -1.0, 1.0)

# f022 complete_midfull_bins (deep): Negative post-placement residual fraction, gated to bins 50-80% full that fit the item.
def _f022(item, bins, capacity):
    """Negative post-placement residual fraction, gated to bins 50-80% full that fit the item."""
    bins = np.asarray(bins, dtype=float)
    cap = float(capacity)
    after = (bins - item) / cap
    fill_before = 1.0 - bins / cap
    gate = ((fill_before >= 0.5) & (fill_before <= 0.80) & (bins >= item)).astype(float)
    return np.clip(gate * (-after), -1.0, 1.0)

_TERMS = [(_f001, np.array([-9.097907])), (_f010, np.array([-2.715061])), (_f012, np.array([-72.015349])), (_f022, np.array([8.720241]))]

def priority(item, bins, capacity):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(item, bins, capacity), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(bins))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
