import numpy as np

def priority(item, bins, capacity):
    cap = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    it = np.asarray(item, dtype=float)
    rem = np.asarray(bins, dtype=float)

    rc = np.maximum(rem[:, 0], 1e-9)
    rm = np.maximum(rem[:, 1], 1e-9)

    # Normalised leftover after placing the item.
    Lc = np.clip(rem[:, 0] - it[0], 0.0, None) / cap[0]
    Lm = np.clip(rem[:, 1] - it[1], 0.0, None) / cap[1]

    # Fill quality: harmonic mean of leftover -> high only if BOTH leftovers
    # are small. This is the core "don't waste a whole resource" signal.
    hmean = 2.0 * Lc * Lm / np.maximum(Lc + Lm, 1e-9)
    quality = -hmean

    # Balance: punish uneven leftover strongly (anticorr killer).
    bal = -np.abs(Lc - Lm)

    # Match: reward a bin whose surplus in the tight resource fits the item.
    tight_c = it[0] / rc
    tight_m = it[1] / rm
    fit = np.minimum(np.minimum(tight_c, tight_m), 1.0)
    slack = np.abs(tight_c - tight_m)
    match = -slack

    # Usable: keep the weaker resource from collapsing.
    weak = np.minimum(Lc, Lm)
    usable = np.minimum(2.0 * weak, 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.15 * fit + 0.95 * quality + 0.75 * bal
             + 0.45 * match + 0.30 * usable)

    # Fresh-bin penalty, weaker for large jobs (they need a new bin anyway).
    score[-1] -= 0.20 - 0.14 * used

    return score
