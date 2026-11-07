import numpy as np
import time
from scipy.optimize import minimize, linprog


def _check(cfg, tol=1e-11):
    pts = cfg[:, :2]; r = cfg[:, 2]
    if np.any(r <= 0): return False
    if np.any(pts[:, 0] - r < -tol) or np.any(pts[:, 0] + r > 1 + tol): return False
    if np.any(pts[:, 1] - r < -tol) or np.any(pts[:, 1] + r > 1 + tol): return False
    dx = pts[:, None, 0] - pts[None, :, 0]; dy = pts[:, None, 1] - pts[None, :, 1]
    d = np.sqrt(dx * dx + dy * dy); s = r[:, None] + r[None, :]; np.fill_diagonal(s, 0)
    return not np.any(d < s - tol)


def _feasible(cfg):
    pts = cfg[:, :2].copy(); r = cfg[:, 2].copy()
    r = np.maximum(r, 1e-6)
    r = np.minimum(r, np.minimum(pts[:, 0], 1 - pts[:, 0]))
    r = np.minimum(r, np.minimum(pts[:, 1], 1 - pts[:, 1]))
    r = np.maximum(r, 1e-6)
    for _ in range(120):
        dx = pts[:, None, 0] - pts[None, :, 0]; dy = pts[:, None, 1] - pts[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy); s = r[:, None] + r[None, :]; np.fill_diagonal(s, 0)
        viol = np.maximum(s - d, 0.0)
        if viol.max() <= 1e-15: break
        shrink = np.max(viol / 2.0, axis=1)
        r = np.maximum(r - shrink - 1e-14, 1e-6)
    return np.column_stack([pts, r])


def _lp_radii(centers):
    n = centers.shape[0]
    pts = centers
    iu, ju = np.triu_indices(n, k=1)
    m = iu.size
    dx = pts[iu, 0] - pts[ju, 0]; dy = pts[iu, 1] - pts[ju, 1]
    dij = np.sqrt(dx * dx + dy * dy)
    wall = np.minimum(np.minimum(pts[:, 0], 1 - pts[:, 0]),
                      np.minimum(pts[:, 1], 1 - pts[:, 1]))
    c = -np.ones(n)
    A_ub = np.zeros((m, n))
    rows = np.arange(m)
    A_ub[rows, iu] = 1.0
    A_ub[rows, ju] = 1.0
    b_ub = dij
    bounds = [(0.0, max(wall[i], 0.0)) for i in range(n)]
    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    except Exception:
        return None
    if not res.success:
        return None
    return np.maximum(res.x, 0.0)


