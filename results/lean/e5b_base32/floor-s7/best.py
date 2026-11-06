import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + max(0.5, budget_seconds - 1.5)
    n = 32
    ii, jj = np.triu_indices(n, 1)

    if start is not None:
        init = np.asarray(start, dtype=float).copy()
    else:
        pts = []
        rows = 6
        for row in range(rows):
            cols = 6 if row % 2 == 0 else 5
            for c in range(cols):
                if len(pts) >= n:
                    break
                x = (c + 0.5 + (0.25 if row % 2 else 0)) / 6.0
                y = (row + 0.5) / rows
                pts.append((x, y))
            if len(pts) >= n:
                break
        while len(pts) < n:
            pts.append((0.5, 0.5))
        init = np.array([[x, y, 0.03] for x, y in pts[:n]])

    init[:, 2] = np.maximum(init[:, 2], 1e-4)

    # --- vectorized strict enforcement -------------------------------------
    def enforce(p, iters=200, shrink=1 - 1e-11):
        p = p.copy()
        p[:, 2] = np.maximum(p[:, 2], 1e-12)
        for _ in range(iters):
            # wall clamp
            p[:, 2] = np.minimum(p[:, 2], p[:, 0])
            p[:, 2] = np.minimum(p[:, 2], 1.0 - p[:, 0])
            p[:, 2] = np.minimum(p[:, 2], p[:, 1])
            p[:, 2] = np.minimum(p[:, 2], 1.0 - p[:, 1])
            dx = p[:, 0][:, None] - p[:, 0][None, :]
            dy = p[:, 1][:, None] - p[:, 1][None, :]
            d = np.sqrt(dx * dx + dy * dy)
            s = p[:, 2][:, None] + p[:, 2][None, :]
            np.fill_diagonal(s, 0.0)
            bad = d < s
            if not np.any(bad):
                break
            # shrink both radii of each violating pair geometrically
            ratio = np.where(bad, np.minimum(d / np.maximum(s, 1e-30), 1.0), 1.0)
            # column product gives combined shrink factor per circle
            fac = np.prod(np.where(bad, ratio ** 0.5, 1.0), axis=1)
            p[:, 2] *= np.clip(fac, 0.5, 1.0)
            p[:, 2] = np.maximum(p[:, 2], 1e-12)
        return p

    # --- SLSQP local polish (constraints exact) ----------------------------
    A_wall = np.zeros((4 * n, 3 * n))
    for i in range(n):
        A_wall[4 * i, 3 * i] = 1.0;     A_wall[4 * i, 3 * i + 2] = -1.0
        A_wall[4 * i + 1, 3 * i] = -1.0; A_wall[4 * i + 1, 3 * i + 2] = -1.0
        A_wall[4 * i + 2, 3 * i + 1] = 1.0;  A_wall[4 * i + 2, 3 * i + 2] = -1.0
        A_wall[4 * i + 3, 3 * i + 1] = -1.0; A_wall[4 * i + 3, 3 * i + 2] = -1.0
    b_wall = np.zeros(4 * n)
    b_wall[1::4] = -1.0
    b_wall[3::4] = -1.0

    def pair_fun(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
        s = r[ii] + r[jj]
        return dx * dx + dy * dy - s * s

    def pair_jac(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        m = len(ii)
        J = np.zeros((m, 3 * n))
        dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
        s = r[ii] + r[jj]
        rows = np.arange(m)
        J[rows, 3 * ii] += 2 * dx
        J[rows, 3 * jj] -= 2 * dx
        J[rows, 3 * ii + 1] += 2 * dy
        J[rows, 3 * jj + 1] -= 2 * dy
        J[rows, 3 * ii + 2] -= 2 * s
        J[rows, 3 * jj + 2] -= 2 * s
        return J

    cons = [
        {'type': 'ineq', 'fun': lambda v: A_wall.dot(v) - b_wall, 'jac': lambda v: A_wall},
        {'type': 'ineq', 'fun': pair_fun, 'jac': pair_jac},
    ]

    def obj(v):
        return -np.sum(v[2::3])

    def jobj(v):
        g = np.zeros(3 * n); g[2::3] = -1.0
        return g

    def slsqp_polish(p, maxiter=300):
        x0 = p.reshape(-1).copy()
        try:
            res = minimize(obj, x0, jac=jobj, method='SLSQP',
                           constraints=cons,
                           options={'maxiter': maxiter, 'ftol': 1e-14})
            return res.x.reshape(n, 3)
        except Exception:
            return p

    p0 = enforce(init)
    best = p0.copy()
    best_score = float(np.sum(p0[:, 2]))

    # Phase A: polish start
    p = enforce(slsqp_polish(best, 500))
    sc = float(np.sum(p[:, 2]))
    if sc > best_score:
        best_score, best = sc, p.copy()

    # Phase B: targeted single-circle bumps with SLSQP re-solve
    rng = np.random.default_rng(20240501)
    improved = True
    while improved and time.process_time() < deadline - 0.25:
        improved = False
        order = rng.permutation(n)
        for i in order:
            if time.process_time() > deadline - 0.2:
                break
            trial = best.copy()
            trial[i, 2] *= 1.02
            trial[i, 2] += 2e-4
            trial = enforce(trial)
            trial = enforce(slsqp_polish(trial, 200))
            sc = float(np.sum(trial[:, 2]))
            if sc > best_score + 1e-13:
                best_score, best = sc, trial.copy()
                improved = True

    # Phase C: small random restarts around best, short SLSQP
    attempts = 0
    while time.process_time() < deadline - 0.3:
        attempts += 1
        p = best.copy()
        scale = 0.003 if attempts < 8 else 0.008
        p[:, 0] = np.clip(p[:, 0] + rng.normal(0, scale, n), 0.0, 1.0)
        p[:, 1] = np.clip(p[:, 1] + rng.normal(0, scale, n), 0.0, 1.0)
        p[:, 2] = np.maximum(p[:, 2] * (1.0 + rng.normal(0, scale * 1.2, n)), 1e-3)
        p = enforce(p)
        if time.process_time() > deadline - 0.25:
            break
        p = enforce(slsqp_polish(p, 200))
        sc = float(np.sum(p[:, 2]))
        if sc > best_score + 1e-13:
            best_score, best = sc, p.copy()

    # Final strict safety
    res = enforce(best)
    res[:, 2] *= (1.0 - 1e-9)
    res = enforce(res)
    res[:, 2] *= (1.0 - 1e-10)
    res[:, 2] = np.maximum(res[:, 2], 1e-9)
    return res
