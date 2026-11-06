import numpy as np
import time
from scipy.optimize import linprog, minimize
from scipy.sparse import coo_matrix


def _score(c):
    return c[:, 2].sum()


def _feasible(c, eps=0.0):
    x = c[:, 0]; y = c[:, 1]; r = c[:, 2]
    if np.any(r <= 0):
        return False
    if np.any(x - r < -eps) or np.any(x + r > 1 + eps):
        return False
    if np.any(y - r < -eps) or np.any(y + r > 1 + eps):
        return False
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d2 = dx * dx + dy * dy
    rs = r[:, None] + r[None, :]
    np.fill_diagonal(d2, 1e9)
    if np.any(d2 < (rs - eps) ** 2):
        return False
    return True


def _build_lp(x, y):
    n = len(x)
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    np.fill_diagonal(d, 1e9)
    rows = []; cols = []; vals = []; b = []
    pair_idx = []
    row = 0
    for i in range(n):
        for j in range(i + 1, n):
            rows.append(row); cols.append(i); vals.append(1.0)
            rows.append(row); cols.append(j); vals.append(1.0)
            b.append(d[i, j])
            pair_idx.append((i, j))
            row += 1
    wall = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
    wall_rows = []
    for i in range(n):
        rows.append(row); cols.append(i); vals.append(1.0)
        b.append(max(wall[i], 0.0))
        wall_rows.append(i)
        row += 1
    A = coo_matrix((vals, (rows, cols)), shape=(row, n)).tocsr()
    return A, np.array(b), d, pair_idx, wall_rows


def _lp_radii(x, y, return_dual=False):
    n = len(x)
    x = x.copy(); y = y.copy()
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    np.fill_diagonal(d, 1e9)
    if np.any(d < 1e-9):
        rng = np.random.default_rng(7)
        for i in range(n):
            for j in range(i + 1, n):
                if d[i, j] < 1e-9:
                    x[j] += rng.normal(0, 1e-6)
                    y[j] += rng.normal(0, 1e-6)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        np.fill_diagonal(d, 1e9)

    A, b, d, pair_idx, wall_rows = _build_lp(x, y)
    res = linprog(c=-np.ones(n), A_ub=A, b_ub=b,
                  bounds=[(0, None)] * n, method='highs')
    if not res.success:
        if return_dual:
            return np.zeros(n), np.zeros(n), np.zeros(n)
        return np.zeros(n)
    r = np.maximum(res.x, 0.0)
    if not return_dual:
        return r

    try:
        lam = -np.asarray(res.ineqlin.marginals, dtype=float)
    except Exception:
        lam = np.zeros(len(b))
    lam = np.maximum(lam, 0.0)

    gx = np.zeros(n); gy = np.zeros(n)
    for k, (i, j) in enumerate(pair_idx):
        w = lam[k]
        if w <= 1e-12:
            continue
        dij = d[i, j]
        if dij < 1e-12:
            continue
        ux = (x[i] - x[j]) / dij
        uy = (y[i] - y[j]) / dij
        gx[i] += w * ux; gy[i] += w * uy
        gx[j] -= w * ux; gy[j] -= w * uy
    for k, i in enumerate(wall_rows):
        w = lam[len(pair_idx) + k]
        if w <= 1e-12:
            continue
        vals4 = [x[i], 1 - x[i], y[i], 1 - y[i]]
        m = int(np.argmin(vals4))
        if m == 0:
            gx[i] += w
        elif m == 1:
            gx[i] -= w
        elif m == 2:
            gy[i] += w
        else:
            gy[i] -= w
    return r, gx, gy


def _relax(c, iters=500, lr=0.3):
    n = len(c)
    x = c[:, 0].copy(); y = c[:, 1].copy(); r = c[:, 2].copy()
    for _ in range(iters):
        fx = np.zeros(n); fy = np.zeros(n)
        fx += np.maximum(0, r - x) - np.maximum(0, x + r - 1)
        fy += np.maximum(0, r - y) - np.maximum(0, y + r - 1)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy) + 1e-12
        rs = r[:, None] + r[None, :]
        overlap = np.maximum(0, rs - d)
        np.fill_diagonal(overlap, 0)
        ux = dx / d; uy = dy / d
        fx += (overlap * ux).sum(axis=1)
        fy += (overlap * uy).sum(axis=1)
        x = np.clip(x + lr * fx, r, 1 - r)
        y = np.clip(y + lr * fy, r, 1 - r)
    c[:, 0] = x; c[:, 1] = y
    return c


