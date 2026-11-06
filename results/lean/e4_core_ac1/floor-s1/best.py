import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve

class _Timeout(Exception):
    pass

def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(fftconvolve(h, h)) / (s * s)

def _smooth_C_grad(h, beta):
    n = len(h)
    s = h.sum()
    if s <= 0:
        return 1e10, np.zeros(n)
    conv = fftconvolve(h, h)
    m = conv.max()
    if m <= 0:
        return 1e10, np.zeros(n)
    z = beta * (conv - m)
    z -= z.max()
    ez = np.exp(z)
    Z = ez.sum()
    lse = m + np.log(Z) / beta
    w = ez / Z
    corr = np.convolve(w, h[::-1], mode='valid')
    C = 2.0 * n * lse / (s * s)
    g = 4.0 * n / (s * s) * corr - 4.0 * n * lse / (s ** 3)
    return C, g

def _resample(h, N):
    xold = np.linspace(0, 1, len(h))
    xnew = np.linspace(0, 1, N)
    return np.maximum(np.interp(xnew, xold, h), 0.0)

def _lbfgs(h0, deadline, maxiter, beta):
    n = len(h0)
    def obj(h):
        if time.process_time() > deadline:
            raise _Timeout()
        hc = np.maximum(h, 0.0)
        C, g = _smooth_C_grad(hc, beta)
        g = g.copy()
        g[h < 0] = 0.0
        return C, g
    try:
        res = minimize(obj, h0.copy(), jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * n,
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-18, 'gtol': 1e-16, 'maxcor': 30})
        h = np.maximum(res.x, 0.0)
    except _Timeout:
        return None, None
    return _C(h), h

def construct(budget_seconds, start):
    t0 = time.process_time()
    limit = t0 + budget_seconds - 0.7

    best_C = np.inf
    best_h = None
    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size > 0 and np.all(np.isfinite(s)) and s.sum() > 0:
            best_C = _C(s)
            best_h = s.copy()
            print(f"start C={best_C:.7f} N={len(s)}")

    if best_h is None:
        N = 400
        x = np.linspace(-1, 1, N)
        best_h = np.cos(np.pi * x / 2.0) ** 2
        best_C = _C(best_h)
        print(f"init C={best_C:.7f} N={N}")

    def polish(h, betas, frac, maxiter=5000):
        c0, h0 = _C(h), h
        for beta in betas:
            if time.process_time() >= limit - 0.3:
                break
            rem = limit - time.process_time()
            sub = time.process_time() + max(0.25, rem * frac)
            c, hn = _lbfgs(h0, sub, maxiter, beta)
            if c is not None and c < c0:
                c0, h0 = c, hn
        return c0, h0

    # Polish at the same resolution first
    c, h = polish(best_h, (3e6, 1e7, 3e7, 1e8, 3e8, 1e9), 0.45)
    if c < best_C:
        best_C, best_h = c, h
        print(f"polish N={len(best_h)} C={best_C:.7f}")

    # Refine at finer resolutions
    N0 = len(best_h)
    tried = set()
    for mult in (2.0, 3.0, 4.0, 6.0):
        N = int(round(N0 * mult))
        if N in tried or N <= len(best_h) or N > 30000:
            continue
        tried.add(N)
        if time.process_time() >= limit - 0.6:
            break
        h0 = _resample(best_h, N)
        k = max(1, N // (N0 * 4))
        if k > 1:
            ker = np.ones(k) / k
            h0 = np.convolve(h0, ker, mode='same')
        c, h = polish(h0, (1e7, 3e7, 1e8, 3e8), 0.5)
        if c is not None and c < best_C:
            best_C, best_h = c, h
            print(f"refine N={N} C={best_C:.7f}")

    # Final multi-resolution exploitation using the current best shape:
    # run the largest feasible beta steps repeatedly to squeeze the max.
    for rnd in range(3):
        if time.process_time() >= limit - 0.4:
            break
        c, h = polish(best_h, (1e9, 3e9, 1e10, 3e10, 1e11), 0.7)
        if c is not None and c < best_C:
            best_C, best_h = c, h
            print(f"final{rnd} N={len(best_h)} C={best_C:.7f}")
        else:
            break

    # One more high-res attempt at a much larger N to capture sharp
    # near-degenerate max structure, if we still have time.
    if time.process_time() < limit - 0.5 and len(best_h) < 30000:
        N = min(30000, max(len(best_h) * 3, 12000))
        if N > len(best_h):
            h0 = _resample(best_h, N)
            c, h = polish(h0, (3e8, 1e9, 3e9, 1e10), 0.5, maxiter=3000)
            if c is not None and c < best_C:
                best_C, best_h = c, h
                print(f"big-refine N={N} C={best_C:.7f}")

    print(f"final C={best_C:.7f} N={len(best_h)}")
    return np.asarray(best_h, dtype=float)
