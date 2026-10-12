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

    # Tight fit in the binding dimension (keeps bins well packed).
    fit = np.minimum(np.minimum(it[0] / rc, it[1] / rm), 1.0)

    # Evenness of leftover.
    bal = -np.abs(Lc - Lm)

    # --- Future-usability terms (the new idea) ---
    small = np.minimum(Lc, Lm)
    big = np.maximum(Lc, Lm)

    # A leftover corner is "useful" if BOTH resources keep a modest floor,
    # so small and medium future jobs still fit.
    floor = np.minimum(np.minimum(Lc, Lm) * 5.0, 1.0)
    floor = floor * floor  # penalise starved corners sharply

    # A "clean" leftover: one resource nearly exhausted, the other still roomy.
    # Skew-heavy future jobs snap into these; balanced leftovers are less reusable.
    clean = (1.0 - small) * big

    # Avoid wasting a nearly-empty bin on a tiny job: reward placing the item
    # into a bin where it uses a meaningful fraction of the freer resource too.
    use_freer = np.minimum(np.minimum(it[0], it[1]) / np.maximum(big * cap.min(), 1e-9), 1.0)

    used = 0.5 * (it[0] / cap[0] + it[1] / cap[1])
    used = min(max(used, 0.0), 1.0)

    score = (1.10 * fit
             + 0.80 * bal
             + 0.90 * floor
             + 0.55 * clean
             + 0.30 * use_freer)

    # Fresh-bin gate: strong suppression for small jobs, weak for large ones.
    gate = 1.0 - 0.30 * (1.0 - used) ** 2
    score = score * gate
    score[-1] -= 0.02

    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
