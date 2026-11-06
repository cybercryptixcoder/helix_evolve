import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _L(h):
    c = fftconvolve(h, h)
    L = np.empty(c.size + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = c
    return L


def _R(h):
    h = np.asarray(h, dtype=float)
    L = _L(h)
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = np.sum(h) ** 2
    linf = np.max(L)
    if l1 <= 0 or linf <= 0:
        return 0.0
    return l2sq / (l1 * linf)


def _R_grad(h):
    h = np.asarray(h, dtype=float)
    c = fftconvolve(h, h)
    n = c.size
    L = np.empty(n + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = c
    a = L[:-1]; b = L[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    B = np.sum(h) ** 2
    k = int(np.argmax(L))
    C = L[k]
    if B <= 0 or C <= 0:
        return 0.0, np.zeros_like(h)
    R = A / (B * C)
    g_c = (L[0:n] + 4.0 * L[1:n + 1] + L[2:n + 2]) / 3.0
    dA = 2.0 * fftconvolve(g_c, h[::-1], 'valid')
    dB = 2.0 * np.sum(h)
    dC = np.zeros_like(h)
    j = k - 1
    m = len(h)
    lo = max(0, j - (m - 1)); hi = min(m - 1, j)
    if lo <= hi:
        idx = np.arange(lo, hi + 1)
        dC[idx] = 2.0 * h[j - idx]
    dlogR = dA / A - dB / B - dC / C
    return R, R * dlogR


def _R_topk_grad(h, K):
    h = np.asarray(h, dtype=float)
    c = fftconvolve(h, h)
    n = c.size
    L = np.empty(n + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = c
    a = L[:-1]; b = L[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    B = np.sum(h) ** 2
    if B <= 0 or A <= 0:
        return 0.0, np.zeros_like(h)
    K = min(K, L.size)
    idx = np.argpartition(L, -K)[-K:]
    C = np.mean(L[idx])
    if C <= 0:
        return 0.0, np.zeros_like(h)
    R = A / (B * C)
    g_c = (L[0:n] + 4.0 * L[1:n + 1] + L[2:n + 2]) / 3.0
    dA = 2.0 * fftconvolve(g_c, h[::-1], 'valid')
    dB = 2.0 * np.sum(h)
    dC_c = np.zeros(c.size)
    sel = idx[(idx >= 1) & (idx <= c.size)]
    dC_c[sel - 1] = 1.0 / K
    dC = 2.0 * fftconvolve(dC_c, h[::-1], 'valid')
    dlogR = dA / A - dB / B - dC / C
    return R, R * dlogR


class _Timeout(Exception):
    pass


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 1.0

    N = 4000

    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size > 0 and np.any(s > 0):
            if s.size == N:
                h0 = np.maximum(s.astype(float).copy(), 0.0)
            else:
                xs = np.linspace(0.0, 1.0, s.size)
                xt = np.linspace(0.0, 1.0, N)
                h0 = np.interp(xt, xs, s)
        else:
            h0 = None
    else:
        h0 = None
    if h0 is None:
        h0 = np.array([min(i + 1, N - i) for i in range(N)], dtype=float)
    h0 = np.maximum(h0, 1e-9)
    if h0.sum() <= 0:
        h0 = np.ones(N)

    best_h = h0.copy()
    best_r = _R(h0)
    print("start R", best_r, "N", N)

    bounds = [(0.0, None)] * N

    def exact_polish(cur):
        def neg_R_grad(h):
            R, g = _R_grad(h)
            return -R, -g
        res = minimize(neg_R_grad, cur, jac=True, method='L-BFGS-B',
                       bounds=bounds,
                       options={'ftol': 1e-18, 'gtol': 1e-15,
                                'maxiter': 5000, 'maxcor': 40})
        return np.maximum(np.asarray(res.x, dtype=float), 0.0)

    def topk_ladder(cur, Ks):
        for K in Ks:
            if time.process_time() > deadline:
                break

            def neg_topk_grad(h, _K=K):
                R, g = _R_topk_grad(h, _K)
                return -R, -g

            def callback(xk):
                if time.process_time() > deadline:
                    raise _Timeout()

            try:
                res = minimize(neg_topk_grad, cur, jac=True, method='L-BFGS-B',
                               bounds=bounds, callback=callback,
                               options={'ftol': 1e-18, 'gtol': 1e-15,
                                        'maxiter': 3000, 'maxcor': 40})
                cur = np.maximum(np.asarray(res.x, dtype=float), 0.0)
            except _Timeout:
                break
            except Exception:
                pass
        return cur

    def try_update(cur, tag):
        nonlocal best_h, best_r
        r = _R(cur)
        if r > best_r:
            best_r = r
            best_h = cur.copy()
            print(tag, best_r)
            return True
        return False

    Ks_big = [min(k, N) for k in
              [1600, 1320, 1040, 800, 600, 480, 400, 320, 240, 200, 160, 120, 100,
               80, 60, 50, 40, 30, 25, 20, 15, 12, 10, 8, 7, 6, 5, 4, 3, 2]]

    # Focused refinement of the given start: exact polish + topk ladder.
    try:
        cur = exact_polish(best_h)
        try_update(cur, "warm exact improved")
    except Exception:
        pass

    try:
        cur = topk_ladder(best_h.copy(), Ks_big)
        cur = exact_polish(cur)
        try_update(cur, "warm topk improved")
    except _Timeout:
        pass
    except Exception:
        pass

    cycle = 0
    rng = np.random.default_rng(12345)

    while time.process_time() < deadline:
        cycle += 1
        prev_r = best_r

        try:
            cur = topk_ladder(best_h.copy(), Ks_big)
            try_update(cur, "topk improved")
        except _Timeout:
            break
        except Exception:
            pass

        if time.process_time() > deadline:
            break
        try:
            cur = exact_polish(best_h.copy())
            try_update(cur, "exact improved")
        except _Timeout:
            break
        except Exception:
            pass

        if best_r <= prev_r + 1e-15 and time.process_time() < deadline:
            for scale in (1e-8, 1e-7, 1e-6):
                if time.process_time() > deadline:
                    break
                cand = best_h * np.exp(scale * rng.standard_normal(N))
                cand = np.maximum(cand, 1e-9)
                cand = cand * (np.sum(best_h) / np.sum(cand))
                try:
                    cx = topk_ladder(cand, [min(400, N), min(200, N), min(100, N),
                                            min(50, N), min(25, N), min(12, N),
                                            min(7, N), min(4, N)])
                    cx = exact_polish(cx)
                    try_update(cx, "perturb improved")
                except _Timeout:
                    break
                except Exception:
                    pass

    if _R(best_h) < _R(h0):
        best_h = h0.copy()
        best_r = _R(h0)

    print("final best R", best_r, "N", N, "cycles", cycle)
    return best_h