def _slsqp_polish(c, maxiter=300):
    n = len(c)
    x0 = c[:, 0].copy(); y0 = c[:, 1].copy(); r0 = c[:, 2].copy()
    cons = []
    def make_wall_jac(i, comp, sign):
        def jac(v):
            g = np.zeros(3 * n)
            g[comp * n + i] = sign
            g[2 * n + i] = -1.0
            return g
        return jac

    for i in range(n):
        cons.append({'type': 'ineq',
                     'fun': lambda v, i=i: v[i] - v[2*n+i],
                     'jac': make_wall_jac(i, 0, 1.0)})
        cons.append({'type': 'ineq',
                     'fun': lambda v, i=i: 1 - v[i] - v[2*n+i],
                     'jac': make_wall_jac(i, 0, -1.0)})
        cons.append({'type': 'ineq',
                     'fun': lambda v, i=i: v[n+i] - v[2*n+i],
                     'jac': make_wall_jac(i, 1, 1.0)})
        cons.append({'type': 'ineq',
                     'fun': lambda v, i=i: 1 - v[n+i] - v[2*n+i],
                     'jac': make_wall_jac(i, 1, -1.0)})

    def make_pair(i, j):
        def f(v):
            dx = v[i] - v[j]
            dy = v[n+i] - v[n+j]
            rs = v[2*n+i] + v[2*n+j]
            return dx*dx + dy*dy - rs*rs
        def jac(v):
            g = np.zeros(3 * n)
            dx = v[i] - v[j]
            dy = v[n+i] - v[n+j]
            rs = v[2*n+i] + v[2*n+j]
            g[i] = 2.0 * dx
            g[j] = -2.0 * dx
            g[n+i] = 2.0 * dy
            g[n+j] = -2.0 * dy
            g[2*n+i] = -2.0 * rs
            g[2*n+j] = -2.0 * rs
            return g
        return f, jac

    for i in range(n):
        for j in range(i + 1, n):
            f, jac = make_pair(i, j)
            cons.append({'type': 'ineq', 'fun': f, 'jac': jac})

    def obj(v):
        return -np.sum(v[2*n:])

    def grad(v):
        g = np.zeros(3*n)
        g[2*n:] = -1.0
        return g

    v0 = np.concatenate([x0, y0, r0])
    bounds = [(0, 1)] * (2*n) + [(1e-6, 0.5)] * n
    try:
        res = minimize(obj, v0, jac=grad, method='SLSQP', bounds=bounds,
                       constraints=cons,
                       options={'maxiter': maxiter, 'ftol': 1e-14})
        v = res.x
        return np.column_stack([v[:n], v[n:2*n], v[2*n:]])
    except Exception:
        return c


