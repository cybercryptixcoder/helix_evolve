import numpy as np
import time
from scipy.optimize import minimize, linprog


def _unpack(v, n):
    P = v.reshape(n, 3)
    return P[:, 0], P[:, 1], P[:, 2]


def _obj(v, n):
    return -v.reshape(n, 3)[:, 2].sum()


def _obj_jac(v, n):
    g = np.zeros_like(v)
    g.reshape(n, 3)[:, 2] = -1.0
    return g


def _build_constraints(n):
    iu = np.triu_indices(n, 1)
    ii = iu[0].copy()
    jj = iu[1].copy()
    m = len(ii)

    def cons_fun(v):
        x, y, r = _unpack(v, n)
        out = np.empty(4 * n + m)
        out[0:n] = x - r
        out[n:2 * n] = 1.0 - x - r
        out[2 * n:3 * n] = y - r
        out[3 * n:4 * n] = 1.0 - y - r
        dx = x[ii] - x[jj]
        dy = y[ii] - y[jj]
        d = np.sqrt(dx * dx + dy * dy)
        out[4 * n:] = d - r[ii] - r[jj]
        return out

    def cons_jac(v):
        x, y, r = _unpack(v, n)
        J = np.zeros((4 * n + m, 3 * n))
        idx = np.arange(n)
        J[idx, 3 * idx] = 1.0
        J[idx, 3 * idx + 2] = -1.0
        J[n + idx, 3 * idx] = -1.0
        J[n + idx, 3 * idx + 2] = -1.0
        J[2 * n + idx, 3 * idx + 1] = 1.0
        J[2 * n + idx, 3 * idx + 2] = -1.0
        J[3 * n + idx, 3 * idx + 1] = -1.0
        J[3 * n + idx, 3 * idx + 2] = -1.0
        dx = x[ii] - x[jj]
        dy = y[ii] - y[jj]
        d = np.sqrt(dx * dx + dy * dy)
        d = np.maximum(d, 1e-12)
        ux = dx / d
        uy = dy / d
        rows = 4 * n + np.arange(m)
        J[rows, 3 * ii] = ux
        J[rows, 3 * jj] = -ux
        J[rows, 3 * ii + 1] = uy
        J[rows, 3 * jj + 1] = -uy
        J[rows, 3 * ii + 2] = -1.0
        J[rows, 3 * jj + 2] = -1.0
        return J

    return {'type': 'ineq', 'fun': cons_fun, 'jac': cons_jac}


def _slsqp_run(v0, n, deadline, t0, maxiter=500):
    bounds = []
    for i in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-6, 0.5))
    cons = _build_constraints(n)
    try:
        res = minimize(_obj, v0, args=(n,), jac=_obj_jac, method='SLSQP',
                       bounds=bounds, constraints=[cons],
                       options={'maxiter': maxiter, 'ftol': 1e-14})
        if time.process_time() - t0 > deadline:
            return None
        return res
    except Exception:
        return None


def _lp_radii(x, y):
    n = len(x)
    iu = np.triu_indices(n, 1)
    ii = iu[0]
    jj = iu[1]
    m = len(ii)
    c = -np.ones(n)
    A = np.zeros((4 * n + m, n))
    b = np.zeros(4 * n + m)
    idx = np.arange(n)
    A[idx, idx] = 1.0
    b[idx] = np.maximum(x, 0.0)
    A[n + idx, idx] = 1.0
    b[n + idx] = np.maximum(1.0 - x, 0.0)
    A[2 * n + idx, idx] = 1.0
    b[2 * n + idx] = np.maximum(y, 0.0)
    A[3 * n + idx, idx] = 1.0
    b[3 * n + idx] = np.maximum(1.0 - y, 0.0)
    d = np.hypot(x[ii] - x[jj], y[ii] - y[jj])
    rows = 4 * n + np.arange(m)
    A[rows, ii] = 1.0
    A[rows, jj] = 1.0
    b[rows] = np.maximum(d, 0.0)
    bounds = [(0.0, None)] * n
    try:
        res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method='highs')
        if res.success:
            return np.maximum(res.x, 1e-9)
    except Exception:
        pass
    return None


