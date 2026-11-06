import numpy as np
import time
from scipy.optimize import minimize

N = 26
IU = np.triu_indices(N, 1)
NP = len(IU[0])
I0, I1 = IU[0], IU[1]


def _pairwise(x, y):
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    return np.sqrt(dx * dx + dy * dy)


def _repair(x, y, r, margin=1e-10):
    r = np.maximum(np.asarray(r, float).copy(), 1e-9)
    r = np.minimum(r, np.minimum(x - margin, 1.0 - x - margin))
    r = np.minimum(r, np.minimum(y - margin, 1.0 - y - margin))
    r = np.maximum(r, 1e-9)
    for _ in range(400):
        d = _pairwise(x, y)
        rs = r[:, None] + r[None, :]
        viol = rs - (d - margin)
        np.fill_diagonal(viol, -1.0)
        v = viol[I0, I1]
        if v.max() <= 0:
            break
        exc = np.maximum(v, 0.0)
        contrib = np.zeros(N)
        np.add.at(contrib, I0, exc * 0.5)
        np.add.at(contrib, I1, exc * 0.5)
        r = np.maximum(r - contrib, 1e-9)
        r = np.minimum(r, np.minimum(x - margin, 1.0 - x - margin))
        r = np.minimum(r, np.minimum(y - margin, 1.0 - y - margin))
        r = np.maximum(r, 1e-9)
    return r


def _grow(x, y, r):
    for _ in range(80):
        improved = False
        for i in range(N):
            mr = min(x[i], 1 - x[i], y[i], 1 - y[i])
            dx = x[i] - x; dy = y[i] - y
            d = np.sqrt(dx * dx + dy * dy)
            d[i] = np.inf
            mr = min(mr, np.min(d - r))
            if mr > r[i] + 1e-14:
                r[i] = mr
                improved = True
        if not improved:
            break
    return r


def _fun(v):
    return -np.sum(v[2::3])


def _jac(v):
    g = np.zeros_like(v)
    g[2::3] = -1.0
    return g


def _cons_fun(v):
    p = v.reshape(N, 3)
    xx, yy, rr = p[:, 0], p[:, 1], p[:, 2]
    out = [xx - rr, 1 - xx - rr, yy - rr, 1 - yy - rr]
    d = _pairwise(xx, yy)
    rs = rr[:, None] + rr[None, :]
    out.append((d - rs)[I0, I1])
    return np.concatenate(out)


