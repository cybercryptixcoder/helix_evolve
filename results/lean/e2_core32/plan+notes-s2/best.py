import numpy as np
import time
import math
from scipy.optimize import minimize, linprog
from scipy.spatial import cKDTree


def _repair(z, n):
    z = z.reshape(n, 3).copy()
    x, y, r = z[:, 0], z[:, 1], z[:, 2]
    r = np.maximum(r, 1e-6)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    for _ in range(300):
        tree = cKDTree(np.column_stack([x, y]))
        pairs = tree.query_pairs(r=0.5, output_type='ndarray')
        if len(pairs) == 0:
            break
        changed = False
        for i, j in pairs:
            d = math.hypot(x[i] - x[j], y[i] - y[j])
            s = r[i] + r[j]
            if d < s - 1e-15:
                if d < 1e-12:
                    r[i] *= 0.5
                    r[j] *= 0.5
                else:
                    f = (d / s) * (1.0 - 1e-12)
                    r[i] *= f
                    r[j] *= f
                changed = True
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
        if not changed:
            break
    z[:, 0], z[:, 1], z[:, 2] = x, y, r
    return z.reshape(-1)


def _lp_solve(centers, n, ii, jj):
    x = centers[:, 0]
    y = centers[:, 1]
    dx = x[ii] - x[jj]
    dy = y[ii] - y[jj]
    d = np.hypot(dx, dy)
    d = np.maximum(d, 1e-12)

    rows = []
    bvec = []
    for i in range(n):
        for val in (x[i], 1.0 - x[i], y[i], 1.0 - y[i]):
            row = np.zeros(n)
            row[i] = 1.0
            rows.append(row)
            bvec.append(max(val, 0.0))
    for k in range(len(ii)):
        row = np.zeros(n)
        row[ii[k]] = 1.0
        row[jj[k]] = 1.0
        rows.append(row)
        bvec.append(d[k])
    A_ub = np.array(rows)
    b_ub = np.array(bvec)
    c = -np.ones(n)
    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method='highs')
        if not res.success:
            return None, -np.inf
        return res.x, -res.fun
    except Exception:
        return None, -np.inf


def _lp_grad(centers, n, ii, jj, marg):
    x = centers[:, 0]
    y = centers[:, 1]
    g = np.zeros((n, 2))
    if marg is None:
        return None
    lam = -np.asarray(marg)
    idx = 0
    for i in range(n):
        g[i, 0] += lam[idx]; idx += 1
        g[i, 0] -= lam[idx]; idx += 1
        g[i, 1] += lam[idx]; idx += 1
        g[i, 1] -= lam[idx]; idx += 1
    dx = x[ii] - x[jj]
    dy = y[ii] - y[jj]
    d = np.maximum(np.hypot(dx, dy), 1e-12)
    for k in range(len(ii)):
        lk = lam[idx]; idx += 1
        a, b = ii[k], jj[k]
        ux = dx[k] / d[k]
        uy = dy[k] / d[k]
        g[a, 0] += lk * ux
        g[b, 0] -= lk * ux
        g[a, 1] += lk * uy
        g[b, 1] -= lk * uy
    return g


def _lp_solve_full(centers, n, ii, jj):
    """LP solve returning marginals for gradient."""
    x = centers[:, 0]
    y = centers[:, 1]
    dx = x[ii] - x[jj]
    dy = y[ii] - y[jj]
    d = np.maximum(np.hypot(dx, dy), 1e-12)
    rows = []
    bvec = []
    for i in range(n):
        for val in (x[i], 1.0 - x[i], y[i], 1.0 - y[i]):
            row = np.zeros(n)
            row[i] = 1.0
            rows.append(row)
            bvec.append(max(val, 0.0))
    for k in range(len(ii)):
        row = np.zeros(n)
        row[ii[k]] = 1.0
        row[jj[k]] = 1.0
        rows.append(row)
        bvec.append(d[k])
    A_ub = np.array(rows)
    b_ub = np.array(bvec)
    try:
        res = linprog(-np.ones(n), A_ub=A_ub, b_ub=b_ub, bounds=(0, None),
                      method='highs')
        if not res.success:
            return None, -np.inf, None
        marg = None
        try:
            marg = res.ineqlin.marginals
        except Exception:
            marg = None
        return res.x, -res.fun, marg
    except Exception:
        return None, -np.inf, None


