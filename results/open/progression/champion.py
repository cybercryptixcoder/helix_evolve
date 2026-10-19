# Helix v3 policy: progression, gap 78.828%, progress 21.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f008 position_frac (deep): Normalised position of each candidate in 1..n: (cand - 1) / (n - 1), clipped to [0, 1].
def _f008(cand, chosen, avail, n, coef):
    """Normalised position of each candidate in 1..n: (cand - 1) / (n - 1), clipped to [0, 1]."""
    return np.clip((cand - 1) / float(n - 1), 0.0, 1.0)

# f012 future_avail_impact (wide): For each candidate v, how many currently-available other numbers w would be killed (share a solution with v an
def _f012(cand, chosen, avail, n, coef):
    """For each candidate v, how many currently-available other numbers w would be killed (share a solution with v and S) if v were added, normalised by available count."""
    a, b, c = int(coef[0]), int(coef[1]), int(coef[2])
    cand = np.asarray(cand, dtype=np.int64)
    k = cand.size
    S = (np.flatnonzero(chosen) + 1).astype(np.int64)
    A = (np.flatnonzero(avail) + 1).astype(np.int64)
    out = np.zeros(k, dtype=float)
    if S.size == 0 or A.size == 0:
        return out

    Smask = chosen  # bool over 1..n
    Amask = avail

    v = cand[:, None]          # (k,1)
    Srow = S[None, :]          # (1,m)

    # We collect, for each candidate v, the set of w in A that share a solution with v and some s in S.
    # Use a boolean matrix over (k, n) marking killed w.
    killed_mask = np.zeros((k, n), dtype=bool)

    def mark(w_arr, ok):
        valid = ok & (w_arr >= 1) & (w_arr <= n)
        wc = np.clip(w_arr, 1, n)
        ina = Amask[wc - 1] & valid  # (k,m)
        # scatter into killed_mask[k, w-1]
        rows = np.broadcast_to(np.arange(k)[:, None], ina.shape)[ina]
        cols = (wc - 1)[ina]
        killed_mask[rows, cols] = True

    # role1: x=v, y=s, z=w: w = (a*v + b*s)/c
    num = a * v + b * Srow
    w1 = num // c
    ok1 = (num % c == 0) & (w1 != v) & (Srow != v) & (Srow != w1)
    mark(w1, ok1)

    # role2: x=s, y=v, z=w: w = (a*s + b*v)/c
    num = a * Srow + b * v
    w2 = num // c
    ok2 = (num % c == 0) & (w2 != v) & (Srow != v) & (Srow != w2)
    mark(w2, ok2)

    # role3: x=v, y=w, z=s: w = (c*s - a*v)/b
    num = c * Srow - a * v
    w3 = num // b
    ok3 = (num % b == 0) & (w3 != v) & (Srow != v) & (Srow != w3)
    mark(w3, ok3)

    # role4: x=w, y=v, z=s: w = (c*s - b*v)/a
    num = c * Srow - b * v
    w4 = num // a
    ok4 = (num % a == 0) & (w4 != v) & (Srow != v) & (Srow != w4)
    mark(w4, ok4)

    killed = killed_mask.sum(axis=1).astype(float)
    nA = max(A.size - 1, 1)
    return np.tanh(killed / nA)

