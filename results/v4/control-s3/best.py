import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _R_from_h(h):
    h = np.asarray(h, dtype=float)
    if not np.all(np.isfinite(h)) or np.any(h < 0):
        return -1.0
    s = h.sum()
    if s <= 0:
        return -1.0
    conv = np.convolve(h, h)
    L = np.concatenate(([0.0], conv, [0.0]))
    l2sq = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    l1 = s * s
    linf = L.max()
    if linf <= 0:
        return -1.0
    return l2sq / (l1 * linf)


def _R_and_grad(logh, p=20.0):
    h = np.exp(logh)
    s = h.sum()
    conv = fftconvolve(h, h)
    L = np.concatenate(([0.0], conv, [0.0]))
    a = L[:-1]
    b = L[1:]
    num = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s

    m = L.max()
    if m <= 0:
        return -1.0, np.zeros_like(logh)
    z = p * (L - m)
    w = np.exp(z)
    S = w.sum()
    if S <= 0 or not np.isfinite(S):
        return -1.0, np.zeros_like(logh)
    linf = m + np.log(S) / p
    if linf <= 0:
        return -1.0, np.zeros_like(logh)
    R = num / (l1 * linf)

    dnum = np.zeros_like(L)
    dnum[:-1] += (2 * a + b) / 3.0
    dnum[1:] += (a + 2 * b) / 3.0
    dR_dL = dnum / (l1 * linf)
    dlinf_dL = w / S
    dR_dL -= num / (l1 * linf * linf) * dlinf_dL
    dR_dconv = dR_dL[1:-1]
    grad_h = 2.0 * fftconvolve(dR_dconv, h[::-1], mode='valid')
    grad_h += -2.0 * R / s
    grad_logh = grad_h * h
    return R, grad_logh


def _lbfgs(logh_init, maxiter=400, ftol=1e-15, p=20.0):
    def fun(z):
        R, g = _R_and_grad(z, p=p)
        return -R, -g
    try:
        res = minimize(fun, logh_init, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'ftol': ftol, 'gtol': 1e-11})
        return res.x, -res.fun
    except Exception:
        return logh_init, _R_from_h(np.exp(logh_init))


def _interp(h, N):
    N0 = len(h)
    xi = np.linspace(0, 1, N0)
    xj = np.linspace(0, 1, N)
    return np.maximum(np.interp(xj, xi, h), 1e-12)


def _lbfgs_masked(h_full, mask, maxiter=300, ftol=1e-16, p=20.0):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return h_full.copy(), _R_from_h(h_full)

    def expand(logv):
        h = np.zeros_like(h_full)
        h[idx] = np.exp(logv)
        return h

    def fun(logv):
        h = expand(logv)
        R, g = _R_and_grad(np.log(np.maximum(h, 1e-300)), p=p)
        return -R, -g[idx]

    x0 = np.log(np.maximum(h_full[idx], 1e-12))
    try:
        res = minimize(fun, x0, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'ftol': ftol, 'gtol': 1e-11})
        h = expand(res.x)
        return h, _R_from_h(h)
    except Exception:
        return h_full.copy(), _R_from_h(h_full)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.7

    if start is not None:
        h0 = np.asarray(start, dtype=float).copy()
    else:
        h0 = np.ones(64)
    h0 = np.maximum(h0, 0.0)
    if h0.sum() <= 0:
        h0 = np.ones(64)

    best_h = h0.copy()
    best_R = _R_from_h(best_h)
    N0 = len(h0)

    # Phase 1: squeeze at same resolution with a high-p ladder (fast, small gains).
    for p in [16384.0, 65536.0, 262144.0]:
        if time.process_time() > deadline - 12.0:
            break
        logh, _ = _lbfgs(np.log(np.maximum(best_h, 1e-12)),
                         maxiter=250, ftol=1e-16, p=p)
        hc = np.exp(logh)
        R = _R_from_h(hc)
        if R > best_R:
            best_R = R
            best_h = hc.copy()

    # Phase 2: upsampling to a finer grid (the dominant lever for resolution).
    # Target a larger N to capture sharper features of f*f's peak.
    target_N = min(200000, max(N0 * 4, 16384))
    if target_N > N0 and time.process_time() < deadline - 10.0:
        hseed = _interp(best_h, target_N)
        for p in [256.0, 2048.0, 16384.0, 131072.0]:
            if time.process_time() > deadline - 6.0:
                break
            logh, _ = _lbfgs(np.log(hseed), maxiter=250, ftol=1e-16, p=p)
            hc = np.exp(logh)
            R = _R_from_h(hc)
            if R > best_R:
                best_R = R
                best_h = hc.copy()
            hseed = np.maximum(best_h, 1e-12)

    # Phase 3: high-p squeeze at final resolution until budget nearly spent.
    cur_p = 131072.0
    while time.process_time() < deadline - 0.9:
        hseed = np.maximum(best_h, 1e-12)
        logh, _ = _lbfgs(np.log(hseed), maxiter=200, ftol=1e-16, p=cur_p)
        hc = np.exp(logh)
        R = _R_from_h(hc)
        if R > best_R + 1e-14:
            best_R = R
            best_h = hc.copy()
        else:
            cur_p *= 2.0
            if cur_p > 1e8:
                break

    # Phase 4: brief sparsity annealing to escape via masked optimization.
    zs = [0.10, 0.20, 0.30, 0.40]
    while time.process_time() < deadline - 0.6:
        improved_any = False
        for z in zs:
            if time.process_time() > deadline - 0.6:
                break
            incumbent = best_h.copy()
            total = incumbent.sum()
            if total <= 0:
                continue
            thr = np.quantile(incumbent, z)
            mask = incumbent > thr
            if mask.sum() == 0 or mask.sum() == len(incumbent):
                continue
            h_z = np.zeros_like(incumbent)
            h_z[mask] = incumbent[mask]
            s_z = h_z.sum()
            if s_z <= 0:
                continue
            h_z *= total / s_z
            h_cur = h_z
            R_cur = _R_from_h(h_cur)
            for p in [1e4, 1e6]:
                if time.process_time() > deadline - 0.5:
                    break
                h_new, R_new = _lbfgs_masked(h_cur, mask, maxiter=200,
                                             ftol=1e-16, p=p)
                if R_new > R_cur:
                    h_cur = h_new
                    R_cur = R_new
            if R_cur > best_R + 1e-14:
                best_h = h_cur
                best_R = R_cur
                improved_any = True
                print("accept z=%.2f R=%.7f" % (z, best_R))
                if time.process_time() < deadline - 0.5:
                    logh, _ = _lbfgs(np.log(np.maximum(best_h, 1e-12)),
                                     maxiter=150, ftol=1e-16, p=1e6)
                    hc = np.exp(logh)
                    R = _R_from_h(hc)
                    if R > best_R:
                        best_R = R
                        best_h = hc.copy()
                        print("regrow R=%.7f" % best_R)
        if not improved_any:
            break

    if _R_from_h(best_h) < _R_from_h(h0):
        return h0
    return best_h
