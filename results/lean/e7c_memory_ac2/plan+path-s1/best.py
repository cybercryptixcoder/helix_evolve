import numpy as np
import time
from scipy.optimize import minimize


def _next_pow2(n):
    p = 1
    while p < n:
        p <<= 1
    return p


def _fft_convolve(h):
    n = h.size
    m = _next_pow2(2 * n - 1)
    H = np.fft.rfft(h, m)
    return np.fft.irfft(H * H, m)[:2 * n - 1]


def _R(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return -1.0
    L = _fft_convolve(h)
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    return l2sq / (s * s * Lp.max())


def _R_and_grad(h):
    h = np.asarray(h, dtype=float)
    n = h.size
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(n)
    m = _next_pow2(2 * n - 1)
    H = np.fft.rfft(h, m)
    L = np.fft.irfft(H * H, m)[:2 * n - 1]
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    B = s * s
    mx = Lp.max()
    if mx <= 0:
        return -1.0, np.zeros(n)
    C = mx
    R = A / (B * C)

    w = np.zeros(Lp.size)
    w[1:-1] = (Lp[:-2] + 4.0 * Lp[1:-1] + Lp[2:]) / 3.0
    W = np.fft.rfft(w[1:-1], m)
    dA = 2.0 * np.fft.irfft(np.conj(H) * W, m)[:n]
    dB = 2.0 * s * np.ones(n)

    active = np.where(Lp >= mx * (1.0 - 1e-7))[0]
    dC = np.zeros(n)
    if active.size > 0:
        cw = np.zeros(Lp.size)
        cw[active] = 1.0 / active.size
        CW = np.fft.rfft(cw[1:-1], m)
        dC = 2.0 * np.fft.irfft(np.conj(H) * CW, m)[:n]

    dR = dA / (B * C) - A * dB / (B * B * C) - A * dC / (B * C * C)
    return R, dR


def _Rp_and_grad(h, p):
    h = np.asarray(h, dtype=float)
    n = h.size
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(n)
    m = _next_pow2(2 * n - 1)
    H = np.fft.rfft(h, m)
    L = np.fft.irfft(H * H, m)[:2 * n - 1]
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    B = s * s

    mx = Lp.max()
    if mx <= 0:
        return -1.0, np.zeros(n)
    y = Lp / mx
    yp = y ** p
    sp = yp.sum()
    if sp <= 0:
        return -1.0, np.zeros(n)
    M = mx * sp ** (1.0 / p)
    if M <= 0:
        return -1.0, np.zeros(n)
    R = A / (B * M)

    w = np.zeros(Lp.size)
    w[1:-1] = (Lp[:-2] + 4.0 * Lp[1:-1] + Lp[2:]) / 3.0
    W = np.fft.rfft(w[1:-1], m)
    dA = 2.0 * np.fft.irfft(np.conj(H) * W, m)[:n]
    dB = 2.0 * s * np.ones(n)
    wt = (y ** (p - 1)) / (sp ** ((p - 1.0) / p))
    WT = np.fft.rfft(wt[1:-1], m)
    dM = 2.0 * np.fft.irfft(np.conj(H) * WT, m)[:n]

    dR = dA / (B * M) - A * dB / (B * B * M) - A * dM / (B * M * M)
    return R, dR


def _neg(x):
    r, g = _R_and_grad(x)
    return -r, -g


def _p_polish(cur, time_left, ps, maxiter=80):
    for p in ps:
        if time_left() <= 0:
            break

        def neg_p(x, p=p):
            r, g = _Rp_and_grad(x, p)
            return -r, -g

        try:
            res = minimize(neg_p, cur, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * cur.size,
                           options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-13})
            xx = np.maximum(res.x, 0.0)
            if xx.sum() > 0:
                cur = xx
        except Exception:
            pass
    return cur


def _exact_polish(cur, time_left, maxiter=4000):
    if time_left() <= 0:
        return cur
    try:
        res = minimize(_neg, cur, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * cur.size,
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-13})
        xx = np.maximum(res.x, 0.0)
        if xx.sum() > 0:
            return xx
    except Exception:
        pass
    return cur


def _trim(h, tol=1e-9):
    nz = np.nonzero(h > tol * (h.max() if h.size else 0.0))[0]
    if nz.size == 0:
        return h
    return h[nz[0]:nz[-1] + 1]


def _smooth_rescale(base, N):
    xi = np.linspace(0.0, 1.0, base.size)
    xo = np.linspace(0.0, 1.0, N)
    return np.maximum(np.interp(xo, xi, base), 0.0)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = budget_seconds - 1.2

    def time_left():
        return deadline - (time.process_time() - t0)

    if start is not None:
        s0 = np.asarray(start, dtype=float)
        if s0.size == 0 or s0.sum() <= 0:
            s0 = np.ones(50)
    else:
        s0 = np.ones(50)

    base = _trim(np.maximum(s0.copy(), 0.0))
    N = 50000
    cur = _smooth_rescale(base, N)
    best = cur.copy()
    best_R = _R(best)

    # Phase 1: p-continuation to smooth max.
    cur = _p_polish(cur, time_left,
                    ps=(4096, 16384, 65536, 262144, 1048576, 4194304),
                    maxiter=120)
    cur = _exact_polish(cur, time_left, maxiter=4000)
    r = _R(cur)
    if r > best_R:
        best_R = r
        best = cur.copy()
    cur = best.copy()

    # Phase 2: many rounds of exact polishing (each improves max-touching set).
    stall = 0
    while time_left() > 1.0 and stall < 30:
        prev_R = best_R
        c = _exact_polish(cur, time_left, maxiter=4000)
        r = _R(c)
        if r > best_R:
            best_R = r
            best = c.copy()
            cur = c
            stall = 0
        else:
            stall += 1
            cur = best.copy()
            # Nudge: tiny random perturbation to escape flat directions.
            rng = np.random.default_rng(stall)
            pert = best * (1.0 + 1e-7 * rng.standard_normal(best.size))
            cur = np.maximum(pert, 0.0)

    # Final exact polish.
    if time_left() > 0:
        c = _exact_polish(best.copy(), time_left, maxiter=4000)
        r = _R(c)
        if r > best_R:
            best_R = r
            best = c

    return best