# f015 available_partner_solution_count (wide): For each candidate, the number of solutions it would create whose OTHER two positions are themselves still add
def _f015(cand, chosen, avail, n, coef):
    """For each candidate, the number of solutions it would create whose OTHER two positions are themselves still addable (avail) — future-blocking threat, not just current conflict."""
    a, b, c = int(coef[0]), int(coef[1]), int(coef[2])
    cand = np.asarray(cand, dtype=np.int64)
    k = cand.size
    S = (np.flatnonzero(chosen) + 1).astype(np.int64)
    m = S.size

    out = np.zeros(k, dtype=float)
    if m == 0:
        return out

    # availability lookup indexed by value 1..n
    av = np.zeros(n + 2, dtype=bool)
    av[1:n + 1] = avail[:n]

    density = m / max(n, 1)
    expected = density * density * n

    v = cand[:, None]
    Srow = S[None, :]

    # x = v : z = (a*v + b*y)/c ; partner y in S, third z must be addable
    num = a * v + b * Srow
    mask = (num % c == 0)
    z = num // c
    ok = mask & (z >= 1) & (z <= n) & (z != v) & (Srow != v) & (Srow != z)
    zc = np.clip(z, 0, n + 1)
    addable = av[zc] | (Srow == z)  # addable OR already in S (that's a real conflict partner)
    # we want the partner that is NOT yet in S but addable: future threat
    future = ok & (Srow != z) & av[zc]
    cnt = future.sum(axis=1)

    # y = v : z = (a*x + b*v)/c
    num = a * Srow + b * v
    mask = (num % c == 0)
    z = num // c
    ok = mask & (z >= 1) & (z <= n) & (z != v) & (Srow != v) & (Srow != z)
    zc = np.clip(z, 0, n + 1)
    future = ok & (Srow != z) & av[zc]
    cnt += future.sum(axis=1)

    # z = v : y = (c*v - a*x)/b
    num = c * v - a * Srow
    mask = (num % b == 0)
    y = num // b
    ok = mask & (y >= 1) & (y <= n) & (y != v) & (Srow != v) & (Srow != y)
    yc = np.clip(y, 0, n + 1)
    future = ok & (Srow != y) & av[yc]
    cnt += future.sum(axis=1)

    cnt = cnt.astype(float)
    return cnt / (expected + cnt)

