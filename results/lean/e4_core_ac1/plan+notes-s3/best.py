import numpy as np
import time
from scipy.optimize import linprog, differential_evolution
from scipy.sparse import csr_matrix


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _lp_step(h, trust, active):
    N = len(h)
    idx = np.nonzero(active)[0]
    if idx.size == 0:
        return None
    conv = np.convolve(h, h)
    na = idx.size
    nv = N + 1
    c = np.zeros(nv)
    c[N] = 1.0
    rows = []
    cols = []
    vals = []
    b = np.zeros(na)
    for r, k in enumerate(idx):
        lo = max(0, k - N + 1)
        hi = min(N - 1, k)
        for i in range(lo, hi + 1):
            j = k - i
            rows.append(r)
            cols.append(j)
            vals.append(2.0 * h[i])
        rows.append(r)
        cols.append(N)
        vals.append(-1.0)
        b[r] = -conv[k]
    A = csr_matrix((vals, (rows, cols)), shape=(na, nv))
    A_eq = csr_matrix((np.ones(N), (np.zeros(N, dtype=int), np.arange(N))),
                      shape=(1, nv))
    b_eq = np.array([0.0])
    mh = max(h.max(), 1e-12)
    lim = trust * mh
    bounds = [(max(-h[i], -lim), lim) for i in range(N)]
    bounds.append((None, None))
    try:
        res = linprog(c, A_ub=A, b_ub=b, A_eq=A_eq, b_eq=b_eq,
                      bounds=bounds, method='highs')
    except Exception:
        return None
    if not res.success:
        return None
    return res.x[:N]


def _lp_refine(h, deadline, trust0=0.005, band0=0.02, cap=None):
    h = np.maximum(np.asarray(h, dtype=float), 0.0)
    s = h.sum()
    if s <= 0:
        return h
    h = h / s
    best = h.copy()
    bestC = _C(h)
    trust = trust0
    alphas = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125]
    stall = 0
    while time.process_time() < deadline:
        conv = np.convolve(h, h)
        mx = conv.max()
        band = min(0.5, band0 + 0.0015 * stall)
        active = conv >= mx * (1.0 - band)
        if cap is not None:
            idx = np.nonzero(active)[0]
            if idx.size > cap:
                sub = idx[np.argsort(conv[idx])[-cap:]]
                active = np.zeros_like(active)
                active[sub] = True
        delta = _lp_step(h, trust, active)
        if delta is None:
            trust *= 0.5
            if trust < 1e-9:
                break
            continue
        best_alpha_h = None
        bC = bestC
        for alpha in alphas:
            h_try = np.maximum(h + alpha * delta, 0.0)
            st = h_try.sum()
            if st <= 0:
                continue
            h_try /= st
            ct = _C(h_try)
            if ct < bC - 1e-15:
                bC = ct
                best_alpha_h = h_try
        if best_alpha_h is not None:
            bestC = bC
            best = best_alpha_h.copy()
            h = best_alpha_h
            trust = min(trust * 1.6, 0.5)
            stall = 0
        else:
            trust *= 0.5
            stall += 1
            if trust < 1e-9:
                break
    return best


def _resample_lin(h, N_new):
    N0 = len(h)
    if N0 == N_new:
        return h.copy()
    c = np.concatenate([[0.0], np.cumsum(h)])
    total = c[-1]
    if total <= 0:
        return np.ones(N_new) / N_new
    c /= total
    edges = np.linspace(0.0, 1.0, N_new + 1)
    xs_new = np.interp(edges, c, np.linspace(0.0, 1.0, N0 + 1))
    newh = np.maximum(np.diff(xs_new), 0.0)
    st = newh.sum()
    if st > 0:
        newh /= st
    else:
        newh = np.ones(N_new) / N_new
    return newh


def _smooth_resample(h, N_new):
    g = _resample_lin(h, N_new)
    ker = np.array([1.0, 2.0, 1.0])
    ker /= ker.sum()
    g = np.convolve(np.pad(g, 1, mode='edge'), ker, mode='valid')
    g = np.maximum(g, 0.0)
    s = g.sum()
    if s > 0:
        g /= s
    return g


def _support_stretch(h):
    h = np.maximum(np.asarray(h, dtype=float).ravel(), 0.0)
    if h.sum() <= 0:
        return h
    nz = np.nonzero(h > 1e-12)[0]
    if nz.size == 0:
        return h
    if nz[0] == 0 and nz[-1] == len(h) - 1:
        return h
    hc = h[nz[0]:nz[-1] + 1]
    return _resample_lin(hc, len(h))


