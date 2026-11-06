import numpy as np
import time
from scipy.optimize import minimize


def _unpack(z, n):
    x = z[0::3]
    y = z[1::3]
    r = z[2::3]
    return x, y, r


def _energy(z, n, P):
    x, y, r = _unpack(z, n)
    E = -np.sum(r)
    wv = np.maximum(0.0, r - x); E += P * np.sum(wv * wv)
    wv = np.maximum(0.0, x + r - 1.0); E += P * np.sum(wv * wv)
    wv = np.maximum(0.0, r - y); E += P * np.sum(wv * wv)
    wv = np.maximum(0.0, y + r - 1.0); E += P * np.sum(wv * wv)
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    rs = r[:, None] + r[None, :]
    ov = np.maximum(0.0, rs - d)
    iu = np.triu_indices(n, 1)
    E += P * np.sum(ov[iu] * ov[iu])
    return E


def _grad(z, n, P):
    x, y, r = _unpack(z, n)
    g = np.zeros_like(z)
    g[2::3] = -1.0
    v = np.maximum(0.0, r - x); g[0::3] += P * (-2.0 * v); g[2::3] += P * (2.0 * v)
    v = np.maximum(0.0, x + r - 1.0); g[0::3] += P * (2.0 * v); g[2::3] += P * (2.0 * v)
    v = np.maximum(0.0, r - y); g[1::3] += P * (-2.0 * v); g[2::3] += P * (2.0 * v)
    v = np.maximum(0.0, y + r - 1.0); g[1::3] += P * (2.0 * v); g[2::3] += P * (2.0 * v)
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    d = np.maximum(d, 1e-12)
    rs = r[:, None] + r[None, :]
    ov = np.maximum(0.0, rs - d)
    iu = np.triu_indices(n, 1)
    coef = np.zeros((n, n))
    coef[iu] = 2.0 * ov[iu]
    coef = coef + coef.T
    gx = -coef * (dx / d)
    gy = -coef * (dy / d)
    g[0::3] += P * np.sum(gx, axis=1)
    g[1::3] += P * np.sum(gy, axis=1)
    g[2::3] += P * np.sum(coef, axis=1)
    return g


def _repair(z, n):
    x, y, r = _unpack(z, n)
    r = np.maximum(r, 1e-8)
    for _ in range(200):
        ok = True
        if np.any(x - r < 0) or np.any(x + r > 1) or np.any(y - r < 0) or np.any(y + r > 1):
            ok = False
        if ok:
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx * dx + dy * dy)
            rs = r[:, None] + r[None, :]
            iu = np.triu_indices(n, 1)
            if np.any(d[iu] < rs[iu]):
                ok = False
        if ok:
            break
        r *= 0.9999
    z2 = z.copy()
    z2[2::3] = r
    return z2


