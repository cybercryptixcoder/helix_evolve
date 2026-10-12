import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    # Normalised demands and residual capacities.
    ic = it[0] / cap[0]
    im = it[1] / cap[1]
    Rc = np.clip(rem[:, 0] / cap[0], 0.0, 1.0)
    Rm = np.clip(rem[:, 1] / cap[1], 0.0, 1.0)

    # Leftover after placing the item.
    Lc = np.clip(Rc - ic, 0.0, None)
    Lm = np.clip(Rm - im, 0.0, None)

    # --- Shape alignment: item's skew vs the bin's residual skew ---
    # A CPU-heavy job (ic>im) should go where memory is relatively more abundant.
    si = ic - im
    sb = Rm - Rc                      # residual skew: + means memory-rich
    comp = np.tanh(3.0 * si * sb)     # match heavy job to rich opposite resource

    # --- Fill tightness: small leftover area is good (well-filled bin) ---
    geom = -np.sqrt(Lc * Lm)

    # --- Balance: even leftovers are more reusable than lopsided ones ---
    bal = -np.abs(Lc - Lm)

    # --- Coverage: reward keeping both leftovers non-trivial ---
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    # --- Fit: prefer bins the item nearly fills, and that fit snugly ---
    eps = 1e-9
    fit = np.minimum(np.minimum(ic / np.maximum(Rc, eps),
                                im / np.maximum(Rm, eps)), 1.0)

    # --- Reuse bias: discourage opening a fresh bin, weaker for big jobs ---
    used = 0.5 * (ic + im)
    used = min(max(used, 0.0), 1.0)

    score = (1.15 * fit
             + 0.55 * comp
             + 0.45 * geom
             + 0.40 * bal
             + 0.35 * usable)

    score[-1] -= 0.30 - 0.22 * used

    return score
