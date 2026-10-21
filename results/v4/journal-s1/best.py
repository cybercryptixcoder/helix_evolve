import numpy as np
import time
from scipy.signal import fftconvolve
from scipy.optimize import minimize


def _R_fast(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0 or h.max() <= 0:
        return -1.0
    c = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], c, [0.0]))
    s = h.sum()
    if s <= 0:
        return -1.0
    linf = L.max()
    if linf <= 0:
        return -1.0
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    return l2sq / (s * s * linf)


def _R_and_grad(h):
    N = h.size
    c = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], c, [0.0]))
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(N)
    l1 = s * s
    j = int(np.argmax(L))
    linf = L[j]
    if linf <= 0:
        return -1.0, np.zeros(N)
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    R = l2sq / (l1 * linf)
    q = (np.concatenate(([0.0], L[:-1])) + 4.0 * L +
         np.concatenate((L[1:], [0.0]))) / 3.0
    q_int = q[1:-1]
    corr = fftconvolve(q_int, h[::-1], mode='full')
    grad_l2sq = 2.0 * corr[N - 1:N - 1 + N]
    grad_linf = np.zeros(N)
    base = j - 1
    lo = max(0, base - (N - 1))
    hi = min(N - 1, base)
    if lo <= hi:
        idx = np.arange(lo, hi + 1)
        grad_linf[idx] = 2.0 * h[base - idx]
    denom = (l1 * linf) ** 2
    num = grad_l2sq * (l1 * linf) - l2sq * (2.0 * s * linf + l1 * grad_linf)
    return R, num / denom


