import numpy as np
import time
from scipy.optimize import minimize


def _pairs(n):
    return np.triu_indices(n, 1)


def _feasible(p, tol=1e-9):
    n = p.shape[0]
    x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
    if np.any(r <= 0): return False
    if np.any(x - r < -tol) or np.any(x + r > 1 + tol): return False
    if np.any(y - r < -tol) or np.any(y + r > 1 + tol): return False
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    rr = r[:, None] + r[None, :]
    iu = _pairs(n)
    return np.all((d - rr)[iu] >= -tol)


def _repair(p, iters=400):
    n = p.shape[0]
    p = p.copy()
    p[:, 2] = np.maximum(p[:, 2], 1e-6)
    iu = _pairs(n)
    ii = iu[0]; jj = iu[1]
    for _ in range(iters):
        p[:, 0] = np.clip(p[:, 0], p[:, 2], 1 - p[:, 2])
        p[:, 1] = np.clip(p[:, 1], p[:, 2], 1 - p[:, 2])
        dx = p[:, 0][:, None] - p[:, 0][None, :]
        dy = p[:, 1][:, None] - p[:, 1][None, :]
        d = np.sqrt(dx * dx + dy * dy + 1e-30)
        rr = p[:, 2][:, None] + p[:, 2][None, :]
        over = (rr - d)[iu]
        if over.max() <= 1e-12:
            break
        mask = over > 1e-12
        big = p[ii, 2] >= p[jj, 2]
        shrink_i = mask & big
        shrink_j = mask & ~big
        np.subtract.at(p, (ii[shrink_i], 2), over[shrink_i] * 0.5 + 1e-12)
        np.subtract.at(p, (jj[shrink_j], 2), over[shrink_j] * 0.5 + 1e-12)
        p[:, 2] = np.maximum(p[:, 2], 1e-6)
    p[:, 0] = np.clip(p[:, 0], p[:, 2], 1 - p[:, 2])
    p[:, 1] = np.clip(p[:, 1], p[:, 2], 1 - p[:, 2])
    return p


def _cons(v, n):
    p = v.reshape(n, 3)
    x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy + 1e-30)
    rr = r[:, None] + r[None, :]
    iu = _pairs(n)
    return (d - rr)[iu]


def _cons_box(v, n):
    p = v.reshape(n, 3)
    x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
    return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])


def _obj(v):
    return -np.sum(v[2::3])


def _obj_grad(v):
    g = np.zeros_like(v)
    g[2::3] = -1.0
    return g


def _cons_grad(v, n):
    p = v.reshape(n, 3)
    x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy + 1e-30)
    iu = _pairs(n)
    ii = iu[0]; jj = iu[1]
    inv_d = 1.0 / d[ii, jj]
    ux = dx[ii, jj] * inv_d
    uy = dy[ii, jj] * inv_d
    m = ii.size
    J = np.zeros((m, 3 * n))
    rows = np.arange(m)
    J[rows, 3 * ii + 0] = ux
    J[rows, 3 * jj + 0] = -ux
    J[rows, 3 * ii + 1] = uy
    J[rows, 3 * jj + 1] = -uy
    J[rows, 3 * ii + 2] = -1.0
    J[rows, 3 * jj + 2] = -1.0
    return J


def _cons_box_grad(v, n):
    m = 4 * n
    J = np.zeros((m, 3 * n))
    rows = np.arange(n)
    J[rows, 3 * rows + 0] = 1.0
    J[rows, 3 * rows + 2] = -1.0
    J[n + rows, 3 * rows + 0] = -1.0
    J[n + rows, 3 * rows + 2] = -1.0
    J[2 * n + rows, 3 * rows + 1] = 1.0
    J[2 * n + rows, 3 * rows + 2] = -1.0
    J[3 * n + rows, 3 * rows + 1] = -1.0
    J[3 * n + rows, 3 * rows + 2] = -1.0
    return J


