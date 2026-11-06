import numpy as np
import time
from scipy.optimize import minimize

N = 32


def _feasible(x, y, r, margin=1e-10):
    r = np.maximum(r, 1e-12)
    r = np.minimum(r, np.minimum(x, 1.0 - x))
    r = np.minimum(r, np.minimum(y, 1.0 - y))
    r = np.maximum(r, 1e-12)
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.hypot(dx, dy)
    np.fill_diagonal(d, 1e18)
    for _ in range(400):
        s = r[:, None] + r[None, :]
        overlap = s - d
        np.fill_diagonal(overlap, -1.0)
        if overlap.max() <= margin:
            break
        i, j = np.unravel_index(np.argmax(overlap), overlap.shape)
        dij = d[i, j]
        if dij < 1e-15:
            r[i] *= 0.5; r[j] *= 0.5
        else:
            f = max((dij - margin) / s[i, j], 0.0)
            r[i] *= f; r[j] *= f
        r = np.minimum(r, np.minimum(x, 1.0 - x))
        r = np.minimum(r, np.minimum(y, 1.0 - y))
        r = np.maximum(r, 1e-12)
    return r


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.55
    rng = np.random.default_rng(int(t0 * 1313) ^ 0x9E3779B1)

    def wall_cap(x, y):
        return np.minimum(np.minimum(x, 1.0 - x), np.minimum(y, 1.0 - y))

    if start is not None:
        arr = np.asarray(start, dtype=float).copy()
        bx = arr[:, 0].copy(); by = arr[:, 1].copy()
        br = _feasible(bx, by, arr[:, 2].copy())
    else:
        k = 6
        xs, ys = [], []
        for j in range(k):
            for i in range(k):
                if len(xs) >= N: break
                xs.append((i + 0.5 + (0.5 if j % 2 else 0.0)) / k)
                ys.append((j + 0.5) / k)
            if len(xs) >= N: break
        bx = np.array(xs[:N]); by = np.array(ys[:N])
        br = _feasible(bx, by, np.full(N, 0.02))

    best_x, best_y, best_r = bx.copy(), by.copy(), br.copy()
    best_s = best_r.sum()

    I, J = np.triu_indices(N, 1)

    def push_apart(x, y, r, iters=40):
        for _ in range(iters):
            dx = x[I] - x[J]; dy = y[I] - y[J]
            d = np.hypot(dx, dy)
            s = r[I] + r[J]
            ov = s - d
            pos = ov > 0
            if not pos.any():
                break
            ovp = ov[pos]; dp = np.maximum(d[pos], 1e-12)
            ii = I[pos]; jj = J[pos]
            ux = dx[pos] / dp; uy = dy[pos] / dp
            disp = ovp * 0.5
            np.add.at(x, ii, ux * disp); np.add.at(y, ii, uy * disp)
            np.add.at(x, jj, -ux * disp); np.add.at(y, jj, -uy * disp)
            x = np.clip(x, 0.0, 1.0); y = np.clip(y, 0.0, 1.0)
        return x, y

    def grow_step(x, y, r, factor):
        r_new = np.minimum(r * factor, wall_cap(x, y))
        r_new = np.maximum(r_new, 1e-12)
        x2, y2 = push_apart(x.copy(), y.copy(), r_new, iters=30)
        r2 = _feasible(x2, y2, r_new, margin=1e-10)
        return x2, y2, r2

    def quick_grow(x, y, r, rounds=30):
        cur = r.sum()
        for _ in range(rounds):
            if time.process_time() >= deadline:
                break
            improved = False
            for factor in (1.05, 1.02, 1.01):
                x2, y2, r2 = grow_step(x, y, r, factor)
                if r2.sum() > cur + 1e-13:
                    x, y, r = x2, y2, r2; cur = r2.sum(); improved = True
                    break
            if not improved:
                break
        return x, y, r

    def lp_radii(x, y, r0, sweeps=200):
        cap = wall_cap(x, y)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        D = np.hypot(dx, dy)
        np.fill_diagonal(D, 1e18)
        r = np.minimum(r0, cap).copy()
        for _ in range(sweeps):
            improved = False
            for i in range(N):
                room = D[i] - r
                room[i] = 1e18
                m = min(cap[i], room.min())
                if m > r[i] + 1e-13:
                    r[i] = m
                    improved = True
            if not improved:
                break
        return np.minimum(r, cap)

    def slsqp_solve(x, y, r, maxiter=150, ftol=1e-14):
        def obj(v):
            return -v[2*N:].sum()
        def cons_walls(v):
            X, Y, R = v[:N], v[N:2*N], v[2*N:]
            return np.concatenate([X - R, 1.0 - X - R, Y - R, 1.0 - Y - R])
        def cons_pairs(v):
            X, Y, R = v[:N], v[N:2*N], v[2*N:]
            dx = X[I] - X[J]; dy = Y[I] - Y[J]
            d = np.hypot(dx, dy)
            return d - (R[I] + R[J])
        r0 = np.maximum(np.minimum(r, wall_cap(x, y)) * (1.0 - 1e-6), 1e-9)
        v0 = np.concatenate([x, y, r0])
        cons = [
            {'type': 'ineq', 'fun': cons_walls},
            {'type': 'ineq', 'fun': cons_pairs},
        ]
        try:
            res = minimize(obj, v0, method='SLSQP', constraints=cons,
                           options={'maxiter': maxiter, 'ftol': ftol})
        except Exception:
            return x, y, r
        if res.x is None or not np.all(np.isfinite(res.x)):
            return x, y, r
        X, Y, R = res.x[:N], res.x[N:2*N], res.x[2*N:]
        X = np.clip(X, 0.0, 1.0); Y = np.clip(Y, 0.0, 1.0)
        R = _feasible(X, Y, np.maximum(R, 1e-12), margin=1e-9)
        return X, Y, R

    def accept(X, Y, R):
        nonlocal best_s, best_x, best_y, best_r
        R = _feasible(X, Y, R, margin=1e-9)
        if R.sum() > best_s + 1e-12:
            best_s = R.sum()
            best_x, best_y, best_r = X.copy(), Y.copy(), R.copy()
            return True
        return False

    def force_insert(x, y, r, i, r_target):
        # move circle i to a random location, push others out, then re-grow
        x = x.copy(); y = y.copy(); r = r.copy()
        x[i] = rng.random(); y[i] = rng.random()
        r[i] = r_target
        x, y = push_apart(x, y, r, iters=60)
        r = _feasible(x, y, r, margin=1e-10)
        x, y, r = quick_grow(x, y, r, rounds=20)
        return x, y, r

    # 1) SLSQP polish on start, then LP-radii
    if time.process_time() < deadline - 1.0:
        X, Y, R = slsqp_solve(best_x, best_y, best_r, maxiter=250, ftol=1e-14)
        R = lp_radii(X, Y, R)
        accept(X, Y, R)

    # 2) Targeted "reinsert the smallest circle" moves (new strategy)
    #    plus perturbed SLSQP starts.
    attempt = 0
    while time.process_time() < deadline - 0.4:
        attempt += 1
        if attempt % 3 == 0:
            # reinsert smallest circle at a random spot then regrow
            i = int(np.argmin(best_r))
            x, y, r = force_insert(best_x, best_y, best_r, i,
                                   r_target=max(best_r[i] * 1.5, 0.03))
            if time.process_time() < deadline - 0.4:
                X, Y, R = slsqp_solve(x, y, r, maxiter=150, ftol=1e-15)
                R = lp_radii(X, Y, R)
                accept(X, Y, R)
        else:
            u = rng.random()
            if u < 0.55:
                scale = 0.004 + 0.010 * rng.random()
            elif u < 0.9:
                scale = 0.02 + 0.04 * rng.random()
            else:
                scale = 0.08 + 0.06 * rng.random()
            x = best_x + rng.normal(0, scale, N)
            y = best_y + rng.normal(0, scale, N)
            x = np.clip(x, 0.0, 1.0); y = np.clip(y, 0.0, 1.0)
            r = np.full(N, 1e-3)
            r = _feasible(x, y, r, margin=1e-10)
            x, y, r = quick_grow(x, y, r, rounds=25)
            if time.process_time() >= deadline - 0.4:
                break
            X, Y, R = slsqp_solve(x, y, r, maxiter=200, ftol=1e-15)
            R = lp_radii(X, Y, R)
            accept(X, Y, R)

    # 3) Final polish: SLSQP + LP radii on best
    if time.process_time() < deadline - 0.1:
        X, Y, R = slsqp_solve(best_x, best_y, best_r, maxiter=300, ftol=1e-16)
        R = lp_radii(X, Y, R)
        accept(X, Y, R)

    # Final strict feasibility
    best_r = _feasible(best_x, best_y, best_r, margin=1e-9)
    best_r *= (1.0 - 1e-8)
    best_r = np.maximum(best_r, 1e-12)
    best_r = np.minimum(best_r, wall_cap(best_x, best_y))
    for _ in range(100):
        dx = best_x[I] - best_x[J]; dy = best_y[I] - best_y[J]
        d = np.hypot(dx, dy)
        s = best_r[I] + best_r[J]
        ov = s - d
        if ov.max() <= 1e-9:
            break
        k = int(np.argmax(ov))
        i, j = I[k], J[k]
        f = max((d[k] - 1e-9) / s[k], 0.0)
        best_r[i] *= f; best_r[j] *= f
    best_r = np.maximum(best_r, 1e-12)
    best_x = np.clip(best_x, best_r, 1.0 - best_r)
    best_y = np.clip(best_y, best_r, 1.0 - best_r)
    return np.column_stack([best_x, best_y, best_r])
