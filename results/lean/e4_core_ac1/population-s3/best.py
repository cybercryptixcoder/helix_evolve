import numpy as np
import time
from scipy.optimize import minimize, linprog


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _resample(s, N):
    s = np.maximum(np.asarray(s, float).ravel(), 0.0)
    if s.size == N:
        return s.copy()
    xs = (np.arange(s.size) + 0.5) / s.size
    xn = (np.arange(N) + 0.5) / N
    return np.maximum(np.interp(xn, xs, s), 0.0)


def _symmetrize(h):
    h = np.maximum(h, 0.0)
    h = 0.5 * (h + h[::-1])
    s = h.sum()
    if s > 0:
        h /= s
    return h


def _softmax_polish(h, deadline, best, bestC, beta_mult, max_iters=400):
    N = len(h)
    h = np.maximum(h.copy(), 1e-12)
    h /= h.sum()

    def f_and_g(x):
        x = x - x.max()
        w = np.exp(x)
        hh = w / w.sum()
        cc = np.convolve(hh, hh)
        beta = beta_mult * N
        mx = cc.max()
        e = np.exp(beta * (cc - mx))
        Z = e.sum()
        softM = mx + np.log(Z) / beta
        C = 2.0 * N * softM
        p = e / Z
        g = 2.0 * np.convolve(p, hh[::-1], mode='full')[N - 1:2 * N - 1]
        dC = 2.0 * N * (g - softM * 2.0 * hh)
        hd = hh * dC
        dCdx = hd - hh * hd.sum()
        return C, dCdx

    x0 = np.log(h + 1e-15)
    try:
        res = minimize(f_and_g, x0, jac=True, method='L-BFGS-B',
                       options={'maxiter': max_iters, 'ftol': 1e-18,
                                'gtol': 1e-15, 'maxcor': 40})
        x = res.x - res.x.max()
        w = np.exp(x)
        hh = w / w.sum()
        c = _C(hh)
        if c < bestC:
            bestC = c
            best = hh.copy()
        return hh, c, best, bestC
    except Exception:
        return h, _C(h), best, bestC


def _topk_grad(h, curC, best, bestC, deadline, k_frac=0.001, lr0=0.02):
    """Subgradient on top-k convolution knots: balances flat plateau peaks."""
    N = len(h)
    h = np.maximum(h.copy(), 1e-15)
    h /= h.sum()
    curC = _C(h)
    if curC < bestC:
        bestC, best = curC, h.copy()
    lr = lr0
    stall = 0
    nk = max(1, int(k_frac * (2 * N - 1)))
    while time.process_time() < deadline:
        conv = np.convolve(h, h)
        M = conv.max()
        idx = np.argpartition(conv, -nk)[-nk:]
        s = h.sum()
        g = np.zeros(N)
        for k in idx:
            lo = max(0, k - N + 1)
            hi = min(N - 1, k)
            g[lo:hi + 1] += 2.0 * h[k - np.arange(lo, hi + 1)]
        g /= len(idx)
        g = g / M - 2.0 / s
        gv = h * g
        gn = np.max(np.abs(gv))
        if gn < 1e-16:
            break
        gv /= gn
        improved = False
        for _ in range(60):
            trial = np.maximum(h * np.exp(-lr * gv), 0)
            ts = trial.sum()
            if ts <= 0:
                lr *= 0.5
                continue
            trial /= ts
            c2 = _C(trial)
            if c2 < curC - 1e-16:
                h = trial
                curC = c2
                improved = True
                lr = min(lr * 1.35, 0.5)
                stall = 0
                if curC < bestC:
                    bestC = c2
                    best = h.copy()
                break
            lr *= 0.5
            if lr < 1e-14:
                break
        if not improved:
            stall += 1
            if stall > 40:
                break
    return h, curC, best, bestC