def _feasible_score(P):
    n = P.shape[0]
    x = P[:, 0]; y = P[:, 1]; r = P[:, 2]
    if np.any(r <= 0):
        return -1.0
    if np.any(x - r < -1e-12) or np.any(1 - x - r < -1e-12):
        return -1.0
    if np.any(y - r < -1e-12) or np.any(1 - y - r < -1e-12):
        return -1.0
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    rr = r[:, None] + r[None, :]
    iu = np.triu_indices(n, 1)
    if np.any(d[iu] - rr[iu] < -1e-9):
        return -1.0
    return r.sum()


def _repair(P, n):
    P = P.copy()
    x = np.clip(P[:, 0], 0.0, 1.0)
    y = np.clip(P[:, 1], 0.0, 1.0)
    r = np.maximum(P[:, 2], 1e-6)
    for _ in range(300):
        changed = False
        maxr_wall = np.minimum.reduce([x, 1 - x, y, 1 - y])
        bad = r > maxr_wall
        if np.any(bad):
            r[bad] = maxr_wall[bad] * 0.999
            changed = True
        for i in range(n):
            for j in range(i + 1, n):
                d = np.hypot(x[i] - x[j], y[i] - y[j])
                if d < r[i] + r[j]:
                    excess = r[i] + r[j] - d
                    half = excess * 0.5 + 1e-9
                    r[i] = max(r[i] - half, 1e-8)
                    r[j] = max(r[j] - half, 1e-8)
                    changed = True
        if not changed:
            break
    r = r * (1.0 - 1e-10)
    r = np.maximum(r, 1e-9)
    P[:, 0] = x; P[:, 1] = y; P[:, 2] = r
    return P


def _lp_polish(P):
    P = P.copy()
    n = P.shape[0]
    x = P[:, 0].copy()
    y = P[:, 1].copy()
    r_lp = _lp_radii(x, y)
    if r_lp is None:
        return P
    P[:, 2] = r_lp
    for _ in range(20):
        x = P[:, 0]; y = P[:, 1]; r = P[:, 2]
        wall_ok = np.all(r <= np.minimum.reduce([x, 1 - x, y, 1 - y]) + 0.0)
        iu = np.triu_indices(n, 1)
        ii = iu[0]; jj = iu[1]
        d = np.hypot(x[ii] - x[jj], y[ii] - y[jj])
        pair_ok = np.all(r[ii] + r[jj] <= d + 0.0)
        if wall_ok and pair_ok:
            break
        P[:, 2] = P[:, 2] * (1.0 - 1e-12)
    return P


def _lp_slsqp_alternate(P0, n, deadline, t0, rounds=3, maxiter=500):
    best_P = _repair(P0, n)
    best_sc = _feasible_score(best_P)
    P = best_P.copy()
    for _ in range(rounds):
        if time.process_time() - t0 > deadline:
            break
        P_lp = _lp_polish(P)
        sc = _feasible_score(P_lp)
        if sc > best_sc:
            best_sc = sc
            best_P = P_lp.copy()
        P = P_lp
        if time.process_time() - t0 > deadline:
            break
        res = _slsqp_run(P.reshape(-1).copy(), n, deadline, t0, maxiter=maxiter)
        if res is None:
            break
        P2 = _lp_polish(res.x.reshape(n, 3).copy())
        sc = _feasible_score(P2)
        if sc > best_sc:
            best_sc = sc
            best_P = P2.copy()
        P = P2
    return best_P, best_sc


def _max_radius_at(cx, cy, x, y, r):
    m = min(cx, 1.0 - cx, cy, 1.0 - cy)
    if m <= 0:
        return 0.0
    if len(x) > 0:
        d = np.hypot(x - cx, y - cy) - r
        m = min(m, d.min())
    return max(m, 0.0)


