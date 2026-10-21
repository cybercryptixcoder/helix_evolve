import numpy as np
import time
from scipy.optimize import minimize


def _R(h):
    h = np.asarray(h, dtype=float)
    if h.ndim != 1 or h.size == 0:
        return -1.0
    if not np.all(np.isfinite(h)) or np.any(h < 0):
        return -1.0
    s = h.sum()
    if s <= 0:
        return -1.0
    L = np.convolve(h, h)
    L = np.concatenate(([0.0], L, [0.0]))
    num = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    den = s * s * np.max(L)
    if den <= 0:
        return -1.0
    return num / den


def _parts(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    L = np.convolve(h, h)
    L = np.concatenate(([0.0], L, [0.0]))
    num = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    return s, L, num


def _soft_and_grad(h, T):
    s, L, num = _parts(h)
    Lm = L.max()
    e = np.exp((L - Lm) / T)
    Z = np.sum(e)
    sm = T * (np.log(Z) + Lm / T)
    w = e / Z
    den = s * s * sm
    R = num / den

    A = L
    dnum = np.zeros_like(A)
    dnum[:-1] += (2 * A[:-1] + A[1:]) / 3.0
    dnum[1:] += (A[:-1] + 2 * A[1:]) / 3.0
    gL = dnum[1:-1]
    gsm = w[1:-1]

    dnum_dh = 2.0 * np.correlate(gL, h, mode='valid')
    dsm_dh = 2.0 * np.correlate(gsm, h, mode='valid')

    dden_dh = 2.0 * s * sm * np.ones_like(h) + s * s * dsm_dh
    grad = dnum_dh / den - (num / (den * den)) * dden_dh
    return R, grad


def _hard_and_grad(h):
    s, L, num = _parts(h)
    Lm = L.max()
    den = s * s * Lm
    R = num / den

    A = L
    dnum = np.zeros_like(A)
    dnum[:-1] += (2 * A[:-1] + A[1:]) / 3.0
    dnum[1:] += (A[:-1] + 2 * A[1:]) / 3.0
    gL = dnum[1:-1]
    dnum_dh = 2.0 * np.correlate(gL, h, mode='valid')

    gmax = np.zeros_like(L)
    idx = np.where(L >= Lm - 1e-12 * max(1.0, Lm))[0]
    gmax[idx] = 1.0 / idx.size
    dmax_dh = 2.0 * np.correlate(gmax[1:-1], h, mode='valid')

    dden_dh = 2.0 * s * Lm * np.ones_like(h) + s * s * dmax_dh
    grad = dnum_dh / den - (num / (den * den)) * dden_dh
    return R, grad


def _lbfgs(h, T, maxiter=200):
    h = np.maximum(h, 0.0)
    n = h.size
    bounds = [(0.0, None)] * n

    def fun(x):
        x = np.maximum(x, 0.0)
        R, g = _soft_and_grad(x, T)
        return -R, -g

    try:
        res = minimize(fun, h, method='L-BFGS-B', jac=True, bounds=bounds,
                       options={'maxiter': maxiter, 'maxfun': 3 * maxiter,
                                'ftol': 1e-16, 'gtol': 1e-13})
        return np.maximum(res.x, 0.0)
    except Exception:
        return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline_all = t0 + budget_seconds * 0.95

    def normalize(h):
        h = np.maximum(np.asarray(h, dtype=float), 0.0)
        m = h.max()
        if m > 0:
            h = h / m
        return h

    def resample_mass(h, N):
        n = h.size
        if n == N:
            return h.copy()
        edges_src = np.linspace(0, 1, n + 1)
        edges_dst = np.linspace(0, 1, N + 1)
        cum = np.concatenate(([0.0], np.cumsum(h)))
        tot = cum[-1]
        if tot <= 0:
            return np.ones(N) / N
        cum_at_dst = np.interp(edges_dst, edges_src, cum)
        out = np.diff(cum_at_dst) * N
        return np.maximum(out, 0.0)

    def refine(h, deadline, T_factors=(1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9)):
        h = normalize(h.copy())
        s = _R(h)
        for f in T_factors:
            if time.process_time() >= deadline:
                break
            Lm = np.max(np.convolve(h, h))
            T = Lm * f
            h2 = _lbfgs(h, T)
            h2 = normalize(h2)
            s2 = _R(h2)
            if s2 > s:
                h, s = h2, s2
        return h, s

    best_h = None
    best_s = -1.0

    if start is not None:
        try:
            hs = normalize(np.asarray(start, dtype=float))
            if hs.size > 0 and _R(hs) > 0:
                best_h = hs.copy()
                best_s = _R(hs)
                keep_best(best_h)
        except Exception:
            pass

    stage_start = time.process_time()
    before_param = best_s if best_s > 0 else 0.0
    if best_h is None:
        Np = 400
        x = np.linspace(-1, 1, Np)
        best_h = normalize(np.exp(-(x ** 2) / 0.3))
        best_s = _R(best_h)
        keep_best(best_h)
    print("stage param: %.6f -> %.6f, %.1f s (N=%d)" % (
        before_param, best_s, time.process_time() - stage_start, best_h.size))

    # ---- Main refine at multiple resolutions ----
    # The key insight: R is a smooth-ish function of the shape; refine at
    # current N, then upsample, refine again. Keep best throughout.
    stage_start = time.process_time()
    before_main = best_s
    Ns = [800, 1200, 1600, 2000, 2400]
    hcur = best_h.copy()
    scur = best_s
    for k, N in enumerate(Ns):
        if time.process_time() >= deadline_all * 0.6:
            break
        hN = normalize(resample_mass(hcur, N))
        sN = _R(hN)
        if sN > scur:
            hcur, scur = hN, sN
        # refine at this N
        budget_share = (deadline_all * 0.6 - time.process_time()) / max(1, (len(Ns) - k))
        sub = min(deadline_all * 0.6, time.process_time() + max(1.5, budget_share))
        hcur, scur = refine(hcur, sub)
        if scur > best_s:
            best_s, best_h = scur, hcur.copy()
            keep_best(best_h)
    print("stage main: %.6f -> %.6f, %.1f s (N=%d)" % (
        before_main, best_s, time.process_time() - stage_start, best_h.size))

    # ---- Perturbation restarts ----
    stage_start = time.process_time()
    before_pert = best_s
    rng = np.random.default_rng(777)
    cycle = 0
    while time.process_time() < deadline_all * 0.88:
        cycle += 1
        hp = best_h.copy()
        nz = hp.size
        amp = 0.02 * (0.5 ** (cycle % 5))
        noise = rng.standard_normal(nz) * amp
        k = max(1, nz // 150)
        kernel = np.ones(k) / k
        noise = np.convolve(noise, kernel, mode='same')
        hp = normalize(np.maximum(hp * (1.0 + noise), 0.0))
        sub = min(deadline_all * 0.88,
                  time.process_time() + max(0.8, (deadline_all * 0.88 - time.process_time()) / 2))
        hpp, spp = refine(hp, sub)
        if spp > best_s:
            best_s, best_h = spp, hpp.copy()
            keep_best(best_h)
    print("stage perturb: %.6f -> %.6f, %.1f s (cycles=%d)" % (
        before_pert, best_s, time.process_time() - stage_start, cycle))

    # ---- Hard-max Adam polish ----
    stage_start = time.process_time()
    before_hard = best_s
    h = normalize(best_h.copy())
    s = _R(h)
    n = h.size
    m = np.zeros(n)
    v = np.zeros(n)
    beta1, beta2 = 0.9, 0.999
    lr = 0.005
    it = 0
    while time.process_time() < deadline_all:
        it += 1
        _, g = _hard_and_grad(h)
        gn = np.linalg.norm(g)
        if gn < 1e-16:
            break
        g = g / gn
        m = beta1 * m + (1 - beta1) * g
        v = beta2 * v + (1 - beta2) * g * g
        mhat = m / (1 - beta1 ** it)
        vhat = v / (1 - beta2 ** it)
        direction = mhat / (np.sqrt(vhat) + 1e-8)
        step = lr
        improved = False
        for _ in range(14):
            cand = normalize(h + step * direction)
            cs = _R(cand)
            if cs > s + 1e-16:
                h, s = cand, cs
                lr = min(step * 1.3, 0.2)
                improved = True
                break
            step *= 0.5
        if not improved:
            lr *= 0.7
            if lr < 1e-10:
                break
    if s > best_s:
        best_s, best_h = s, h.copy()
        keep_best(best_h)
    print("stage hard: %.6f -> %.6f, %.1f s (it=%d)" % (
        before_hard, best_s, time.process_time() - stage_start, it))

    return best_h
