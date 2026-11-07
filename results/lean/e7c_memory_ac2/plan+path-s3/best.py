import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _conv(a, b):
    if a.size > 2000 or b.size > 2000:
        return fftconvolve(a, b)
    return np.convolve(a, b)


def _Lvals(h):
    c = _conv(h, h)
    L = np.empty(c.size + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = c
    return L


def _R(h):
    h = np.asarray(h, dtype=float)
    if not np.all(np.isfinite(h)):
        return -np.inf
    s = h.sum()
    if s <= 0:
        return -np.inf
    L = _Lvals(h)
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    linf = L.max()
    if linf <= 0:
        return -np.inf
    return l2sq / (s * s * linf)


def _R_grad(h, rel_tol=1e-9):
    h = np.asarray(h, dtype=float)
    n = h.size
    s = h.sum()
    if s <= 0 or not np.all(np.isfinite(h)):
        return -np.inf, np.zeros(n)
    L = _Lvals(h)
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    linf = L.max()
    if linf <= 0:
        return -np.inf, np.zeros(n)
    R = l2sq / (l1 * linf)

    gL = np.zeros_like(L)
    gL[:-1] += (2.0 * a + b) / 3.0
    gL[1:] += (a + 2.0 * b) / 3.0
    gc = gL[1:-1]
    conv = _conv(gc, h[::-1])
    gl2sq = 2.0 * conv[n - 1: n - 1 + n]

    dl1 = 2.0 * s

    glinf_h = np.zeros(n)
    active = np.where(L >= linf * (1.0 - rel_tol))[0]
    if active.size > 0:
        inv = 1.0 / active.size
        idx = np.arange(n)
        for i in active:
            if 1 <= i <= 2 * n - 1:
                k = i - 1
                j = k - idx
                valid = (j >= 0) & (j < n)
                glinf_h[valid] += 2.0 * h[j[valid]] * inv

    denom = l1 * linf
    gR = gl2sq / denom - l2sq * (dl1 * linf + l1 * glinf_h) / (denom * denom)
    return R, gR


def _negR_grad_tol(h, rel_tol):
    R, g = _R_grad(h, rel_tol)
    if not np.isfinite(R):
        return 1e10, np.zeros_like(h)
    return -R, -g


def _negR_grad_soft(h, alpha):
    h = np.asarray(h, dtype=float)
    n = h.size
    s = h.sum()
    if s <= 0 or not np.all(np.isfinite(h)):
        return 1e10, np.zeros(n)
    L = _Lvals(h)
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    mx = L.max()
    e = np.exp((L - mx) / alpha)
    Z = e.sum()
    linf = (e * L).sum() / Z
    if linf <= 0:
        return 1e10, np.zeros(n)
    R = l2sq / (l1 * linf)

    gL = np.zeros_like(L)
    gL[:-1] += (2.0 * a + b) / 3.0
    gL[1:] += (a + 2.0 * b) / 3.0
    gc = gL[1:-1]
    conv = _conv(gc, h[::-1])
    gl2sq = 2.0 * conv[n - 1: n - 1 + n]

    dlinf = e * (L - linf + alpha) / (alpha * Z)
    dlinf_c = dlinf[1:-1]
    conv2 = _conv(dlinf_c, h[::-1])
    glinf_h = 2.0 * conv2[n - 1: n - 1 + n]

    dl1 = 2.0 * s
    denom = l1 * linf
    gR = gl2sq / denom - l2sq * (dl1 * linf + l1 * glinf_h) / (denom * denom)
    return -R, -gR


def _upsample(start, N):
    if start is None:
        return np.ones(N)
    start = np.asarray(start, dtype=float)
    if start.size == 0:
        return np.ones(N)
    xs = np.linspace(0.0, 1.0, start.size)
    xt = np.linspace(0.0, 1.0, N)
    h = np.interp(xt, xs, start)
    if h.sum() <= 0:
        h = np.ones(N)
    return h


def _polish_tol(h, rel_tol, maxiter=1500, bounds=None):
    N = h.size
    if bounds is None:
        bounds = [(0.0, None)] * N
    try:
        res = minimize(_negR_grad_tol, h, method='L-BFGS-B', jac=True,
                       bounds=bounds, args=(rel_tol,),
                       options={'maxiter': maxiter, 'maxfun': maxiter * 100,
                                'ftol': 1e-16, 'gtol': 1e-14})
        return np.maximum(res.x, 0.0)
    except Exception:
        return h


def _polish_soft(h, alpha, maxiter=1500, bounds=None):
    N = h.size
    if bounds is None:
        bounds = [(0.0, None)] * N
    try:
        res = minimize(_negR_grad_soft, h, method='L-BFGS-B', jac=True,
                       bounds=bounds, args=(alpha,),
                       options={'maxiter': maxiter, 'maxfun': maxiter * 100,
                                'ftol': 1e-16, 'gtol': 1e-14})
        return np.maximum(res.x, 0.0)
    except Exception:
        return h


def _Rk_grad(h, k):
    h = np.asarray(h, dtype=float)
    n = h.size
    s = h.sum()
    if s <= 0 or not np.all(np.isfinite(h)):
        return 1e10, np.zeros(n)
    L = _Lvals(h)
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    m = L.size
    k = max(1, min(k, m))
    idx = np.argpartition(L, m - k)[m - k:]
    lk = L[idx].mean()
    if lk <= 0:
        return 1e10, np.zeros(n)
    Rk = l2sq / (l1 * lk)

    gL = np.zeros_like(L)
    gL[:-1] += (2.0 * a + b) / 3.0
    gL[1:] += (a + 2.0 * b) / 3.0
    gc = gL[1:-1]
    conv = _conv(gc, h[::-1])
    gl2sq = 2.0 * conv[n - 1: n - 1 + n]

    dl1 = 2.0 * s
    glk_h = np.zeros(n)
    inv_k = 1.0 / k
    for i in idx:
        if 1 <= i <= 2 * n - 1:
            kk = i - 1
            j = kk - np.arange(n)
            valid = (j >= 0) & (j < n)
            glk_h[valid] += 2.0 * h[j[valid]] * inv_k

    denom = l1 * lk
    gRk = gl2sq / denom - l2sq * (dl1 * lk + l1 * glk_h) / (denom * denom)
    return -Rk, -gRk


def _polish_k(h, k, maxiter=3000):
    N = h.size
    bounds = [(0.0, None)] * N
    try:
        res = minimize(_Rk_grad, h, method='L-BFGS-B', jac=True,
                       bounds=bounds, args=(k,),
                       options={'maxiter': maxiter, 'maxfun': maxiter * 100,
                                'ftol': 1e-16, 'gtol': 1e-14})
        return np.maximum(res.x, 0.0)
    except Exception:
        return h


def _refine(h, deadline, cur_r):
    """Coordinate-polish with exact R, adaptive step, returns best h/r."""
    h = h.copy()
    n = h.size
    cur = cur_r
    step = 0.05 * h.max()
    while step > 1e-7 and time.process_time() < deadline:
        improved = False
        for i in range(n):
            if time.process_time() > deadline:
                break
            old = h[i]
            accepted = False
            for cand in (old + step, old - step):
                if cand < 0:
                    continue
                h[i] = cand
                r = _R(h)
                if r > cur + 1e-13:
                    cur = r
                    improved = True
                    accepted = True
                    break
            if not accepted:
                h[i] = old
        if not improved:
            step *= 0.5
    return h, cur


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + max(0.0, budget_seconds - 3.0)

    best_h = None
    best_r = -np.inf

    def consider(h):
        nonlocal best_h, best_r
        if h is None or h.size == 0:
            return False
        h = np.maximum(np.asarray(h, dtype=float), 0.0)
        if h.sum() <= 0:
            return False
        r = _R(h)
        if np.isfinite(r) and r > best_r + 1e-12:
            best_r = r
            best_h = h.copy()
            return True
        return False

    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.size > 0 and s.sum() > 0:
            consider(s / s.max())

    N = 3200
    h0 = _upsample(best_h if best_h is not None else start, N)
    if h0.sum() <= 0:
        h0 = np.ones(N)
    h0 = h0 / h0.max()

    # Soft-max continuation.
    for alpha in [1e-4, 1e-5, 1e-6, 1e-7, 1e-8]:
        if time.process_time() > deadline:
            break
        h = _polish_soft(h0, alpha=alpha, maxiter=1000)
        consider(h)
        h0 = h

    m = 2 * N + 1

    # Top-k ladder, annealed down.
    kfracs = [0.55, 0.45, 0.35, 0.25, 0.15, 0.08]
    for kf in kfracs:
        if time.process_time() > deadline:
            break
        k = max(1, int(kf * m))
        h = _polish_k(h0, k, maxiter=400)
        consider(h)
        h0 = h

    # Final exact polish.
    if time.process_time() <= deadline:
        h = _polish_tol(h0, 1e-9, maxiter=1000)
        consider(h)

    # Coordinate refinement from current best.
    if best_h is not None and time.process_time() < deadline:
        h, r = _refine(best_h, deadline, best_r)
        consider(h)

    if best_h is None:
        best_h = _upsample(start, N)
    return np.asarray(best_h, dtype=float)
