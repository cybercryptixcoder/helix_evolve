import numpy as np
import time
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize


def _R(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    L = np.convolve(h, h)
    if L.max() <= 0:
        return 0.0
    Lp = np.concatenate(([0.0], L, [0.0]))
    a = Lp[:-1]
    b = Lp[1:]
    l2 = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    linf = Lp.max()
    return l2 / (l1 * linf)


def _R_fft(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    N = h.size
    nfft = 1
    while nfft < 2 * N - 1:
        nfft <<= 1
    H = np.fft.rfft(h, nfft)
    L = np.fft.irfft(H * H, nfft)[:2 * N - 1]
    linf = L.max()
    if linf <= 0:
        return 0.0
    a = np.empty(L.size + 1)
    b = np.empty(L.size + 1)
    a[0] = 0.0
    a[1:] = L
    b[:-1] = L
    b[-1] = 0.0
    l2 = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    return l2 / (l1 * linf)


def _cd(xc, lv, N, step0, step_min, deadline):
    xi = np.arange(N, dtype=float)
    M = lv.size

    def build(lvv):
        cs = CubicSpline(xc, lvv)
        h = np.exp(cs(xi))
        return np.maximum(h, 0.0)

    h = build(lv)
    cur_R = _R_fft(h)
    step = step0
    while step > step_min and time.process_time() < deadline:
        improved = False
        for j in range(M):
            if time.process_time() > deadline:
                break
            for sgn in (1.0, -1.0):
                if time.process_time() > deadline:
                    break
                trial = lv.copy()
                trial[j] += sgn * step
                ht = build(trial)
                r = _R_fft(ht)
                if r > cur_R + 1e-12:
                    cur_R = r
                    lv = trial
                    improved = True
                    break
        if not improved:
            step *= 0.5
    return lv, cur_R


def _adaptive_xc(hs, N, M):
    g = np.log(np.maximum(hs, 1e-9))
    if g.size < 3:
        return np.linspace(0.0, N - 1.0, M)
    d2 = np.abs(g[2:] - 2.0 * g[1:-1] + g[:-2])
    if d2.size > 101:
        k = np.ones(101) / 101.0
        d2s = np.convolve(d2, k, mode="same")
    else:
        d2s = d2
    dmax = d2s.max() if d2s.size > 0 else 0.0
    weights = d2s + 1e-3 * dmax
    c = np.cumsum(weights)
    tot = c[-1]
    if tot <= 0:
        return np.linspace(0.0, N - 1.0, M)
    c = c / tot
    q = np.linspace(0.0, 1.0, M)
    pos = np.interp(q, c, np.arange(1, d2s.size + 1, dtype=float))
    xc = pos * (N - 1.0) / (hs.size - 1.0)
    xc[0] = 0.0
    xc[-1] = N - 1.0
    return xc


def _pixel_polish(h, deadline, rng):
    h = np.array(h, dtype=float)
    N = h.size
    cur_R = _R_fft(h)
    hmax = h.max()
    if hmax <= 0:
        return h, cur_R
    sel = set(rng.integers(0, N, size=min(2000, N)).tolist())
    high = np.where(h >= 0.9 * hmax)[0]
    sel.update(high.tolist())
    idx = np.array(sorted(sel), dtype=int)
    if idx.size == 0:
        return h, cur_R
    for s in (0.01, 0.005, 0.002, 0.001):
        improved_any = True
        while improved_any and time.process_time() < deadline:
            improved_any = False
            for i in idx:
                if time.process_time() > deadline:
                    break
                hi = h[i]
                if hi <= 0:
                    continue
                for mult in (np.exp(s), np.exp(-s)):
                    h[i] = hi * mult
                    r = _R_fft(h)
                    if r > cur_R + 1e-13:
                        cur_R = r
                        hi = h[i]
                        improved_any = True
                    else:
                        h[i] = hi
            if not improved_any:
                break
    return h, cur_R


def _grad_R(h):
    N = h.size
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    w = (L[:-2] + 4.0 * L[1:-1] + L[2:]) / 3.0
    w_full = np.empty(2 * N + 1)
    w_full[1:-1] = w
    w_full[0] = (4.0 * L[0] + L[1]) / 3.0
    w_full[-1] = (L[-2] + 4.0 * L[-1]) / 3.0
    wq = w_full[1:-1]
    c = np.convolve(wq, h[::-1])
    dA = 2.0 * c[N - 1: N - 1 + N]

    B = h.sum() ** 2
    dB = 2.0 * h.sum() * np.ones(N)

    C = L.max()
    K = np.where(L >= C - 1e-10 * C)[0]
    dC = np.zeros(N)
    if K.size > 0:
        acc = np.zeros(N)
        cnt = 0
        for kstar in K:
            if 1 <= kstar <= 2 * N - 1:
                m = kstar - 1
                lo = max(0, m - N + 1)
                hi = min(N - 1, m)
                if lo <= hi:
                    ii = np.arange(lo, hi + 1)
                    acc[ii] += 2.0 * h[m - ii]
                    cnt += 1
        if cnt > 0:
            dC = acc / cnt

    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0

    denom = (B * C) ** 2
    grad = (dA * B * C - A * (dB * C + B * dC)) / denom
    return grad, A, B, C


def _pgd_bb(h, deadline, max_iter=400):
    h = np.array(h, dtype=float)
    h = np.maximum(h, 0.0)
    s = h.sum()
    if s <= 0:
        return h, 0.0
    h = h / s
    cur_R = _R_fft(h)
    best_h = h.copy()
    best_R = cur_R

    grad, _, _, _ = _grad_R(h)
    gn = np.linalg.norm(grad)
    if gn <= 0 or not np.isfinite(gn):
        return best_h, best_R
    gdir = grad / gn

    step_bb = 1e-3
    prev_h = None
    prev_gdir = None

    for it in range(max_iter):
        if time.process_time() > deadline:
            break

        if prev_h is not None and prev_gdir is not None:
            s_vec = h - prev_h
            y_vec = gdir - prev_gdir
            sy = float(np.dot(s_vec, y_vec))
            ss = float(np.dot(s_vec, s_vec))
            yy = float(np.dot(y_vec, y_vec))
            cands = []
            if sy > 1e-30:
                cands.append(ss / sy)
            if yy > 1e-30:
                cands.append(sy / yy)
            if cands:
                step_bb = float(np.median(cands))
            step_bb = min(max(step_bb, 1e-8), 1e-2)

        prev_h = h.copy()
        prev_gdir = gdir.copy()

        step = step_bb
        improved = False
        for _ in range(25):
            if time.process_time() > deadline:
                break
            trial = h + step * gdir
            trial = np.maximum(trial, 0.0)
            ts = trial.sum()
            if ts <= 0:
                step *= 0.5
                continue
            trial = trial / ts
            r = _R_fft(trial)
            if r > cur_R + 1e-14:
                h = trial
                cur_R = r
                improved = True
                break
            step *= 0.5

        if not improved:
            grad, _, _, _ = _grad_R(h)
            gn = np.linalg.norm(grad)
            if gn <= 0 or not np.isfinite(gn):
                break
            gdir = grad / gn
            step_bb = max(step_bb * 0.5, 1e-8)
            continue

        if cur_R > best_R:
            best_R = cur_R
            best_h = h.copy()

        grad, _, _, _ = _grad_R(h)
        gn = np.linalg.norm(grad)
        if gn <= 0 or not np.isfinite(gn):
            break
        gdir = grad / gn

    return best_h, best_R


def _R_p(h, p):
    N = h.size
    s = h.sum()
    if s <= 0:
        return 0.0
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    B = s * s
    Lp = np.maximum(L, 0.0)
    mx = Lp.max()
    if mx <= 0:
        return 0.0
    Cp = mx * (np.sum((Lp / mx) ** p) ** (1.0 / p))
    if Cp <= 0:
        return 0.0
    return A / (B * Cp)


def _grad_R_p(h, p):
    N = h.size
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    w = (L[:-2] + 4.0 * L[1:-1] + L[2:]) / 3.0
    w_full = np.empty(2 * N + 1)
    w_full[1:-1] = w
    w_full[0] = (4.0 * L[0] + L[1]) / 3.0
    w_full[-1] = (L[-2] + 4.0 * L[-1]) / 3.0
    wq = w_full[1:-1]
    c = np.convolve(wq, h[::-1])
    dA = 2.0 * c[N - 1: N - 1 + N]

    s = h.sum()
    B = s * s
    dB = 2.0 * s * np.ones(N)

    Lp = np.maximum(L, 0.0)
    mx = Lp.max()
    if mx <= 0:
        return np.zeros(N)
    r = Lp / mx
    S = np.sum(r ** p)
    if S <= 0:
        return np.zeros(N)
    Cp = mx * S ** (1.0 / p)
    denomS = S ** ((p - 1.0) / p)
    dC_dL = (r ** (p - 1.0)) / denomS
    dCdL_inner = dC_dL[1:2 * N]
    cc = np.convolve(dCdL_inner, h[::-1])
    dC = 2.0 * cc[N - 1: N - 1 + N]

    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0

    denom = (B * Cp) ** 2
    grad = (dA * B * Cp - A * (dB * Cp + B * dC)) / denom
    return grad


def _R_topk(h, K):
    N = h.size
    s = h.sum()
    if s <= 0:
        return 0.0
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    B = s * s
    M = L.size
    kk = min(K, M)
    if kk <= 0:
        return 0.0
    idx = np.argpartition(L, M - kk)[M - kk:]
    C = L[idx].mean()
    if C <= 0:
        return 0.0
    return A / (B * C)


def _grad_R_topk(h, K):
    N = h.size
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    w = (L[:-2] + 4.0 * L[1:-1] + L[2:]) / 3.0
    w_full = np.empty(2 * N + 1)
    w_full[1:-1] = w
    w_full[0] = (4.0 * L[0] + L[1]) / 3.0
    w_full[-1] = (L[-2] + 4.0 * L[-1]) / 3.0
    wq = w_full[1:-1]
    c = np.convolve(wq, h[::-1])
    dA = 2.0 * c[N - 1: N - 1 + N]

    s = h.sum()
    B = s * s
    dB = 2.0 * s * np.ones(N)

    M = L.size
    kk = min(K, M)
    if kk <= 0:
        return np.zeros(N)
    idx = np.argpartition(L, M - kk)[M - kk:]
    C = L[idx].mean()
    if C <= 0:
        return np.zeros(N)

    dC = np.zeros(N)
    for kstar in idx:
        if 1 <= kstar <= 2 * N - 1:
            m = kstar - 1
            lo = max(0, m - N + 1)
            hi = min(N - 1, m)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                dC[ii] += 2.0 * h[m - ii]
    dC = dC / float(kk)

    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0

    denom = (B * C) ** 2
    grad = (dA * B * C - A * (dB * C + B * dC)) / denom
    return grad


def _lbfgs_smooth(h0, p, deadline, maxiter=40):
    h0 = np.array(h0, dtype=float)
    h0 = np.maximum(h0, 0.0)
    s = h0.sum()
    if s <= 0:
        return h0, 0.0
    h0 = h0 / s
    z0 = np.log(np.maximum(h0, 1e-12))

    def fun(z):
        if time.process_time() > deadline:
            raise TimeoutError
        h = np.exp(z)
        return -_R_p(h, p)

    def jac(z):
        if time.process_time() > deadline:
            raise TimeoutError
        h = np.exp(z)
        g = _grad_R_p(h, p)
        return -g * h

    bounds = [(-30.0, 10.0)] * z0.size
    try:
        res = minimize(fun, z0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        z = res.x
    except TimeoutError:
        z = z0
    h = np.exp(z)
    h = np.maximum(h, 0.0)
    return h, _R_fft(h)


def _lbfgs_direct(h0, p, deadline, maxiter=50):
    h0 = np.array(h0, dtype=float)
    h0 = np.maximum(h0, 0.0)
    s = h0.sum()
    if s <= 0:
        return h0, 0.0
    h0 = h0 / s

    def fun(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_R_p(h, p)

    def jac(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_grad_R_p(h, p)

    bounds = [(0.0, None)] * h0.size
    try:
        res = minimize(fun, h0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        h = res.x
    except TimeoutError:
        h = h0
    h = np.maximum(h, 0.0)
    return h, _R_fft(h)


def _lbfgs_topk(h0, K, deadline, maxiter=40):
    h0 = np.array(h0, dtype=float)
    h0 = np.maximum(h0, 0.0)
    s = h0.sum()
    if s <= 0:
        return h0, 0.0
    h0 = h0 / s

    def fun(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_R_topk(h, K)

    def jac(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_grad_R_topk(h, K)

    bounds = [(0.0, None)] * h0.size
    try:
        res = minimize(fun, h0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        h = res.x
    except TimeoutError:
        h = h0
    h = np.maximum(h, 0.0)
    return h, _R_fft(h)


def _R_pen(h, K, lam):
    N = h.size
    s = h.sum()
    if s <= 0:
        return 0.0
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    B = s * s
    M = L.size
    am = int(np.argmax(L))
    mx = L[am]
    if mx <= 0:
        return 0.0
    kk = min(K, M - 1)
    if kk <= 0:
        C = mx
    else:
        mask = np.ones(M, dtype=bool)
        mask[am] = False
        rest = L[mask]
        idx = np.argpartition(rest, rest.size - kk)[rest.size - kk:]
        C = mx + lam * rest[idx].mean()
    if C <= 0:
        return 0.0
    return A / (B * C)


def _grad_R_pen(h, K, lam):
    N = h.size
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    w = (L[:-2] + 4.0 * L[1:-1] + L[2:]) / 3.0
    w_full = np.empty(2 * N + 1)
    w_full[1:-1] = w
    w_full[0] = (4.0 * L[0] + L[1]) / 3.0
    w_full[-1] = (L[-2] + 4.0 * L[-1]) / 3.0
    wq = w_full[1:-1]
    c = np.convolve(wq, h[::-1])
    dA = 2.0 * c[N - 1: N - 1 + N]

    s = h.sum()
    B = s * s
    dB = 2.0 * s * np.ones(N)

    M = L.size
    am = int(np.argmax(L))
    mx = L[am]
    if mx <= 0:
        return np.zeros(N)
    kk = min(K, M - 1)

    dCdL = np.zeros(M)
    dCdL[am] = 1.0
    if kk > 0:
        mask = np.ones(M, dtype=bool)
        mask[am] = False
        rest_idx = np.where(mask)[0]
        rest_vals = L[rest_idx]
        sel = np.argpartition(rest_vals, rest_vals.size - kk)[rest_vals.size - kk:]
        chosen = rest_idx[sel]
        dCdL[chosen] += lam / float(kk)
        C = mx + lam * L[chosen].mean()
    else:
        C = mx
    if C <= 0:
        return np.zeros(N)

    dC = np.zeros(N)
    for kstar in np.where(dCdL != 0.0)[0]:
        wt = dCdL[kstar]
        if 1 <= kstar <= 2 * N - 1:
            m = kstar - 1
            lo = max(0, m - N + 1)
            hi = min(N - 1, m)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                dC[ii] += wt * 2.0 * h[m - ii]

    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0

    denom = (B * C) ** 2
    grad = (dA * B * C - A * (dB * C + B * dC)) / denom
    return grad


def _lbfgs_pen(h0, K, lam, deadline, maxiter=35):
    h0 = np.array(h0, dtype=float)
    h0 = np.maximum(h0, 0.0)
    s = h0.sum()
    if s <= 0:
        return h0, 0.0
    h0 = h0 / s

    def fun(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_R_pen(h, K, lam)

    def jac(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_grad_R_pen(h, K, lam)

    bounds = [(0.0, None)] * h0.size
    try:
        res = minimize(fun, h0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        h = res.x
    except TimeoutError:
        h = h0
    h = np.maximum(h, 0.0)
    return h, _R_fft(h)


def _mirror(u):
    return np.concatenate((u, u[::-1]))


def _lbfgs_pen_sym(u0, K, lam, deadline, maxiter=40):
    u0 = np.array(u0, dtype=float)
    u0 = np.maximum(u0, 0.0)
    s = u0.sum()
    if s <= 0:
        return u0, 0.0
    u0 = u0 / s

    def fun(u):
        if time.process_time() > deadline:
            raise TimeoutError
        h = _mirror(np.maximum(u, 0.0))
        return -_R_pen(h, K, lam)

    def jac(u):
        if time.process_time() > deadline:
            raise TimeoutError
        uu = np.maximum(u, 0.0)
        h = _mirror(uu)
        g = _grad_R_pen(h, K, lam)
        M = uu.size
        gu = g[:M] + g[M:][::-1]
        return -gu

    bounds = [(0.0, None)] * u0.size
    try:
        res = minimize(fun, u0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        u = res.x
    except TimeoutError:
        u = u0
    u = np.maximum(u, 0.0)
    h = _mirror(u)
    return h, _R_fft(h)


def _lbfgs_smooth_sym(u0, p, deadline, maxiter=35):
    u0 = np.array(u0, dtype=float)
    u0 = np.maximum(u0, 0.0)
    s = u0.sum()
    if s <= 0:
        return u0, 0.0
    u0 = u0 / s

    def fun(u):
        if time.process_time() > deadline:
            raise TimeoutError
        h = _mirror(np.maximum(u, 0.0))
        return -_R_p(h, p)

    def jac(u):
        if time.process_time() > deadline:
            raise TimeoutError
        uu = np.maximum(u, 0.0)
        h = _mirror(uu)
        g = _grad_R_p(h, p)
        M = uu.size
        gu = g[:M] + g[M:][::-1]
        return -gu

    bounds = [(0.0, None)] * u0.size
    try:
        res = minimize(fun, u0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        u = res.x
    except TimeoutError:
        u = u0
    u = np.maximum(u, 0.0)
    h = _mirror(u)
    return h, _R_fft(h)


def _run_schedule(h_seed, deadline):
    h = np.array(h_seed, dtype=float)
    h = np.maximum(h, 0.0)
    s = h.sum()
    if s <= 0:
        return h, 0.0
    h = h / s
    best_h = h.copy()
    best_R = _R_fft(h)
    for p in (50, 100, 200, 400, 800):
        if time.process_time() > deadline:
            break
        h, r = _lbfgs_smooth(h, p, deadline, maxiter=40)
        if r > best_R:
            best_R = r
            best_h = h.copy()
    return best_h, best_R


def _R_pen_win(h, K, w, lam):
    N = h.size
    s = h.sum()
    if s <= 0:
        return 0.0
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    B = s * s
    M = L.size
    am = int(np.argmax(L))
    mx = L[am]
    if mx <= 0:
        return 0.0
    idx_all = np.arange(M)
    far = np.abs(idx_all - am) > w
    far_idx = np.where(far)[0]
    if far_idx.size == 0:
        C = mx
    else:
        vals = L[far_idx]
        kk = min(K, far_idx.size)
        sel = np.argpartition(vals, vals.size - kk)[vals.size - kk:]
        chosen = far_idx[sel]
        C = mx + lam * L[chosen].mean()
    if C <= 0:
        return 0.0
    return A / (B * C)


def _grad_R_pen_win(h, K, w, lam):
    N = h.size
    q = np.convolve(h, h)
    L = np.concatenate(([0.0], q, [0.0]))
    wgt = (L[:-2] + 4.0 * L[1:-1] + L[2:]) / 3.0
    w_full = np.empty(2 * N + 1)
    w_full[1:-1] = wgt
    w_full[0] = (4.0 * L[0] + L[1]) / 3.0
    w_full[-1] = (L[-2] + 4.0 * L[-1]) / 3.0
    wq = w_full[1:-1]
    c = np.convolve(wq, h[::-1])
    dA = 2.0 * c[N - 1: N - 1 + N]

    s = h.sum()
    B = s * s
    dB = 2.0 * s * np.ones(N)

    M = L.size
    am = int(np.argmax(L))
    mx = L[am]
    if mx <= 0:
        return np.zeros(N)

    dCdL = np.zeros(M)
    dCdL[am] = 1.0
    idx_all = np.arange(M)
    far = np.abs(idx_all - am) > w
    far_idx = np.where(far)[0]
    if far_idx.size > 0:
        vals = L[far_idx]
        kk = min(K, far_idx.size)
        sel = np.argpartition(vals, vals.size - kk)[vals.size - kk:]
        chosen = far_idx[sel]
        dCdL[chosen] += lam / float(kk)
        C = mx + lam * L[chosen].mean()
    else:
        C = mx
    if C <= 0:
        return np.zeros(N)

    dC = np.zeros(N)
    for kstar in np.where(dCdL != 0.0)[0]:
        wt = dCdL[kstar]
        if 1 <= kstar <= 2 * N - 1:
            m = kstar - 1
            lo = max(0, m - N + 1)
            hi = min(N - 1, m)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                dC[ii] += wt * 2.0 * h[m - ii]

    A = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0

    denom = (B * C) ** 2
    grad = (dA * B * C - A * (dB * C + B * dC)) / denom
    return grad


def _lbfgs_pen_win_sym(u0, K, w, lam, deadline, maxiter=40):
    u0 = np.array(u0, dtype=float)
    u0 = np.maximum(u0, 0.0)
    s = u0.sum()
    if s <= 0:
        return u0, 0.0
    u0 = u0 / s

    def fun(u):
        if time.process_time() > deadline:
            raise TimeoutError
        h = _mirror(np.maximum(u, 0.0))
        return -_R_pen_win(h, K, w, lam)

    def jac(u):
        if time.process_time() > deadline:
            raise TimeoutError
        uu = np.maximum(u, 0.0)
        h = _mirror(uu)
        g = _grad_R_pen_win(h, K, w, lam)
        M = uu.size
        gu = g[:M] + g[M:][::-1]
        return -gu

    bounds = [(0.0, None)] * u0.size
    try:
        res = minimize(fun, u0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        u = res.x
    except TimeoutError:
        u = u0
    u = np.maximum(u, 0.0)
    h = _mirror(u)
    return h, _R_fft(h)


def _lbfgs_pen_win(h0, K, w, lam, deadline, maxiter=40):
    h0 = np.array(h0, dtype=float)
    h0 = np.maximum(h0, 0.0)
    s = h0.sum()
    if s <= 0:
        return h0, 0.0
    h0 = h0 / s

    def fun(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_R_pen_win(h, K, w, lam)

    def jac(h):
        if time.process_time() > deadline:
            raise TimeoutError
        return -_grad_R_pen_win(h, K, w, lam)

    bounds = [(0.0, None)] * h0.size
    try:
        res = minimize(fun, h0, jac=jac, method="L-BFGS-B",
                       bounds=bounds, options={"maxiter": maxiter, "maxfun": 4 * maxiter})
        h = res.x
    except TimeoutError:
        h = h0
    h = np.maximum(h, 0.0)
    return h, _R_fft(h)


def _smooth_seed(base, sigma, rng, nctrl=7):
    N = base.size
    xc = np.linspace(0.0, N - 1.0, nctrl)
    ctrl = rng.normal(0.0, 1.0, size=nctrl)
    cs = CubicSpline(xc, ctrl)
    xi = np.arange(N, dtype=float)
    s = cs(xi)
    h = base * np.exp(sigma * s)
    h = np.maximum(h, 0.0)
    ss = h.sum()
    if ss > 0:
        h = h / ss
    return h


def _adaptive_ctrl_xc(base, nctrl):
    """Place nctrl control points at quantiles of smoothed |d2 log h| plus endpoints."""
    N = base.size
    g = np.log(np.maximum(base, 1e-9))
    if g.size < 3:
        return np.linspace(0.0, N - 1.0, nctrl)
    d2 = np.abs(g[2:] - 2.0 * g[1:-1] + g[:-2])
    if d2.size > 101:
        k = np.ones(101) / 101.0
        d2s = np.convolve(d2, k, mode="same")
    else:
        d2s = d2
    dmax = d2s.max() if d2s.size > 0 else 0.0
    weights = d2s + 1e-3 * dmax
    c = np.cumsum(weights)
    tot = c[-1]
    if tot <= 0:
        return np.linspace(0.0, N - 1.0, nctrl)
    c = c / tot
    q = np.linspace(0.0, 1.0, nctrl)
    pos = np.interp(q, c, np.arange(1, d2s.size + 1, dtype=float))
    xc = pos * (N - 1.0) / (g.size - 1.0)
    xc[0] = 0.0
    xc[-1] = N - 1.0
    return xc


def _adaptive_smooth_seed(base, sigma, rng, xc):
    N = base.size
    ctrl = rng.normal(0.0, 1.0, size=xc.size)
    cs = CubicSpline(xc, ctrl)
    xi = np.arange(N, dtype=float)
    s = cs(xi)
    h = base * np.exp(sigma * s)
    h = np.maximum(h, 0.0)
    ss = h.sum()
    if ss > 0:
        h = h / ss
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    d_pgd = t0 + budget_seconds * 0.55
    d_direct = t0 + budget_seconds * 0.75

    hs_start = None
    if start is not None:
        hs = np.asarray(start, dtype=float)
        if hs.size > 0 and hs.size <= 50000 and np.all(np.isfinite(hs)) and hs.sum() > 0:
            hs = np.maximum(hs, 0.0)
            hs_start = hs

    if hs_start is None:
        N = 20001
        h = np.ones(N)
        h, _ = _pgd_bb(h, d_pgd, max_iter=400)
        return h

    best_h = hs_start.copy()
    best_R = _R_fft(best_h)

    rng = np.random.default_rng(12345)
    seeds = [hs_start.copy()]
    for sigma in (0.003, 0.01, 0.03):
        noise = rng.normal(0.0, sigma, size=hs_start.size)
        hseed = hs_start * np.exp(noise)
        hseed = np.maximum(hseed, 0.0)
        if hseed.sum() > 0:
            seeds.append(hseed)

    n_seeds = len(seeds)
    slice_frac = 0.12
    for k, seed in enumerate(seeds):
        seed_deadline = t0 + budget_seconds * min(slice_frac * (k + 1), 0.85)
        if time.process_time() > seed_deadline:
            continue
        h_out, r_out = _run_schedule(seed, seed_deadline)
        if r_out > best_R:
            best_R = r_out
            best_h = h_out.copy()

    hd = np.maximum(best_h, 0.0)
    sd = hd.sum()
    if sd > 0:
        hd = hd / sd
        for p in (200, 400, 800, 1200):
            if time.process_time() > d_direct:
                break
            h_out, r_out = _lbfgs_direct(hd, p, d_direct, maxiter=50)
            if r_out > best_R:
                best_R = r_out
                best_h = h_out.copy()
            hd = h_out

    base = np.maximum(best_h, 0.0)
    if base.sum() > 0:
        base = base / base.sum()
        rng2 = np.random.default_rng(98765)
        sigmas = (0.0005, 0.001, 0.002, 0.005, 0.01, 0.03, 0.08, 0.2)
        for k, sigma in enumerate(sigmas):
            seed_deadline = t0 + budget_seconds * min(0.08 * (k + 1), 0.95)
            if time.process_time() > seed_deadline:
                break
            noise = rng2.normal(0.0, sigma, size=base.size)
            hseed = base * np.exp(noise)
            hseed = np.maximum(hseed, 0.0)
            ss = hseed.sum()
            if ss <= 0:
                continue
            hseed = hseed / ss
            hcur = hseed
            for p in (400, 800, 1200, 1600):
                if time.process_time() > seed_deadline:
                    break
                h_out, r_out = _lbfgs_direct(hcur, p, seed_deadline, maxiter=30)
                if r_out > best_R:
                    best_R = r_out
                    best_h = h_out.copy()
                hcur = h_out

    hh = np.maximum(best_h, 0.0)
    sh = hh.sum()
    if sh > 0:
        hh = hh / sh
        for p in (1600, 2400, 3200, 4800):
            if time.process_time() > d_direct:
                break
            h_out, r_out = _lbfgs_direct(hh, p, d_direct, maxiter=35)
            if r_out > best_R:
                best_R = r_out
                best_h = h_out.copy()
            hh = h_out

    base2 = np.maximum(best_h, 0.0)
    if base2.sum() > 0:
        base2 = base2 / base2.sum()
        rng3 = np.random.default_rng(24680)
        fine_sigmas = (0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01)
        for k, sigma in enumerate(fine_sigmas):
            seed_deadline = t0 + budget_seconds * min(0.08 * (k + 1), 0.95)
            if time.process_time() > seed_deadline:
                break
            noise = rng3.normal(0.0, sigma, size=base2.size)
            hseed = base2 * np.exp(noise)
            hseed = np.maximum(hseed, 0.0)
            ss = hseed.sum()
            if ss <= 0:
                continue
            hseed = hseed / ss
            hcur = hseed
            for p in (800, 1200, 1600, 2400):
                if time.process_time() > seed_deadline:
                    break
                h_out, r_out = _lbfgs_direct(hcur, p, seed_deadline, maxiter=30)
                if r_out > best_R:
                    best_R = r_out
                    best_h = h_out.copy()
                hcur = h_out

    d_topk = t0 + budget_seconds * 0.88
    hk = np.maximum(best_h, 0.0)
    sk = hk.sum()
    if sk > 0:
        hk = hk / sk
        for K in (32, 16, 8, 4, 2, 1):
            if time.process_time() > d_topk:
                break
            h_out, r_out = _lbfgs_topk(hk, K, d_topk, maxiter=35)
            if r_out > best_R:
                best_R = r_out
                best_h = h_out.copy()
            hk = h_out

    d_pen = t0 + budget_seconds * 0.88
    hp = np.maximum(best_h, 0.0)
    sp = hp.sum()
    if sp > 0:
        hp = hp / sp
        for K in (4, 8):
            for lam in (0.02, 0.05, 0.1):
                if time.process_time() > d_pen:
                    break
                h_out, r_out = _lbfgs_pen(hp, K, lam, d_pen, maxiter=35)
                if r_out > best_R:
                    best_R = r_out
                    best_h = h_out.copy()

    d_sym = t0 + budget_seconds * 0.88
    hsym = 0.5 * (np.maximum(best_h, 0.0) + np.maximum(best_h, 0.0)[::-1])
    ssym = hsym.sum()
    if ssym > 0:
        hsym = hsym / ssym
        N = hsym.size
        if N % 2 == 0:
            u0 = hsym[:N // 2].copy()
        else:
            u0 = hsym[:(N + 1) // 2].copy()
        su = u0.sum()
        if su > 0:
            u0 = u0 / su
            for K in (8, 4, 2):
                for lam in (0.01, 0.02, 0.05):
                    if time.process_time() > d_sym:
                        break
                    if N % 2 == 0:
                        h_out, r_out = _lbfgs_pen_sym(u0, K, lam, d_sym, maxiter=40)
                    else:
                        def _mirror_odd(u):
                            return np.concatenate((u, u[-2::-1]))
                        uu0 = np.array(u0, dtype=float)
                        uu0 = np.maximum(uu0, 0.0)
                        s0 = uu0.sum()
                        if s0 <= 0:
                            continue
                        uu0 = uu0 / s0

                        def fun(u):
                            if time.process_time() > d_sym:
                                raise TimeoutError
                            h = _mirror_odd(np.maximum(u, 0.0))
                            return -_R_pen(h, K, lam)

                        def jac(u):
                            if time.process_time() > d_sym:
                                raise TimeoutError
                            uu = np.maximum(u, 0.0)
                            h = _mirror_odd(uu)
                            g = _grad_R_pen(h, K, lam)
                            M = uu.size
                            gu = g[:M].copy()
                            tail = g[M:]
                            gu[1:M] += tail[::-1]
                            return -gu

                        bounds = [(0.0, None)] * uu0.size
                        try:
                            res = minimize(fun, uu0, jac=jac, method="L-BFGS-B",
                                           bounds=bounds,
                                           options={"maxiter": 40, "maxfun": 160})
                            u = res.x
                        except TimeoutError:
                            u = uu0
                        u = np.maximum(u, 0.0)
                        h_out = _mirror_odd(u)
                        r_out = _R_fft(h_out)
                    if r_out > best_R:
                        best_R = r_out
                        best_h = h_out.copy()
                    hb = np.maximum(best_h, 0.0)
                    sb = hb.sum()
                    if sb > 0:
                        hb = hb / sb
                        if N % 2 == 0:
                            u0 = hb[:N // 2].copy()
                        else:
                            u0 = hb[:(N + 1) // 2].copy()
                        s0 = u0.sum()
                        if s0 > 0:
                            u0 = u0 / s0

    d_win = t0 + budget_seconds * 0.88
    hw = np.maximum(best_h, 0.0)
    sw = hw.sum()
    if sw > 0:
        hw = hw / sw
        for K in (1, 2, 4):
            for lam in (0.0002, 0.001, 0.005):
                if time.process_time() > d_win:
                    break
                h_out, r_out = _lbfgs_pen_win(hw, K, 2, lam, d_win, maxiter=35)
                if r_out > best_R:
                    best_R = r_out
                    best_h = h_out.copy()

    # ---- NEW: adaptive-control spline seeds + pen_win polish ----
    base3 = np.maximum(best_h, 0.0)
    if base3.sum() > 0:
        base3 = base3 / base3.sum()
        xc = _adaptive_ctrl_xc(base3, 11)
        rng4 = np.random.default_rng(13579)
        sigmas4 = (0.001, 0.003, 0.01, 0.03)
        seed_list = []
        for sigma in sigmas4:
            for _ in range(2):
                hseed = _adaptive_smooth_seed(base3, sigma, rng4, xc)
                seed_list.append(hseed)
        n_s = len(seed_list)
        for k, hseed in enumerate(seed_list):
            seed_deadline = t0 + budget_seconds * min(0.06 * (k + 1), 0.94)
            if time.process_time() > seed_deadline:
                break
            h_out, r_out = _lbfgs_pen_win(hseed, 1, 2, 0.0002, seed_deadline, maxiter=45)
            if r_out > best_R:
                best_R = r_out
                best_h = h_out.copy()

    d_final = t0 + budget_seconds * 0.94
    hf = np.maximum(best_h, 0.0)
    sf = hf.sum()
    if sf > 0:
        hf = hf / sf
        h_out, r_out = _pgd_bb(hf, d_final, max_iter=200)
        if r_out > best_R:
            best_R = r_out
            best_h = h_out.copy()

    return np.maximum(best_h, 0.0)
