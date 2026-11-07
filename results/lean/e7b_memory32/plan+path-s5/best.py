import numpy as np
import time
from scipy.optimize import minimize

def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    deadline = t0 + budget_seconds - 0.7
    rng = np.random.default_rng(2024)

    def score(c):
        return c[:, 2].sum()

    def repair(circles):
        c = circles.copy()
        for _ in range(80):
            c[:, 2] = np.minimum(c[:, 2], np.minimum(c[:, 0], 1 - c[:, 0]))
            c[:, 2] = np.minimum(c[:, 2], np.minimum(c[:, 1], 1 - c[:, 1]))
            c[:, 2] = np.maximum(c[:, 2], 1e-6)
            dx = c[:, 0:1] - c[:, 0:1].T
            dy = c[:, 1:2] - c[:, 1:2].T
            d = np.sqrt(dx*dx + dy*dy)
            rs = c[:, 2:3] + c[:, 2:3].T
            overlap = rs - d
            np.fill_diagonal(overlap, 0.0)
            if overlap.max() <= 1e-10:
                break
            shrink = np.maximum(overlap, 0) * 0.5
            c[:, 2] -= shrink.max(axis=1)
            c[:, 2] = np.maximum(c[:, 2], 1e-6)
        return c

    def grow(circles, steps=300):
        c = circles.copy()
        for _ in range(steps):
            improved = False
            order = rng.permutation(n)
            for i in order:
                r_max = min(c[i, 0], 1 - c[i, 0], c[i, 1], 1 - c[i, 1])
                dx = c[i, 0] - c[:, 0]
                dy = c[i, 1] - c[:, 1]
                d = np.sqrt(dx*dx + dy*dy)
                d[i] = np.inf
                r_max = min(r_max, (d - c[:, 2]).min())
                if r_max > c[i, 2] + 1e-13:
                    c[i, 2] = r_max
                    improved = True
            if not improved:
                break
        return c

    def slsqp_polish(c, iters=200, active_only=False, ftol=1e-16):
        c = repair(c)
        v0 = np.empty(3 * n)
        v0[0::3] = c[:, 0]; v0[1::3] = c[:, 1]; v0[2::3] = c[:, 2]

        if active_only:
            dx = c[:, 0:1] - c[:, 0:1].T
            dy = c[:, 1:2] - c[:, 1:2].T
            d = np.sqrt(dx*dx + dy*dy)
            rs = c[:, 2:3] + c[:, 2:3].T
            gap = d - rs
            np.fill_diagonal(gap, np.inf)
            pairs = [(i, j) for i in range(n) for j in range(i + 1, n)
                     if gap[i, j] < 1e-2]
            wall_active = np.zeros((n, 4), dtype=bool)
            wall_active[:, 0] = (c[:, 0] - c[:, 2]) < 1e-2
            wall_active[:, 1] = (1 - c[:, 0] - c[:, 2]) < 1e-2
            wall_active[:, 2] = (c[:, 1] - c[:, 2]) < 1e-2
            wall_active[:, 3] = (1 - c[:, 1] - c[:, 2]) < 1e-2
        else:
            pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
            wall_active = np.ones((n, 4), dtype=bool)

        if len(pairs) == 0:
            pairs = [(0, 1)]
        pi = np.array([p[0] for p in pairs]); pj = np.array([p[1] for p in pairs])
        npairs = len(pairs)

        def obj(v):
            return -v[2::3].sum()

        def obj_jac(v):
            g = np.zeros(3*n); g[2::3] = -1.0; return g

        def c_pair(v):
            x = v[0::3]; y = v[1::3]; r = v[2::3]
            dx = x[pi] - x[pj]; dy = y[pi] - y[pj]; rs = r[pi] + r[pj]
            return dx*dx + dy*dy - rs*rs

        def c_pair_jac(v):
            x = v[0::3]; y = v[1::3]; r = v[2::3]
            dx = x[pi] - x[pj]; dy = y[pi] - y[pj]; rs = r[pi] + r[pj]
            J = np.zeros((npairs, 3*n))
            rows = np.arange(npairs)
            J[rows, 3*pi+0] += 2*dx; J[rows, 3*pj+0] += -2*dx
            J[rows, 3*pi+1] += 2*dy; J[rows, 3*pj+1] += -2*dy
            J[rows, 3*pi+2] += -2*rs; J[rows, 3*pj+2] += -2*rs
            return J

        wall_specs = []
        for i in range(n):
            for k in range(4):
                if wall_active[i, k]:
                    wall_specs.append((i, k))
        nwall = len(wall_specs)

        def c_box(v):
            x = v[0::3]; y = v[1::3]; r = v[2::3]
            out = np.empty(nwall + n)
            for idx, (i, k) in enumerate(wall_specs):
                if k == 0: out[idx] = x[i] - r[i]
                elif k == 1: out[idx] = 1 - x[i] - r[i]
                elif k == 2: out[idx] = y[i] - r[i]
                else: out[idx] = 1 - y[i] - r[i]
            out[nwall:] = r - 1e-7
            return out

        def c_box_jac(v):
            J = np.zeros((nwall + n, 3*n))
            for idx, (i, k) in enumerate(wall_specs):
                if k == 0:
                    J[idx, 3*i+0] = 1; J[idx, 3*i+2] = -1
                elif k == 1:
                    J[idx, 3*i+0] = -1; J[idx, 3*i+2] = -1
                elif k == 2:
                    J[idx, 3*i+1] = 1; J[idx, 3*i+2] = -1
                else:
                    J[idx, 3*i+1] = -1; J[idx, 3*i+2] = -1
            for i in range(n):
                J[nwall+i, 3*i+2] = 1
            return J

        cons = [{'type': 'ineq', 'fun': c_pair, 'jac': c_pair_jac},
                {'type': 'ineq', 'fun': c_box, 'jac': c_box_jac}]
        try:
            res = minimize(obj, v0, jac=obj_jac, method='SLSQP',
                           constraints=cons,
                           options={'maxiter': iters, 'ftol': ftol})
            v = res.x
            c2 = np.empty_like(c)
            c2[:, 0] = v[0::3]; c2[:, 1] = v[1::3]; c2[:, 2] = v[2::3]
            return repair(c2)
        except Exception:
            return c

    def penalty_polish(c, lam, iters=150):
        v0 = np.empty(3 * n)
        v0[0::3] = c[:, 0]; v0[1::3] = c[:, 1]; v0[2::3] = c[:, 2]

        def obj(v):
            x = v[0::3]; y = v[1::3]; r = v[2::3]
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx*dx + dy*dy)
            rs = r[:, None] + r[None, :]
            ov = np.maximum(0.0, rs - d)
            np.fill_diagonal(ov, 0.0)
            pen = (ov*ov).sum()
            wv = (np.maximum(0.0, r - x) + np.maximum(0.0, r - (1 - x))
                  + np.maximum(0.0, r - y) + np.maximum(0.0, r - (1 - y)))
            pen += (wv*wv).sum()
            return -r.sum() + lam * pen

        def obj_jac(v):
            x = v[0::3]; y = v[1::3]; r = v[2::3]
            g = np.zeros(3*n)
            g[2::3] = -1.0
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx*dx + dy*dy) + 1e-12
            rs = r[:, None] + r[None, :]
            ov = rs - d
            mask = ov > 0
            np.fill_diagonal(mask, False)
            ovp = np.where(mask, ov, 0.0)
            coef = 2.0 * ovp * (-1.0 / d)
            gx = (coef * dx).sum(axis=1) - (coef * dx).sum(axis=0)
            gy = (coef * dy).sum(axis=1) - (coef * dy).sum(axis=0)
            gr = 2.0 * ovp.sum(axis=1)
            g[0::3] += lam * gx
            g[1::3] += lam * gy
            g[2::3] += lam * gr
            wx = np.zeros(n); wy = np.zeros(n); wr = np.zeros(n)
            a = np.maximum(0.0, r - x); wx -= 2*a; wr += 2*a
            a = np.maximum(0.0, r + x - 1); wx += 2*a; wr += 2*a
            a = np.maximum(0.0, r - y); wy -= 2*a; wr += 2*a
            a = np.maximum(0.0, r + y - 1); wy += 2*a; wr += 2*a
            g[0::3] += lam * wx
            g[1::3] += lam * wy
            g[2::3] += lam * wr
            return g

        try:
            res = minimize(obj, v0, jac=obj_jac, method='L-BFGS-B',
                           options={'maxiter': iters, 'ftol': 1e-14, 'gtol': 1e-10})
            v = res.x
            c2 = np.empty_like(c)
            c2[:, 0] = v[0::3]; c2[:, 1] = v[1::3]; c2[:, 2] = v[2::3]
            return c2
        except Exception:
            return c

    def penalty_path(c):
        cur = c.copy()
        for lam in (1e2, 1e3, 1e4, 1e5):
            cur = penalty_polish(cur, lam, iters=120)
        cur = repair(cur)
        cur = slsqp_polish(cur, iters=150, active_only=False)
        return cur

    def largest_empty_disk(c_keep, mask_keep, grid=200):
        # c_keep: (n,3) with deleted circles having r=0 (ignored via mask_keep)
        xs = (np.arange(grid) + 0.5) / grid
        X, Y = np.meshgrid(xs, xs, indexing='ij')
        Xf = X.ravel(); Yf = Y.ravel()
        # wall distance
        rwall = np.minimum(np.minimum(Xf, 1 - Xf), np.minimum(Yf, 1 - Yf))
        best_r = rwall.copy()
        for i in range(n):
            if not mask_keep[i]:
                continue
            xi, yi, ri = c_keep[i]
            d = np.sqrt((Xf - xi)**2 + (Yf - yi)**2)
            best_r = np.minimum(best_r, d - ri)
        idx = int(np.argmax(best_r))
        return Xf[idx], Yf[idx], best_r[idx]

    if start is not None:
        best_c = repair(np.asarray(start, dtype=float).copy())
        best_c = grow(best_c, 300)
    else:
        k = 6
        init = np.zeros((n, 3))
        idx = 0
        for j in range(k):
            for i in range(k):
                if idx < n:
                    init[idx] = ((i+0.5)/k, (j+0.5)/k, 0.04)
                    idx += 1
        best_c = grow(repair(init), 400)
    best_s = score(best_c)

    c = penalty_path(best_c)
    s = score(c)
    if s > best_s:
        best_s, best_c = s, c.copy()

    # Reinsertion loop: remove 2-3 smallest, reinsert at largest empty disks
    it = 0
    while time.process_time() < deadline:
        it += 1
        k_remove = 2 + (it % 2)  # 2 or 3
        c2 = best_c.copy()
        order = np.argsort(c2[:, 2])
        removed = order[:k_remove]
        mask_keep = np.ones(n, dtype=bool)
        mask_keep[removed] = False
        # Zero out removed radii for empty-disk search
        c_search = c2.copy()
        c_search[removed, 2] = 0.0
        for i in removed:
            x, y, r_empty = largest_empty_disk(c_search, mask_keep, grid=200)
            c2[i, 0] = x
            c2[i, 1] = y
            c2[i, 2] = max(0.8 * r_empty, 1e-3)
            # update search: this circle now blocks
            c_search[i] = c2[i]
            mask_keep[i] = True
        c2 = repair(c2)
        c2 = grow(c2, 300)
        c2 = penalty_path(c2)
        c2 = slsqp_polish(c2, iters=200, active_only=True)
        s2 = score(c2)
        if s2 > best_s + 1e-10:
            best_s, best_c = s2, c2.copy()

    if time.process_time() < deadline + 0.3:
        c2 = slsqp_polish(best_c, iters=400, active_only=False, ftol=1e-18)
        s2 = score(c2)
        if s2 > best_s:
            best_s, best_c = s2, c2.copy()

    c = best_c.copy()
    c[:, 2] = np.maximum(c[:, 2] - 2e-9, 1e-7)
    c[:, 0] = np.clip(c[:, 0], c[:, 2], 1 - c[:, 2])
    c[:, 1] = np.clip(c[:, 1], c[:, 2], 1 - c[:, 2])

    # Final exact inflation pass
    c = c.copy()
    for _ in range(200):
        changed = False
        for i in range(n):
            xi, yi, ri = c[i]
            rmax = min(xi, 1 - xi, yi, 1 - yi)
            dx = xi - c[:, 0]
            dy = yi - c[:, 1]
            d = np.sqrt(dx*dx + dy*dy)
            d[i] = np.inf
            rmax = min(rmax, (d - c[:, 2]).min())
            newr = rmax - 1e-12
            if newr > ri + 1e-14:
                c[i, 2] = newr
                changed = True
        if not changed:
            break

    # Global scale-up if there is slack everywhere
    dx = c[:, 0:1] - c[:, 0:1].T
    dy = c[:, 1:2] - c[:, 1:2].T
    d = np.sqrt(dx*dx + dy*dy)
    rs = c[:, 2:3] + c[:, 2:3].T
    np.fill_diagonal(d, np.inf)
    pair_ratio = (d / np.maximum(rs, 1e-30)).min()
    wall_ratio = (np.minimum(np.minimum(c[:, 0], 1 - c[:, 0]),
                             np.minimum(c[:, 1], 1 - c[:, 1])) / c[:, 2]).min()
    s = min(pair_ratio, wall_ratio)
    if s > 1:
        c[:, 2] *= s * (1 - 1e-12)

    return c