def _pnorm_max_grad(h, p):
    N = h.size
    c = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], c, [0.0]))
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(N)
    l1 = s * s
    Lp = np.maximum(L, 0.0) ** p
    Sp = Lp.sum()
    if Sp <= 0:
        return -1.0, np.zeros(N)
    Mp = Sp ** (1.0 / p)
    a = L[:-1]; b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    R = l2sq / (l1 * Mp)
    q = (np.concatenate(([0.0], L[:-1])) + 4.0 * L +
         np.concatenate((L[1:], [0.0]))) / 3.0
    q_int = q[1:-1]
    corr = fftconvolve(q_int, h[::-1], mode='full')
    grad_l2sq = 2.0 * corr[N - 1:N - 1 + N]
    dMp_dL = (Mp ** (1.0 - p)) * (np.maximum(L, 0.0) ** (p - 1.0))
    w = dMp_dL[1:-1]
    corrP = fftconvolve(w, h[::-1], mode='full')
    grad_Mp = 2.0 * corrP[N - 1:N - 1 + N]
    denom = (l1 * Mp) ** 2
    num = grad_l2sq * (l1 * Mp) - l2sq * (2.0 * s * Mp + l1 * grad_Mp)
    return R, num / denom


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.93

    N = 6000

    if start is not None:
        start = np.asarray(start, dtype=float)
        M = start.size
        if M == 0:
            best = np.ones(N)
        elif M == N:
            best = start.copy()
        else:
            xs = (np.arange(M) + 0.5) / M
            xn = (np.arange(N) + 0.5) / N
            best = np.interp(xn, xs, start)
    else:
        best = np.ones(N)

    best = np.maximum(best, 0.0)
    if best.max() <= 0:
        best = np.ones(N)

    def norm(h):
        m = h.max()
        return h / m if m > 0 else h

    best = norm(best)
    bestR = _R_fast(best)

    if bestR < 0.68:
        x = (np.arange(N) + 0.5) / N
        for p in (1, 2, 4, 8):
            h = np.maximum(np.cos(np.pi * (x - 0.5)), 0) ** p
            r = _R_fast(h)
            if r > bestR:
                bestR = r; best = norm(h)

    # ---- Phase A: exact-R L-BFGS-B ----
    phaseA_end = t0 + budget_seconds * 0.45
    h = best.copy()
    while time.process_time() < phaseA_end:
        def fg(x):
            R, g = _R_and_grad(x)
            if not np.all(np.isfinite(g)):
                g = np.zeros_like(x)
            return -R, -g
        try:
            res = minimize(fg, h, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * N,
                           options={'maxiter': 300, 'maxfun': 600,
                                    'ftol': 1e-20, 'gtol': 1e-18})
            cand = np.maximum(res.x, 0.0)
            if cand.max() > 0:
                cand = norm(cand)
                r = _R_fast(cand)
                if r > bestR:
                    bestR = r; best = cand.copy()
                if r <= _R_fast(h) + 1e-15:
                    h = cand
                    break
                h = cand
            else:
                break
        except Exception:
            break
        if time.process_time() > phaseA_end:
            break

    # ---- Phase B: p-norm continuation to escape flat max ----
    phaseB_end = t0 + budget_seconds * 0.68
    h = best.copy()
    for p in [8, 16, 32, 64, 128, 256]:
        if time.process_time() > phaseB_end:
            break
        def fg(x, p=p):
            R, g = _pnorm_max_grad(x, p)
            if not np.all(np.isfinite(g)):
                g = np.zeros_like(x)
            return -R, -g
        try:
            res = minimize(fg, h, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * N,
                           options={'maxiter': 200, 'maxfun': 400,
                                    'ftol': 1e-18, 'gtol': 1e-16})
            cand = np.maximum(res.x, 0.0)
            if cand.max() > 0:
                cand = norm(cand)
                r = _R_fast(cand)
                if r > bestR:
                    bestR = r; best = cand.copy()
                h = cand
        except Exception:
            pass

    # ---- Phase C: exact-R Adam polish ----
    h = best.copy()
    beta1, beta2 = 0.9, 0.999
    eps = 1e-8
    m = np.zeros(N); v = np.zeros(N)
    step = 0
    phaseC_start = time.process_time()
    phaseC_end = t0 + budget_seconds * 0.88
    lr_start = 3e-4
    lr_end = 1e-9
    while True:
        if (step & 3) == 0 and time.process_time() > phaseC_end:
            break
        step += 1
        R, g = _R_and_grad(h)
        if not np.all(np.isfinite(g)):
            break
        m = beta1 * m + (1 - beta1) * g
        v = beta2 * v + (1 - beta2) * (g * g)
        mhat = m / (1 - beta1 ** step)
        vhat = v / (1 - beta2 ** step)
        frac = (time.process_time() - phaseC_start) / max(1e-9, phaseC_end - phaseC_start)
        frac = min(1.0, max(0.0, frac))
        lr = lr_start * (lr_end / lr_start) ** frac
        h = h + lr * mhat / (np.sqrt(vhat) + eps)
        h = np.maximum(h, 0.0)
        if h.max() > 0:
            h = h / h.max()
        if (step & 15) == 0:
            r = _R_fast(h)
            if r > bestR:
                bestR = r; best = h.copy()

    r = _R_fast(h)
    if r > bestR:
        bestR = r; best = h.copy()

    # ---- Phase D: active-set L-BFGS-B on peak region ----
    phaseD_end = deadline
    h = best.copy()
    c = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], c, [0.0]))
    lmax = L.max()
    if lmax > 0:
        mask = np.zeros(N, dtype=bool)
        js = np.nonzero(L >= 0.99 * lmax)[0]
        for j in js:
            base = j - 1
            lo = max(0, base - (N - 1))
            hi = min(N - 1, base)
            if lo <= hi:
                mask[lo:hi + 1] = True
        active = np.nonzero(mask)[0]
        if active.size > 0 and active.size < N:
            def fg_sub(xsub):
                hh = h.copy()
                hh[active] = xsub
                Rr, g = _R_and_grad(hh)
                if not np.all(np.isfinite(g)):
                    g = np.zeros_like(hh)
                return -Rr, -g[active]
            try:
                res = minimize(fg_sub, h[active].copy(), jac=True,
                               method='L-BFGS-B',
                               bounds=[(0.0, None)] * active.size,
                               options={'maxiter': 300, 'maxfun': 600,
                                        'ftol': 1e-20, 'gtol': 1e-18})
                cand = h.copy()
                cand[active] = np.maximum(res.x, 0.0)
                if cand.max() > 0:
                    cand = norm(cand)
                    r = _R_fast(cand)
                    if r > bestR:
                        bestR = r; best = cand.copy()
            except Exception:
                pass

    # ---- Phase E: full exact-R L-BFGS-B to finish ----
    h = best.copy()
    while time.process_time() < phaseD_end:
        def fg(x):
            R, g = _R_and_grad(x)
            if not np.all(np.isfinite(g)):
                g = np.zeros_like(x)
            return -R, -g
        try:
            res = minimize(fg, h, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * N,
                           options={'maxiter': 200, 'maxfun': 400,
                                    'ftol': 1e-20, 'gtol': 1e-18})
            cand = np.maximum(res.x, 0.0)
            if cand.max() > 0:
                cand = norm(cand)
                r = _R_fast(cand)
                if r > bestR:
                    bestR = r; best = cand.copy()
                if r <= _R_fast(h) + 1e-15:
                    break
                h = cand
            else:
                break
        except Exception:
            break

    return best
