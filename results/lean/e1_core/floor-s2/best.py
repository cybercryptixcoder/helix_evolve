import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    # leave a generous margin for the final feasibility fix
    budget = budget_seconds * 0.80
    n = 26
    ii, jj = np.triu_indices(n, 1)
    m = len(ii)

    def elapsed():
        return time.process_time() - t0

    # ---------- feasibility projection on radii ----------
    def make_feasible(x, y, r):
        r = np.array(r, dtype=float)
        lim = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        r = np.minimum(r, lim)
        r = np.maximum(r, 1e-12)
        for _ in range(600):
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d2 = dx * dx + dy * dy
            d = np.sqrt(d2)
            np.fill_diagonal(d, 1e9)
            rs = r[:, None] + r[None, :]
            viol = rs - d
            np.fill_diagonal(viol, 0.0)
            vmax = viol.max()
            if vmax <= 1e-14:
                break
            need = np.maximum(viol.max(axis=1), 0.0)
            r = r - need / 2
            r = np.maximum(r, 1e-12)
            r = np.minimum(r, lim)
        return r

    # ---------- SLSQP refine ----------
    def refine(x0, y0, r0, maxiter, ftol=1e-14):
        z0 = np.concatenate([x0, y0, r0])

        def obj(z):
            return -np.sum(z[2 * n:])

        def obj_grad(z):
            g = np.zeros_like(z)
            g[2 * n:] = -1.0
            return g

        def cons(z):
            x = z[:n]; y = z[n:2 * n]; r = z[2 * n:]
            c = np.empty(4 * n + m)
            c[:n] = x - r
            c[n:2 * n] = 1 - x - r
            c[2 * n:3 * n] = y - r
            c[3 * n:4 * n] = 1 - y - r
            dx = x[ii] - x[jj]
            dy = y[ii] - y[jj]
            c[4 * n:] = np.sqrt(dx * dx + dy * dy) - (r[ii] + r[jj])
            return c

        def cons_jac(z):
            x = z[:n]; y = z[n:2 * n]
            J = np.zeros((4 * n + m, 3 * n))
            ar = np.arange(n)
            J[ar, ar] = 1.0
            J[ar, 2 * n + ar] = -1.0
            J[n + ar, ar] = -1.0
            J[n + ar, 2 * n + ar] = -1.0
            J[2 * n + ar, n + ar] = 1.0
            J[2 * n + ar, 2 * n + ar] = -1.0
            J[3 * n + ar, n + ar] = -1.0
            J[3 * n + ar, 2 * n + ar] = -1.0
            dx = x[ii] - x[jj]
            dy = y[ii] - y[jj]
            d = np.sqrt(dx * dx + dy * dy) + 1e-15
            base = 4 * n
            ux = dx / d; uy = dy / d
            rows = base + np.arange(m)
            J[rows, ii] = ux
            J[rows, jj] = -ux
            J[rows, n + ii] = uy
            J[rows, n + jj] = -uy
            J[rows, 2 * n + ii] = -1.0
            J[rows, 2 * n + jj] = -1.0
            return J

        bounds = [(0.0, 1.0)] * (2 * n) + [(1e-9, 0.5)] * n
        try:
            res = minimize(obj, z0, jac=obj_grad, method='SLSQP',
                           bounds=bounds,
                           constraints=[{'type': 'ineq', 'fun': cons, 'jac': cons_jac}],
                           options={'maxiter': maxiter, 'ftol': ftol})
            z = res.x
        except Exception:
            return x0, y0, r0, -np.inf
        return z[:n], z[n:2 * n], z[2 * n:], -obj(z)

    # ---------- initial ----------
    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.shape == (n, 3):
            x0 = s[:, 0].copy(); y0 = s[:, 1].copy(); r0 = s[:, 2].copy()
        else:
            x0 = np.full(n, 0.5); y0 = np.full(n, 0.5); r0 = np.full(n, 0.05)
    else:
        x0 = np.zeros(n); y0 = np.zeros(n)
        idx = 0
        for j in range(5):
            for i in range(6):
                if idx >= n:
                    break
                x0[idx] = (i + 0.5 + (0.5 if j % 2 else 0.0)) / 6
                y0[idx] = (j + 0.5) / 5
                idx += 1
        x0 = np.clip(x0, 0.05, 0.95)
        y0 = np.clip(y0, 0.05, 0.95)
        r0 = np.full(n, 0.05)

    r0 = make_feasible(x0, y0, r0)
    best_x, best_y, best_r = x0.copy(), y0.copy(), r0.copy()
    best_val = float(np.sum(best_r))

    # initial polish (heavier, since we have a good start)
    x, y, r, val = refine(best_x, best_y, best_r, maxiter=3000)
    if np.isfinite(val):
        r = make_feasible(x, y, r)
        v = float(np.sum(r))
        if v > best_val:
            best_val = v
            best_x, best_y, best_r = x.copy(), y.copy(), r.copy()

    rng = np.random.default_rng(20240917 + int(time.time()) % 1000)
    pool = [(best_val, best_x.copy(), best_y.copy(), best_r.copy())]
    scale = 0.5
    rounds = 0
    stall = 0

    # ---------- main loop ----------
    while elapsed() < budget:
        rounds += 1
        mode = rounds % 10

        if mode == 0 and len(pool) > 1:
            pool.sort(key=lambda t: -t[0])
            _, xa, ya, ra = pool[0]
            _, xb, yb, rb = pool[min(1, len(pool) - 1)]
            mask = rng.random(n) < 0.5
            x = np.where(mask, xa, xb)
            y = np.where(mask, ya, yb)
            r = np.where(mask, ra, rb)
            x += rng.normal(0, 0.005 * scale, n)
            y += rng.normal(0, 0.005 * scale, n)
            r += rng.normal(0, 0.002 * scale, n)
        else:
            x = best_x.copy(); y = best_y.copy(); r = best_r.copy()
            if mode == 1:
                k = int(rng.integers(2, 6))
                idxs = rng.choice(n, size=k, replace=False)
                x[idxs] += rng.normal(0, 0.010 * scale, k)
                y[idxs] += rng.normal(0, 0.010 * scale, k)
                r[idxs] += rng.normal(0, 0.004 * scale, k)
            elif mode == 2:
                r *= (1 - 0.02 * scale)
                x += rng.normal(0, 0.004 * scale, n)
                y += rng.normal(0, 0.004 * scale, n)
            elif mode == 3:
                x += rng.normal(0, 0.006 * scale, n)
                y += rng.normal(0, 0.006 * scale, n)
                r += rng.normal(0, 0.002 * scale, n)
            elif mode == 4:
                idxs = rng.choice(n, size=int(rng.integers(1, 4)), replace=False)
                r[idxs] *= (1 + 0.02 * scale)
                x += rng.normal(0, 0.002 * scale, n)
                y += rng.normal(0, 0.002 * scale, n)
            elif mode == 5:
                x += rng.normal(0, 0.015 * scale, n)
                y += rng.normal(0, 0.015 * scale, n)
                r += rng.normal(0, 0.006 * scale, n)
            elif mode == 6:
                order = np.argsort(r)
                idxs = order[:int(rng.integers(1, 4))]
                r[idxs] *= (1 + 0.03 * scale)
                x[idxs] += rng.normal(0, 0.006 * scale, len(idxs))
                y[idxs] += rng.normal(0, 0.006 * scale, len(idxs))
            elif mode == 7:
                # swap two circles
                a, b = rng.choice(n, size=2, replace=False)
                x[a], x[b] = x[b], x[a]
                y[a], y[b] = y[b], y[a]
                x += rng.normal(0, 0.004 * scale, n)
                y += rng.normal(0, 0.004 * scale, n)
            elif mode == 8:
                # reflect a circle across the square about its nearest wall
                a = int(rng.integers(0, n))
                w = rng.integers(0, 4)
                if w == 0:   x[a] = 1 - x[a]
                elif w == 1: x[a] = 1 - x[a]
                elif w == 2: y[a] = 1 - y[a]
                else:        y[a] = 1 - y[a]
                x += rng.normal(0, 0.003 * scale, n)
                y += rng.normal(0, 0.003 * scale, n)
            else:
                ang = rng.uniform(0, 2 * np.pi, n)
                mag = rng.uniform(0, 0.008 * scale, n)
                x += mag * np.cos(ang)
                y += mag * np.sin(ang)
                r += rng.normal(0, 0.002 * scale, n)

        x = np.clip(x, 1e-4, 1 - 1e-4)
        y = np.clip(y, 1e-4, 1 - 1e-4)
        r = np.maximum(r, 1e-4)
        r = make_feasible(x, y, r)

        if elapsed() >= budget:
            break
        x2, y2, r2, val = refine(x, y, r, maxiter=300)
        if np.isfinite(val):
            r2 = make_feasible(x2, y2, r2)
            v = float(np.sum(r2))
            if v > best_val + 1e-12:
                best_val = v
                best_x, best_y, best_r = x2.copy(), y2.copy(), r2.copy()
                scale = max(0.25, scale * 0.9)
                stall = 0
            else:
                scale = min(2.5, scale * 1.04)
                stall += 1
            pool.append((v, x2.copy(), y2.copy(), r2.copy()))
            pool.sort(key=lambda t: -t[0])
            pool = pool[:8]
            if stall > 40:
                scale = min(3.0, scale * 1.5)
                stall = 0

    # ---------- final polish ----------
    while elapsed() < budget * 0.97:
        x2, y2, r2, val = refine(best_x, best_y, best_r, maxiter=1500, ftol=1e-16)
        if not np.isfinite(val):
            break
        r2 = make_feasible(x2, y2, r2)
        v = float(np.sum(r2))
        if v > best_val + 1e-13:
            best_val = v
            best_x, best_y, best_r = x2.copy(), y2.copy(), r2.copy()
        else:
            break

    x = best_x.copy(); y = best_y.copy(); r = best_r.copy()
    r = make_feasible(x, y, r)
    sol = np.column_stack([x, y, r])

    def ok(sol):
        x = sol[:, 0]; y = sol[:, 1]; r = sol[:, 2]
        if np.any(r <= 0):
            return False
        if np.any(x - r < 0) or np.any(x + r > 1):
            return False
        if np.any(y - r < 0) or np.any(y + r > 1):
            return False
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        np.fill_diagonal(d, 1e9)
        return bool(np.all(d >= rs))

    # robust safety shrink
    while not ok(sol):
        sol[:, 2] *= 0.999
        sol[:, 0] = np.clip(sol[:, 0], sol[:, 2], 1 - sol[:, 2])
        sol[:, 1] = np.clip(sol[:, 1], sol[:, 2], 1 - sol[:, 2])
    return sol
