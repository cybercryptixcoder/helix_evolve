import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.78
    N = 32
    rng = np.random.default_rng(24680)

    P = None
    if start is not None:
        S = np.asarray(start, dtype=float)
        if S.ndim == 2 and S.shape[0] >= N and S.shape[1] == 3 and \
                np.all(np.isfinite(S)) and np.all(S[:N, 2] > 0):
            P = S[:N].copy()
    if P is None:
        k = 6
        P = np.zeros((N, 3))
        idx = 0
        for j in range(k):
            for i in range(k):
                if idx >= N:
                    break
                P[idx] = [(i + 0.5) / k, (j + 0.5) / k, 0.02]
                idx += 1

    iu = np.triu_indices(N, 1)
    ii, jj = iu

    def repair(Q, iters=300):
        x = Q[:, 0].copy(); y = Q[:, 1].copy()
        r = np.maximum(Q[:, 2].copy(), 1e-9)
        for _ in range(iters):
            r = np.minimum(r, np.minimum(x, 1 - x))
            r = np.minimum(r, np.minimum(y, 1 - y))
            r = np.maximum(r, 1e-9)
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx * dx + dy * dy)
            s = r[:, None] + r[None, :]
            ov = (s - d)[iu]
            if ov.max() <= 1e-13:
                break
            scale = np.where(ov > 0, (d[iu] - 1e-12) / np.maximum(s[iu], 1e-12), 1.0)
            scale = np.clip(scale, 0.0, 1.0)
            factor = np.ones(N)
            np.minimum.at(factor, ii, scale)
            np.minimum.at(factor, jj, scale)
            factor = np.clip(factor, 1e-3, 1.0)
            r = np.maximum(r * factor, 1e-9)
        x = np.clip(x, r, 1 - r)
        y = np.clip(y, r, 1 - r)
        return np.stack([x, y, r], axis=1)

    def grow(Q):
        Q = Q.copy()
        x = Q[:, 0]; y = Q[:, 1]; r = Q[:, 2].copy()
        for _ in range(120):
            improved = False
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx * dx + dy * dy)
            np.fill_diagonal(d, np.inf)
            for i in np.argsort(r):
                lim = min(x[i], 1 - x[i], y[i], 1 - y[i])
                allowed = d[i] - r
                allowed[i] = np.inf
                lim = min(lim, allowed.min())
                if lim > r[i] + 1e-14:
                    r[i] = lim
                    improved = True
                    d[i, :] = np.sqrt((x - x[i]) ** 2 + (y - y[i]) ** 2)
                    d[:, i] = d[i, :]
                    d[i, i] = np.inf
            if not improved:
                break
        Q[:, 2] = r
        return Q

    wall_i = np.repeat(np.arange(N), 4)
    wall_k = np.tile(np.arange(4), N)
    pa = ii.copy(); pb = jj.copy()
    wall_rows = np.arange(wall_i.size)
    wm0 = wall_k == 0; wm1 = wall_k == 1; wm2 = wall_k == 2; wm3 = wall_k == 3
    pair_rows = np.arange(pa.size)

    def slsqp_polish(Q, maxiter=100, ftol=1e-14):
        z0 = Q.flatten()

        def obj(z):
            return -np.sum(z[2::3])

        def obj_grad(z):
            g = np.zeros_like(z)
            g[2::3] = -1.0
            return g

        def wall_fun(z):
            x = z[0::3][wall_i]; y = z[1::3][wall_i]; r = z[2::3][wall_i]
            out = np.empty_like(x)
            out[wm0] = x[wm0] - r[wm0]
            out[wm1] = 1 - x[wm1] - r[wm1]
            out[wm2] = y[wm2] - r[wm2]
            out[wm3] = 1 - y[wm3] - r[wm3]
            return out

        def wall_jac(z):
            J = np.zeros((wall_i.size, z.size))
            J[wall_rows[wm0], 3 * wall_i[wm0]] = 1.0
            J[wall_rows[wm0], 3 * wall_i[wm0] + 2] = -1.0
            J[wall_rows[wm1], 3 * wall_i[wm1]] = -1.0
            J[wall_rows[wm1], 3 * wall_i[wm1] + 2] = -1.0
            J[wall_rows[wm2], 3 * wall_i[wm2] + 1] = 1.0
            J[wall_rows[wm2], 3 * wall_i[wm2] + 2] = -1.0
            J[wall_rows[wm3], 3 * wall_i[wm3] + 1] = -1.0
            J[wall_rows[wm3], 3 * wall_i[wm3] + 2] = -1.0
            return J

        def pair_fun(z):
            xa = z[3 * pa]; ya = z[3 * pa + 1]; ra = z[3 * pa + 2]
            xb = z[3 * pb]; yb = z[3 * pb + 1]; rb = z[3 * pb + 2]
            dx = xa - xb; dy = ya - yb
            return dx * dx + dy * dy - (ra + rb) ** 2

        def pair_jac(z):
            J = np.zeros((pa.size, z.size))
            xa = z[3 * pa]; ya = z[3 * pa + 1]; ra = z[3 * pa + 2]
            xb = z[3 * pb]; yb = z[3 * pb + 1]; rb = z[3 * pb + 2]
            dx = xa - xb; dy = ya - yb
            sr = ra + rb
            J[pair_rows, 3 * pa] = 2 * dx
            J[pair_rows, 3 * pa + 1] = 2 * dy
            J[pair_rows, 3 * pa + 2] = -2 * sr
            J[pair_rows, 3 * pb] = -2 * dx
            J[pair_rows, 3 * pb + 1] = -2 * dy
            J[pair_rows, 3 * pb + 2] = -2 * sr
            return J

        cons = [
            {'type': 'ineq', 'fun': wall_fun, 'jac': wall_jac},
            {'type': 'ineq', 'fun': pair_fun, 'jac': pair_jac},
        ]

        bounds = []
        for i in range(N):
            bounds.append((0.0, 1.0))
            bounds.append((0.0, 1.0))
            bounds.append((1e-7, 0.5))

        try:
            res = minimize(obj, z0, jac=obj_grad, method='SLSQP',
                           constraints=cons, bounds=bounds,
                           options={'maxiter': maxiter, 'ftol': ftol})
            Z = res.x
            return np.stack([Z[0::3], Z[1::3], Z[2::3]], axis=1)
        except Exception:
            return Q

    # NEW: coordinated "shrink & slide" move. Shrinks a small cluster of
    # circles slightly, applies a coherent translation toward free space,
    # then regrows. This escapes jammed ridges that single-circle moves
    # cannot, by exploiting the slack released across a group.
    def cluster_slide(Q, k=4, scale=0.01):
        Q2 = Q.copy()
        idx = rng.choice(N, size=k, replace=False)
        # centre of the cluster and a random direction
        cx = Q2[idx, 0].mean(); cy = Q2[idx, 1].mean()
        ang = rng.uniform(0, 2 * np.pi)
        dirx = np.cos(ang); diry = np.sin(ang)
        # shrink to make room
        Q2[idx, 2] *= rng.uniform(0.85, 0.97)
        # slide the whole cluster
        Q2[idx, 0] = np.clip(Q2[idx, 0] + dirx * scale, 0.005, 0.995)
        Q2[idx, 1] = np.clip(Q2[idx, 1] + diry * scale, 0.005, 0.995)
        return Q2

    def expand_one(Q, i, tries=6):
        best = Q.copy(); bs = Q[:, 2].sum()
        x = Q[:, 0]; y = Q[:, 1]; r = Q[:, 2].copy()
        for _ in range(tries):
            Qx = Q.copy()
            Qx[i, 0] = np.clip(x[i] + rng.normal(0, 0.02), 0.01, 0.99)
            Qx[i, 1] = np.clip(y[i] + rng.normal(0, 0.02), 0.01, 0.99)
            Qx[i, 2] = r[i] * rng.uniform(1.0, 1.15)
            Qx = repair(Qx, iters=150)
            Qx = grow(Qx)
            s = Qx[:, 2].sum()
            if s > bs:
                best = Qx; bs = s
        return best

    P = repair(P)
    P = grow(P)
    best = P.copy()
    best_score = float(best[:, 2].sum())

    Q = slsqp_polish(best, maxiter=300, ftol=1e-16)
    Q = repair(Q); Q = grow(Q)
    if Q[:, 2].sum() > best_score:
        best = Q; best_score = float(Q[:, 2].sum())

    step = 0.03
    stagnation = 0
    while time.process_time() < deadline:
        Q = best.copy()
        u = rng.random()
        if u < 0.30:
            # cluster slide (new move): coordinated group translation
            k = int(rng.integers(2, 6))
            sc = rng.uniform(0.005, 0.02)
            Q = cluster_slide(Q, k=k, scale=sc)
            Q = repair(Q, iters=250); Q = grow(Q)
        elif u < 0.40:
            i = int(rng.integers(0, N))
            Q = expand_one(Q, i, tries=3)
        elif u < 0.47:
            Q[:, 2] *= (1.0 + rng.uniform(0.005, 0.05))
            Q = repair(Q); Q = grow(Q)
        elif u < 0.55:
            i = int(rng.integers(0, N))
            Q[i, 0] = rng.uniform(0.05, 0.95)
            Q[i, 1] = rng.uniform(0.05, 0.95)
            Q[i, 2] = rng.uniform(0.02, 0.08)
            Q = repair(Q); Q = grow(Q)
        elif u < 0.63:
            i, j = rng.choice(N, size=2, replace=False)
            Q[i, :2], Q[j, :2] = Q[j, :2].copy(), Q[i, :2].copy()
            Q = repair(Q); Q = grow(Q)
        else:
            m = int(rng.integers(1, 6))
            idx = rng.choice(N, size=m, replace=False)
            for i in idx:
                Q[i, 0] += rng.normal() * step
                Q[i, 1] += rng.normal() * step
            Q = repair(Q); Q = grow(Q)

        time_left = deadline - time.process_time()
        if time_left > 0.5:
            maxit = 60 if time_left < 3.0 else 100
            R = slsqp_polish(Q, maxiter=maxit)
            R = repair(R); R = grow(R)
            s = float(R[:, 2].sum())
        else:
            R = Q
            s = float(Q[:, 2].sum())

        if s > best_score + 1e-11:
            best = R; best_score = s
            step = max(step * 0.995, 5e-4)
            stagnation = 0
        else:
            step = min(step * 1.0010, 0.09)
            stagnation += 1

        if stagnation >= 25 and time_left > 2.0:
            stagnation = 0
            R2 = slsqp_polish(best, maxiter=250, ftol=1e-16)
            R2 = repair(R2); R2 = grow(R2)
            s2 = float(R2[:, 2].sum())
            if s2 > best_score + 1e-12:
                best = R2; best_score = s2

    remaining = deadline - time.process_time()
    if remaining > 0.3:
        Q = slsqp_polish(best, maxiter=400, ftol=1e-16)
        Q = repair(Q); Q = grow(Q)
        if Q[:, 2].sum() > best_score - 1e-12:
            best = Q; best_score = float(Q[:, 2].sum())

    P = repair(best, iters=500)
    P = grow(P)
    P[:, 2] *= (1.0 - 1e-9)
    P[:, 2] = np.maximum(P[:, 2], 1e-9)
    x = np.clip(P[:, 0], P[:, 2] + 1e-12, 1 - P[:, 2] - 1e-12)
    y = np.clip(P[:, 1], P[:, 2] + 1e-12, 1 - P[:, 2] - 1e-12)
    P = np.stack([x, y, P[:, 2]], axis=1)
    for _ in range(40):
        dx = P[:, 0][:, None] - P[:, 0][None, :]
        dy = P[:, 1][:, None] - P[:, 1][None, :]
        d = np.sqrt(dx * dx + dy * dy)
        s = P[:, 2][:, None] + P[:, 2][None, :]
        over = s - d
        np.fill_diagonal(over, -np.inf)
        if over.max() < 1e-12:
            break
        P[:, 2] *= (1 - 1e-9)
        x = np.clip(P[:, 0], P[:, 2], 1 - P[:, 2])
        y = np.clip(P[:, 1], P[:, 2], 1 - P[:, 2])
        P = np.stack([x, y, P[:, 2]], axis=1)
    return P
