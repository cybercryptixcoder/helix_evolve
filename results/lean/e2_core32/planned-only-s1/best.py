import numpy as np
import time
import math
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85
    n = 32

    def feasible(c, tol=0.0):
        x = c[:, 0]; y = c[:, 1]; r = c[:, 2]
        if np.any(r <= 0):
            return False
        if np.any(x - r < -tol) or np.any(x + r > 1 + tol) or \
           np.any(y - r < -tol) or np.any(y + r > 1 + tol):
            return False
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d2 = dx * dx + dy * dy
        rs = r[:, None] + r[None, :]
        np.fill_diagonal(d2, 1e9)
        if np.any(d2 < rs * rs - tol):
            return False
        return True

    def relax(c, sweeps=30):
        c = c.copy()
        for _ in range(sweeps):
            x = c[:, 0].copy(); y = c[:, 1].copy(); r = c[:, 2].copy()
            for i in range(n):
                for j in range(i + 1, n):
                    dx = x[j] - x[i]; dy = y[j] - y[i]
                    d = math.hypot(dx, dy)
                    need = r[i] + r[j]
                    if d < need and d > 1e-12:
                        push = (need - d) * 0.5
                        ux = dx / d; uy = dy / d
                        x[i] -= ux * push; y[i] -= uy * push
                        x[j] += ux * push; y[j] += uy * push
            for i in range(n):
                ri = r[i]
                if x[i] < ri: x[i] = ri
                elif x[i] > 1 - ri: x[i] = 1 - ri
                if y[i] < ri: y[i] = ri
                elif y[i] > 1 - ri: y[i] = 1 - ri
            c[:, 0] = x; c[:, 1] = y
        return c

    if start is not None:
        cfg = np.array(start, dtype=float).copy()
    else:
        pts = []
        for j in range(4):
            for i in range(8):
                pts.append([(i + 0.5) / 8.0, (j + 0.5) / 4.0, 0.05])
        cfg = np.array(pts, dtype=float)

    if not feasible(cfg):
        cfg = relax(cfg, 50)
    best = cfg.copy()
    best_score = best[:, 2].sum() if feasible(best) else -1e9

    def build_cons(m):
        iu = np.triu_indices(m, 1)
        ncons = 4 * m + m * (m - 1) // 2

        def cons_fun(z):
            x = z[0::3]; y = z[1::3]; r = z[2::3]
            cons = [x - r, 1 - x - r, y - r, 1 - y - r]
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d2 = dx * dx + dy * dy
            rs = r[:, None] + r[None, :]
            cons.append(d2[iu] - rs[iu] ** 2)
            return np.concatenate(cons)

        def cons_jac(z):
            x = z[0::3]; y = z[1::3]; r = z[2::3]
            J = np.zeros((ncons, 3 * m))
            for i in range(m):
                J[i, 3 * i] = 1.0; J[i, 3 * i + 2] = -1.0
                J[m + i, 3 * i] = -1.0; J[m + i, 3 * i + 2] = -1.0
                J[2 * m + i, 3 * i + 1] = 1.0; J[2 * m + i, 3 * i + 2] = -1.0
                J[3 * m + i, 3 * i + 1] = -1.0; J[3 * m + i, 3 * i + 2] = -1.0
            row = 4 * m
            for i in range(m):
                for j in range(i + 1, m):
                    dx = x[i] - x[j]; dy = y[i] - y[j]
                    ri = r[i]; rj = r[j]
                    J[row, 3 * i] = 2 * dx
                    J[row, 3 * i + 1] = 2 * dy
                    J[row, 3 * i + 2] = -2 * (ri + rj)
                    J[row, 3 * j] = -2 * dx
                    J[row, 3 * j + 1] = -2 * dy
                    J[row, 3 * j + 2] = -2 * (ri + rj)
                    row += 1
            return J

        return cons_fun, cons_jac

    def run_slsqp(cfg_in, maxiter, m=None):
        if m is None:
            m = cfg_in.shape[0]
        z0 = np.empty(3 * m)
        z0[0::3] = cfg_in[:, 0]
        z0[1::3] = cfg_in[:, 1]
        z0[2::3] = cfg_in[:, 2]
        bounds = [(0.0, 1.0)] * (3 * m)
        for i in range(m):
            bounds[3 * i + 2] = (1e-6, 0.5)
        cf, cj = build_cons(m)
        constraints = [{'type': 'ineq', 'fun': cf, 'jac': cj}]

        def obj(z):
            return -np.sum(z[2::3])

        def obj_grad(z):
            g = np.zeros_like(z)
            g[2::3] = -1.0
            return g

        try:
            res = minimize(obj, z0, jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=constraints,
                           options={'maxiter': maxiter, 'ftol': 1e-12})
            zr = res.x
            return np.column_stack([zr[0::3], zr[1::3], zr[2::3]])
        except Exception:
            return None

    # Initial unweighted polish
    cand = run_slsqp(best, 150)
    if cand is not None:
        c2 = cand.copy()
        c2[:, 2] -= 1e-9
        if feasible(c2) and c2[:, 2].sum() > best_score:
            best = c2.copy()
            best_score = c2[:, 2].sum()

    # Coarse grid for insertion search (160x160)
    gx, gy = np.meshgrid(np.linspace(0, 1, 160), np.linspace(0, 1, 160))
    gx = gx.ravel(); gy = gy.ravel()

    rng = np.random.default_rng(98765)

    def try_accept(cand):
        nonlocal best, best_score
        if cand is None:
            return False
        c2 = cand.copy()
        c2[:, 2] -= 1e-9
        if feasible(c2):
            s = c2[:, 2].sum()
            if s > best_score + 1e-12:
                best = c2.copy()
                best_score = s
                return True
        return False

    def clearance_at(px, py, sx, sy, sr):
        dx = px - sx
        dy = py - sy
        d = np.sqrt(dx * dx + dy * dy) - sr
        clear = d.min()
        wall = min(px, 1 - px, py, 1 - py)
        return min(clear, wall)

    def find_insertion(sub_res):
        sx = sub_res[:, 0]; sy = sub_res[:, 1]; sr = sub_res[:, 2]
        dx = gx[:, None] - sx[None, :]
        dy = gy[:, None] - sy[None, :]
        d = np.sqrt(dx * dx + dy * dy) - sr[None, :]
        clear = d.min(axis=1)
        wall = np.minimum(np.minimum(gx, 1 - gx), np.minimum(gy, 1 - gy))
        clr = np.minimum(clear, wall)
        k = int(np.argmax(clr))
        bx = gx[k]; by = gy[k]
        # Local refinements: 21x21 grids of shrinking side
        for side in (0.0125, 0.003125, 0.00078125):
            half = side * 0.5
            xs = np.linspace(bx - half, bx + half, 21)
            ys = np.linspace(by - half, by + half, 21)
            xs = np.clip(xs, 0.0, 1.0)
            ys = np.clip(ys, 0.0, 1.0)
            best_c = -1e18
            best_pt = (bx, by)
            for yy in ys:
                for xx in xs:
                    c = clearance_at(xx, yy, sx, sy, sr)
                    if c > best_c:
                        best_c = c
                        best_pt = (xx, yy)
            bx, by = best_pt
        # Exact clearance for chosen point
        newr = clearance_at(bx, by, sx, sy, sr) - 1e-9
        if newr < 1e-6:
            newr = 1e-6
        return np.array([bx, by, newr])

    sweep = 0
    while time.process_time() < deadline and sweep < 50:
        sweep += 1
        improved_any = False
        perm = rng.permutation(n)
        for idx in perm:
            if time.process_time() >= deadline:
                break
            mask = np.ones(n, dtype=bool)
            mask[idx] = False
            sub = best[mask].copy()
            sub_res = run_slsqp(sub, 200, m=n - 1)
            if sub_res is None:
                continue
            sub_res[:, 2] -= 1e-9
            if not feasible(sub_res):
                continue
            newc = find_insertion(sub_res)
            full = np.vstack([sub_res, newc[None, :]])
            res = run_slsqp(full, 300)
            if try_accept(res):
                improved_any = True
        if not improved_any:
            break

    out = best.copy()
    out[:, 2] -= 1e-9
    if not feasible(out):
        out = relax(out, 50)
        out[:, 2] -= 1e-8
        if not feasible(out):
            if start is not None:
                out = np.array(start, dtype=float).copy()
                out[:, 2] -= 1e-8
    return out
