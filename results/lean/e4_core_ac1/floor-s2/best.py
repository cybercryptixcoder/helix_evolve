import numpy as np
import time
from scipy.optimize import minimize


def _conv(h):
    n = len(h)
    L = 1
    while L < 2 * n:
        L <<= 1
    F = np.fft.rfft(h, L)
    return np.fft.irfft(F * F, L)[:2 * n - 1]


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * float(np.max(_conv(h))) / (s * s)


def _trim(h):
    m = h.max()
    if m <= 0:
        return h
    nz = np.nonzero(h > 1e-10 * m)[0]
    if len(nz) == 0:
        return h
    return h[nz[0]:nz[-1] + 1]


def _resample(h, N):
    if len(h) == N:
        return h.copy()
    xo = np.linspace(0, 1, len(h))
    xn = np.linspace(0, 1, N)
    return np.maximum(np.interp(xn, xo, h), 0)


def construct(budget_seconds, start):
    t0 = time.process_time()
    budget = budget_seconds * 0.88

    def elapsed():
        return time.process_time() - t0

    if start is not None:
        h0 = np.asarray(start, dtype=float).copy()
        m = h0.max()
        if m > 0:
            h0 /= m
        h0 = _trim(h0)
    else:
        N = 200
        x = np.linspace(-0.5, 0.5, N)
        h0 = np.exp(-(x / 0.15) ** 2)

    best = h0.copy()
    bestC = _C(best)

    def make_obj(n, beta):
        def f(v):
            h = np.maximum(v, 0.0)
            s = h.sum()
            if s <= 0:
                return 1e10, np.zeros(n)
            conv = _conv(h)
            M = conv.max()
            e = np.exp(beta * (conv - M))
            Z = e.sum()
            sm = (e @ conv) / Z
            Cval = 2.0 * n * sm / (s * s)
            es = e / Z
            dsm = es * (1.0 + beta * (conv - sm))
            gs = 2.0 * np.convolve(dsm, h[::-1])[n - 1:n - 1 + n]
            dC = 2.0 * n / (s * s) * gs - 4.0 * n * sm / (s * s * s)
            return Cval, dC
        return f

    def opt(h_init, beta, maxiter=250):
        n = len(h_init)
        f = make_obj(n, beta)
        res = minimize(f, h_init.copy(), jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * n,
                       options={'maxiter': maxiter, 'ftol': 1e-17, 'gtol': 1e-13})
        h = np.maximum(res.x, 0.0)
        return h, _C(h)

    # Try several resolutions, but also try the *existing* start length first
    # with high beta since the start is already good.
    start_N = len(best)
    resolutions = sorted(set([start_N, 8000, 15000, 22000, 30000]))

    cur = best.copy()
    curC = bestC

    # Quick high-beta polish on the existing start before changing resolution.
    for beta in (200000.0, 600000.0):
        if elapsed() >= budget * 0.25:
            break
        cc, ccc = opt(cur, beta, 300)
        if ccc < curC - 1e-14:
            cur, curC = cc, ccc
            if ccc < bestC:
                best, bestC = cc.copy(), ccc

    for N in resolutions:
        if N < start_N:
            continue
        if elapsed() >= budget * 0.7:
            break
        cand = _resample(cur, N)
        for beta in (20000.0, 100000.0, 400000.0):
            if elapsed() >= budget * 0.75:
                break
            cc, ccc = opt(cand, beta, 300)
            if ccc < curC - 1e-13:
                cur, curC = cc, ccc
                if ccc < bestC:
                    best, bestC = cc.copy(), ccc
            cand = cc

    # Final aggressive polish at highest resolution reached.
    for beta in (1000000.0, 3000000.0):
        if elapsed() >= budget * 0.95:
            break
        cc, ccc = opt(best, beta, 400)
        if ccc < bestC - 1e-14:
            best, bestC = cc.copy(), ccc

    best = _trim(best)
    if best.sum() <= 0:
        best = np.ones(50)
    if len(best) > 30000:
        best = _resample(best, 30000)
    return best