def _blocks_to_h(z, N, M):
    """z: length 2M, first M log-heights, next M log-lengths."""
    zh = z[:M]
    zL = z[M:]
    zL = zL - zL.max()
    w = np.exp(zL)
    w /= w.sum()
    counts = np.maximum(1, np.round(w * N).astype(int))
    diff = N - counts.sum()
    if diff != 0:
        order = np.argsort(-w)
        i = 0
        while diff != 0:
            j = order[i % M]
            if diff > 0:
                counts[j] += 1
                diff -= 1
            else:
                if counts[j] > 1:
                    counts[j] -= 1
                    diff += 1
            i += 1
            if i > 100 * M:
                break
    zh = zh - zh.max()
    hh = np.exp(zh)
    h = np.repeat(hh, counts)
    if h.size != N:
        h = _resample_lin(h, N)
    s = h.sum()
    if s > 0:
        h = h / s
    return h


def _de_phase(best_h, deadline, N=320, M=6, popsize=15, maxiter=200, seed=42):
    if time.process_time() >= deadline:
        return best_h

    def obj(z):
        h = _blocks_to_h(z, N, M)
        return _C(h)

    bounds = [(-3.0, 3.0)] * (2 * M)
    try:
        res = differential_evolution(
            obj, bounds, popsize=popsize, maxiter=maxiter, seed=seed,
            tol=1e-8, polish=False, init='latinhypercube',
            updating='immediate', workers=1)
        z = res.x
        h = _blocks_to_h(z, N, M)
        return h
    except Exception:
        return best_h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85

    best_h = None
    best_C = np.inf

    def consider(h):
        nonlocal best_h, best_C
        if h is None:
            return
        h = np.maximum(np.asarray(h, dtype=float), 0.0).ravel()
        if h.size == 0 or h.size > 30000 or h.sum() <= 0:
            return
        h = h / h.sum()
        c = _C(h)
        if c < best_C - 1e-15:
            best_C = c
            best_h = h.copy()

    base = None
    if start is not None:
        s0 = np.asarray(start, dtype=float).ravel()
        if s0.size > 0 and np.all(np.isfinite(s0)) and s0.sum() > 0:
            consider(s0)
            b = np.maximum(s0, 0.0)
            if b.sum() > 0:
                base = b / b.sum()

    if base is None:
        N = 320
        x = np.linspace(-0.5, 0.5, N)
        base = np.exp(-(x / 0.22) ** 2)
        base /= base.sum()

    if start is not None:
        hs = _support_stretch(base)
        consider(hs)

    # --- DE phase 1: M=10, popsize=20, maxiter=400, seed=123, 55% of budget ---
    now = time.process_time()
    if now < deadline:
        de_end = min(deadline, now + 0.55 * (deadline - now))
        h_de = _de_phase(best_h if best_h is not None else base, de_end,
                         N=320, M=10, popsize=20, maxiter=400, seed=123)
        consider(h_de)
        if best_h is not None:
            now2 = time.process_time()
            sub_end = min(deadline, now2 + 3.0)
            consider(_lp_refine(best_h, sub_end, trust0=0.001, band0=0.01))

    # --- DE phase 2: M=14, popsize=15, maxiter=200, seed=456, then LP refine ---
    now = time.process_time()
    if now < deadline:
        de_end2 = min(deadline, now + 0.60 * (deadline - now))
        h_de2 = _de_phase(best_h if best_h is not None else base, de_end2,
                          N=320, M=14, popsize=15, maxiter=200, seed=456)
        consider(h_de2)
        if best_h is not None:
            now3 = time.process_time()
            sub_end2 = min(deadline, now3 + 3.0)
            consider(_lp_refine(best_h, sub_end2, trust0=0.001, band0=0.01))

    # Quick LP refine at start resolution.
    now = time.process_time()
    if now < deadline and best_h is not None:
        seg = min(deadline, now + 0.10 * (deadline - now))
        consider(_lp_refine(best_h, seg, trust0=0.003, band0=0.02))

    # Multi-resolution exploration.
    resolutions = [640, 1280, 480, 960, 1600, 2400]
    for i, N in enumerate(resolutions):
        if time.process_time() >= deadline or best_h is None:
            break
        remaining = deadline - time.process_time()
        seg = min(deadline, time.process_time() + remaining * 0.30)
        for maker in (_resample_lin, _smooth_resample):
            if time.process_time() >= seg:
                break
            h_up = maker(best_h, N)
            sub_end = min(seg, time.process_time() +
                          (seg - time.process_time()) * 0.6)
            cand = _lp_refine(h_up, sub_end, trust0=0.002, band0=0.01)
            consider(cand)

    # Final polish at moderate resolution with wide band.
    if time.process_time() < deadline and best_h is not None:
        N_final = min(640, len(best_h))
        h_f = _resample_lin(best_h, N_final)
        consider(_lp_refine(h_f, deadline, trust0=0.0008, band0=0.004))

    if best_h is None:
        best_h = np.ones(320)
        best_h /= best_h.sum()
    return best_h