def _slsqp(cfg, n, maxiter=300):
    def obj(x):
        return -np.sum(x[2 * n:])

    def obj_grad(x):
        g = np.zeros_like(x)
        g[2 * n:] = -1.0
        return g

    iu, ju = np.triu_indices(n, k=1)
    m = iu.size

    def con_pairs(x):
        pts = x[:2 * n].reshape(n, 2); r = x[2 * n:]
        dx = pts[iu, 0] - pts[ju, 0]; dy = pts[iu, 1] - pts[ju, 1]
        d = np.sqrt(dx * dx + dy * dy + 1e-300)
        return d - (r[iu] + r[ju])

    def con_pairs_jac(x):
        pts = x[:2 * n].reshape(n, 2)
        dx = pts[iu, 0] - pts[ju, 0]; dy = pts[iu, 1] - pts[ju, 1]
        d = np.sqrt(dx * dx + dy * dy + 1e-300)
        J = np.zeros((m, 3 * n))
        ux = dx / d; uy = dy / d
        rows = np.arange(m)
        J[rows, 2 * iu] = ux
        J[rows, 2 * iu + 1] = uy
        J[rows, 2 * ju] = -ux
        J[rows, 2 * ju + 1] = -uy
        J[rows, 2 * n + iu] = -1.0
        J[rows, 2 * n + ju] = -1.0
        return J

    def con_walls(x):
        pts = x[:2 * n].reshape(n, 2); r = x[2 * n:]
        out = np.empty(4 * n)
        out[0::4] = pts[:, 0] - r
        out[1::4] = 1.0 - pts[:, 0] - r
        out[2::4] = pts[:, 1] - r
        out[3::4] = 1.0 - pts[:, 1] - r
        return out

    def con_walls_jac(x):
        J = np.zeros((4 * n, 3 * n))
        for i in range(n):
            J[4 * i, 2 * i] = 1.0; J[4 * i, 2 * n + i] = -1.0
            J[4 * i + 1, 2 * i] = -1.0; J[4 * i + 1, 2 * n + i] = -1.0
            J[4 * i + 2, 2 * i + 1] = 1.0; J[4 * i + 2, 2 * n + i] = -1.0
            J[4 * i + 3, 2 * i + 1] = -1.0; J[4 * i + 3, 2 * n + i] = -1.0
        return J

    cons = [
        {'type': 'ineq', 'fun': con_pairs, 'jac': con_pairs_jac},
        {'type': 'ineq', 'fun': con_walls, 'jac': con_walls_jac},
    ]
    x0 = np.concatenate([cfg[:, :2].ravel(), cfg[:, 2]])
    bounds = [(0.0, 1.0)] * (2 * n) + [(1e-6, 0.5)] * n
    try:
        res = minimize(obj, x0, jac=obj_grad, method='SLSQP', bounds=bounds,
                       constraints=cons,
                       options={'maxiter': maxiter, 'ftol': 1e-14})
        x = res.x
    except Exception:
        return cfg
    return _feasible(np.column_stack([x[:2 * n].reshape(n, 2), x[2 * n:]]))


def _slp(cfg, n, iters=40, trust=0.02, deadline=None, elapsed=None):
    """Sequential linear programming: linearize constraints, maximize sum(dr)."""
    cfg = _feasible(cfg)
    pts = cfg[:, :2].copy(); r = cfg[:, 2].copy()
    best = cfg.copy(); best_s = r.sum()
    iu, ju = np.triu_indices(n, k=1)
    m = iu.size
    rows = np.arange(m)
    A = np.zeros((m + 4 * n, 3 * n))
    b = np.zeros(m + 4 * n)
    for it in range(iters):
        if deadline is not None and elapsed() > deadline:
            break
        dx = pts[iu, 0] - pts[ju, 0]; dy = pts[iu, 1] - pts[ju, 1]
        d = np.maximum(np.sqrt(dx * dx + dy * dy), 1e-12)
        ux = dx / d; uy = dy / d
        A[:] = 0.0
        A[rows, 2 * iu] = -ux
        A[rows, 2 * iu + 1] = -uy
        A[rows, 2 * ju] = ux
        A[rows, 2 * ju + 1] = uy
        A[rows, 2 * n + iu] = 1.0
        A[rows, 2 * n + ju] = 1.0
        b[:m] = d - (r[iu] + r[ju])
        for i in range(n):
            k = m + 4 * i
            A[k, 2 * i] = -1.0; A[k, 2 * n + i] = 1.0
            b[k] = pts[i, 0] - r[i]
            A[k + 1, 2 * i] = 1.0; A[k + 1, 2 * n + i] = 1.0
            b[k + 1] = 1.0 - pts[i, 0] - r[i]
            A[k + 2, 2 * i + 1] = -1.0; A[k + 2, 2 * n + i] = 1.0
            b[k + 2] = pts[i, 1] - r[i]
            A[k + 3, 2 * i + 1] = 1.0; A[k + 3, 2 * n + i] = 1.0
            b[k + 3] = 1.0 - pts[i, 1] - r[i]
        c = np.zeros(3 * n); c[2 * n:] = -1.0
        bounds = [(-trust, trust)] * (2 * n) + [(-trust, trust)] * n
        try:
            res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method='highs')
        except Exception:
            break
        if not res.success:
            trust *= 0.5
            if trust < 1e-8:
                break
            continue
        z = res.x
        new_pts = pts + z[:2 * n].reshape(n, 2)
        new_r = r + z[2 * n:]
        new_pts[:, 0] = np.clip(new_pts[:, 0], 1e-9, 1 - 1e-9)
        new_pts[:, 1] = np.clip(new_pts[:, 1], 1e-9, 1 - 1e-9)
        new_r = np.maximum(new_r, 1e-7)
        cand = _feasible(np.column_stack([new_pts, new_r]))
        cs = cand[:, 2].sum()
        if cs > r.sum() + 1e-12:
            pts = cand[:, :2].copy(); r = cand[:, 2].copy()
            if cs > best_s:
                best = cand.copy(); best_s = cs
            trust = min(trust * 1.5, 0.1)
        else:
            trust *= 0.5
            if trust < 1e-8:
                break
    return best


