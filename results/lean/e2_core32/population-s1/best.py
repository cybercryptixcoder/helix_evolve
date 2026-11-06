import numpy as np
import time
from scipy.optimize import minimize, linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.80
    N = 32
    rng = np.random.default_rng(int(t0 * 1e6) % 100000)

    ii, jj = np.triu_indices(N, 1)
    npairs = len(ii)

    def feasible(c, eps=0.0):
        x = c[:, 0]; y = c[:, 1]; r = c[:, 2]
        if np.any(r <= 0):
            return False
        if np.any(x - r < -eps) or np.any(x + r > 1 + eps):
            return False
        if np.any(y - r < -eps) or np.any(y + r > 1 + eps):
            return False
        dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
        rr = r[ii] + r[jj]
        if np.any(dx * dx + dy * dy < (rr - eps) ** 2):
            return False
        return True

    def safe(c, shrink=1e-10):
        c = c.copy()
        c[:, 2] = np.maximum(c[:, 2], 1e-9)
        c[:, 2] *= (1.0 - shrink)
        for _ in range(20000):
            if feasible(c, 0.0):
                return c
            c[:, 2] *= 0.9995
        return c

    def score(c):
        return float(c[:, 2].sum())

    # LP for radii given centers
    A_wall = np.zeros((N, N + 1))
    for i in range(N):
        A_wall[i, i] = 1.0
    A_pair = np.zeros((npairs, N + 1))
    A_pair[np.arange(npairs), ii] = 1.0
    A_pair[np.arange(npairs), jj] = 1.0
    A_sum = np.zeros((1, N + 1))
    A_sum[0, :N] = 1.0
    A_sum[0, -1] = -1.0
    A_ub = np.vstack([A_wall, A_pair, A_sum])
    cvec = np.zeros(N + 1); cvec[-1] = -1.0
    bounds_lp = [(0, None)] * N + [(None, None)]

    def lp_radii(c):
        x = c[:, 0]; y = c[:, 1]
        lim = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
        d = np.sqrt(dx * dx + dy * dy)
        b = np.concatenate([lim, d, [0.0]])
        try:
            res = linprog(cvec, A_ub=A_ub, b_ub=b, bounds=bounds_lp, method='highs')
            if res.success:
                out = c.copy()
                out[:, 2] = np.maximum(res.x[:N], 1e-9)
                return out
        except Exception:
            pass
        return c

    # SLSQP jacobian
    mcon = 4 * N + npairs + N
    Jconst = np.zeros((mcon, 3 * N))
    idx = 0
    for k in range(N):
        Jconst[idx, k] = 1.0; Jconst[idx, 2 * N + k] = -1.0; idx += 1
    for k in range(N):
        Jconst[idx, k] = -1.0; Jconst[idx, 2 * N + k] = -1.0; idx += 1
    for k in range(N):
        Jconst[idx, N + k] = 1.0; Jconst[idx, 2 * N + k] = -1.0; idx += 1
    for k in range(N):
        Jconst[idx, N + k] = -1.0; Jconst[idx, 2 * N + k] = -1.0; idx += 1
    pair_start = idx
    idx += npairs
    for k in range(N):
        Jconst[idx, 2 * N + k] = 1.0; idx += 1

    def slsqp(c, max_iter=300):
        z0 = np.concatenate([c[:, 0], c[:, 1], c[:, 2]])

        def obj(z):
            return -z[2 * N:].sum()

        def grad(z):
            g = np.zeros(3 * N); g[2 * N:] = -1.0
            return g

        def ineq(z):
            x = z[:N]; y = z[N:2 * N]; r = z[2 * N:]
            dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
            d = np.sqrt(dx * dx + dy * dy)
            return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r,
                                   d - (r[ii] + r[jj]), r])

        def ineq_jac(z):
            x = z[:N]; y = z[N:2 * N]; r = z[2 * N:]
            J = Jconst.copy()
            dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
            d = np.sqrt(np.maximum(dx * dx + dy * dy, 1e-20))
            ux = dx / d; uy = dy / d
            rows = pair_start + np.arange(npairs)
            J[rows, ii] = ux
            J[rows, jj] = -ux
            J[rows, N + ii] = uy
            J[rows, N + jj] = -uy
            J[rows, 2 * N + ii] = -1.0
            J[rows, 2 * N + jj] = -1.0
            return J

        bounds = [(0.0, 1.0)] * (2 * N) + [(1e-9, 0.5)] * N
        try:
            res = minimize(obj, z0, jac=grad, method='SLSQP', bounds=bounds,
                           constraints=[{'type': 'ineq', 'fun': ineq, 'jac': ineq_jac}],
                           options={'maxiter': max_iter, 'ftol': 1e-15})
            z = res.x
        except Exception:
            return c
        return np.column_stack([z[:N], z[N:2 * N], z[2 * N:]])

    def polish(c, iters=2, slsqp_iters=200):
        c = safe(c)
        for _ in range(iters):
            c2 = lp_radii(c)
            c2 = safe(c2)
            if score(c2) < score(c) - 1e-12:
                break
            c = c2
        c2 = slsqp(c, max_iter=slsqp_iters)
        c2 = safe(c2)
        if score(c2) > score(c):
            c = c2
        c = lp_radii(c)
        c = safe(c)
        return c

    def resolve(x, y, r, iters=100):
        x = x.copy(); y = y.copy()
        for _ in range(iters):
            dx = x[jj] - x[ii]; dy = y[jj] - y[ii]
            d2 = dx * dx + dy * dy
            d = np.sqrt(np.maximum(d2, 1e-24))
            need = r[ii] + r[jj]
            overlap = need - d
            mask = overlap > 0
            if not np.any(mask):
                break
            push = 0.5 * overlap[mask]
            ux = dx[mask] / d[mask]; uy = dy[mask] / d[mask]
            np.add.at(x, ii[mask], -push * ux)
            np.add.at(x, jj[mask], push * ux)
            np.add.at(y, ii[mask], -push * uy)
            np.add.at(y, jj[mask], push * uy)
            x = np.clip(x, r, 1.0 - r)
            y = np.clip(y, r, 1.0 - r)
        return x, y

    best = None
    if start is not None:
        s = np.asarray(start, dtype=float).copy()
        if s.shape == (N, 3):
            best = safe(s)

    if best is not None:
        best = polish(best, iters=4, slsqp_iters=500)
        for _ in range(3):
            if time.process_time() >= deadline:
                break
            b2 = slsqp(best, max_iter=600)
            b2 = safe(b2)
            b2 = lp_radii(b2); b2 = safe(b2)
            if score(b2) > score(best) + 1e-13:
                best = b2
            else:
                break

    best_score = score(best) if best is not None else -1.0
    stall = 0
    archive = [best.copy()] if best is not None else []

    while time.process_time() < deadline:
        if best is None:
            P = np.zeros((N, 3))
            P[:, 0] = rng.uniform(0.1, 0.9, N)
            P[:, 1] = rng.uniform(0.1, 0.9, N)
            P[:, 2] = 0.05
            x, y = resolve(P[:, 0], P[:, 1], P[:, 2], iters=250)
            P[:, 0] = x; P[:, 1] = y
            best = polish(safe(P), iters=2, slsqp_iters=300)
            best_score = score(best)
            archive = [best.copy()]
            continue

        if len(archive) > 1 and rng.random() < 0.3:
            parent = archive[rng.integers(0, len(archive))].copy()
        else:
            parent = best.copy()

        scale = 0.02 * (0.9 ** min(stall, 20))
        if rng.random() < 0.1:
            scale *= 4.0

        mode = rng.integers(0, 5)
        if mode == 0:
            k = rng.integers(2, 7)
            sel = rng.choice(N, size=k, replace=False)
            parent[sel, 2] *= rng.uniform(0.75, 0.97, k)
            parent[sel, 0] += rng.normal(0, 3 * scale, k)
            parent[sel, 1] += rng.normal(0, 3 * scale, k)
        elif mode == 1:
            k = rng.integers(1, 4)
            sel = rng.choice(N, size=k, replace=False)
            parent[sel, 2] *= rng.uniform(1.02, 1.08, k)
        elif mode == 2:
            a, b = rng.choice(N, size=2, replace=False)
            parent[[a, b], 0] = parent[[b, a], 0]
            parent[[a, b], 1] = parent[[b, a], 1]
        elif mode == 3:
            ia, ib = rng.choice(N, size=2, replace=False)
            mx = 0.5 * (parent[ia, 0] + parent[ib, 0])
            my = 0.5 * (parent[ia, 1] + parent[ib, 1])
            ang = rng.normal(0, scale * 6.0)
            ca, sa = np.cos(ang), np.sin(ang)
            for k in (ia, ib):
                dx = parent[k, 0] - mx; dy = parent[k, 1] - my
                parent[k, 0] = mx + ca * dx - sa * dy
                parent[k, 1] = my + sa * dx + ca * dy
        else:
            parent[:, 0] += rng.normal(0, scale, N)
            parent[:, 1] += rng.normal(0, scale, N)

        parent[:, 0] = np.clip(parent[:, 0], 0.005, 0.995)
        parent[:, 1] = np.clip(parent[:, 1], 0.005, 0.995)
        x, y = resolve(parent[:, 0], parent[:, 1], parent[:, 2], iters=120)
        parent[:, 0] = x; parent[:, 1] = y
        parent = safe(parent)

        if time.process_time() >= deadline:
            break

        trial = lp_radii(parent)
        trial = safe(trial)
        if score(trial) > best_score - 0.02:
            trial = slsqp(trial, max_iter=200)
            trial = safe(trial)
            trial = lp_radii(trial)
            trial = safe(trial)

        ts = score(trial)
        if ts > best_score + 1e-12:
            best = trial
            best_score = ts
            stall = 0
            archive.append(best.copy())
            if len(archive) > 8:
                archive.pop(0)
        else:
            stall += 1

        if stall >= 14 and time.process_time() < deadline - 0.7:
            P = np.zeros((N, 3))
            P[:, 0] = rng.uniform(0.05, 0.95, N)
            P[:, 1] = rng.uniform(0.05, 0.95, N)
            P[:, 2] = 0.05
            x, y = resolve(P[:, 0], P[:, 1], P[:, 2], iters=200)
            P[:, 0] = x; P[:, 1] = y
            t = polish(safe(P), iters=2, slsqp_iters=250)
            if score(t) > best_score:
                best = t
                best_score = score(best)
                archive.append(best.copy())
            stall = 0

    if best is None:
        best = np.zeros((N, 3))
        best[:, 0] = np.linspace(0.1, 0.9, N)
        best[:, 1] = 0.5
        best[:, 2] = 0.01
    best = safe(best)
    if not feasible(best, 0.0):
        best = safe(best)
    return best
