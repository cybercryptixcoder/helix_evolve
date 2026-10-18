# Helix v3 policy: binpack2d, gap 6.115%, progress 35.1%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f008 stranded_risk_penalty (deep): -1 where placing the job strands the bin (min remaining <5% of capacity, max >25%), else 0.
def _f008(item, bins, capacity):
    """-1 where placing the job strands the bin (min remaining <5% of capacity, max >25%), else 0."""
    res = bins - item
    min_r = np.minimum(res[:, 0], res[:, 1]) / np.min(capacity)
    max_r = np.maximum(res[:, 0], res[:, 1]) / np.max(capacity)
    stranded = (min_r < 0.05) & (max_r > 0.25)
    return np.where(stranded, -1.0, 0.0)

# f010 worst_relative_leftover_after_placement (wide): Worst-case relative leftover after placing: negative of the max over resources of |remaining-after| / capacity
def _f010(item, bins, capacity):
    """Worst-case relative leftover after placing: negative of the max over resources of |remaining-after| / capacity, i.e. how badly the best-fitting dimension is left unbalanced."""
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    b = np.asarray(bins, dtype=float) / cap[None, :]
    it = np.asarray(item, dtype=float) / cap
    rem = b - it[None, :]                       # leftover per resource after placement
    # Per-resource relative imbalance, capped so infeasible (negative) rows are penalised hard.
    rel = rem / np.maximum(b, 1e-9)             # leftover as a fraction of what the bin had
    worst = np.max(np.abs(rel), axis=1)         # the most lopsided dimension dominates
    return np.clip(-worst, -1.0, 1.0)

# f016 bolder_stranding_magnitude (deep): Negative max normalised residual where the min residual is below 10% of capacity, else 0.
def _f016(item, bins, capacity):
    """Negative max normalised residual where the min residual is below 10% of capacity, else 0."""
    cap = np.asarray(capacity, dtype=float)
    cap = np.where(cap > 0, cap, 1.0)
    rem = np.clip(np.asarray(bins, dtype=float) / cap - np.asarray(item, dtype=float) / cap, 0.0, None)
    mn = rem.min(axis=1)
    mx = rem.max(axis=1)
    values = np.where(mn < 0.10, -mx, 0.0)
    return np.clip(values, -1.0, 1.0)

# f049 item_caused_stranding_large (deep): Negative stranding penalty weighted by the tightest-dimension fraction the item consumes, only for large items
def _f049(item, bins, capacity):
    """Negative stranding penalty weighted by the tightest-dimension fraction the item consumes, only for large items (max dim > 35% of capacity)."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)

    rem = b / cap - it / cap
    strand = (rem.min(axis=1) < 0.05) & (rem.max(axis=1) > 0.25)

    consumed = (it / np.maximum(b, 1.0)).max(axis=1)
    consumed = np.clip(consumed, 0.0, 1.0)

    big = float((it / cap).max() > 0.35)

    return np.clip(-strand.astype(float) * consumed * big, -1.0, 1.0)

# f080 item_bin_harmonic_residual (wide): Residual after placement measured relative to the *harmonic* interaction of item and bin: negative of the max 
def _f080(item, bins, capacity):
    """Residual after placement measured relative to the *harmonic* interaction of item and bin: negative of the max over resources of |remaining| / sqrt(item * bin_remaining_before), so a dimension where the bin was nearly empty or the item is tiny cannot dominate, and only a genuinely badly-matched tight dimension is penalised."""
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    b = np.asarray(bins, dtype=float) / cap[None, :]
    it = np.asarray(item, dtype=float) / cap
    rem = b - it[None, :]                       # leftover per resource after placement
    # Geometric-mean scale: large only when the item AND the bin were both substantial on
    # this resource. A leftover is only "bad" if it wastes a resource the item relied on
    # and the bin actually had. This decouples from pure size (f010) and pure item demand.
    scale = np.sqrt(np.maximum(it[None, :], 1e-9) * np.maximum(b, 1e-9))
    rel = rem / scale
    # Asymmetric: over-stuffing the tight dimension (rem>0 huge) vs leaving the bin empty
    # there. Cap magnitude so infeasible rows are penalised but bounded.
    signed = np.clip(rel, -3.0, 3.0)
    worst = np.max(np.abs(signed), axis=1)
    return np.clip(-worst, -1.0, 1.0)

# f117 large_both_dim_dead_band (deep): -1 when a large item leaves both post-placement residuals in the dead band [5%, 30%], else 0.
def _f117(item, bins, capacity):
    """-1 when a large item leaves both post-placement residuals in the dead band [5%, 30%], else 0."""
    cap = np.asarray(capacity, dtype=float)
    it = np.asarray(item, dtype=float)
    b = np.asarray(bins, dtype=float)
    r = np.clip((b - it) / cap, 0.0, 1.0)          # shape (k, 2)
    rmin = r.min(axis=1)
    rmax = r.max(axis=1)
    large = (it / cap).max() >= 0.30
    dead = (rmin >= 0.05) & (rmax <= 0.30)
    return np.where(large & dead, -1.0, 0.0)

_TERMS = [(_f008, np.array([8.608683])), (_f010, np.array([7.053094])), (_f016, np.array([3.905622])), (_f049, np.array([-0.679])), (_f080, np.array([1.034155])), (_f117, np.array([2.04061]))]

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
