import numpy as np
import time
import math


def _fftconv(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return np.zeros(0)
    n = a.size + b.size - 1
    nf = 1 << int(math.ceil(math.log2(max(n, 2))))
    fa = np.fft.rfft(a, nf)
    fb = np.fft.rfft(b, nf)
    return np.fft.irfft(fa * fb, nf)[:n]


def _R_from_heights(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0:
        return 0.0
    L = _fftconv(h, h)
    m = L.max()
    s = h.sum()
    if m <= 0 or s <= 0:
        return 0.0
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    return l2sq / (s * s * m)


def _knot_shares(h):
    h = np.asarray(h, dtype=float)
    L = _fftconv(h, h)
    m = L.max()
    if m <= 0:
        return 0.0, 0.0, 0.0
    return (100.0 * np.mean(L >= 0.999 * m),
            100.0 * np.mean(L >= 0.99 * m),
            100.0 * np.mean(L >= 0.95 * m))


def _score_grad_soft(h, tau):
    h = np.asarray(h, dtype=float)
    N = h.size
    L = _fftconv(h, h)
    M = L.max()
    s = h.sum()
    if M <= 0 or s <= 0:
        return 0.0, np.zeros(N)
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2sq / (l1 * M)

    dL2 = (Lp[:-2] + 4.0 * Lp[1:-1] + Lp[2:]) / 3.0
    dL2_dh = 2.0 * _fftconv(dL2, h[::-1])[N - 1:2 * N - 1]

    t = max(tau * M, 1e-300)
    z = (Lp - Lp.max()) / t
    e = np.exp(z)
    Z = e.sum()
    w = e / Z
    wL = w[1:-1]
    dM = 2.0 * _fftconv(wL, h[::-1])[N - 1:2 * N - 1]

    denom = l1 * M
    grad = dL2_dh / denom - l2sq * (2.0 * s * M + l1 * dM) / (denom * denom)
    return R, grad


def _lbfgs_polish(h, taus, budget_end, maxiter=60):
    from scipy.optimize import minimize
    h = np.maximum(np.asarray(h, dtype=float), 0.0)
    mean_h = h.mean() if h.mean() > 0 else 1.0
    best_h = h.copy()
    best_R = _R_from_heights(h)
    for tau in taus:
        if time.process_time() > budget_end:
            break
        def fun(x):
            R, g = _score_grad_soft(x, tau)
            return -R, -g
        try:
            res = minimize(fun, best_h, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * best_h.size,
                           options={'maxiter': maxiter, 'maxfun': 4 * maxiter})
            cand = np.maximum(res.x, 0.0)
        except Exception:
            continue
        if cand.sum() <= 0:
            continue
        cand = cand * (mean_h / cand.mean())
        Rc = _R_from_heights(cand)
        if Rc > best_R:
            best_R = Rc
            best_h = cand.copy()
    return best_h, best_R


def _upsample(h, N1):
    N0 = h.size
    if N0 == N1:
        return np.maximum(np.asarray(h, dtype=float).copy(), 0.0)
    x_old = (np.arange(N0) + 0.5) / N0
    x_new = (np.arange(N1) + 0.5) / N1
    out = np.interp(x_new, x_old, h)
    return np.maximum(out, 0.0)


def _perturb(h, rng, scale):
    N = h.size
    nk = int(rng.integers(3, 12))
    xs = np.linspace(0, 1, nk)
    ys = rng.standard_normal(nk)
    xi = np.linspace(0, 1, N)
    noise = np.interp(xi, xs, ys)
    mult = np.exp(scale * noise)
    out = h * mult
    return np.maximum(out, 0.0)


def _perturb_struct(h, rng, scale_N=1600):
    """Smooth low-freq multiplicative perturbation (heavy-tailed scale),
    then with prob 0.45 one structural window move. Window lengths scaled
    by N/scale_N."""
    N = h.size
    ratio = max(1.0, N / float(scale_N))
    scale = 0.02 + 0.50 * (rng.random() ** 2)
    out = _perturb(h, rng, scale).copy()
    if rng.random() < 0.45:
        Lmin = max(2, int(round((N // 20) / ratio * ratio)))  # keep base
        Lmin = max(2, N // 20)
        Lmax = max(3, N // 4)
        L = int(rng.integers(Lmin, Lmax + 1))
        a = int(rng.integers(0, max(1, N - L)))
        move = int(rng.integers(0, 4))
        if move == 0:
            b = int(rng.integers(0, max(1, N - L)))
            out[a:a + L] = h[b:b + L]
        elif move == 1:
            out[a:a + L] = h[a:a + L][::-1]
        elif move == 2:
            f = math.exp(rng.normal(0.0, 0.5))
            out[a:a + L] = h[a:a + L] * f
        else:
            out[a:a + L] = 0.0
    out = np.maximum(out, 0.0)
    m = out.mean()
    if m > 0:
        out = out * (h.mean() / m)
    return out


def construct(budget_seconds, start):
    t0 = time.process_time()
    budget_end = t0 + 0.92 * budget_seconds
    rng = np.random.default_rng(97531)

    best_h = None
    best_R = -1.0
    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.size > 0 and s.sum() > 0:
            best_h = np.maximum(s, 0.0).copy()
            best_R = _R_from_heights(best_h)
            keep_best(best_h)

    if best_h is None:
        best_h = np.ones(1600)
        best_R = _R_from_heights(best_h)
        keep_best(best_h)

    N = best_h.size
    print("start: N=%d R=%.10f" % (N, best_R))

    # ---- Stage: exact staircase upsample ----
    print("stage upsample: start")
    R_before = best_R
    h32 = np.repeat(best_h, 2)
    R32 = _R_from_heights(h32)
    print("  staircase N=%d R=%.10f (start N=%d R=%.10f)" % (h32.size, R32, N, best_R))
    if R32 > best_R:
        best_R = R32
        best_h = h32.copy()
        keep_best(best_h)
    print("stage upsample: %.6f -> %.6f, %.2f s" % (R_before, best_R, time.process_time() - t0))

    Nw = best_h.size

    # ---- Stage: polish at N=3200 with full tau ladder ----
    print("stage polish: start")
    R_before = best_R
    taus_full = (1e-3, 1e-4, 1e-5, 1e-6, 1e-7)
    h_work, R_work = _lbfgs_polish(best_h, taus_full, budget_end, maxiter=80)
    if R_work > best_R:
        best_R = R_work
        best_h = h_work.copy()
        keep_best(best_h)
    print("stage polish: %.6f -> %.6f, %.2f s" % (R_before, best_R, time.process_time() - t0))

    # ---- Stage: basin-hopping at N=3200 ----
    print("stage basinhop: start")
    R_before = best_R
    h_cur = best_h.copy()
    R_cur = best_R
    pool = [(best_h.copy(), best_R)]
    n_try = 0
    n_acc = 0
    taus_short = (1e-4, 1e-6)
    while time.process_time() < budget_end:
        if len(pool) > 1 and rng.random() < 0.4:
            idx = int(rng.integers(0, len(pool)))
            base_h, base_R = pool[idx]
        else:
            base_h, base_R = h_cur, R_cur
        cand = _perturb_struct(base_h, rng, scale_N=1600)
        if cand.size != Nw:
            cand = _upsample(cand, Nw)
        Rc = _R_from_heights(cand)
        if Rc > base_R * 0.97:
            if Rc > best_R:
                cand2, Rc2 = _lbfgs_polish(cand, taus_full, budget_end, maxiter=80)
            else:
                cand2, Rc2 = _lbfgs_polish(cand, taus_short, budget_end, maxiter=30)
            n_try += 1
            if Rc2 > best_R:
                best_R = Rc2
                best_h = cand2.copy()
                keep_best(best_h)
                print("  basinhop improve R=%.7f (try %d, t=%.1fs)" % (best_R, n_try, time.process_time() - t0))
            if Rc2 > base_R - 2e-4:
                pool.append((cand2.copy(), Rc2))
                if len(pool) > 6:
                    pool.sort(key=lambda x: -x[1])
                    pool = pool[:6]
            if Rc2 > R_cur:
                h_cur = cand2.copy()
                R_cur = Rc2
                n_acc += 1
            else:
                if rng.random() < 0.4:
                    h_cur = best_h.copy()
                    R_cur = best_R
        if time.process_time() > budget_end:
            break
    print("stage basinhop: %.6f -> %.6f, %.2f s (%d tries, %d accepted)" %
          (R_before, best_R, time.process_time() - t0, n_try, n_acc))

    # ---- Stage: final polish ----
    print("stage final: start")
    R_before = best_R
    if time.process_time() < budget_end:
        h_fin, R_fin = _lbfgs_polish(best_h, taus_full, budget_end, maxiter=120)
        if R_fin > best_R:
            best_R = R_fin
            best_h = h_fin.copy()
            keep_best(best_h)
    print("stage final: %.6f -> %.6f, %.2f s" % (R_before, best_R, time.process_time() - t0))

    if best_h is None:
        best_h = np.ones(1600)
    s01, s1, s5 = _knot_shares(best_h)
    print("final: N=%d R=%.7f shares %.2f/%.2f/%.2f" % (best_h.size, best_R, s01, s1, s5))
    keep_best(best_h)
    return best_h
