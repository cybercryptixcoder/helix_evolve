import numpy as np
import time
from scipy.optimize import minimize


def _R(h):
    s = h.sum()
    if s <= 0.0:
        return -1.0
    L = np.convolve(h, h)
    q = (L @ L + L[:-1] @ L[1:]) / 3.0
    inf = L.max()
    if inf <= 0:
        return -1.0
    return q / (s * s * inf)


def _R_and_grad(h, temp=0.0, tie_tol=1e-4):
    n = len(h)
    L = np.convolve(h, h)
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(n)
    Lmax = L.max()
    if Lmax <= 0:
        return -1.0, np.zeros(n)
    Lf = np.concatenate(([0.0], L, [0.0]))
    a = Lf[:-1]
    b = Lf[1:]
    q = np.sum(a * a + a * b + b * b) / 3.0
    if temp > 0:
        e = np.exp((L - Lmax) / temp)
        es = e.sum()
        Ms = Lmax + temp * np.log(es)
        w = e / es
    else:
        Ms = Lmax
        thr = Lmax - tie_tol * Lmax
        tied = np.where(L >= thr)[0]
        w = np.zeros(n)
        w[tied] = 1.0 / len(tied)
    r = q / (s * s * Ms)
    left = Lf[:-2]
    right = Lf[2:]
    dq_dL = (left + 2 * L) / 3.0 + (2 * L + right) / 3.0
    dq_dh = 2.0 * np.correlate(dq_dL, h, mode='valid')
    dM_dh = np.zeros(n)
    nz = np.nonzero(w)[0]
    for jmax in nz:
        lo = max(0, jmax - (n - 1))
        hi = min(n - 1, jmax)
        idx = np.arange(lo, hi + 1)
        dM_dh[idx] += w[jmax] * 2.0 * h[jmax - idx]
    denom = s * s * Ms
    dR = dq_dh / denom - q * (2.0 / s + dM_dh / Ms) / denom
    return r, dR


def _lbfgsb_anneal(h0, deadline, temps=(0.02, 0.005, 0.001, 0.0), maxiter=2000):
    h0 = np.maximum(np.asarray(h0, dtype=float), 0.0)
    if h0.sum() <= 0:
        return h0, -1.0
    m = h0.mean()
    x = h0 / m if m > 0 else h0
    best_x = x.copy()
    best_r = _R(x)
    for temp in temps:
        if time.process_time() >= deadline:
            break
        def fg(xx, _t=temp):
            if time.process_time() >= deadline:
                raise RuntimeError("stop")
            r, g = _R_and_grad(xx, temp=_t)
            return -r, -g
        try:
            res = minimize(fg, x, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * len(x),
                           options={'maxiter': maxiter, 'ftol': 1e-17,
                                    'gtol': 1e-14, 'maxcor': 30})
            x = np.maximum(res.x, 0.0)
            r = _R(x)
            if r > best_r:
                best_x, best_r = x.copy(), r
        except Exception:
            pass
    return best_x, best_r


def _resample(h, new_n):
    n = len(h)
    if new_n <= 0 or new_n == n:
        return h.copy()
    x_old = np.linspace(0.0, 1.0, n)
    x_new = np.linspace(0.0, 1.0, new_n)
    hn = np.interp(x_new, x_old, h)
    return np.maximum(hn, 0.0)


def _smooth_sym_opt(h0, deadline, fine_mult=4, temps=(0.02, 0.005, 0.001)):
    n = len(h0)
    fine = fine_mult * n + 1
    xc = np.linspace(-1, 1, n)
    xf = np.linspace(-1, 1, fine)
    hf = np.maximum(np.interp(xf, xc, h0), 1e-6)
    half = (fine + 1) // 2
    hf[half:] = hf[:fine - half][::-1]

    def build_half(v):
        h = np.concatenate((v, v[:fine - half][::-1]))
        return np.maximum(h, 0.0)

    v = hf[:half].copy()
    best_h = build_half(v)
    best_r = _R(best_h)

    for temp in temps:
        if time.process_time() >= deadline:
            break
        def fg(vv, _t=temp):
            if time.process_time() >= deadline:
                raise RuntimeError("stop")
            h = build_half(vv)
            r, g = _R_and_grad(h, temp=_t)
            gv = g[:half].copy()
            gv[:fine - half] += g[half:][::-1]
            return -r, -gv
        try:
            res = minimize(fg, v, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * half,
                           options={'maxiter': 2000, 'ftol': 1e-17,
                                    'gtol': 1e-14, 'maxcor': 40})
            v = np.maximum(res.x, 0.0)
            h = build_half(v)
            r = _R(h)
            if r > best_r:
                best_r = r
                best_h = h
        except Exception:
            pass

    edges = np.linspace(0, fine, n + 1).astype(int)
    hc = np.zeros(n)
    for i in range(n):
        lo = edges[i]; hi = edges[i + 1]
        if hi <= lo:
            hi = lo + 1
        hc[i] = best_h[lo:hi].mean()
    hc = 0.5 * (hc + hc[::-1])
    rc = _R(hc)
    if rc > best_r:
        return hc, rc
    return _resample(best_h, n), best_r