def _slsqp_polish(z, n, maxiter=400):
    def obj(v):
        return -np.sum(v[2::3])

    def jac(v):
        g = np.zeros_like(v)
        g[2::3] = -1.0
        return g

    def cons(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        c = []
        c.append(x - r)
        c.append(1.0 - x - r)
        c.append(y - r)
        c.append(1.0 - y - r)
        iu = np.triu_indices(n, 1)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        c.append((d - rs)[iu])
        return np.concatenate(c)

    def cons_jac(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        J = np.zeros((4 * n, 3 * n))
        for i in range(n):
            J[i, 3 * i] = 1.0; J[i, 3 * i + 2] = -1.0
            J[n + i, 3 * i] = -1.0; J[n + i, 3 * i + 2] = -1.0
            J[2 * n + i, 3 * i + 1] = 1.0; J[2 * n + i, 3 * i + 2] = -1.0
            J[3 * n + i, 3 * i + 1] = -1.0; J[3 * n + i, 3 * i + 2] = -1.0
        iu = np.triu_indices(n, 1)
        npair = len(iu[0])
        Jp = np.zeros((npair, 3 * n))
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        d = np.maximum(d, 1e-12)
        for k, (i, j) in enumerate(zip(iu[0], iu[1])):
            ux = dx[i, j] / d[i, j]
            uy = dy[i, j] / d[i, j]
            Jp[k, 3 * i] = ux; Jp[k, 3 * j] = -ux
            Jp[k, 3 * i + 1] = uy; Jp[k, 3 * j + 1] = -uy
            Jp[k, 3 * i + 2] = -1.0; Jp[k, 3 * j + 2] = -1.0
        return np.vstack([J, Jp])

    bounds = [(0.0, 1.0)] * (3 * n)
    for i in range(n):
        bounds[3 * i + 2] = (1e-9, 0.5)
    try:
        res = minimize(obj, z, jac=jac, method='SLSQP',
                       bounds=bounds,
                       constraints=[{'type': 'ineq', 'fun': cons, 'jac': cons_jac}],
                       options={'maxiter': maxiter, 'ftol': 1e-14})
        return res.x
    except Exception:
        return z


def _to_z(arr):
    n = arr.shape[0]
    z = np.empty(3 * n)
    z[0::3] = arr[:, 0]
    z[1::3] = arr[:, 1]
    z[2::3] = arr[:, 2]
    return z


def _to_arr(z):
    n = len(z) // 3
    return np.column_stack([z[0::3], z[1::3], z[2::3]])


def _find_void(arr):
    g = 200
    xs = np.linspace(0.001, 0.999, g)
    ys = np.linspace(0.001, 0.999, g)
    GX, GY = np.meshgrid(xs, ys, indexing='ij')
    px = GX.ravel()
    py = GY.ravel()
    wall = np.minimum(np.minimum(px, 1.0 - px), np.minimum(py, 1.0 - py))
    best = wall.copy()
    cx = arr[:, 0]; cy = arr[:, 1]; cr = arr[:, 2]
    for j in range(len(cr)):
        d = np.sqrt((px - cx[j]) ** 2 + (py - cy[j]) ** 2) - cr[j]
        np.minimum(best, d, out=best)
    k = int(np.argmax(best))
    return px[k], py[k], best[k]


def _exact_shrink(arr):
    arr = arr.copy()
    for _ in range(1000):
        x = arr[:, 0]; y = arr[:, 1]; r = arr[:, 2]
        ok = True
        if np.any(r <= 0): ok = False
        if np.any(x - r < 0) or np.any(x + r > 1) or np.any(y - r < 0) or np.any(y + r > 1):
            ok = False
        if ok:
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx * dx + dy * dy)
            rs = r[:, None] + r[None, :]
            iu = np.triu_indices(len(r), 1)
            if np.any(d[iu] < rs[iu]):
                ok = False
        if ok:
            break
        arr[:, 2] = np.maximum(arr[:, 2] - 1e-9, 1e-9)
    return arr


def _is_valid(arr):
    x = arr[:, 0]; y = arr[:, 1]; r = arr[:, 2]
    if np.any(r <= 0):
        return False
    if np.any(x - r < 0) or np.any(x + r > 1) or np.any(y - r < 0) or np.any(y + r > 1):
        return False
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    rs = r[:, None] + r[None, :]
    iu = np.triu_indices(len(r), 1)
    if np.any(d[iu] < rs[iu]):
        return False
    return True


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    if start is not None:
        start = np.asarray(start, dtype=float)
        z0 = _to_z(start)
    else:
        k = 6
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)]
        corners = {(0, 0), (0, k - 1), (k - 1, 0), (k - 1, k - 1)}
        pts = [p for idx, p in enumerate(pts) if idx not in corners][:n]
        z0 = np.empty(3 * n)
        for i, (x, y) in enumerate(pts):
            z0[3 * i] = x; z0[3 * i + 1] = y; z0[3 * i + 2] = 0.02

    base_z = _repair(z0.copy(), n)
    base_z = _slsqp_polish(base_z, n, maxiter=400)
    base_z = _repair(base_z, n)
    base_arr = _to_arr(base_z)
    best_arr = base_arr.copy()
    best_score = float(np.sum(best_arr[:, 2]))

    deadline = budget_seconds * 0.85

    # Systematic delete-reinsertion: sweep all 32 deletions, repeat passes
    # until no improvement or CPU budget nearly exhausted.
    while True:
        improved = False
        for i in range(n):
            if time.process_time() - t0 > deadline:
                break
            arr31 = np.delete(best_arr, i, axis=0)
            vx, vy, vd = _find_void(arr31)
            arr32 = np.vstack([arr31, [vx, vy, 1e-4]])
            z32 = _to_z(arr32)
            z32 = _repair(z32, n)
            z32 = _slsqp_polish(z32, n, maxiter=800)
            z32 = _repair(z32, n)
            arr32 = _to_arr(z32)
            arr32 = _exact_shrink(arr32)
            if not _is_valid(arr32):
                continue
            sc = float(np.sum(arr32[:, 2]))
            if sc > best_score:
                best_score = sc
                best_arr = arr32.copy()
                improved = True
        if not improved:
            break
        if time.process_time() - t0 > deadline:
            break

    best_arr = _exact_shrink(best_arr)
    return best_arr
