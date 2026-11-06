import numpy as np
import time
from scipy.optimize import minimize


def _R_fast(h):
    s = h.sum()
    if s <= 0:
        return 0.0
    c = np.convolve(h, h)
    L = np.concatenate(([0.0], c, [0.0]))
    L2 = L * L
    num = (L2[:-1] + L[:-1] * L[1:] + L2[1:]).sum() / 3.0
    den = (s * s) * L.max()
    if den <= 0:
        return 0.0
    return num / den


def _R_and_grad(h):
    h = np.asarray(h, dtype=float)
    N = h.size
    s = h.sum()
    if s <= 0:
        return 0.0, np.zeros(N)
    c = np.convolve(h, h)
    L = np.concatenate(([0.0], c, [0.0]))
    L2 = L * L
    num = (L2[:-1] + L[:-1] * L[1:] + L2[1:]).sum() / 3.0
    imax = int(np.argmax(L))
    M = L[imax]
    if M <= 0:
        return 0.0, np.zeros(N)
    den = (s * s) * M
    R = num / den

    dnum_dL = np.zeros_like(L)
    dnum_dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    dnum_dL[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0

    g = dnum_dL[1:2 * N]
    conv = np.convolve(g, h[::-1])
    dnum_dh = 2.0 * conv[N - 1: N - 1 + N]

    dden_dh = 2.0 * s * M * np.ones(N)
    if 1 <= imax <= 2 * N - 1:
        m = imax - 1
        dM_dh = np.zeros(N)
        lo = max(0, m - (N - 1))
        hi = min(N - 1, m)
        for i in range(lo, hi + 1):
            dM_dh[i] = 2.0 * h[m - i]
        dden_dh += (s * s) * dM_dh

    grad = (dnum_dh * den - num * dden_dh) / (den * den)
    return R, grad


def _Rbeta_and_grad(h, beta):
    h = np.asarray(h, dtype=float)
    N = h.size
    s = h.sum()
    if s <= 0:
        return 0.0, np.zeros(N)
    c = np.convolve(h, h)
    L = np.concatenate(([0.0], c, [0.0]))
    L2 = L * L
    num = (L2[:-1] + L[:-1] * L[1:] + L2[1:]).sum() / 3.0

    Mmax = L.max()
    z = beta * (L - Mmax)
    ez = np.exp(z)
    S = ez.sum()
    logS = np.log(S)
    Msoft = Mmax + logS / beta
    if Msoft <= 0:
        return 0.0, np.zeros(N)
    den = (s * s) * Msoft
    R = num / den

    dnum_dL = np.zeros_like(L)
    dnum_dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    dnum_dL[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0

    g = dnum_dL[1:2 * N]
    conv = np.convolve(g, h[::-1])
    dnum_dh = 2.0 * conv[N - 1: N - 1 + N]

    w = ez / S
    wc = w[1:2 * N]
    convM = np.convolve(wc, h[::-1])
    dMsoft_dh = 2.0 * convM[N - 1: N - 1 + N]

    dden_dh = 2.0 * s * Msoft * np.ones(N) + (s * s) * dMsoft_dh

    grad = (dnum_dh * den - num * dden_dh) / (den * den)
    return R, grad


def _coord_polish(h, deadline, sweeps=200):
    h = np.asarray(h, dtype=float).copy()
    N = h.size
    if h.max() > 0:
        h = h / h.max()
    best = _R_fast(h)
    if best <= 0:
        return h, best

    for sw in range(sweeps):
        if time.process_time() >= deadline:
            break
        improved_any = False
        scale = 10.0 ** (-2.0 - 4.0 * (sw / max(1, sweeps - 1)))
        for i in range(N):
            if time.process_time() >= deadline:
                break
            hi = h[i]
            for delta in (scale, -scale, 0.5 * scale, -0.5 * scale):
                newv = hi + delta * (1.0 + hi)
                if newv < 0:
                    newv = 0.0
                if newv == hi:
                    continue
                old = h[i]
                h[i] = newv
                v = _R_fast(h)
                if v > best + 1e-15:
                    best = v
                    improved_any = True
                    break
                else:
                    h[i] = old
        if not improved_any and scale < 1e-6:
            break
    return h, best


def _optimize(h0, deadline):
    base = np.asarray(h0, dtype=float).ravel().copy()
    if base.size == 0 or base.max() <= 0:
        base = np.ones(300)
    base = base / base.max()

    N = base.size
    best_h = base.copy()
    best_v = _R_fast(best_h)

    h_cur = best_h.copy()
    betas = (30000.0, 100000.0, 300000.0, 1000000.0, 3000000.0,
             10000000.0, 30000000.0, 100000000.0)
    bounds = [(0.0, None)] * N
    for beta in betas:
        if time.process_time() >= deadline:
            break

        def obj_beta(x, b=beta):
            v, g = _Rbeta_and_grad(x, b)
            return -v, -g

        try:
            res = minimize(obj_beta, h_cur, method='L-BFGS-B', jac=True,
                           bounds=bounds,
                           options={'maxiter': 2000, 'ftol': 1e-15, 'gtol': 1e-12})
            cand = np.maximum(res.x, 0.0)
            if cand.max() > 0:
                cand = cand / cand.max()
                h_cur = cand
        except Exception:
            pass

        if time.process_time() < deadline:
            try:
                res2 = minimize(obj_beta, h_cur, method='SLSQP', jac=True,
                                bounds=bounds,
                                options={'maxiter': 500, 'ftol': 1e-15})
                cand2 = np.maximum(res2.x, 0.0)
                if cand2.max() > 0:
                    cand2 = cand2 / cand2.max()
                    h_cur = cand2
            except Exception:
                pass

        v = _R_fast(h_cur)
        if v > best_v:
            best_v = v
            best_h = h_cur.copy()

    if time.process_time() < deadline:
        polished, pv = _coord_polish(best_h, deadline, sweeps=200)
        if pv > best_v:
            best_v = pv
            best_h = polished.copy()

    rng = np.random.default_rng(987654321)
    restart = 0
    while time.process_time() < deadline:
        restart += 1
        if restart == 1:
            x0 = best_h.copy()
        else:
            sigma = 10.0 ** rng.uniform(-8.0, -4.0)
            x0 = best_h * np.exp(sigma * rng.standard_normal(N))
            x0 = x0 / max(x0.max(), 1e-12)

        if restart % 5 == 0:
            thr = 1e-5 * x0.max()
            x0 = np.where(x0 < thr, 0.0, x0)
            if x0.max() > 0:
                x0 = x0 / x0.max()

        def obj(x):
            v, g = _R_and_grad(x)
            return -v, -g

        cand = x0
        if time.process_time() < deadline:
            try:
                res = minimize(obj, cand, method='SLSQP', jac=True, bounds=bounds,
                               options={'maxiter': 1000, 'ftol': 1e-15})
                c = np.maximum(res.x, 0.0)
                if c.max() > 0:
                    c = c / c.max()
                cand = c
            except Exception:
                pass

        if time.process_time() < deadline:
            try:
                res = minimize(obj, cand, method='TNC', jac=True, bounds=bounds,
                               options={'maxfun': 200000, 'ftol': 1e-15})
                c = np.maximum(res.x, 0.0)
                if c.max() > 0:
                    c = c / c.max()
                cand = c
            except Exception:
                pass

        v = _R_fast(cand)
        if v > best_v:
            best_v = v
            best_h = cand.copy()

    return best_h, best_v


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 16.0

    if start is not None:
        s = np.asarray(start, dtype=float).ravel().copy()
    else:
        s = np.ones(300)
    if s.size == 0 or s.max() <= 0:
        s = np.ones(300)

    base = np.maximum(s, 0.0)
    if base.max() > 0:
        base = base / base.max()

    # Trim near-zero boundary padding.
    if base.size > 0 and base.max() > 0:
        eps = 1e-12 * base.max()
        while base.size > 1 and base[0] < eps:
            base = base[1:]
        while base.size > 1 and base[-1] < eps:
            base = base[:-1]
    if base.size == 0 or base.max() <= 0:
        base = np.ones(300)
    base = base / base.max()

    start_v = _R_fast(base)
    best_h = base.copy()
    best_v = start_v

    # Experiment: resample to N=520 and optimize there.
    N0 = base.size
    N1 = 520
    if N0 != N1:
        h0 = np.interp(np.linspace(0.0, 1.0, N1),
                       np.linspace(0.0, 1.0, N0), base)
    else:
        h0 = base.copy()
    h0 = np.maximum(h0, 0.0)
    if h0.max() > 0:
        h0 = h0 / h0.max()
    thr = 1e-8 * h0.max()
    h0 = np.where(h0 < thr, 1e-3 * h0.max(), h0)
    if h0.max() > 0:
        h0 = h0 / h0.max()

    cand_h, cand_v = _optimize(h0, deadline)

    if cand_v > start_v:
        out = cand_h
    else:
        out = base

    if out.sum() <= 0:
        out = np.ones(N1)
    return out
