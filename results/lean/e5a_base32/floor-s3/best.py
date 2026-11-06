import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    rng = np.random.default_rng(1234567)

    if start is not None:
        s = np.asarray(start, dtype=float).copy()
    else:
        cols, rows = 6, 6
        pts = []
        for j in range(rows):
            for i in range(cols):
                x = (i + 0.5 + 0.5 * (j % 2)) / cols
                y = (j + 0.5) / rows
                pts.append((x, y))
        pts = pts[:n]
        s = np.array([[x, y, 0.045] for x, y in pts], dtype=float)

    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    pi = np.array([p[0] for p in pairs])
    pj = np.array([p[1] for p in pairs])
    m = len(pairs)

    def pack(c):
        v = np.empty(3 * n)
        v[:n] = c[:, 0]
        v[n:2 * n] = c[:, 1]
        v[2 * n:] = c[:, 2]
        return v

    def unpack(v):
        c = np.empty((n, 3))
        c[:, 0] = v[:n]
        c[:, 1] = v[n:2 * n]
        c[:, 2] = np.maximum(v[2 * n:], 1e-9)
        return c

    def objective(v):
        return -np.sum(v[2 * n:])

    def objective_grad(v):
        g = np.zeros(3 * n)
        g[2 * n:] = -1.0
        return g

    def constraints_vec(v):
        x = v[:n]; y = v[n:2 * n]; r = v[2 * n:]
        dx = x[pi] - x[pj]
        dy = y[pi] - y[pj]
        d = np.sqrt(dx * dx + dy * dy)
        g1 = d - (r[pi] + r[pj])
        g2 = x - r
        g3 = 1.0 - x - r
        g4 = y - r
        g5 = 1.0 - y - r
        return np.concatenate([g1, g2, g3, g4, g5])

    def constraints_jac(v):
        x = v[:n]; y = v[n:2 * n]; r = v[2 * n:]
        dx = x[pi] - x[pj]
        dy = y[pi] - y[pj]
        d = np.sqrt(dx * dx + dy * dy)
        d = np.maximum(d, 1e-12)
        J = np.zeros((m + 4 * n, 3 * n))
        ux = dx / d
        uy = dy / d
        J[np.arange(m), pi] = ux
        J[np.arange(m), pj] = -ux
        J[np.arange(m), n + pi] = uy
        J[np.arange(m), n + pj] = -uy
        J[np.arange(m), 2 * n + pi] = -1.0
        J[np.arange(m), 2 * n + pj] = -1.0
        idx = np.arange(n)
        J[m + idx, idx] = 1.0
        J[m + idx, 2 * n + idx] = -1.0
        J[m + n + idx, idx] = -1.0
        J[m + n + idx, 2 * n + idx] = -1.0
        J[m + 2 * n + idx, n + idx] = 1.0
        J[m + 2 * n + idx, 2 * n + idx] = -1.0
        J[m + 3 * n + idx, n + idx] = -1.0
        J[m + 3 * n + idx, 2 * n + idx] = -1.0
        return J

    cons = [{'type': 'ineq', 'fun': constraints_vec, 'jac': constraints_jac}]
    bounds = [(0.0, 1.0)] * (2 * n) + [(1e-6, 0.5)] * n

    def repair(c):
        c = c.copy()
        c[:, 0] = np.clip(c[:, 0], 0.0, 1.0)
        c[:, 1] = np.clip(c[:, 1], 0.0, 1.0)
        c[:, 2] = np.clip(c[:, 2], 1e-6, 0.5)
        for k in range(n):
            x, y, r = c[k]
            c[k, 2] = max(min(r, x, 1.0 - x, y, 1.0 - y), 1e-9)
        for _ in range(200):
            changed = False
            # pairwise
            dx = c[pi, 0] - c[pj, 0]
            dy = c[pi, 1] - c[pj, 1]
            d = np.hypot(dx, dy)
            need = c[pi, 2] + c[pj, 2]
            viol = need - d
            mask = viol > 0
            if np.any(mask):
                changed = True
                for k in np.where(mask)[0]:
                    i, j = pi[k], pj[k]
                    excess = viol[k]
                    si, sj = c[i, 2], c[j, 2]
                    tot = si + sj
                    if tot <= 0:
                        continue
                    c[i, 2] = max(c[i, 2] - excess * (si / tot) - 1e-12, 1e-9)
                    c[j, 2] = max(c[j, 2] - excess * (sj / tot) - 1e-12, 1e-9)
            # walls
            lim = np.minimum.reduce([c[:, 0], 1.0 - c[:, 0], c[:, 1], 1.0 - c[:, 1]])
            if np.any(c[:, 2] > lim):
                changed = True
                c[:, 2] = np.minimum(c[:, 2], lim)
            if not changed:
                break
        return c

    best_c = repair(s)
    best_val = np.sum(best_c[:, 2])

    def try_slsqp(c0, maxiter, ftol=1e-15):
        nonlocal best_c, best_val
        v0 = pack(c0)
        try:
            res = minimize(objective, v0, method='SLSQP', jac=objective_grad,
                           bounds=bounds, constraints=cons,
                           options={'maxiter': maxiter, 'ftol': ftol})
            if np.min(constraints_vec(res.x)) > -1e-7:
                c = unpack(res.x)
                c = repair(c)
                val = np.sum(c[:, 2])
                if val > best_val + 1e-12:
                    best_c = c
                    best_val = val
                    return True
        except Exception:
            pass
        return False

    try_slsqp(best_c, 2000)

    deadline = t0 + budget_seconds * 0.85

    tries = 0
    scale = 0.02
    since_improve = 0
    while time.process_time() < deadline and tries < 3000:
        tries += 1
        c0 = best_c.copy()
        mode = tries % 11
        if mode == 0:
            c0[:, 0] += rng.normal(0, 0.08, n)
            c0[:, 1] += rng.normal(0, 0.08, n)
        elif mode == 2:
            # move a small cluster
            k = rng.integers(0, n)
            d2 = np.sum((c0[:, :2] - c0[k, :2]) ** 2, axis=1)
            idxs = np.argsort(d2)[:rng.integers(3, 7)]
            dx = rng.normal(0, 0.06)
            dy = rng.normal(0, 0.06)
            c0[idxs, 0] += dx
            c0[idxs, 1] += dy
        elif mode == 4:
            # relocate a circle fully
            k = rng.integers(0, n)
            c0[k, 0] = rng.uniform(0.05, 0.95)
            c0[k, 1] = rng.uniform(0.05, 0.95)
        elif mode == 6:
            # swap radii
            a, b = rng.choice(n, size=2, replace=False)
            c0[a, 2], c0[b, 2] = c0[b, 2], c0[a, 2]
        elif mode == 8:
            # swap positions
            a, b = rng.choice(n, size=2, replace=False)
            c0[[a, b], :2] = c0[[b, a], :2]
        elif mode == 10:
            # reflect
            a = rng.integers(0, n)
            c0[a, 0] = 1.0 - c0[a, 0]
        c0[:, 0] += rng.normal(0, scale, n)
        c0[:, 1] += rng.normal(0, scale, n)
        c0[:, 2] *= np.exp(rng.normal(0, 0.05, n))
        c0 = repair(c0)
        improved = try_slsqp(c0, 500)
        if improved:
            scale = max(0.002, scale * 0.9)
            since_improve = 0
        else:
            since_improve += 1
            scale = min(0.05, scale * 1.06)
            if since_improve > 50:
                scale = 0.025
                since_improve = 0
        if time.process_time() >= deadline:
            break

    # extra local polish with slightly perturbed radii growth
    for _ in range(3):
        if time.process_time() >= deadline + budget_seconds * 0.05:
            break
        c0 = best_c.copy()
        c0[:, 2] *= 1.005
        c0 = repair(c0)
        try_slsqp(c0, 1000)

    try_slsqp(best_c, 3000)

    # strict feasibility
    c = best_c.copy()
    for _ in range(8):
        c[:, 2] = np.minimum.reduce([c[:, 2], c[:, 0], 1.0 - c[:, 0], c[:, 1], 1.0 - c[:, 1]])
        dx = c[pi, 0] - c[pj, 0]
        dy = c[pi, 1] - c[pj, 1]
        d = np.hypot(dx, dy)
        need = c[pi, 2] + c[pj, 2]
        mask = d < need
        if np.any(mask):
            for k in np.where(mask)[0]:
                i, j = pi[k], pj[k]
                nd = d[k]
                if nd > 1e-15:
                    shrink = (nd / need[k]) * (1.0 - 1e-12)
                    c[i, 2] *= shrink
                    c[j, 2] *= shrink
                else:
                    c[i, 2] *= 0.5
                    c[j, 2] *= 0.5
    c[:, 2] = np.minimum.reduce([c[:, 2], c[:, 0], 1.0 - c[:, 0], c[:, 1], 1.0 - c[:, 1]])
    c[:, 2] *= (1.0 - 1e-12)
    return c