def _cons_jac(v):
    p = v.reshape(N, 3)
    xx, yy, rr = p[:, 0], p[:, 1], p[:, 2]
    dx = xx[:, None] - xx[None, :]
    dy = yy[:, None] - yy[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    d = np.maximum(d, 1e-12)
    m = 4 * N + NP
    J = np.zeros((m, 3 * N))
    idx = np.arange(N)
    J[idx, 3 * idx] = 1.0; J[idx, 3 * idx + 2] = -1.0
    J[N + idx, 3 * idx] = -1.0; J[N + idx, 3 * idx + 2] = -1.0
    J[2 * N + idx, 3 * idx + 1] = 1.0; J[2 * N + idx, 3 * idx + 2] = -1.0
    J[3 * N + idx, 3 * idx + 1] = -1.0; J[3 * N + idx, 3 * idx + 2] = -1.0
    base = 4 * N
    ii, jj = I0, I1
    dd = d[ii, jj]
    ux = (xx[ii] - xx[jj]) / dd
    uy = (yy[ii] - yy[jj]) / dd
    rows = base + np.arange(NP)
    J[rows, 3 * ii] = ux
    J[rows, 3 * ii + 1] = uy
    J[rows, 3 * jj] = -ux
    J[rows, 3 * jj + 1] = -uy
    J[rows, 3 * ii + 2] = -1.0
    J[rows, 3 * jj + 2] = -1.0
    return J


def _slsqp(x, y, r, maxiter=400):
    v0 = np.column_stack([x, y, r]).ravel()
    bounds = [(0.0, 1.0)] * (2 * N) + [(1e-9, 0.5)] * N
    try:
        res = minimize(_fun, v0, jac=_jac, method='SLSQP', bounds=bounds,
                       constraints=[{'type': 'ineq', 'fun': _cons_fun,
                                     'jac': _cons_jac}],
                       options={'maxiter': maxiter, 'ftol': 1e-15})
        p = res.x.reshape(N, 3)
        xr = np.clip(p[:, 0].copy(), 1e-5, 1 - 1e-5)
        yr = np.clip(p[:, 1].copy(), 1e-5, 1 - 1e-5)
        rr = _repair(xr, yr, p[:, 2].copy(), margin=1e-11)
        rr = _grow(xr, yr, rr)
        rr = _repair(xr, yr, rr, margin=1e-11)
        return xr, yr, rr
    except Exception:
        return None


def _feasible(x, y, r, tol=0.0):
    if np.any(r <= 0):
        return False
    if np.any(x - r < -tol) or np.any(x + r > 1 + tol):
        return False
    if np.any(y - r < -tol) or np.any(y + r > 1 + tol):
        return False
    d = _pairwise(x, y)
    rs = r[:, None] + r[None, :]
    viol = rs - d
    np.fill_diagonal(viol, -1.0)
    return viol.max() <= tol


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.82
    rng = np.random.default_rng(20250721)

    if start is not None:
        arr = np.asarray(start, float).copy()
        x = np.clip(arr[:, 0].copy(), 1e-4, 1 - 1e-4)
        y = np.clip(arr[:, 1].copy(), 1e-4, 1 - 1e-4)
        r = _repair(x, y, arr[:, 2].copy(), margin=1e-10)
    else:
        k = 6
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:N]
        x = np.array([p[0] for p in pts])
        y = np.array([p[1] for p in pts])
        r = _repair(x, y, np.full(N, 0.5 / k * 0.9), margin=1e-10)
    r = _grow(x, y, r)
    r = _repair(x, y, r, margin=1e-10)

    best_x, best_y, best_r = x.copy(), y.copy(), r.copy()
    best_s = float(best_r.sum())

    def try_update(xr, yr, rr):
        nonlocal best_x, best_y, best_r, best_s
        s = float(rr.sum())
        if s > best_s + 1e-13:
            best_x, best_y, best_r = xr.copy(), yr.copy(), rr.copy()
            best_s = s
            return True
        return False

    out = _slsqp(best_x, best_y, best_r, maxiter=900)
    if out is not None:
        try_update(*out)

    pool = [(best_s, best_x.copy(), best_y.copy(), best_r.copy())]

    def add_pool(s, xr, yr, rr):
        pool.append((s, xr.copy(), yr.copy(), rr.copy()))
        pool.sort(key=lambda t: -t[0])
        del pool[8:]

    grid = [(gx, gy) for gx in np.linspace(0.02, 0.98, 26)
                     for gy in np.linspace(0.02, 0.98, 26)]

    def reinsert(x, y, r, i):
        keep = [j for j in range(N) if j != i]
        xk, yk, rk = x[keep], y[keep], r[keep]
        best_pt = None; best_val = -1.0
        cand = list(grid)
        for _ in range(40):
            cand.append((rng.uniform(0.02, 0.98), rng.uniform(0.02, 0.98)))
        for (px, py) in cand:
            mr = min(px, 1 - px, py, 1 - py)
            dx = px - xk; dy = py - yk
            d = np.sqrt(dx * dx + dy * dy)
            mr = min(mr, np.min(d - rk))
            if mr > best_val:
                best_val = mr; best_pt = (px, py)
        if best_pt is None or best_val <= 1e-6:
            return x.copy(), y.copy(), r.copy()
        x2 = np.append(xk, best_pt[0])
        y2 = np.append(yk, best_pt[1])
        r2 = np.append(rk, max(best_val, 1e-6))
        return x2, y2, r2

    scales = [1.001, 1.003, 1.006, 1.01, 1.015, 1.022, 1.03, 1.04, 1.055,
              1.075, 1.10, 1.14, 1.20, 1.30]

    stall = 0
    while time.process_time() < deadline:
        improved = False
        mode = stall % 9

        if mode == 8 and len(pool) > 1 and rng.random() < 0.6:
            pick = int(rng.integers(0, min(len(pool), 5)))
            _, bx, by, br = pool[pick]
            cx, cy, cr = bx.copy(), by.copy(), br.copy()
        else:
            cx, cy, cr = best_x.copy(), best_y.copy(), best_r.copy()

        if mode <= 1:
            sc = scales[int(rng.integers(0, len(scales)))]
            rr = _repair(cx, cy, cr * sc, margin=1e-10)
            out = _slsqp(cx, cy, rr, maxiter=350)
            if out is not None and try_update(*out):
                improved = True
                add_pool(best_s, best_x, best_y, best_r)

        if not improved and mode == 2:
            if rng.random() < 0.5:
                i = int(np.argmin(cr))
            else:
                i = int(rng.integers(0, N))
            gx, gy, gr = reinsert(cx, cy, cr, i)
            gr = _grow(gx, gy, gr)
            gr = _repair(gx, gy, gr, margin=1e-10)
            out = _slsqp(gx, gy, gr, maxiter=400)
            if out is not None and try_update(*out):
                improved = True
                add_pool(best_s, best_x, best_y, best_r)

        if not improved and mode == 3:
            order = np.argsort(cr)
            nkick = min(N, 3 + int(rng.integers(0, 6)))
            idx = order[:nkick]
            mag = 0.008 * (1 + stall * 0.4)
            cx[idx] += rng.normal(0, mag, len(idx))
            cy[idx] += rng.normal(0, mag, len(idx))
            cx = np.clip(cx, 1e-4, 1 - 1e-4)
            cy = np.clip(cy, 1e-4, 1 - 1e-4)
            cr = _repair(cx, cy, cr * rng.uniform(0.90, 1.10), margin=1e-10)
            cr = _grow(cx, cy, cr)
            out = _slsqp(cx, cy, cr, maxiter=400)
            if out is not None and try_update(*out):
                improved = True
                add_pool(best_s, best_x, best_y, best_r)

        if not improved and mode == 4:
            cx = cx + rng.normal(0, 0.012, N)
            cy = cy + rng.normal(0, 0.012, N)
            cx = np.clip(cx, 1e-4, 1 - 1e-4)
            cy = np.clip(cy, 1e-4, 1 - 1e-4)
            cr = _repair(cx, cy, cr * rng.uniform(0.95, 1.08), margin=1e-10)
            cr = _grow(cx, cy, cr)
            out = _slsqp(cx, cy, cr, maxiter=350)
            if out is not None and try_update(*out):
                improved = True
                add_pool(best_s, best_x, best_y, best_r)

        if not improved and mode == 5:
            order = np.argsort(cr)
            i = int(order[0])
            gx, gy, gr = reinsert(cx, cy, cr, i)
            j = int(np.argmin(gr))
            gx, gy, gr = reinsert(gx, gy, gr, j)
            gr = _grow(gx, gy, gr)
            gr = _repair(gx, gy, gr, margin=1e-10)
            out = _slsqp(gx, gy, gr, maxiter=450)
            if out is not None and try_update(*out):
                improved = True
                add_pool(best_s, best_x, best_y, best_r)

        if not improved and mode == 6:
            sc = scales[int(rng.integers(0, len(scales)))]
            rr = _repair(cx, cy, cr * sc, margin=1e-10)
            rr = _grow(cx, cy, rr)
            rr = _repair(cx, cy, rr, margin=1e-10)
            out = _slsqp(cx, cy, rr, maxiter=350)
            if out is not None and try_update(*out):
                improved = True
                add_pool(best_s, best_x, best_y, best_r)

        if not improved and mode == 7:
            # random restart within local neighborhood with big kick
            cx = cx + rng.normal(0, 0.03, N)
            cy = cy + rng.normal(0, 0.03, N)
            cx = np.clip(cx, 1e-4, 1 - 1e-4)
            cy = np.clip(cy, 1e-4, 1 - 1e-4)
            cr = _repair(cx, cy, cr * rng.uniform(0.85, 1.05), margin=1e-10)
            cr = _grow(cx, cy, cr)
            out = _slsqp(cx, cy, cr, maxiter=450)
            if out is not None and try_update(*out):
                improved = True
                add_pool(best_s, best_x, best_y, best_r)

        if improved:
            stall = 0
        else:
            stall += 1

    x, y, r = best_x.copy(), best_y.copy(), best_r.copy()
    r = _grow(x, y, r)
    r = _repair(x, y, r, margin=1e-8)
    r = np.maximum(r - 1e-9, 1e-9)
    for i in range(N):
        r[i] = min(r[i], x[i] - 1e-9, 1.0 - x[i] - 1e-9,
                   y[i] - 1e-9, 1.0 - y[i] - 1e-9)
    r = np.maximum(r, 1e-9)
    for _ in range(200):
        d = _pairwise(x, y)
        rs = r[:, None] + r[None, :]
        viol = rs - (d - 1e-9)
        np.fill_diagonal(viol, -1.0)
        if viol.max() <= 0:
            break
        exc = np.maximum(viol[I0, I1], 0.0)
        contrib = np.zeros(N)
        np.add.at(contrib, I0, exc * 0.5)
        np.add.at(contrib, I1, exc * 0.5)
        r = np.maximum(r - contrib, 1e-9)

    if not _feasible(x, y, r, tol=0.0):
        r = _repair(x, y, r, margin=1e-7)
        r = np.maximum(r - 1e-10, 1e-9)

    return np.column_stack([x, y, r])