def _insert_best(P31, deadline, t0):
    n = 31
    x = P31[:, 0]; y = P31[:, 1]; r = P31[:, 2]
    cands = []
    g = 25
    for i in range(g):
        cx = (i + 0.5) / g
        for j in range(g):
            cy = (j + 0.5) / g
            rr = _max_radius_at(cx, cy, x, y, r)
            if rr > 1e-6:
                cands.append((rr, cx, cy))
    for i in range(n):
        for j in range(i + 1, n):
            mx = 0.5 * (x[i] + x[j]); my = 0.5 * (y[i] + y[j])
            rr = _max_radius_at(mx, my, x, y, r)
            if rr > 1e-6:
                cands.append((rr, mx, my))
            for t in (1.0 / 3.0, 2.0 / 3.0):
                px = x[i] + t * (x[j] - x[i]); py = y[i] + t * (y[j] - y[i])
                rr = _max_radius_at(px, py, x, y, r)
                if rr > 1e-6:
                    cands.append((rr, px, py))
    if not cands:
        return None
    cands.sort(key=lambda z: -z[0])
    top = cands[:20]
    best_P = None
    best_sc = -1.0
    for rr, cx, cy in top:
        if time.process_time() - t0 > deadline:
            break
        P32 = np.zeros((32, 3))
        P32[:31] = P31
        P32[31] = (cx, cy, rr * 0.99)
        P32 = _repair(P32, 32)
        sc0 = _feasible_score(P32)
        if sc0 < 0:
            continue
        res = _slsqp_run(P32.reshape(-1).copy(), 32, deadline, t0, maxiter=150)
        if res is None:
            continue
        P2 = _lp_polish(res.x.reshape(32, 3).copy())
        P2, sc = _lp_slsqp_alternate(P2, 32, deadline, t0, rounds=2, maxiter=120)
        if sc > best_sc:
            best_sc = sc
            best_P = P2
    return best_P, best_sc


def _safe_finish(P):
    P = _lp_polish(P)
    x = P[:, 0]; y = P[:, 1]; r = P[:, 2]
    r = np.minimum(r, np.minimum.reduce([x, 1 - x, y, 1 - y]))
    n = P.shape[0]
    iu = np.triu_indices(n, 1)
    ii = iu[0]; jj = iu[1]
    for _ in range(50):
        d = np.hypot(x[ii] - x[jj], y[ii] - y[jj])
        viol = (r[ii] + r[jj]) - d
        if np.all(viol <= 0):
            break
        scale = np.where(viol > 0, d / np.maximum(r[ii] + r[jj], 1e-15), 1.0)
        fac = np.ones(n)
        mask = viol > 0
        np.minimum.at(fac, ii[mask], scale[mask])
        np.minimum.at(fac, jj[mask], scale[mask])
        r = r * fac * (1.0 - 1e-12)
        r = np.minimum(r, np.minimum.reduce([x, 1 - x, y, 1 - y]))
    r = np.maximum(r, 1e-9)
    P[:, 2] = r
    return P


