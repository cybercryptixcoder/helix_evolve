import numpy as np
import time
from scipy.optimize import minimize

N = 32
IU = np.triu_indices(N, 1)
II, JJ = IU


def _to_z(x, y, r):
    z = np.empty(3 * N)
    z[0::3] = x; z[1::3] = y; z[2::3] = r
    return z


def _unpack(z):
    return z[0::3].copy(), z[1::3].copy(), z[2::3].copy()


def _cons(z):
    x = z[0::3]; y = z[1::3]; r = z[2::3]
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d2 = dx * dx + dy * dy
    rs = r[:, None] + r[None, :]
    return np.concatenate([
        r - 1e-8,
        x - r, 1.0 - x - r, y - r, 1.0 - y - r,
        (d2 - rs * rs)[IU],
    ])


def _cons_jac(z):
    x = z[0::3]; y = z[1::3]; r = z[2::3]
    niu = len(II)
    m = 5 * N + niu
    J = np.zeros((m, 3 * N))
    rows = np.arange(N)
    J[rows, 3 * rows + 2] = 1.0
    J[N + rows, 3 * rows] = 1.0
    J[N + rows, 3 * rows + 2] = -1.0
    J[2 * N + rows, 3 * rows] = -1.0
    J[2 * N + rows, 3 * rows + 2] = -1.0
    J[3 * N + rows, 3 * rows + 1] = 1.0
    J[3 * N + rows, 3 * rows + 2] = -1.0
    J[4 * N + rows, 3 * rows + 1] = -1.0
    J[4 * N + rows, 3 * rows + 2] = -1.0
    dx = x[II] - x[JJ]
    dy = y[II] - y[JJ]
    rs = r[II] + r[JJ]
    base = 5 * N
    rows2 = np.arange(niu)
    J[base + rows2, 3 * II] = 2.0 * dx
    J[base + rows2, 3 * JJ] = -2.0 * dx
    J[base + rows2, 3 * II + 1] = 2.0 * dy
    J[base + rows2, 3 * JJ + 1] = -2.0 * dy
    J[base + rows2, 3 * II + 2] = -2.0 * rs
    J[base + rows2, 3 * JJ + 2] = -2.0 * rs
    return J


def _obj(z):
    return -np.sum(z[2::3])


def _grad(z):
    g = np.zeros_like(z)
    g[2::3] = -1.0
    return g


def _repair(z, iters=300):
    z = z.copy()
    x = z[0::3]; y = z[1::3]
    r = np.maximum(z[2::3], 1e-7)
    r = np.minimum(r, np.minimum(x, 1 - x))
    r = np.minimum(r, np.minimum(y, 1 - y))
    r = np.maximum(r, 1e-7)
    for _ in range(iters):
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        viol = (rs - d)[IU]
        if viol.max() <= 1e-14:
            break
        order = np.argsort(-viol)[:64]
        for idx in order:
            if viol[idx] <= 1e-14:
                continue
            i, j = II[idx], JJ[idx]
            ex = (r[i] + r[j]) - d[i, j]
            if ex <= 1e-15:
                continue
            tot = r[i] + r[j]
            if tot <= 1e-15:
                continue
            r[i] = max(r[i] - ex * r[i] / tot - 1e-15, 1e-7)
            r[j] = max(r[j] - ex * r[j] / tot - 1e-15, 1e-7)
        r = np.minimum(r, np.minimum(x, 1 - x))
        r = np.minimum(r, np.minimum(y, 1 - y))
        r = np.maximum(r, 1e-7)
    z[2::3] = r
    return z


def _polish(z, maxiter):
    try:
        res = minimize(_obj, z, jac=_grad, method='SLSQP',
                       constraints=[{'type': 'ineq', 'fun': _cons, 'jac': _cons_jac}],
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'disp': False})
        if np.all(np.isfinite(res.x)):
            return _repair(res.x)
    except Exception:
        pass
    return z


