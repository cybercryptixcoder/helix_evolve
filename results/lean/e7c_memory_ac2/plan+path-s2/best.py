import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _R_from_L(L, s):
    m = L.max()
    if m <= 0 or s <= 0:
        return 0.0
    L2 = (L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2).sum() / 3.0
    return L2 / (s * s * m)


def _R_fast(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    conv = fftconvolve(h, h)
    L = np.empty(conv.size + 2)
    L[0] = 0.0
    L[1:-1] = conv
    L[-1] = 0.0
    return _R_from_L(L, s)


def _binom(N):
    h = np.empty(N, dtype=float)
    h[0] = 1.0
    for n in range(N - 1):
        h[n + 1] = h[n] * (2.0 * n + 1.0) / (2.0 * n + 2.0)
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85

    N = 50000
    base = _binom(N)
    base = base / base.max()

    n = np.arange(N, dtype=float)
    x = 2.0 * n / (N - 1) - 1.0

    K = 20
    T = np.empty((K, N))
    T[0] = np.ones(N)
    if K > 1:
        T[1] = x
    for k in range(2, K):
        T[k] = 2.0 * x * T[k - 1] - T[k - 2]

    best_h = base.copy()
    best_r = _R_fast(best_h)

    a0 = np.zeros(K)
    if start is not None:
        hs = np.asarray(start, dtype=float)
        if hs.size > 0 and hs.sum() > 0 and hs.size <= 50000:
            rs = _R_fast(hs)
            if rs > best_r:
                best_r = rs
                best_h = hs.copy()
            if hs.size == N:
                ratio = np.log(np.clip(hs / base, 1e-12, None))
                try:
                    a_fit, *_ = np.linalg.lstsq(T.T, ratio, rcond=None)
                    if np.all(np.isfinite(a_fit)):
                        a0 = a_fit
                except Exception:
                    pass

    def make_h(a):
        logp = a @ T
        logp = np.clip(logp, -50.0, 50.0)
        return base * np.exp(logp)

    def negR(a):
        if time.process_time() > deadline:
            return 1.0
        return -_R_fast(make_h(a))

    best_a = a0.copy()
    val0 = _R_fast(make_h(a0))
    best_val = val0
    if val0 > best_r:
        best_r = val0
        best_h = make_h(a0)

    rng = np.random.default_rng(20240607)

    def run_nm(a_start, maxiter, fatol=1e-12):
        try:
            res = minimize(negR, a_start, method='Nelder-Mead',
                           options={'maxiter': maxiter, 'xatol': 1e-9, 'fatol': fatol})
            return res.x, -res.fun
        except Exception:
            return a_start, -1.0

    ax, val = run_nm(best_a, 3000)
    if val > best_val:
        best_val, best_a = val, ax
        best_h = make_h(ax)

    restart = 0
    while time.process_time() < deadline * 0.7 and restart < 40:
        restart += 1
        scale = 0.002 * (1.0 + restart * 0.1)
        a_start = best_a + rng.normal(0, scale, K)
        ax, val = run_nm(a_start, 800)
        if val > best_val:
            best_val, best_a = val, ax
            best_h = make_h(ax)
        if time.process_time() > deadline * 0.7:
            break

    if time.process_time() < deadline:
        ax, val = run_nm(best_a, 2000)
        if val > best_val:
            best_val, best_a = val, ax
            best_h = make_h(ax)

    h_final = make_h(best_a)
    r_final = _R_fast(h_final)
    if r_final > best_r:
        best_h = h_final
        best_r = r_final

    # --- Local coordinate-wise refinement: perturb individual heights in
    #     small windows around the plateau of f*f, using a cheap proxy ---
    # We tune a global multiplicative taper on the top of `best_h` combined
    # with a smooth end-taper, using a fine 2-parameter NM polish directly on
    # the current best shape (not on the fixed binomial base).
    if time.process_time() < deadline:
        hb = best_h.copy()
        hb = hb / hb.max()
        nn = np.arange(N, dtype=float)
        u = nn / (N - 1)  # 0..1

        def make_h_shape(p):
            # p[0]: exponent on right-tail taper start fraction; p[1]: power
            a = float(np.clip(p[0], 0.5, 1.0))
            beta = float(np.clip(p[1], 0.0, 6.0))
            g = np.ones(N)
            mask = u > a
            if beta > 0.0 and mask.any():
                g[mask] = ((1.0 - u[mask]) / (1.0 - a)) ** beta
            return hb * g

        def negR_shape(p):
            if time.process_time() > deadline:
                return 1.0
            return -_R_fast(make_h_shape(p))

        try:
            res = minimize(negR_shape, np.array([1.0, 0.0]), method='Nelder-Mead',
                           options={'maxiter': 600, 'xatol': 1e-5, 'fatol': 1e-12})
            r = -res.fun
            if r > best_r:
                best_r = r
                best_h = make_h_shape(res.x)
        except Exception:
            pass

    print(f"best R = {best_r:.9f}, restarts = {restart}")
    return best_h