# f026 live_block_frac_retry (deep): Fraction of still-available numbers killed (share a solution with candidate and S).
def _f026(cand, chosen, avail, n, coef):
    """Fraction of still-available numbers killed (share a solution with candidate and S)."""
    a, b, c = int(coef[0]), int(coef[1]), int(coef[2])
    k = cand.shape[0]
    S = np.flatnonzero(chosen) + 1
    m = S.size
    A = np.flatnonzero(avail) + 1
    denom = max(A.size, 1)
    if m == 0:
        return np.zeros(k, dtype=float)

    v = cand.astype(np.int64)[:, None]      # (k,1)
    s = S.astype(np.int64)[None, :]         # (1,m)

    K = np.zeros((k, n), dtype=bool)

    # (1) t = (a*v + b*s)/c
    num = a * v + b * s
    ok = (num % c == 0)
    t = np.where(ok, num // c, 0)
    valid = ok & (t >= 1) & (t <= n)
    rows, cols = np.nonzero(valid)
    K[rows, t[rows, cols] - 1] = True

    # (2) t = (b*v + a*s)/c
    num = b * v + a * s
    ok = (num % c == 0)
    t = np.where(ok, num // c, 0)
    valid = ok & (t >= 1) & (t <= n)
    rows, cols = np.nonzero(valid)
    K[rows, t[rows, cols] - 1] = True

    # (3) t = (c*v - a*s)/b
    num = c * v - a * s
    ok = (num % b == 0)
    t = np.where(ok, num // b, 0)
    valid = ok & (t >= 1) & (t <= n)
    rows, cols = np.nonzero(valid)
    K[rows, t[rows, cols] - 1] = True

    # (4) t = (c*v - b*s)/a
    num = c * v - b * s
    ok = (num % a == 0)
    t = np.where(ok, num // a, 0)
    valid = ok & (t >= 1) & (t <= n)
    rows, cols = np.nonzero(valid)
    K[rows, t[rows, cols] - 1] = True

    # (5) t = (c*s - a*v)/b
    num = c * s - a * v
    ok = (num % b == 0)
    t = np.where(ok, num // b, 0)
    valid = ok & (t >= 1) & (t <= n)
    rows, cols = np.nonzero(valid)
    K[rows, t[rows, cols] - 1] = True

    # (6) t = (c*s - b*v)/a
    num = c * s - b * v
    ok = (num % a == 0)
    t = np.where(ok, num // a, 0)
    valid = ok & (t >= 1) & (t <= n)
    rows, cols = np.nonzero(valid)
    K[rows, t[rows, cols] - 1] = True

    # exclude each row's own candidate
    K[np.arange(k), cand.astype(np.int64) - 1] = False
    # restrict to still-available numbers
    K &= avail[None, :]

    return K.sum(axis=1).astype(float) / denom

# f054 ratio_offset_resonance (deep): Mean over s in S of cos(2*pi*a*(v-s)/c) plus mean over s in S of cos(2*pi*b*(v-s)/c), halved and clipped to [-
def _f054(cand, chosen, avail, n, coef):
    """Mean over s in S of cos(2*pi*a*(v-s)/c) plus mean over s in S of cos(2*pi*b*(v-s)/c), halved and clipped to [-1,1]."""
    a, b, c = int(coef[0]), int(coef[1]), int(coef[2])
    S = np.flatnonzero(chosen) + 1  # chosen numbers, shape (m,)
    cand = np.asarray(cand, dtype=np.int64)
    if S.size == 0:
        return np.zeros(cand.shape[0])
    # closed form: cos(2*pi*a*v/c)*Re(mean_s exp(-2*pi*i*a*s/c)) + same for b
    def term(k):
        phase_s = np.exp(-2j * np.pi * k * S / c)
        re_mean = np.real(phase_s.mean())
        return np.cos(2 * np.pi * k * cand / c) * re_mean
    score = 0.5 * (term(a) + term(b))
    return np.clip(score, -1.0, 1.0)

# f091 density_weighted_block_frac (wide): Share of available numbers killed by the candidate, weighted by how scarce each killed number is (1/(local ava
def _f091(cand, chosen, avail, n, coef):
    """Share of available numbers killed by the candidate, weighted by how scarce each killed number is (1/(local avail density)), and by whether the kill comes from a high-count (conflict-dense) third value; rewards sparse-region candidates."""
    a, b, c = int(coef[0]), int(coef[1]), int(coef[2])
    k = cand.shape[0]
    S = np.flatnonzero(chosen) + 1
    m = S.size
    if m == 0:
        return np.zeros(k, dtype=float)

    A = np.flatnonzero(avail) + 1
    nA = max(A.size, 1)

    # local availability density over a sliding window (window = max(3, n//20))
    W = max(3, n // 20)
    dens = np.zeros(n + 1, dtype=float)
    av = np.zeros(n + 1, dtype=float)
    av[1:n + 1] = avail[:n].astype(float)
    csum = np.concatenate([[0.0], np.cumsum(av[1:n + 1])])
    for v in range(1, n + 1):
        lo = max(1, v - W)
        hi = min(n, v + W)
        dens[v] = (csum[hi] - csum[lo - 1]) / float(hi - lo + 1)

    v = cand.astype(np.int64)[:, None]
    s = S.astype(np.int64)[None, :]

    K = np.zeros((k, n), dtype=bool)

    def mark(num, mod, mul_ok_mask=None):
        ok = (num % mod == 0)
        t = np.where(ok, num // mod, 0)
        valid = ok & (t >= 1) & (t <= n)
        rows, cols = np.nonzero(valid)
        K[rows, t[rows, cols] - 1] = True

    mark(a * v + b * s, c)
    mark(b * v + a * s, c)
    mark(c * v - a * s, b)
    mark(c * v - b * s, a)
    mark(c * s - a * v, b)
    mark(c * s - b * v, a)

    K[np.arange(k), cand.astype(np.int64) - 1] = False
    K &= avail[None, :]

    # weight each killed number by inverse local density (scarce -> kill hurts more)
    w = 1.0 / (dens[1:n + 1] + 1.0 / nA)
    weighted = (K.astype(float) * w[None, :]).sum(axis=1)
    # also count raw kills, scaled
    raw = K.sum(axis=1).astype(float)

    score = 0.5 * (weighted / (nA * (1.0 / nA) * nA + 1.0)) + 0.5 * (raw / nA)
    return np.tanh(score)

# f092 danger_weighted_future_threat (wide): For each candidate, the number of solutions it would create whose OTHER two slots are chosen (in S) summed ove
def _f092(cand, chosen, avail, n, coef):
    """For each candidate, the number of solutions it would create whose OTHER two slots are chosen (in S) summed over multi-step completions one level deeper: solutions v can form where one partner is in S and the third is addable, weighted by how many solutions that addable third already has with S."""
    a, b, c = int(coef[0]), int(coef[1]), int(coef[2])
    cand = np.asarray(cand, dtype=np.int64)
    k = cand.size
    S = (np.flatnonzero(chosen) + 1).astype(np.int64)
    m = S.size
    if m == 0:
        return np.zeros(k, dtype=float)

    av = np.zeros(n + 2, dtype=bool)
    av[1:n + 1] = avail[:n]

    density = m / max(n, 1)
    expected = density * density * n

    # Precompute, for every addable number w, how many solutions w forms with S
    # (partner in S, third slot addable) -- this is the "danger" of w.
    A = np.flatnonzero(av[:n]) + 1  # addable numbers
    danger = np.zeros(n + 2, dtype=float)
    if A.size > 0:
        w = A[:, None].astype(np.int64)
        s = S[None, :].astype(np.int64)
        # count completions with third slot addable, excluding w and s
        cnt_w = np.zeros(A.size, dtype=float)
        # role x=w: t=(a*w+b*s)/c
        for coef_k, coef_o, denom in ((a, b, c), (b, a, c)):
            num = coef_k * w + coef_o * s
            okm = (num % denom == 0)
            t = np.where(okm, num // denom, -1)
            valid = okm & (t >= 1) & (t <= n) & (t != w) & (s != w) & (s != t)
            tc = np.clip(t, 0, n + 1)
            cnt_w += (valid & av[tc]).sum(axis=1)
        # role z=w: t=(c*w - a*s)/b and (c*w - b*s)/a
        for coef_k, coef_o, denom in ((a, b, None), (b, a, None)):
            num = c * w - coef_k * s
            okm = (num % coef_o == 0)
            t = np.where(okm, num // coef_o, -1)
            valid = okm & (t >= 1) & (t <= n) & (t != w) & (s != w) & (s != t)
            tc = np.clip(t, 0, n + 1)
            cnt_w += (valid & av[tc]).sum(axis=1)
        danger[A] = cnt_w

    v = cand[:, None].astype(np.int64)
    Srow = S[None, :].astype(np.int64)

    # For each candidate v, for each completion where a partner s in S and third slot t is
    # addable, add danger[t] -- i.e. how dangerous the addable third would become.
    score = np.zeros(k, dtype=float)
    for coef_k, coef_o, denom in ((a, b, c), (b, a, c)):
        num = coef_k * v + coef_o * Srow
        okm = (num % denom == 0)
        t = np.where(okm, num // denom, -1)
        valid = okm & (t >= 1) & (t <= n) & (t != v) & (Srow != v) & (Srow != t)
        tc = np.clip(t, 0, n + 1)
        score += (valid & av[tc]).dot(danger[tc] if False else 0) if False else 0  # placeholder
    # vectorised gather of danger
    for coef_k, coef_o, denom in ((a, b, c), (b, a, c)):
        num = coef_k * v + coef_o * Srow
        okm = (num % denom == 0)
        t = np.where(okm, num // denom, -1)
        valid = okm & (t >= 1) & (t <= n) & (t != v) & (Srow != v) & (Srow != t)
        tc = np.clip(t, 0, n + 1)
        contrib = np.where(valid & av[tc], danger[tc], 0.0)
        score += contrib.sum(axis=1)
    for coef_k, coef_o in ((a, b), (b, a)):
        num = c * v - coef_k * Srow
        okm = (num % coef_o == 0)
        t = np.where(okm, num // coef_o, -1)
        valid = okm & (t >= 1) & (t <= n) & (t != v) & (Srow != v) & (Srow != t)
        tc = np.clip(t, 0, n + 1)
        contrib = np.where(valid & av[tc], danger[tc], 0.0)
        score += contrib.sum(axis=1)

    denom_scale = (expected * expected) + score
    return np.where(denom_scale > 0, score / denom_scale, 0.0)

_TERMS = [(_f008, np.array([10.518399])), (_f012, np.array([-150.533338])), (_f015, np.array([-47.137878])), (_f026, np.array([-220.599332])), (_f054, np.array([-6.374171])), (_f091, np.array([-91.24063])), (_f092, np.array([1.701976]))]

def priority(cand, chosen, avail, n, coef):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(cand, chosen, avail, n, coef), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(cand))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
