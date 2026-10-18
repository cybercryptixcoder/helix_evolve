# Helix v3 policy: binpack1d, gap 3.468%, progress 38.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 residual_newbin_halfbin (wide): Normalised post-placement residual room, new-bin flag x item size, and closeness of the resulting free room to
def _f005(item, bins, capacity):
    """Normalised post-placement residual room, new-bin flag x item size, and closeness of the resulting free room to half a bin."""
    cap = float(capacity)
    b = np.asarray(bins, dtype=float)
    it = float(item)
    # tightness of the fit: how much room is left once the item is placed
    resid = np.clip((b - it) / cap, -1.0, 1.0)
    # new bins are the only ones at full capacity; let the policy open them only for large items
    is_new = (b >= cap - 1e-9).astype(float)
    new_term = np.clip(is_new * (it / cap), -1.0, 1.0)
    # hedging preference for bins that end up close to half full (flexible for future items)
    half_affinity = np.clip(1.0 - 2.0 * np.abs((b - it) / cap - 0.5), -1.0, 1.0)
    return np.column_stack([resid, new_term, half_affinity])

# f015 dead_space_hump_midband (wide): Dead-space hump: penalises post-placement leftovers inside the (0, 0.3*capacity) dead zone, peaking at 0.15*ca
def _f015(item, bins, capacity):
    """Dead-space hump: penalises post-placement leftovers inside the (0, 0.3*capacity) dead zone, peaking at 0.15*capacity and vanishing for exact fits and for leftovers >= 0.3*capacity."""
    cap = float(capacity)
    d = np.asarray(bins, dtype=float) - float(item)
    t = d / cap
    # triangular hump centred at 0.15*capacity, half-width 0.15*capacity
    v = np.clip(1.0 - np.abs(t - 0.15) / 0.15, 0.0, 1.0)
    # exact fits (d == 0) leave no dead space at all: notched out
    v = np.where(d > 1e-12, v, 0.0)
    return np.clip(v, 0.0, 1.0)

# f009 residual_newbin_modulo_fit (wide): Post-placement residual room (fraction of capacity), item-size-gated new-bin flag, and a modulo-fit term: how 
def _f009(item, bins, capacity):
    """Post-placement residual room (fraction of capacity), item-size-gated new-bin flag, and a modulo-fit term: how close the leftover is to a whole multiple of the arriving item's size (good future packing) rather than a wasteful near-miss."""
    cap = float(capacity)
    b = np.asarray(bins, dtype=float)
    it = max(float(item), 1.0)
    # tightness of the fit: room left once the item is placed, in capacity units
    resid = np.clip((b - it) / cap, -1.0, 1.0)
    # new bins are the only ones at full capacity; opening is priced by the item's size
    is_new = (b >= cap - 1e-9).astype(float)
    new_term = np.clip(is_new * (it / cap), -1.0, 1.0)
    # modulo fit: leftover that is a whole multiple of the item keeps the bin usable for
    # more items of this size; a near-miss (frac -> 1) strands almost a full item of room
    frac = np.mod(b - it, it) / it
    mod_term = np.clip(1.0 - 2.0 * frac, -1.0, 1.0)
    return np.column_stack([resid, new_term, mod_term])

# f025 item_relative_dead_leftover (deep): Dead-leftover fit relative to the item: 1 when post-placement leftover equals half the item size, decaying lin
def _f025(item, bins, capacity):
    """Dead-leftover fit relative to the item: 1 when post-placement leftover equals half the item size, decaying linearly to 0 at leftover 0 or leftover=item; 0 for zero leftover."""
    b = np.asarray(bins, dtype=float)
    s = float(max(item, 1))
    d = b - float(item)
    L = d / s
    v = np.clip(1.0 - np.abs(L - 0.5) / 0.5, 0.0, 1.0)
    v = np.where(d > 1e-12, v, 0.0)
    return np.clip(v, 0.0, 1.0)

_TERMS = [(_f005, np.array([-14.317505, -4.711341, 0.464965])), (_f015, np.array([-13.752054])), (_f009, np.array([2.418551, 2.617394, 2.162927])), (_f025, np.array([-0.358752]))]

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
