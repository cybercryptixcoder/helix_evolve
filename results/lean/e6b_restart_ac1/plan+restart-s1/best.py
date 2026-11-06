import numpy as np
import time
from scipy.optimize import minimize


def _C(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _resample(h, N):
    h = np.asarray(h, dtype=float).ravel()
    n = len(h)
    if n == N:
        return h.copy()
    xo = (np.arange(n) + 0.5) / n
    xn = (np.arange(N) + 0.5) / N
    return np.interp(xn, xo, h)


def _active_set_grad(h, ks):
    n = h.size
    g = np.zeros(n)
    for k in ks:
        lo = max(0, k - (n - 1))
        hi = min(n - 1, k)
        j = np.arange(lo, hi + 1)
        g[j] += 2.0 * h[k - j]
    return g


def _exact_pg(h, deadline, tol=1e-6, max_active=48):
    """Exact-C projected gradient on active convolution peaks."""
    h = np.maximum(np.asarray(h, dtype=float), 0.0)
    s = h.sum()
    if s <= 0:
        return h
    h = h / s
    bestC = _C(h)
    alpha = 1e-3
    while time.process_time() < deadline:
        c = np.convolve(h, h)
        cmax = c.max()
        thr = cmax * (1.0 - tol)
        S = np.flatnonzero(c >= thr)
        if S.size > max_active:
            S = np.argpartition(c, -max_active)[-max_active:]
        g = _active_set_grad(h, S)
        g -= g.mean()
        accepted = False
        a = alpha
        for _ in range(40):
            trial = h - a * g
            trial = np.maximum(trial, 0.0)
            ts = trial.sum()
            if ts <= 0:
                a *= 0.5
                continue
            trial /= ts
            tc = _C(trial)
            if tc < bestC - 1e-15:
                h = trial
                bestC = tc
                alpha = min(a * 1.5, 1e-1)
                accepted = True
                break
            a *= 0.5
        if not accepted:
            alpha *= 0.5
            if alpha < 1e-14:
                break
    return h


def _softmax_obj(v, beta):
    v2 = v * v
    s = v2.sum()
    if s <= 0:
        s = 1e-30
    h = v2 / s
    c = np.convolve(h, h)
    bc = beta * c
    m = bc.max()
    w = np.exp(bc - m)
    sw = w.sum()
    F = (np.log(sw) + m) / beta
    w = w / sw
    g = np.correlate(w, h, 'valid')
    grad_h = 2.0 * g
    dot = np.dot(h, grad_h)
    grad = (2.0 * v / s) * (grad_h - dot)
    return F, grad


def _refine(v, beta, deadline, maxiter=400):
    if time.process_time() > deadline:
        return v
    try:
        res = minimize(lambda vv: _softmax_obj(vv, beta), v, jac=True,
                       method='L-BFGS-B',
                       options={'maxiter': maxiter, 'ftol': 1e-16, 'gtol': 1e-13})
    except Exception:
        return v
    if res.x is not None and np.all(np.isfinite(res.x)):
        return res.x
    return v


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

    if start is not None:
        h0 = np.asarray(start, dtype=float).ravel()
        if h0.size == 0 or h0.sum() <= 0 or not np.all(np.isfinite(h0)):
            h0 = None
    else:
        h0 = None
    if h0 is None:
        x = np.linspace(-0.25, 0.25, 400)
        h0 = np.maximum(np.cos(2 * np.pi * x) ** 2, 1e-6)
    h0 = np.maximum(h0, 0.0)

    best_h = h0.copy()
    best_C = _C(h0)

    def consider(h):
        nonlocal best_h, best_C
        h = np.maximum(np.asarray(h, dtype=float), 0.0)
        if h.size == 0 or h.size > 30000 or h.sum() <= 0:
            return False
        if not np.all(np.isfinite(h)):
            return False
        c = _C(h)
        if c < best_C - 1e-14:
            best_C = c
            best_h = h.copy()
            return True
        return False

    # Strong attack at native resolution: exact-C PG with tight tol.
    if time.process_time() < deadline:
        pg = _exact_pg(best_h, deadline, tol=1e-6)
        consider(pg)
    # Tighter plateau tolerance to broaden the active set
    if time.process_time() < deadline:
        pg = _exact_pg(best_h, deadline, tol=1e-3, max_active=64)
        consider(pg)

    betas = np.geomspace(1e3, 5e7, 24)

    def run_ladder(N, hseed, maxiter=400):
        if time.process_time() > deadline:
            return False
        improved = False
        h = _resample(hseed, N)
        h = np.maximum(h, 1e-12)
        h = h / h.sum()
        if consider(h):
            improved = True
        v = np.sqrt(h)
        for beta in betas:
            if time.process_time() > deadline:
                break
            v = _refine(v, beta, deadline, maxiter=maxiter)
            v2 = v * v
            s = v2.sum()
            if s <= 0:
                continue
            hh = v2 / s
            if consider(hh):
                improved = True
        return improved

    # Multi-resolution exploration
    for N in (best_h.size, 1200, 1600, 2000, 2600):
        if time.process_time() >= deadline:
            break
        if N > 30000:
            continue
        run_ladder(N, best_h, maxiter=300)
        if time.process_time() < deadline and N <= 2600:
            pg = _exact_pg(_resample(best_h, N), deadline, tol=1e-5, max_active=48)
            consider(pg)

    # Main alternating loop: PG + softmax escape
    no_improve = 0
    while time.process_time() < deadline:
        N = min(best_h.size, 2400)
        cycle = no_improve % 4
        improved = False
        if cycle == 0:
            pg = _exact_pg(_resample(best_h, N), deadline, tol=1e-6, max_active=48)
            improved = consider(pg)
        elif cycle == 1:
            improved = run_ladder(N, best_h, maxiter=250)
        elif cycle == 2:
            pg = _exact_pg(_resample(best_h, N), deadline, tol=1e-3, max_active=64)
            improved = consider(pg)
        else:
            N2 = min(30000, int(N * 1.3))
            improved = run_ladder(N2, best_h, maxiter=250)
        if improved:
            no_improve = 0
        else:
            no_improve += 1
            if no_improve > 30:
                break

    best_h = np.maximum(best_h, 0.0)
    if best_h.sum() <= 0:
        best_h = np.ones(200) / 200.0
    return best_h