def _lp_radius_step(cfg, n):
    r = _lp_radii(cfg[:, :2])
    if r is None:
        return cfg
    return _feasible(np.column_stack([cfg[:, :2], r]))


def _finalize(best):
    out = best.copy()
    out[:, 2] = np.maximum(out[:, 2], 1e-6)
    out[:, 2] *= (1.0 - 1e-9)
    out[:, 0] = np.clip(out[:, 0], out[:, 2], 1 - out[:, 2])
    out[:, 1] = np.clip(out[:, 1], out[:, 2], 1 - out[:, 2])
    for _ in range(30):
        if _check(out, tol=1e-13):
            break
        out = _feasible(out)
        out[:, 2] *= (1.0 - 1e-10)
        out[:, 0] = np.clip(out[:, 0], out[:, 2], 1 - out[:, 2])
        out[:, 1] = np.clip(out[:, 1], out[:, 2], 1 - out[:, 2])
    return out


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    rng = np.random.default_rng(20240701 + int(time.time()) % 1000)

    def elapsed():
        return time.process_time() - t0

    deadline = t0 + budget_seconds * 0.85
    hard_end = t0 + budget_seconds * 0.93

    best = None; best_s = -1.0

    def try_update(c):
        nonlocal best, best_s
        c = _feasible(c)
        s = c[:, 2].sum()
        if s > best_s:
            best, best_s = c.copy(), s

    if start is not None:
        arr = np.asarray(start, dtype=float).copy()
        arr[:, 2] = np.maximum(arr[:, 2], 1e-4)
        s0 = _feasible(arr)
        try_update(s0)
        c = _lp_radius_step(s0, n)
        try_update(c)
        c = _slsqp(c, n, maxiter=400)
        try_update(c)
        c = _slp(c, n, iters=30, trust=0.02, deadline=deadline, elapsed=elapsed)
        try_update(c)
        c = _slsqp(c, n, maxiter=300)
        try_update(c)

    # Multi-start SLP from perturbed variants of best
    if best is None:
        pts = rng.uniform(0.05, 0.95, size=(n, 2))
        r0 = _lp_radii(pts)
        if r0 is None:
            r0 = np.full(n, 0.05)
        best = np.column_stack([pts, r0])
        best_s = best[:, 2].sum()

    it = 0
    while elapsed() < deadline - 0.4:
        it += 1
        base = best.copy()
        # perturb centers
        scale = 0.005 + 0.01 * (it % 3)
        base[:, 0] += rng.normal(0, scale, n)
        base[:, 1] += rng.normal(0, scale, n)
        base[:, 0] = np.clip(base[:, 0], 0.01, 0.99)
        base[:, 1] = np.clip(base[:, 1], 0.01, 0.99)
        # re-solve radii via LP
        r0 = _lp_radii(base[:, :2])
        if r0 is not None:
            base[:, 2] = r0
        base = _feasible(base)
        # SLP + SLSQP alternating
        c = _slp(base, n, iters=25, trust=0.02, deadline=deadline, elapsed=elapsed)
        try_update(c)
        if elapsed() < deadline - 0.3:
            c = _slsqp(c, n, maxiter=200)
            try_update(c)

    # Final intense polish
    if best is not None:
        for _ in range(3):
            if elapsed() > deadline:
                break
            c = _slsqp(best, n, maxiter=500)
            try_update(c)
            c = _slp(best, n, iters=30, trust=0.01, deadline=deadline, elapsed=elapsed)
            try_update(c)

    return _finalize(best)
