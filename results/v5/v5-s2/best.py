import numpy as np
import time
import math

try:
    from scipy.optimize import minimize
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False


def R_of_h(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0:
        return 0.0
    s = h.sum()
    if s <= 0:
        return 0.0
    c = np.convolve(h, h)
    L = np.empty(c.size + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = c
    a = L[:-1]
    b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    linf = L.max()
    if linf <= 0:
        return 0.0
    return l2sq / (l1 * linf)


def L_and_dL(h):
    h = np.asarray(h, dtype=float)
    c = np.convolve(h, h)
    L = np.empty(c.size + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = c
    return L


def resample(h, N):
    h = np.asarray(h, dtype=float)
    M = h.size
    if M == N:
        return h.copy()
    edges = np.linspace(0.0, 1.0, N + 1) * M
    out = np.empty(N)
    cum = np.concatenate([[0.0], np.cumsum(h)])
    for i in range(N):
        x0 = edges[i]
        x1 = edges[i + 1]
        i0 = int(math.floor(x0))
        i1 = int(math.floor(x1))
        if i1 >= M:
            i1 = M - 1
        if i0 == i1:
            out[i] = h[min(i0, M - 1)]
        else:
            total = h[i0] * (i0 + 1 - x0)
            if i1 > i0 + 1:
                total += cum[i1] - cum[i0 + 1]
            total += h[min(i1, M - 1)] * (x1 - i1)
            out[i] = total / (x1 - x0)
    return out


def lbfgsb_refine(h0, maxiter=800):
    h0 = np.asarray(h0, dtype=float)
    N = h0.size
    if not HAVE_SCIPY:
        return h0, R_of_h(h0)

    def obj(x):
        s = x.sum()
        if s <= 0:
            return 1e10, np.zeros(N)
        L = L_and_dL(x)
        a = L[:-1]
        b = L[1:]
        l2sq = np.sum(a * a + a * b + b * b) / 3.0
        l1 = s * s
        linf = L.max()
        if linf <= 0:
            return 1e10, np.zeros(N)
        kmax = int(np.argmax(L))
        dL = np.zeros(L.size)
        dL[:-1] += (2.0 * a + b) / 3.0
        dL[1:] += (a + 2.0 * b) / 3.0
        dL_int = dL[1:-1]
        corr = np.convolve(dL_int, x[::-1])
        g_l2 = 2.0 * corr[N:N + N]
        dlinf = np.zeros(N)
        if 1 <= kmax <= 2 * N - 1:
            lo = max(0, kmax - N)
            hi = min(N - 1, kmax - 1)
            for i in range(lo, hi + 1):
                dlinf[i] = 2.0 * x[kmax - 1 - i]
        val = -l2sq / (l1 * linf)
        grad = -g_l2 / (l1 * linf) + l2sq * (2.0 * s) / (l1 * l1 * linf) \
               + l2sq * dlinf / (l1 * linf * linf)
        return val, grad

    try:
        res = minimize(obj, h0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * N,
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-15, 'gtol': 1e-12})
        h = np.clip(res.x, 0.0, None)
        return h, R_of_h(h)
    except Exception:
        return h0, R_of_h(h0)


def lse_refine(h0, beta, maxiter=150):
    h0 = np.asarray(h0, dtype=float)
    N = h0.size
    if not HAVE_SCIPY:
        return h0, R_of_h(h0)

    def obj(x):
        s = x.sum()
        if s <= 0:
            return 1e10, np.zeros(N)
        L = L_and_dL(x)
        a = L[:-1]
        b = L[1:]
        l2sq = np.sum(a * a + a * b + b * b) / 3.0
        l1 = s * s
        m = L.max()
        e = np.exp(beta * (L - m))
        Z = e.sum()
        S = m + math.log(Z) / beta
        if S <= 0:
            return 1e10, np.zeros(N)
        w = e / Z
        dL = np.zeros(L.size)
        dL[:-1] += (2.0 * a + b) / 3.0
        dL[1:] += (a + 2.0 * b) / 3.0
        dL_int = dL[1:-1]
        corr = np.convolve(dL_int, x[::-1])
        g_l2 = 2.0 * corr[N:N + N]
        val = -l2sq / (l1 * S)
        grad = -g_l2 / (l1 * S) + l2sq * (2.0 * s) / (l1 * l1 * S)
        w_int = w[1:-1]
        corr2 = np.convolve(w_int, x[::-1])
        g_S = 2.0 * corr2[N:N + N]
        grad = grad + l2sq / (l1 * S * S) * g_S
        return val, grad

    try:
        res = minimize(obj, h0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * N,
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-15, 'gtol': 1e-12})
        h = np.clip(res.x, 0.0, None)
        return h, R_of_h(h)
    except Exception:
        return h0, R_of_h(h0)


def construct(budget_seconds, start):
    t0 = time.process_time()
    hard_end = t0 + 0.75 * budget_seconds
    N = 3200
    N2 = 6400

    best_R = -1.0
    best_h = None

    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.size > 0 and s.sum() > 0:
            h0 = resample(s, N)
            r0 = R_of_h(h0)
            if r0 > 0:
                best_R = r0
                best_h = h0.copy()
                keep_best(best_h)
    if best_h is None:
        const = np.ones(N)
        best_R = R_of_h(const)
        best_h = const.copy()
        keep_best(const)

    print("stage init: %.6f -> %.6f, %.2f s" % (best_R, best_R, time.process_time() - t0))

    def consider(h, v):
        nonlocal best_R, best_h
        if v > best_R + 1e-13:
            best_R = v
            best_h = np.asarray(h, dtype=float).copy()
            keep_best(best_h)
            return True
        return False

    # ---- Stage A: 3 passes of fine LSE beta ladder at N=3200 ----
    before_A = best_R
    betas = [2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]
    for p in range(3):
        if time.process_time() > hard_end:
            break
        h = best_h.copy()
        h = h * (N / h.sum())
        for beta in betas:
            if time.process_time() > hard_end:
                break
            h, v = lse_refine(h, beta, maxiter=150)
            if h.sum() > 0:
                h = h * (N / h.sum())
            consider(h, v)
        if time.process_time() > hard_end:
            break
        h, v = lbfgsb_refine(h, maxiter=400)
        consider(h, v)
        print("  pass %d done: R=%.6f, %.2f s" % (p + 1, best_R, time.process_time() - t0))
    print("stage lse-anneal-N3200: %.6f -> %.6f, %.2f s"
          % (before_A, best_R, time.process_time() - t0))

    # ---- Stage B: real N=6400 LSE pass + exact-R polish ----
    before_B = best_R
    if time.process_time() < hard_end:
        h2 = resample(best_h, N2)
        h2 = h2 * (N2 / h2.sum())
        betas2 = [5, 20, 100, 500, 2000, 10000, 50000]
        for beta in betas2:
            if time.process_time() > hard_end:
                break
            h2, v = lse_refine(h2, beta, maxiter=150)
            if h2.sum() > 0:
                h2 = h2 * (N2 / h2.sum())
            consider(h2, v)
            h32 = resample(h2, N)
            consider(h32, R_of_h(h32))
        if time.process_time() < hard_end:
            h2, v = lbfgsb_refine(h2, maxiter=500)
            consider(h2, v)
            h32 = resample(h2, N)
            consider(h32, R_of_h(h32))
    print("stage lse-anneal-N6400: %.6f -> %.6f, %.2f s"
          % (before_B, best_R, time.process_time() - t0))

    # ---- Final: exact-R polish at the resolution of the best array ----
    before_F = best_R
    if time.process_time() < hard_end:
        h, v = lbfgsb_refine(best_h, maxiter=1500)
        consider(h, v)
        if time.process_time() < hard_end:
            h2 = resample(best_h, N2)
            h2, v2 = lbfgsb_refine(h2, maxiter=1000)
            consider(h2, v2)
            consider(resample(h2, N), R_of_h(resample(h2, N)))
    print("stage polish: %.6f -> %.6f, %.2f s"
          % (before_F, best_R, time.process_time() - t0))

    print("final R = %.6f, N = %d, %.2f s"
          % (best_R, best_h.size, time.process_time() - t0))
    return best_h
