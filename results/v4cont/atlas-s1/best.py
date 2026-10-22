import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _conv(h):
    if h.size > 1500:
        return fftconvolve(h, h)
    return np.convolve(h, h)


def _knots(h):
    return np.concatenate(([0.0], _conv(h), [0.0]))


def R_of(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    L = _knots(h)
    a = L[:-1]; b = L[1:]
    num = np.sum(a * a + a * b + b * b) / 3.0
    den = s * s * L.max()
    if den <= 0:
        return 0.0
    return num / den


def _num_and_dq(h):
    Lf = _knots(h)
    a = Lf[:-1]; b = Lf[1:]
    num = np.sum(a * a + a * b + b * b) / 3.0
    dq = np.zeros_like(Lf)
    dq[:-1] += (2 * a + b)
    dq[1:] += (a + 2 * b)
    dq /= 3.0
    return num, dq, Lf


def _backprop(gLf, h):
    gL = gLf[1:-1]
    n = h.size
    if n > 1500:
        return 2.0 * fftconvolve(gL, h[::-1], mode='valid')[:n]
    return 2.0 * np.correlate(gL, h, mode='valid')[:n]


def _rescale(h):
    h = np.clip(h, 0, None)
    if h.sum() <= 0:
        return h
    mx = _knots(h).max()
    if mx <= 0:
        return h
    return h / np.sqrt(mx)


def _fun_grad(h):
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(h.size)
    num, dq, Lf = _num_and_dq(h)
    m = int(np.argmax(Lf))
    Lm = Lf[m]
    gLf = -dq / num
    gLf[m] += 1.0 / Lm
    grad = _backprop(gLf, h) + 2.0 / s
    val = -np.log(num) + 2.0 * np.log(s) + np.log(Lm)
    return val, grad


def _make_cb(deadline):
    def cb(xk):
        if time.process_time() > deadline:
            raise TimeoutError
    return cb


def _lbfgs_log(h0, maxiter, deadline):
    if time.process_time() >= deadline - 0.3:
        return h0
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    n = h.size
    thresh = 1e-13 * h.max()
    active = np.flatnonzero(h > thresh)
    if active.size == 0:
        return h0
    u0 = np.log(np.clip(h[active], 1e-300, None))

    def f(u):
        uu = np.clip(u, -30.0, 30.0)
        hh = np.zeros(n)
        hh[active] = np.exp(uu)
        val, g = _fun_grad(hh)
        return val, g[active] * hh[active]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, u0, jac=True, method='L-BFGS-B',
                       bounds=[(-30.0, 30.0)] * active.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = np.zeros(n)
    h2[active] = np.exp(np.clip(res.x, -30.0, 30.0))
    return _rescale(h2)


def _lbfgs_block(h0, free, maxiter, deadline):
    if time.process_time() >= deadline - 0.3:
        return h0
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    active = np.asarray(free, dtype=int)
    if active.size == 0:
        return h0
    x0 = h[active].copy()

    def f(x):
        hh = h.copy()
        hh[active] = np.clip(x, 0.0, None)
        val, g = _fun_grad(hh)
        return val, g[active]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * active.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = h.copy()
    h2[active] = np.clip(res.x, 0.0, None)
    return _rescale(h2)


def _peak_region(h, tol=0.999):
    Lf = _knots(h)
    mx = Lf.max()
    if mx <= 0:
        return 0, h.size - 1
    idx = np.flatnonzero(Lf >= tol * mx)
    lo = max(0, idx.min() - 1)
    hi = min(h.size - 1, idx.max())
    return lo, hi


def _window_polish_peak(h, deadline, frac, extra, maxiter=400):
    n = h.size
    lo, hi = _peak_region(h)
    span = hi - lo
    pad = max(extra, int(span * frac))
    lo = max(0, lo - pad)
    hi = min(n - 1, hi + pad)
    free = np.arange(lo, hi + 1)
    return _lbfgs_block(h, free, maxiter=maxiter, deadline=deadline)


def _prolongate(h_small, N_big):
    n = h_small.size
    if n == N_big:
        return h_small.copy()
    S = np.concatenate(([0.0], np.cumsum(h_small)))
    xs = np.linspace(0.0, 1.0, n + 1)
    xb = np.linspace(0.0, 1.0, N_big + 1)
    Sb = np.interp(xb, xs, S)
    Sb = np.maximum.accumulate(Sb)
    h = np.clip(np.diff(Sb), 0.0, None)
    if h.sum() <= 0:
        return np.ones(N_big)
    return h


def _coarse(h, Nc):
    n = h.size
    if n == Nc:
        return h.copy()
    S = np.concatenate(([0.0], np.cumsum(h)))
    xs = np.linspace(0.0, 1.0, n + 1)
    xb = np.linspace(0.0, 1.0, Nc + 1)
    Sb = np.interp(xb, xs, S)
    Sb = np.maximum.accumulate(Sb)
    hc = np.clip(np.diff(Sb), 0.0, None)
    if hc.sum() <= 0:
        return np.ones(Nc)
    return hc


def _phase_shift(h, delta):
    n = h.size
    C = np.concatenate(([0.0], np.cumsum(h)))
    edges = np.arange(n + 1, dtype=float) - delta
    edges = np.clip(edges, 0.0, float(n))
    Cq = np.interp(edges, np.arange(n + 1, dtype=float), C)
    return np.diff(Cq)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

    if start is not None:
        base = np.clip(np.asarray(start, dtype=float).copy(), 0, None)
        if base.size > 0 and base.sum() > 0:
            best = _rescale(base)
            bestR = R_of(best)
        else:
            best, bestR = None, 0.0
    else:
        best, bestR = None, 0.0

    if best is None:
        N = 8192
        i = np.arange(N, dtype=float)
        h = 2.0 * np.sqrt(N) * (np.sqrt(i + 1.0) - np.sqrt(i))
        best = _rescale(h)
        bestR = R_of(best)

    print("base R=%.7f (N=%d)" % (bestR, best.size))

    N = best.size

    # NEW: resolution sweep upward from a coarse solve. Optimising at higher
    # resolution than the start often unlocks extra R; we grow N gradually
    # so L-BFGS converges at each stage before prolongating.
    if time.process_time() < deadline - 8.0:
        for Nt in (N, int(N * 1.5), int(N * 2.0)):
            if Nt <= best.size:
                continue
            if Nt > 200000:
                Nt = 200000
            if time.process_time() >= deadline - 6.0:
                break
            hp = _prolongate(best, Nt)
            hp = _rescale(hp)
            hp = _lbfgs_log(hp, 400, deadline)
            r = R_of(hp)
            print("grow %d -> R=%.7f" % (Nt, r))
            if r > bestR + 1e-15:
                best, bestR = hp, r

    # Peak-focused multi-scale polish at full resolution.
    for frac, extra in ((0.10, 4), (0.20, 8), (0.35, 16), (0.50, 32), (0.75, 64)):
        if time.process_time() >= deadline - 2.0:
            break
        h = _window_polish_peak(best, deadline, frac, extra)
        h = _lbfgs_log(h, 500, deadline)
        r = R_of(h)
        if r > bestR + 1e-15:
            best, bestR = h, r
            print("peak(%.2f) R=%.7f" % (frac, bestR))

    # Phase exploration around best.
    for delta in (-0.5, -0.25, 0.25, 0.5):
        if time.process_time() >= deadline - 2.0:
            break
        hp = _phase_shift(best, delta)
        hp = _rescale(hp)
        if hp.sum() <= 0:
            continue
        hp = _lbfgs_log(hp, 600, deadline)
        hp = _window_polish_peak(hp, deadline, 0.35, 16)
        r = R_of(hp)
        print("phase %+.2f R=%.7f" % (delta, r))
        if r > bestR + 1e-15:
            best, bestR = hp, r

    # Final loop: alternate full and peak polish until budget exhausted.
    stall = 0
    while time.process_time() < deadline - 1.0:
        improved = False
        h = _lbfgs_log(best, 800, deadline)
        r = R_of(h)
        if r > bestR + 1e-15:
            best, bestR = h, r
            improved = True
            print("full R=%.7f" % bestR)
        if time.process_time() >= deadline - 1.5:
            break
        h = _window_polish_peak(best, deadline, 0.40, 24)
        r = R_of(h)
        if r > bestR + 1e-15:
            best, bestR = h, r
            improved = True
            print("win R=%.7f" % bestR)
        if not improved:
            stall += 1
            if stall >= 2:
                break
        else:
            stall = 0

    print("final R=%.7f (N=%d)" % (bestR, best.size))
    return best