def _kkt_polish(P, tol_active=1e-7, max_iter=30):
    n = P.shape[0]
    z = P.reshape(-1).astype(np.longdouble)
    x = z[0::3].copy()
    y = z[1::3].copy()
    r = z[2::3].copy()

    active = []
    mw = np.minimum.reduce([x, 1 - x, y, 1 - y])
    for i in range(n):
        if r[i] > mw[i] - tol_active:
            cands = [(x[i], 'xl'), (1 - x[i], 'xr'), (y[i], 'yl'), (1 - y[i], 'yr')]
            cands.sort(key=lambda t: t[0])
            active.append(('wall', i, cands[0][1]))
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sqrt((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2)
            if d - r[i] - r[j] < tol_active:
                active.append(('pair', i, j))

    m = len(active)
    if m == 0:
        return P

    def c_val(z):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        out = np.empty(m, dtype=np.longdouble)
        for k, a in enumerate(active):
            if a[0] == 'wall':
                _, i, kind = a
                if kind == 'xl':
                    out[k] = x[i] - r[i]
                elif kind == 'xr':
                    out[k] = 1 - x[i] - r[i]
                elif kind == 'yl':
                    out[k] = y[i] - r[i]
                else:
                    out[k] = 1 - y[i] - r[i]
            else:
                _, i, j = a
                out[k] = np.sqrt((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2) - r[i] - r[j]
        return out

    def c_jac(z):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        J = np.zeros((m, 3 * n), dtype=np.longdouble)
        for k, a in enumerate(active):
            if a[0] == 'wall':
                _, i, kind = a
                if kind == 'xl':
                    J[k, 3 * i] = 1; J[k, 3 * i + 2] = -1
                elif kind == 'xr':
                    J[k, 3 * i] = -1; J[k, 3 * i + 2] = -1
                elif kind == 'yl':
                    J[k, 3 * i + 1] = 1; J[k, 3 * i + 2] = -1
                else:
                    J[k, 3 * i + 1] = -1; J[k, 3 * i + 2] = -1
            else:
                _, i, j = a
                dx = x[i] - x[j]; dy = y[i] - y[j]
                d = np.sqrt(dx * dx + dy * dy)
                if d < 1e-18:
                    d = np.longdouble(1e-18)
                ux = dx / d; uy = dy / d
                J[k, 3 * i] = ux; J[k, 3 * j] = -ux
                J[k, 3 * i + 1] = uy; J[k, 3 * j + 1] = -uy
                J[k, 3 * i + 2] = -1; J[k, 3 * j + 2] = -1
        return J

    lam = np.zeros(m, dtype=np.longdouble)
    for it in range(max_iter):
        cv = c_val(z)
        Jc = c_jac(z)
        g = np.zeros(3 * n, dtype=np.longdouble)
        g[2::3] = -1.0
        F = np.concatenate([g + Jc.T @ lam, cv])
        if np.max(np.abs(F)) < np.longdouble(1e-18):
            break
        H = np.zeros((3 * n, 3 * n), dtype=np.longdouble)
        for k, a in enumerate(active):
            if a[0] == 'pair':
                _, i, j = a
                dx = x[i] - x[j]; dy = y[i] - y[j]
                d = np.sqrt(dx * dx + dy * dy)
                if d < 1e-18:
                    d = np.longdouble(1e-18)
                ux = dx / d; uy = dy / d
                hxx = (1 - ux * ux) / d
                hxy = (-ux * uy) / d
                hyy = (1 - uy * uy) / d
                lk = lam[k]
                H[3 * i, 3 * i] += lk * hxx
                H[3 * i, 3 * j] -= lk * hxx
                H[3 * j, 3 * i] -= lk * hxx
                H[3 * j, 3 * j] += lk * hxx
                H[3 * i, 3 * i + 1] += lk * hxy
                H[3 * i + 1, 3 * i] += lk * hxy
                H[3 * i, 3 * j + 1] -= lk * hxy
                H[3 * j + 1, 3 * i] -= lk * hxy
                H[3 * j, 3 * i + 1] -= lk * hxy
                H[3 * i + 1, 3 * j] -= lk * hxy
                H[3 * j, 3 * j + 1] += lk * hxy
                H[3 * j + 1, 3 * j] += lk * hxy
                H[3 * i + 1, 3 * i + 1] += lk * hyy
                H[3 * i + 1, 3 * j + 1] -= lk * hyy
                H[3 * j + 1, 3 * i + 1] -= lk * hyy
                H[3 * j + 1, 3 * j + 1] += lk * hyy
        JF = np.zeros((3 * n + m, 3 * n + m), dtype=np.longdouble)
        JF[:3 * n, :3 * n] = H
        JF[:3 * n, 3 * n:] = Jc.T
        JF[3 * n:, :3 * n] = Jc
        try:
            delta = np.linalg.lstsq(JF, -F, rcond=None)[0]
        except Exception:
            break
        z = z + delta[:3 * n]
        lam = lam + delta[3 * n:]
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        if not np.all(np.isfinite(z)):
            return P
        if np.any(r <= 0):
            return P
        if np.any(x < -1e-6) or np.any(x > 1 + 1e-6) or np.any(y < -1e-6) or np.any(y > 1 + 1e-6):
            return P

    P2 = P.copy()
    P2[:, 0] = np.asarray(x, dtype=float)
    P2[:, 1] = np.asarray(y, dtype=float)
    P2[:, 2] = np.asarray(r, dtype=float)
    return P2


def _strict_check(P):
    n = P.shape[0]
    x = P[:, 0]; y = P[:, 1]; r = P[:, 2]
    if np.any(r <= 0):
        return False
    if np.any(x - r < 0) or np.any(1 - x - r < 0):
        return False
    if np.any(y - r < 0) or np.any(1 - y - r < 0):
        return False
    iu = np.triu_indices(n, 1)
    ii = iu[0]; jj = iu[1]
    d = np.hypot(x[ii] - x[jj], y[ii] - y[jj])
    if np.any(d - r[ii] - r[jj] < 0):
        return False
    return True


def _kkt_finish(P):
    base = _safe_finish(P.copy())
    base_sc = base[:, 2].sum()
    try:
        Pk = _kkt_polish(base)
        Pk = Pk.copy()
        Pk[:, 2] = Pk[:, 2] * (1.0 - 1e-14)
        if _strict_check(Pk):
            sc = Pk[:, 2].sum()
            if sc > base_sc:
                return Pk
    except Exception:
        pass
    return base


def _basin_hop(best_P, best_score, n, deadline, t0, rng):
    """Perturb 1-3 circles, repair, LP-polish, SLSQP; accept improvements."""
    while time.process_time() - t0 < deadline:
        P = best_P.copy()
        k = int(rng.integers(1, 4))
        idx = rng.choice(n, size=k, replace=False)
        P[idx, 0] = np.clip(P[idx, 0] + rng.uniform(-0.02, 0.02, k), 0.0, 1.0)
        P[idx, 1] = np.clip(P[idx, 1] + rng.uniform(-0.02, 0.02, k), 0.0, 1.0)
        P[idx, 2] = P[idx, 2] * rng.uniform(0.9, 1.1, k)
        P = _repair(P, n)
        P = _lp_polish(P)
        if time.process_time() - t0 > deadline:
            break
        res = _slsqp_run(P.reshape(-1).copy(), n, deadline, t0, maxiter=150)
        if res is None:
            continue
        P2 = _lp_polish(res.x.reshape(n, 3).copy())
        sc = _feasible_score(P2)
        if sc > best_score:
            best_score = sc
            best_P = P2.copy()
    return best_P, best_score


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    margin = 0.4
    deadline = budget_seconds - margin

    best_P = None
    best_score = -1.0

    if start is not None:
        P0 = np.asarray(start, dtype=float).reshape(n, 3).copy()
        P0 = _repair(P0, n)
        sc = _feasible_score(P0)
        if sc > best_score:
            best_score = sc
            best_P = P0.copy()

    if best_P is None:
        P = np.zeros((n, 3))
        P[:, 0] = 0.5; P[:, 1] = 0.5; P[:, 2] = 1e-3
        best_P = _repair(P, n)
        best_score = _feasible_score(best_P)

    # Initial polish
    if time.process_time() - t0 < deadline:
        P2, sc = _lp_slsqp_alternate(best_P.copy(), n, deadline, t0, rounds=4, maxiter=500)
        if sc > best_score:
            best_score = sc
            best_P = P2

    # Basin-hopping: perturb 1-3 circles and re-optimize
    rng = np.random.default_rng(12345)
    best_P, best_score = _basin_hop(best_P, best_score, n, deadline, t0, rng)

    best_P = _kkt_finish(best_P)
    return best_P