def _final_shrink(xc, yc, r_in, n):
    r = np.maximum(r_in.copy(), 1e-11)
    for i in range(n):
        for dist in (xc[i], 1.0 - xc[i], yc[i], 1.0 - yc[i]):
            if r[i] > dist:
                r[i] = math.nextafter(dist, 0.0)
    r = np.maximum(r, 1e-11)
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(xc[i] - xc[j], yc[i] - yc[j])
            s = r[i] + r[j]
            if s > d:
                excess = s - d
                r[i] = math.nextafter(r[i] - excess / 2.0, 0.0)
                r[j] = math.nextafter(r[j] - excess / 2.0, 0.0)
    r = np.maximum(r, 1e-11)
    for _ in range(3):
        viol = False
        for i in range(n):
            for dist in (xc[i], 1.0 - xc[i], yc[i], 1.0 - yc[i]):
                if r[i] > dist:
                    r[i] = math.nextafter(r[i], 0.0)
                    viol = True
        for i in range(n):
            for j in range(i + 1, n):
                d = math.hypot(xc[i] - xc[j], yc[i] - yc[j])
                if r[i] + r[j] > d:
                    r[i] = math.nextafter(r[i], 0.0)
                    r[j] = math.nextafter(r[j], 0.0)
                    viol = True
        if not viol:
            break
    return np.maximum(r, 1e-11)


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    ii = np.array([p[0] for p in pairs])
    jj = np.array([p[1] for p in pairs])

    def time_left():
        return budget_seconds - (time.process_time() - t0)

    if start is not None:
        s = np.asarray(start, dtype=float).reshape(n, 3).copy()
        s[:, 2] = np.maximum(s[:, 2], 1e-6)
        z0 = _repair(s.reshape(-1), n).reshape(n, 3)
    else:
        pts = []
        for j in range(7):
            for i in range(5):
                pts.append(((i + 0.5) / 5.0, (j + 0.5) / 7.0))
        pts = pts[:n]
        r0 = 1.0 / 14.0 - 1e-6
        z0 = np.array([[x, y, r0] for x, y in pts], dtype=float)
        z0 = _repair(z0.reshape(-1), n).reshape(n, 3)

    # --- Phase 1: coordinate ascent on centers with exact LP radius solve ---
    # Faster, more direct than gradient ascent: try moving each center along
    # a few directions and keep best LP value.
    centers = np.clip(z0[:, :2].copy(), 1e-4, 1.0 - 1e-4)
    r, val = _lp_solve(centers, n, ii, jj)
    if r is None:
        centers = np.clip(z0[:, :2].copy(), 1e-4, 1.0 - 1e-4)
        r, val = _lp_solve(centers, n, ii, jj)
    best_val = val if np.isfinite(val) else -np.inf
    best_centers = centers.copy()
    best_r = r.copy() if r is not None else np.full(n, 1e-6)

    # Gradient ascent with LP value (uses marginals for speed)
    r, val, marg = _lp_solve_full(centers, n, ii, jj)
    lr = 0.003
    lp_end = t0 + 0.55 * budget_seconds
    it = 0
    while time.process_time() < lp_end and it < 2000:
        it += 1
        g = _lp_grad(centers, n, ii, jj, marg)
        if g is None or not np.all(np.isfinite(g)):
            break
        gn = np.linalg.norm(g)
        if gn < 1e-14:
            break
        step = lr
        accepted = False
        for _ in range(6):
            newc = centers + step * g
            newc[:, 0] = np.clip(newc[:, 0], 1e-4, 1.0 - 1e-4)
            newc[:, 1] = np.clip(newc[:, 1], 1e-4, 1.0 - 1e-4)
            rnew, vnew, mnew = _lp_solve_full(newc, n, ii, jj)
            if np.isfinite(vnew) and vnew >= val - 1e-13:
                centers = newc
                r, val, marg = rnew, vnew, mnew
                accepted = True
                if vnew > best_val:
                    best_val = vnew
                    best_centers = newc.copy()
                    best_r = rnew.copy()
                break
            step *= 0.5
        if not accepted:
            lr *= 0.6
            if lr < 1e-7:
                break

    if np.isfinite(best_val):
        r_final, v_final = _lp_solve(best_centers, n, ii, jj)
        if r_final is not None and v_final > best_val - 1e-9:
            best_centers = best_centers
            best_r = r_final

    # --- Phase 2: SLSQP polish on full (x,y,r) ---
    z = np.column_stack([best_centers, np.maximum(best_r - 1e-9, 1e-10)])
    z = _repair(z.reshape(-1), n)

    bounds = []
    for _ in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-7, 0.5))

    def neg_sum(zz):
        return -np.sum(zz.reshape(n, 3)[:, 2])

    def neg_sum_grad(zz):
        g = np.zeros_like(zz)
        g.reshape(n, 3)[:, 2] = -1.0
        return g

    def wall(zz):
        zz = zz.reshape(n, 3)
        x, y, r = zz[:, 0], zz[:, 1], zz[:, 2]
        return np.concatenate([x - r, 1.0 - x - r, y - r, 1.0 - y - r])

    def wall_grad(zz):
        g = np.zeros((4 * n, 3 * n))
        for k in range(n):
            g[k, 3 * k] = 1.0; g[k, 3 * k + 2] = -1.0
            g[n + k, 3 * k] = -1.0; g[n + k, 3 * k + 2] = -1.0
            g[2 * n + k, 3 * k + 1] = 1.0; g[2 * n + k, 3 * k + 2] = -1.0
            g[3 * n + k, 3 * k + 1] = -1.0; g[3 * n + k, 3 * k + 2] = -1.0
        return g

    def overlap(zz):
        zz = zz.reshape(n, 3)
        x, y, r = zz[:, 0], zz[:, 1], zz[:, 2]
        dx = x[ii] - x[jj]
        dy = y[ii] - y[jj]
        return dx * dx + dy * dy - (r[ii] + r[jj]) ** 2

    def overlap_grad(zz):
        zz = zz.reshape(n, 3)
        x, y, r = zz[:, 0], zz[:, 1], zz[:, 2]
        m = len(ii)
        g = np.zeros((m, 3 * n))
        dx = x[ii] - x[jj]
        dy = y[ii] - y[jj]
        rs = r[ii] + r[jj]
        for k in range(m):
            a, b = ii[k], jj[k]
            g[k, 3 * a] = 2 * dx[k]; g[k, 3 * b] = -2 * dx[k]
            g[k, 3 * a + 1] = 2 * dy[k]; g[k, 3 * b + 1] = -2 * dy[k]
            g[k, 3 * a + 2] = -2 * rs[k]; g[k, 3 * b + 2] = -2 * rs[k]
        return g

    cons = [
        {'type': 'ineq', 'fun': wall, 'jac': wall_grad},
        {'type': 'ineq', 'fun': overlap, 'jac': overlap_grad},
    ]

    best_z = z.copy()
    best_score = -neg_sum(z)

    def run_slsqp(zinit, maxiter, ftol=1e-13):
        try:
            res = minimize(neg_sum, zinit, jac=neg_sum_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter': maxiter, 'ftol': ftol, 'disp': False})
            if res.x is not None:
                zc = _repair(res.x, n)
                return zc, -neg_sum(zc)
        except Exception:
            pass
        return None, -np.inf

    if time_left() > 0.5:
        zc, val = run_slsqp(best_z, 1000)
        if zc is not None and val > best_score:
            best_score, best_z = val, zc

    # --- Phase 3: random restarts / perturbations ---
    rng = np.random.default_rng(12345)
    attempt = 0
    while time_left() > 0.7 and attempt < 40:
        attempt += 1
        scale = [0.003, 0.008, 0.02, 0.04][attempt % 4]
        zp = best_z.reshape(n, 3).copy()
        zp[:, 0] += rng.normal(0, scale, n)
        zp[:, 1] += rng.normal(0, scale, n)
        zp[:, 2] *= (1.0 + rng.normal(0, scale * 1.2, n))
        zp = _repair(zp.reshape(-1), n)
        zc, val = run_slsqp(zp, 350)
        if zc is not None and val > best_score:
            best_score, best_z = val, zc

    if time_left() > 0.3:
        zc, val = run_slsqp(best_z, 2500, ftol=1e-15)
        if zc is not None and val > best_score - 1e-6:
            best_z = zc
            best_score = max(best_score, val)

    # --- Phase 4: ULP coordinate ascent on centers with exact LP re-solve ---
    out = best_z.reshape(n, 3).copy()
    x = out[:, 0].copy()
    y = out[:, 1].copy()

    r_lp, _ = _lp_solve(np.column_stack([x, y]), n, ii, jj)
    r = np.maximum(r_lp, 1e-11) if r_lp is not None else np.maximum(out[:, 2], 1e-11)
    r = _final_shrink(x, y, r, n)
    cur_val = float(np.sum(r))
    cur_centers = np.column_stack([x, y]).copy()

    lp_count = 0
    improved = True
    while improved and lp_count < 150 and time_left() > 0.15:
        improved = False
        for i in range(n):
            if lp_count >= 150 or time_left() <= 0.15:
                break
            for k in range(2):
                if lp_count >= 150 or time_left() <= 0.15:
                    break
                base = cur_centers[i, k]
                for direction in (math.inf, -math.inf):
                    if lp_count >= 150 or time_left() <= 0.15:
                        break
                    cand = math.nextafter(base, direction)
                    if cand < 0.0 or cand > 1.0:
                        continue
                    trial = cur_centers.copy()
                    trial[i, k] = cand
                    r_try, v_try = _lp_solve(trial, n, ii, jj)
                    lp_count += 1
                    if r_try is None or not np.isfinite(v_try):
                        continue
                    r_try = _final_shrink(trial[:, 0], trial[:, 1], r_try, n)
                    v_try = float(np.sum(r_try))
                    if v_try > cur_val:
                        cur_val = v_try
                        cur_centers = trial
                        r = r_try
                        improved = True
                        break

    x = cur_centers[:, 0]
    y = cur_centers[:, 1]
    r = _final_shrink(x, y, r, n)

    return np.column_stack([x, y, r])
