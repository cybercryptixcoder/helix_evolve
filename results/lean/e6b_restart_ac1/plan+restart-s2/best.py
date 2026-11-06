import numpy as np
import time


def _C(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _resize(h, N_new):
    N = len(h)
    if N == N_new:
        return np.asarray(h, dtype=float).copy()
    h = np.asarray(h, dtype=float)
    cum = np.concatenate([[0.0], np.cumsum(h)])
    if cum[-1] <= 0:
        return np.ones(N_new)
    cum = cum / cum[-1]
    new_edges = np.arange(N_new + 1) / N_new
    mass = np.interp(new_edges, np.arange(N + 1) / N, cum)
    out = np.diff(mass)
    out = np.maximum(out, 0.0)
    if out.sum() <= 0:
        return np.ones(N_new)
    return out / out.sum() * N_new


def _slsqp_solve(h, t0, budget, maxiter=500):
    """SLSQP on [h, M]: minimize M s.t. conv_k(h) <= M, sum(h)=1, h>=0."""
    from scipy.optimize import minimize
    h = np.asarray(h, dtype=float).copy()
    s = h.sum()
    if s <= 0:
        return h
    h = h / s
    N = len(h)
    K = 2 * N - 1

    conv0 = np.convolve(h, h)
    M0 = float(np.max(conv0)) * 1.001 + 1e-12
    x0 = np.concatenate([h, [M0]])

    def obj(x):
        return x[-1]

    def obj_grad(x):
        g = np.zeros(N + 1)
        g[-1] = 1.0
        return g

    def cons_fun(x):
        hh = x[:N]
        M = x[-1]
        c = np.convolve(hh, hh)
        return M - c  # >= 0

    def cons_jac(x):
        hh = x[:N]
        J = np.zeros((K, N + 1))
        # d/dh_i of (M - conv_k) = -2 h_{k-i}
        for k in range(K):
            lo = max(0, k - (N - 1))
            hi = min(N - 1, k)
            for i in range(lo, hi + 1):
                j = k - i
                if 0 <= j < N:
                    J[k, i] += -2.0 * hh[j]
            J[k, N] = 1.0
        return J

    def sum_fun(x):
        return x[:N].sum() - 1.0

    def sum_jac(x):
        g = np.zeros(N + 1)
        g[:N] = 1.0
        return g

    bounds = [(0.0, None)] * N + [(0.0, None)]
    constraints = [
        {'type': 'ineq', 'fun': cons_fun, 'jac': cons_jac},
        {'type': 'eq', 'fun': sum_fun, 'jac': sum_jac},
    ]

    def cb(xk):
        if time.process_time() - t0 > budget:
            raise StopIteration

    try:
        res = minimize(obj, x0, jac=obj_grad, method='SLSQP',
                       bounds=bounds, constraints=constraints,
                       options={'ftol': 1e-12, 'maxiter': maxiter, 'disp': False},
                       callback=cb)
        xf = res.x
    except StopIteration:
        return h
    except Exception:
        return h

    hf = np.maximum(xf[:N], 0.0)
    if hf.sum() <= 0:
        return h
    hf = hf / hf.sum()
    return hf


def construct(budget_seconds, start):
    t0 = time.process_time()
    budget = budget_seconds * 0.90

    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.size > 0 and np.all(np.isfinite(s)) and s.sum() > 0:
            base_h = s.copy()
        else:
            base_h = np.ones(300) / 300
    else:
        base_h = np.ones(300) / 300

    best_h = np.asarray(base_h, dtype=float).copy()
    best_C = _C(best_h)

    # Stage 1: SLSQP at N=300
    if time.process_time() - t0 < budget * 0.55:
        h300 = _resize(best_h, 300)
        h300 = _slsqp_solve(h300, t0, budget * 0.55, maxiter=500)
        c = _C(h300)
        if c < best_C:
            best_C = c
            best_h = h300.copy()

    # Stage 2: SLSQP at N=600 if time permits
    if time.process_time() - t0 < budget * 0.85:
        h600 = _resize(best_h, 600)
        h600 = _slsqp_solve(h600, t0, budget * 0.85, maxiter=400)
        c = _C(h600)
        if c < best_C:
            best_C = c
            best_h = h600.copy()

    # Stage 3: second SLSQP pass at N=300 from improved point
    if time.process_time() - t0 < budget:
        h300b = _resize(best_h, 300)
        h300b = _slsqp_solve(h300b, t0, budget, maxiter=400)
        c = _C(h300b)
        if c < best_C:
            best_C = c
            best_h = h300b.copy()

    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.size > 0 and np.all(np.isfinite(s)) and s.sum() > 0:
            if _C(s) < _C(best_h):
                best_h = s.copy()

    best_h = np.asarray(best_h, dtype=float)
    best_h = np.where(np.isfinite(best_h) & (best_h >= 0), best_h, 0.0)
    if best_h.sum() <= 0:
        best_h = np.ones(300)
    print("final C =", _C(best_h), "N =", len(best_h))
    return best_h