def _score(z, tol=1e-10):
    x = z[0::3]; y = z[1::3]; r = z[2::3]
    if np.any(r <= 0):
        return -1e9
    if np.any(x - r < -tol) or np.any(1 - x - r < -tol):
        return -1e9
    if np.any(y - r < -tol) or np.any(1 - y - r < -tol):
        return -1e9
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    rs = r[:, None] + r[None, :]
    if np.any((rs - d)[IU] > tol):
        return -1e9
    return float(np.sum(r))


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.6
    radii_deadline = t0 + 0.5 * budget_seconds

    pool = []

    def consider(z):
        sc = _score(z)
        pool.append((sc, z.copy()))
        pool.sort(key=lambda t: -t[0])
        del pool[8:]

    if start is not None:
        a = np.asarray(start, dtype=float)
        if a.shape == (N, 3):
            z = _to_z(a[:, 0].copy(), a[:, 1].copy(), np.maximum(a[:, 2], 1e-6))
            z = _repair(z)
            consider(z)

    if not pool:
        pts = [((i + 0.5) / 6, (j + 0.5) / 6) for j in range(6) for i in range(6)][:N]
        pts = np.array(pts)
        consider(_repair(_to_z(pts[:, 0], pts[:, 1], np.full(N, 0.5 / 6 * 0.95))))

    zp = _polish(pool[0][1], 2000)
    consider(zp)

    best_val, best_z = pool[0]

    rng = np.random.default_rng(20240517)

    # --- Radii reassignment / rescaling phase (new experiment) ---
    # Permute or rescale radii among fixed centres to explore different
    # contact graphs, then re-polish.
    base_x, base_y, base_r = _unpack(pool[0][1])
    while time.process_time() < radii_deadline - 0.3:
        if rng.random() < 0.5:
            r_new = base_r[rng.permutation(N)].copy()
        else:
            r_new = base_r * np.exp(rng.normal(0.0, 0.18, N))
        zc = _repair(_to_z(base_x.copy(), base_y.copy(), r_new))
        zc = _polish(zc, 800)
        consider(zc)

    best_val, best_z = pool[0]

    # --- Targeted "split largest circle" moves ---
    def try_split(src):
        x, y, r = _unpack(src)
        i = int(np.argmax(r))
        ri = r[i]
        if ri < 0.05:
            return None
        ang = rng.uniform(0, 2 * np.pi)
        sep = ri * rng.uniform(0.3, 0.9)
        nx1 = x[i] + sep * np.cos(ang)
        ny1 = y[i] + sep * np.sin(ang)
        nx2 = x[i] - sep * np.cos(ang)
        ny2 = y[i] - sep * np.sin(ang)
        j = int(np.argmin(r))
        if j == i:
            j = (i + 1) % N
        x2 = x.copy(); y2 = y.copy(); r2 = r.copy()
        x2[i], y2[i], r2[i] = nx1, ny1, ri * 0.6
        x2[j], y2[j], r2[j] = nx2, ny2, ri * 0.6
        x2 = np.clip(x2, 1e-4, 1 - 1e-4)
        y2 = np.clip(y2, 1e-4, 1 - 1e-4)
        return _to_z(x2, y2, r2)

    scales = [0.040, 0.025, 0.060, 0.018, 0.080, 0.030, 0.050, 0.015, 0.045, 0.022]
    cur_z = best_z.copy()
    cur_val = best_val
    it = 0
    stall = 0
    while time.process_time() < deadline - 0.4:
        it += 1
        if rng.random() < 0.25:
            src = pool[int(rng.integers(min(3, len(pool))))][1]
            zc = try_split(src)
            if zc is not None:
                zc = _repair(zc)
                zc = _polish(zc, 800)
                sc = _score(zc)
                if sc > cur_val + 1e-12:
                    cur_z = zc; cur_val = sc
                    stall = 0
                    if sc > best_val + 1e-12:
                        best_z = zc.copy(); best_val = sc
                        consider(zc)
                else:
                    stall += 1
                continue

        scale = scales[it % len(scales)]
        if rng.random() < 0.6:
            src = cur_z
        else:
            src = pool[int(rng.integers(len(pool)))][1]
        x, y, r = _unpack(src)
        if rng.random() < 0.5:
            k = int(rng.integers(1, max(2, N // 4)))
        else:
            k = int(rng.integers(N // 3, N + 1))
        idx = rng.choice(N, size=k, replace=False)
        ang = rng.uniform(0, 2 * np.pi, k)
        mag = rng.uniform(0.3, 1.0, k) * scale
        x[idx] += mag * np.cos(ang)
        y[idx] += mag * np.sin(ang)
        x = np.clip(x, 1e-4, 1 - 1e-4)
        y = np.clip(y, 1e-4, 1 - 1e-4)
        if rng.random() < 0.5:
            jdx = rng.choice(N, size=int(rng.integers(1, 6)), replace=False)
            r[jdx] *= (1.0 + rng.uniform(-0.08, 0.15, len(jdx)))
        zc = _repair(_to_z(x, y, r))
        zc = _polish(zc, 500)
        sc = _score(zc)
        if sc > cur_val + 1e-12:
            cur_z = zc; cur_val = sc
            stall = 0
            if sc > best_val + 1e-12:
                best_z = zc.copy(); best_val = sc
                consider(zc)
        else:
            stall += 1
            if stall > 15:
                p = pool[int(rng.integers(len(pool)))][1]
                cur_z = p.copy(); cur_val = _score(p)
                stall = 0

    if time.process_time() < deadline:
        zf = _polish(best_z, 3000)
        vf = _score(zf)
        if vf > best_val:
            best_z = zf; best_val = vf

    best = _repair(best_z)
    x = best[0::3].copy(); y = best[1::3].copy(); r = best[2::3].copy()
    r *= (1 - 1e-9)
    r = np.minimum(r, np.minimum(x, 1 - x))
    r = np.minimum(r, np.minimum(y, 1 - y))
    r = np.maximum(r, 1e-7)
    return np.column_stack([x, y, r])