def _pattern_search(h, deadline, rng, iters=4000):
    h = h.copy()
    n = len(h)
    r = _R(h)
    s = h.mean()
    steps = np.array([0.1, 0.03, 0.01, 0.003, 0.001, 0.0003]) * max(s, 1e-9)
    for st in steps:
        improved = True
        while improved and time.process_time() < deadline:
            improved = False
            order = rng.permutation(n)
            for i in order:
                if time.process_time() >= deadline:
                    break
                old = h[i]
                best_local = r
                best_val = old
                for f in (1.0, -1.0):
                    nv = max(0.0, old + f * st)
                    if nv == old:
                        continue
                    h[i] = nv
                    if h.sum() <= 0:
                        continue
                    nr = _R(h)
                    if nr > best_local + 1e-16:
                        best_local = nr
                        best_val = nv
                h[i] = best_val
                if best_local > r:
                    r = best_local
                    improved = True
    return h, r


def _plateau_widen(h, deadline):
    """Duplicated-step refinement: split each step into two equal pieces.
    This adds degrees of freedom that can lift the plateau near max."""
    n = len(h)
    h2 = np.repeat(h, 2) * 0.5
    return h2


def _plateau_collapse(h):
    """Merge adjacent pairs back to original N."""
    n2 = len(h)
    if n2 % 2 != 0:
        return h
    return 0.5 * (h[0::2] + h[1::2])


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 1.0
    rng = np.random.default_rng(20240517)

    if start is not None:
        best = np.maximum(np.asarray(start, dtype=float).ravel().copy(), 0.0)
        if best.size == 0 or best.sum() <= 0:
            best = np.ones(36)
    else:
        best = np.ones(36)
    nz = np.nonzero(best)[0]
    if nz.size > 0:
        best = best[nz[0]:nz[-1] + 1].copy()
    best_r = _R(best)

    def upd(h, r):
        nonlocal best, best_r
        h = np.maximum(np.asarray(h, dtype=float), 0.0)
        if h.sum() <= 0:
            return False
        if r > best_r + 1e-15:
            best = h.copy()
            best_r = r
            return True
        return False

    # 1) Direct refine of start.
    if time.process_time() < deadline:
        h, r = _lbfgsb_anneal(best, deadline,
                              temps=(0.01, 0.003, 0.001, 0.0), maxiter=3000)
        upd(h, r)

    # 2) Plateau-widening: split each step into 2, refine, then collapse.
    #    This attacks the flatness of the maximum of f*f directly.
    if time.process_time() < deadline:
        h2 = _plateau_widen(best, deadline)
        h2, r2 = _lbfgsb_anneal(h2, deadline,
                                temps=(0.005, 0.002, 0.0005, 0.0), maxiter=2000)
        hc = _plateau_collapse(h2)
        upd(hc, _R(hc))
        if r2 > best_r:
            # keep the doubled version if it is genuinely better and fits
            if len(h2) <= 50000:
                upd(h2, r2)

    # 3) Symmetric fine-grid lifting.
    for fm in (2, 3, 4, 6):
        if time.process_time() >= deadline:
            break
        h, r = _smooth_sym_opt(best, deadline, fine_mult=fm,
                               temps=(0.01, 0.003, 0.001, 0.0))
        upd(h, r)

    # 4) Size sweep.
    base_n = len(best)
    for dn in (-3, -2, -1, 1, 2, 3, 5, 8):
        if time.process_time() >= deadline:
            break
        new_n = base_n + dn
        if 3 <= new_n <= 500:
            hn = _resample(best, new_n)
            hn = 0.5 * (hn + hn[::-1])
            h, r = _lbfgsb_anneal(hn, deadline,
                                  temps=(0.005, 0.001, 0.0), maxiter=1500)
            upd(h, r)

    # 5) Random symmetric perturbations.
    n_pert = 0
    while time.process_time() < deadline - 0.5 and n_pert < 200:
        n_pert += 1
        n = len(best)
        half = (n + 1) // 2
        v = best[:half].copy()
        if v.sum() <= 0:
            break
        scale = 0.003 + 0.06 * rng.random()
        pert = np.maximum(v * np.exp(scale * rng.standard_normal(half)), 0.0)
        full = np.concatenate((pert, pert[:n - half][::-1]))
        h, r = _lbfgsb_anneal(full, deadline, temps=(0.005, 0.001, 0.0),
                              maxiter=800)
        upd(h, r)

    # 6) Coordinate descent polish.
    if time.process_time() < deadline - 0.3:
        h, r = _pattern_search(best, deadline, rng)
        upd(h, r)

    # 7) Final plateau-widening pass at max budget.
    if time.process_time() < deadline - 0.5:
        h2 = _plateau_widen(best, deadline)
        h2, r2 = _lbfgsb_anneal(h2, deadline,
                                temps=(0.002, 0.0005, 0.0), maxiter=1500)
        hc = _plateau_collapse(h2)
        upd(hc, _R(hc))
        if r2 > best_r and len(h2) <= 50000:
            upd(h2, r2)

    # 8) Final fine polish.
    if time.process_time() < deadline:
        h, r = _smooth_sym_opt(best, deadline, fine_mult=5,
                               temps=(0.003, 0.001, 0.0))
        upd(h, r)

    if time.process_time() < deadline:
        h, r = _lbfgsb_anneal(best, deadline,
                              temps=(0.002, 0.0005, 0.0), maxiter=2000)
        upd(h, r)
    if time.process_time() < deadline:
        h, r = _pattern_search(best, deadline, rng, iters=2000)
        upd(h, r)

    best = np.maximum(best, 0.0)
    if best.sum() <= 0:
        best = np.ones(36)
    return best