def _solidify(c):
    """Minimal additive shrink so the result is exactly feasible in floating point."""
    out = c.copy()
    if _feasible(out, 0.0):
        return out
    lo, hi = 0.0, 1e-4
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        trial = out.copy()
        trial[:, 2] = out[:, 2] - mid
        if np.all(trial[:, 2] > 0) and _feasible(trial, 0.0):
            hi = mid
        else:
            lo = mid
    out[:, 2] = out[:, 2] - hi - 1e-12
    if not _feasible(out, 0.0):
        # fallback safety
        for _ in range(60):
            if _feasible(out, 0.0):
                return out
            out[:, 2] *= 0.9995
    return out


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = budget_seconds * 0.85
    n = 32

    if start is not None:
        best = np.array(start, dtype=float, copy=True)
    else:
        k = 6
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        best = np.array([[x, y, 0.01] for x, y in pts], dtype=float)

    best[:, 2] = _lp_radii(best[:, 0], best[:, 1])
    best = _solidify(best)
    best_score = _score(best)
    cur = best.copy()

    rng = np.random.default_rng(int(time.process_time() * 1e6) % 2**31)

    def elapsed():
        return time.process_time() - t0

    # Phase A: dual ascent
    phase_a_end = deadline * 0.35
    h = 0.01
    while elapsed() < phase_a_end:
        r, gx, gy = _lp_radii(cur[:, 0], cur[:, 1], return_dual=True)
        cur[:, 2] = r
        gn = np.sqrt(gx * gx + gy * gy)
        if gn.sum() < 1e-12:
            break
        mask = gn > 1e-12
        dx_dir = np.zeros(n); dy_dir = np.zeros(n)
        dx_dir[mask] = gx[mask] / gn[mask]
        dy_dir[mask] = gy[mask] / gn[mask]
        cand = cur.copy()
        cand[mask, 0] += h * dx_dir[mask]
        cand[mask, 1] += h * dy_dir[mask]
        cand[:, 0] = np.clip(cand[:, 0], cand[:, 2], 1 - cand[:, 2])
        cand[:, 1] = np.clip(cand[:, 1], cand[:, 2], 1 - cand[:, 2])
        cand = _relax(cand, iters=40, lr=0.4)
        cand[:, 2] = _lp_radii(cand[:, 0], cand[:, 1])
        if _feasible(cand, 1e-9) and _score(cand) > _score(cur) + 1e-12:
            cur = cand
            h = min(0.05, 1.2 * h)
            if _score(cur) > best_score:
                best = cur.copy(); best_score = _score(cur)
        else:
            h *= 0.5
            if h < 1e-5:
                break

    # Phase B: SLSQP polish on current best, then re-run dual ascent from it
    if elapsed() < deadline * 0.55:
        pol = _slsqp_polish(best, maxiter=400)
        if _feasible(pol, 1e-7):
            pol[:, 2] = _lp_radii(pol[:, 0], pol[:, 1])
            if _score(pol) > best_score:
                best = pol.copy(); best_score = _score(best)
                cur = best.copy()

    # Phase C: simulated annealing on positions
    it = 0
    while elapsed() < deadline:
        it += 1
        frac = elapsed() / deadline
        cand = cur.copy()
        mode = rng.random()
        if mode < 0.1:
            scale = 0.97 + 0.04 * rng.random()
            cx = cand[:, 0].mean(); cy = cand[:, 1].mean()
            cand[:, 0] = cx + (cand[:, 0] - cx) * scale
            cand[:, 1] = cy + (cand[:, 1] - cy) * scale
            cand[:, 0] = np.clip(cand[:, 0], 1e-3, 1 - 1e-3)
            cand[:, 1] = np.clip(cand[:, 1], 1e-3, 1 - 1e-3)
        elif mode < 0.6:
            m = int(rng.integers(1, 4))
            idx = rng.choice(n, size=m, replace=False)
            scale = 0.03 * (1.0 - 0.6 * frac)
            cand[idx, 0] += rng.normal(0, scale, size=m)
            cand[idx, 1] += rng.normal(0, scale, size=m)
        else:
            i = int(rng.integers(0, n))
            scale = 0.08 * (1.0 - 0.5 * frac)
            cand[i, 0] += rng.normal(0, scale)
            cand[i, 1] += rng.normal(0, scale)

        cand[:, 0] = np.clip(cand[:, 0], cand[:, 2], 1 - cand[:, 2])
        cand[:, 1] = np.clip(cand[:, 1], cand[:, 2], 1 - cand[:, 2])
        cand = _relax(cand, iters=50, lr=0.4)
        cand[:, 2] = _lp_radii(cand[:, 0], cand[:, 1])
        if _feasible(cand, 1e-9):
            s = _score(cand)
            T = 0.01 * max(1e-3, 1.0 - frac)
            cs = _score(cur)
            if s > cs or rng.random() < np.exp((s - cs) / max(T, 1e-6)):
                cur = cand
            if s > best_score:
                best = cand.copy(); best_score = s

        if it % 50 == 0 and elapsed() < deadline * 0.92:
            pol = _slsqp_polish(best, maxiter=200)
            if _feasible(pol, 1e-7):
                pol[:, 2] = _lp_radii(pol[:, 0], pol[:, 1])
                if _score(pol) > best_score:
                    best = pol.copy(); best_score = _score(best)
                    cur = best.copy()

    best[:, 2] = _lp_radii(best[:, 0], best[:, 1])
    best = _solidify(best)
    return best
