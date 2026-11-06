import numpy as np
import time
from scipy.optimize import minimize

def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = budget_seconds - 1.2
    n = 26

    pi = np.array([i for i in range(n) for j in range(i+1, n)])
    pj = np.array([j for i in range(n) for j in range(i+1, n)])
    npairs = len(pi)

    def project(a):
        a = a.copy()
        x, y, r = a[:, 0], a[:, 1], a[:, 2]
        r = np.maximum(r, 1e-9)
        r = np.minimum(r, np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y)))
        for _ in range(3000):
            dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
            d = np.hypot(dx, dy)
            s = r[pi] + r[pj]
            viol = s - d
            if np.all(viol <= 0):
                break
            shrink = np.zeros(n)
            mask = viol > 0
            for k in np.where(mask)[0]:
                i = pi[k]; j = pj[k]
                excess = viol[k]
                tot = r[i] + r[j]
                if tot > 0:
                    shrink[i] = max(shrink[i], excess * r[i]/tot)
                    shrink[j] = max(shrink[j], excess * r[j]/tot)
            r = np.maximum(r - shrink, 1e-9)
            r = np.minimum(r, np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y)))
        a[:, 2] = r
        return a

    if start is not None:
        arr = np.asarray(start, dtype=float).copy()
    else:
        arr = np.zeros((n, 3))
        k = 6
        idx = 0
        for j in range(k):
            for i in range(k):
                if idx >= n: break
                x = (i + 0.5 + 0.5*(j % 2)) / k
                y = (j + 0.5) / k
                arr[idx] = (x, y, 0.03)
                idx += 1
            if idx >= n: break
    arr[:, 2] = np.maximum(arr[:, 2], 1e-3)
    arr = project(arr)

    def obj(v):
        return -np.sum(v[2::3])

    def obj_grad(v):
        g = np.zeros_like(v)
        g[2::3] = -1.0
        return g

    def wall_con(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])

    def wall_jac(v):
        J = np.zeros((4*n, 3*n))
        idx = np.arange(n)
        J[idx, 3*idx] = 1.0; J[idx, 3*idx+2] = -1.0
        J[n+idx, 3*idx] = -1.0; J[n+idx, 3*idx+2] = -1.0
        J[2*n+idx, 3*idx+1] = 1.0; J[2*n+idx, 3*idx+2] = -1.0
        J[3*n+idx, 3*idx+1] = -1.0; J[3*n+idx, 3*idx+2] = -1.0
        return J

    def pair_con(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.sqrt(dx*dx + dy*dy) + 1e-12
        return d - r[pi] - r[pj]

    def pair_jac(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.sqrt(dx*dx + dy*dy) + 1e-12
        ux = dx / d; uy = dy / d
        J = np.zeros((npairs, 3*n))
        rows = np.arange(npairs)
        J[rows, 3*pi]   = ux;  J[rows, 3*pi+1] = uy;  J[rows, 3*pi+2] = -1.0
        J[rows, 3*pj]   = -ux; J[rows, 3*pj+1] = -uy; J[rows, 3*pj+2] = -1.0
        return J

    bounds = [(0.0, 1.0), (0.0, 1.0), (1e-9, 0.5)] * n
    cons = [
        {'type': 'ineq', 'fun': wall_con, 'jac': wall_jac},
        {'type': 'ineq', 'fun': pair_con, 'jac': pair_jac},
    ]

    def score_of(v):
        return float(np.sum(v[2::3]))

    def feasible(v, tol=1e-7):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        if not np.all(r > 0): return False
        if np.any(x - r < -tol) or np.any(1 - x - r < -tol): return False
        if np.any(y - r < -tol) or np.any(1 - y - r < -tol): return False
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.hypot(dx, dy)
        if np.any(d < r[pi] + r[pj] - tol): return False
        return True

    best_x = arr.ravel().copy()
    best_val = score_of(best_x)
    rng = np.random.default_rng(192837465)

    def slsqp_polish(v, maxiter=200):
        try:
            res = minimize(obj, v, jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter': maxiter, 'ftol': 1e-14})
            if feasible(res.x, tol=1e-8):
                return res.x
        except Exception:
            pass
        return None

    attempt = 0
    while time.process_time() - t0 < deadline:
        attempt += 1
        frac = (time.process_time() - t0) / max(deadline, 1e-9)
        scale = 0.003 + 0.02 * frac
        if attempt % 7 == 0:
            scale = 0.05
        x_start = best_x + rng.normal(0, scale, size=best_x.shape)
        x_start[0::3] = np.clip(x_start[0::3], 0.0, 1.0)
        x_start[1::3] = np.clip(x_start[1::3], 0.0, 1.0)
        x_start[2::3] = np.maximum(x_start[2::3], 1e-4)
        x_start = project(x_start.reshape(n, 3)).ravel()

        res = slsqp_polish(x_start, maxiter=150)
        if res is not None:
            val = score_of(res)
            if val > best_val + 1e-12:
                best_val = val
                best_x = res.copy()

    # Final: re-polish from best with extra iterations, then ensure strict feasibility
    res = slsqp_polish(best_x.copy(), maxiter=400)
    if res is not None and score_of(res) > best_val:
        best_val = score_of(res)
        best_x = res.copy()

    a = best_x.reshape(n, 3).copy()
    a = project(a)
    x = a[:, 0].copy(); y = a[:, 1].copy(); r = a[:, 2].copy()
    r = np.minimum(r, np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y)))
    for _ in range(200):
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.hypot(dx, dy)
        s = r[pi] + r[pj]
        viol = s - d + 1e-11
        if np.all(viol <= 0):
            break
        mask = viol > 0
        shrink = np.zeros(n)
        for k in np.where(mask)[0]:
            i = pi[k]; j = pj[k]
            excess = viol[k]
            tot = r[i] + r[j]
            if tot > 0:
                shrink[i] = max(shrink[i], excess * r[i]/tot)
                shrink[j] = max(shrink[j], excess * r[j]/tot)
        r = np.maximum(r - shrink, 1e-12)
        r = np.minimum(r, np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y)))
    r = np.maximum(r - 1e-11, 1e-10)
    out = np.column_stack([x, y, r])
    return out