def _slsqp_refine(v, n, maxiter):
    bounds = [(0.0, 1.0), (0.0, 1.0), (1e-4, 0.5)] * n
    cons = [
        {'type': 'ineq', 'fun': lambda vv: _cons(vv, n),
         'jac': lambda vv: _cons_grad(vv, n)},
        {'type': 'ineq', 'fun': lambda vv: _cons_box(vv, n),
         'jac': lambda vv: _cons_box_grad(vv, n)},
    ]
    res = minimize(_obj, v, jac=_obj_grad, method='SLSQP', bounds=bounds,
                   constraints=cons,
                   options={'maxiter': maxiter, 'ftol': 1e-14})
    return res.x.reshape(n, 3)


def _score(p):
    return p[:, 2].sum()


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    deadline = budget_seconds - 0.6

    if start is not None:
        p0 = np.asarray(start, dtype=float).reshape(n, 3).copy()
        if not _feasible(p0, 1e-6):
            p0 = _repair(p0)
    else:
        p0 = np.zeros((n, 3))
        r0 = 0.085
        pts = []
        dy = r0 * np.sqrt(3)
        y = r0
        row = 0
        while len(pts) < n and y + r0 <= 1.0:
            offset = r0 if row % 2 else 0.0
            x = r0 + offset
            while x + r0 <= 1.0 + 1e-12 and len(pts) < n:
                pts.append([x, y, r0])
                x += 2 * r0
            y += dy
            row += 1
        while len(pts) < n:
            pts.append([0.5, 0.5, 0.02])
        p0 = np.array(pts[:n], dtype=float)
        p0 = _repair(p0)

    best = _repair(p0)
    best = _slsqp_refine(best.reshape(-1), n, 800)
    best = _repair(best)
    if not _feasible(best, 1e-9):
        best = _repair(best)
    best_score = _score(best)

    rng = np.random.RandomState(20240607)
    attempt = 0
    # Simulated-annealing-like acceptance on SLSQP refinements.
    cur = best.copy()
    cur_score = best_score
    T0 = 0.02
    while time.process_time() - t0 < deadline:
        attempt += 1
        mode = rng.rand()
        p = cur.copy()
        if mode < 0.45:
            # small perturbation
            scale = 0.001 + 0.01 * rng.rand()
            k = rng.randint(1, 8)
            idx = rng.choice(n, size=k, replace=False)
            p[idx, 0] += rng.uniform(-scale, scale, k)
            p[idx, 1] += rng.uniform(-scale, scale, k)
            p[:, 2] *= (1 + rng.uniform(-0.01, 0.02, n))
        elif mode < 0.75:
            # global radii bump
            p[:, 2] *= (1 + rng.uniform(0.005, 0.04))
            p[:, 0] += rng.uniform(-0.003, 0.003, n)
            p[:, 1] += rng.uniform(-0.003, 0.003, n)
        else:
            # larger structural shake
            scale = 0.03 + 0.08 * rng.rand()
            idx = rng.choice(n, size=n // 2, replace=False)
            p[idx, 0] += rng.uniform(-scale, scale, idx.size)
            p[idx, 1] += rng.uniform(-scale, scale, idx.size)
            p[:, 2] *= (1 + rng.uniform(-0.04, 0.04, n))
        p[:, 2] = np.clip(p[:, 2], 1e-4, 0.45)
        p = _repair(p)

        try:
            p = _slsqp_refine(p.reshape(-1), n, 250)
            if p[:, 2].min() > 0:
                p = _repair(p)
                s = _score(p)
                if _feasible(p, 1e-9):
                    frac = (time.process_time() - t0) / max(deadline, 1e-9)
                    T = T0 * max(1e-3, 1.0 - frac)
                    if s > cur_score or rng.rand() < np.exp((s - cur_score) / T):
                        cur = p.copy()
                        cur_score = s
                    if s > best_score + 1e-12:
                        best = p.copy()
                        best_score = s
        except Exception:
            pass

    p = best.copy()
    p[:, 2] *= (1 - 1e-9)
    p[:, 0] = np.clip(p[:, 0], p[:, 2], 1 - p[:, 2])
    p[:, 1] = np.clip(p[:, 1], p[:, 2], 1 - p[:, 2])
    return p