def _slp_polish(h, curC, best, bestC, deadline, active_frac=0.01,
                step_frac=0.05):
    N = len(h)
    h = np.maximum(h.copy(), 1e-14)
    h /= h.sum()
    curC = _C(h)
    if curC < bestC:
        bestC = curC
        best = h.copy()

    while time.process_time() < deadline:
        conv = np.convolve(h, h)
        M = conv.max()
        th = M * (1.0 - active_frac)
        ks = [k for k in range(len(conv))
              if conv[k] >= th and
              (k == 0 or conv[k] >= conv[k - 1]) and
              (k == len(conv) - 1 or conv[k] >= conv[k + 1])]
        if not ks:
            ks = [int(np.argmax(conv))]
        rows = []
        for k in ks:
            lo = max(0, k - N + 1)
            hi = min(N - 1, k)
            r = np.zeros(N)
            idx = np.arange(lo, hi + 1)
            r[idx] = 2.0 * h[k - idx]
            rows.append(r)
        A = np.array(rows)
        m = A.shape[0]
        c_obj = np.zeros(N + 1)
        c_obj[-1] = 1.0
        A_ub = np.hstack([A, -np.ones((m, 1))])
        b_ub = np.zeros(m)
        A_ub2 = np.hstack([-np.eye(N), np.zeros((N, 1))])
        b_ub2 = h.copy()
        step_bound = step_frac * max(1.0, np.max(h))
        A_ub3 = np.hstack([np.eye(N), np.zeros((N, 1))])
        b_ub3 = np.full(N, step_bound)
        A_ub4 = np.hstack([-np.eye(N), np.zeros((N, 1))])
        b_ub4 = np.full(N, step_bound)
        A_ub_all = np.vstack([A_ub, A_ub2, A_ub3, A_ub4])
        b_ub_all = np.concatenate([b_ub, b_ub2, b_ub3, b_ub4])
        A_eq = np.zeros((1, N + 1))
        A_eq[0, :N] = 1.0
        b_eq = np.array([0.0])
        bounds = [(None, None)] * (N + 1)
        try:
            res = linprog(c_obj, A_ub=A_ub_all, b_ub=b_ub_all,
                          A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                          method='highs')
        except Exception:
            break
        if not res.success or res.x is None:
            break
        delta = res.x[:N]
        improved = False
        for lam in (1.0, 0.5, 0.25, 0.1, 0.05, 0.02):
            trial = np.maximum(h + lam * delta, 0)
            ts = trial.sum()
            if ts <= 0:
                continue
            trial /= ts
            c2 = _C(trial)
            if c2 < curC - 1e-16:
                h = trial
                curC = c2
                improved = True
                if curC < bestC:
                    bestC = curC
                    best = h.copy()
                break
        if not improved:
            if active_frac < 0.05:
                active_frac = min(active_frac * 2, 0.05)
                continue
            break
    return h, curC, best, bestC


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85

    candidates = []
    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size >= 1 and np.all(np.isfinite(s)) and np.any(s > 0):
            s = np.maximum(s, 0)
            s = s / s.sum()
            candidates.append(s.copy())
            candidates.append(_symmetrize(s))
            for mult in (1.5, 2.0, 3.0, 4.0):
                N = int(round(s.size * mult))
                if 1 <= N <= 30000 and N != s.size:
                    candidates.append(_resample(s, N))
    if not candidates:
        x = np.linspace(-1.0, 1.0, 800)
        h0 = np.cos(np.pi * x / 2.0) ** 2 + 0.05
        h0 /= h0.sum()
        candidates.append(h0)

    best = None
    bestC = np.inf
    for c in candidates:
        cc = _C(c)
        if cc < bestC:
            bestC = cc
            best = c.copy()

    h = best.copy()
    curC = bestC

    # Phase A: softmax ladder
    for bm in (1000.0, 5000.0, 20000.0):
        rem = deadline - time.process_time()
        if rem <= 0.02:
            break
        sd = time.process_time() + rem * 0.30
        h, curC, best, bestC = _softmax_polish(h, sd, best, bestC,
                                               beta_mult=bm, max_iters=300)

    # Phase B: alternate SLP + softmax
    while time.process_time() < deadline:
        prev = curC
        rem = deadline - time.process_time()
        if rem <= 0.02:
            break
        sd = time.process_time() + rem * 0.45
        h, curC, best, bestC = _slp_polish(
            h, curC, best, bestC, sd, active_frac=0.003, step_frac=0.02)
        rem = deadline - time.process_time()
        if rem <= 0.02:
            break
        sd = time.process_time() + rem * 0.5
        h, curC, best, bestC = _softmax_polish(h, sd, best, bestC,
                                               beta_mult=30000.0, max_iters=250)
        if curC >= prev - 1e-14:
            break

    # Phase C: top-k subgradient to balance plateau (the key addition)
    rem = deadline - time.process_time()
    if rem > 0.02:
        sd = time.process_time() + rem * 0.6
        h, curC, best, bestC = _topk_grad(best.copy(), bestC, best, bestC,
                                          sd, k_frac=0.001, lr0=0.02)
    # Final softmax polish
    rem = deadline - time.process_time()
    if rem > 0.02:
        h, curC, best, bestC = _softmax_polish(best.copy(), deadline, best,
                                               bestC, beta_mult=50000.0,
                                               max_iters=200)

    return np.maximum(best, 0.0)
