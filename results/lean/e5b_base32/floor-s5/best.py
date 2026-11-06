import numpy as np
import time
from scipy.optimize import minimize, linprog


def _hex_grid(n=32):
    pts = []
    k = 6
    dy = 1.0 / k
    dx = 1.0 / k
    for j in range(k + 1):
        off = 0.5 * dx if (j % 2) else 0.0
        for i in range(k + 1):
            if len(pts) < n:
                x = (i + 0.5) * dx + off
                y = (j + 0.5) * dy
                if x < 1 and y < 1:
                    pts.append([x, y, 0.4 / k])
    while len(pts) < n:
        pts.append([0.5, 0.5, 0.1])
    return np.array(pts[:n], dtype=float)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.80

    n = 32
    rng = np.random.default_rng(24680)

    if start is not None and np.asarray(start).shape == (32, 3):
        best = np.array(start, dtype=float)
    else:
        best = _hex_grid(n)

    iu, ju = np.triu_indices(n, k=1)
    n_pairs = len(iu)
    rows = np.arange(n_pairs)
    k_ar = np.arange(n)

    def unpack(z):
        return z[:n], z[n:2 * n], z[2 * n:]

    def con_walls(z):
        x, y, r = unpack(z)
        return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])

    def jac_walls(z):
        J = np.zeros((4 * n, 3 * n))
        J[k_ar, k_ar] = 1.0;               J[k_ar, 2 * n + k_ar] = -1.0
        J[n + k_ar, k_ar] = -1.0;          J[n + k_ar, 2 * n + k_ar] = -1.0
        J[2 * n + k_ar, n + k_ar] = 1.0;   J[2 * n + k_ar, 2 * n + k_ar] = -1.0
        J[3 * n + k_ar, n + k_ar] = -1.0;  J[3 * n + k_ar, 2 * n + k_ar] = -1.0
        return J

    def con_pairs(z):
        x, y, r = unpack(z)
        dx = x[iu] - x[ju]; dy = y[iu] - y[ju]
        rs = r[iu] + r[ju]
        return dx * dx + dy * dy - rs * rs

    def jac_pairs(z):
        x, y, r = unpack(z)
        dx = x[iu] - x[ju]; dy = y[iu] - y[ju]
        rs = r[iu] + r[ju]
        J = np.zeros((n_pairs, 3 * n))
        np.add.at(J, (rows, iu), 2 * dx)
        np.add.at(J, (rows, ju), -2 * dx)
        np.add.at(J, (rows, n + iu), 2 * dy)
        np.add.at(J, (rows, n + ju), -2 * dy)
        np.add.at(J, (rows, 2 * n + iu), -2 * rs)
        np.add.at(J, (rows, 2 * n + ju), -2 * rs)
        return J

    constraints = [
        {'type': 'ineq', 'fun': con_walls, 'jac': jac_walls},
        {'type': 'ineq', 'fun': con_pairs, 'jac': jac_pairs},
    ]

    def objective(z):
        return -np.sum(z[2 * n:])

    def grad_objective(z):
        g = np.zeros_like(z)
        g[2 * n:] = -1.0
        return g

    def pack(z0, maxiter=200):
        bounds = [(0.0, 1.0)] * (2 * n) + [(1e-8, 0.5)] * n
        try:
            res = minimize(objective, z0, jac=grad_objective, method='SLSQP',
                           bounds=bounds, constraints=constraints,
                           options={'maxiter': maxiter, 'ftol': 1e-15})
            return res.x
        except Exception:
            return z0

    def to_z(pts):
        return np.concatenate([pts[:, 0], pts[:, 1], pts[:, 2]])

    def to_pts(z):
        return np.column_stack([z[:n], z[n:2 * n], z[2 * n:]])

    def score_of(p):
        return p[:, 2].sum()

    def feasible_soft(p, tol=1e-9):
        x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
        if np.any(r <= 0):
            return False
        if np.any(x - r < -tol) or np.any(x + r > 1 + tol):
            return False
        if np.any(y - r < -tol) or np.any(y + r > 1 + tol):
            return False
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d2 = dx * dx + dy * dy
        rs = r[:, None] + r[None, :]
        np.fill_diagonal(d2, np.inf)
        return not np.any(d2 < rs * rs - tol)

    # Vectorized LP for max radii given fixed centers; A structure fixed by pairs.
    A_wall = np.zeros((n, n))
    A_wall[k_ar, k_ar] = 1.0
    A_pairs = np.zeros((n_pairs, n))
    A_pairs[rows, iu] = 1.0
    A_pairs[rows, ju] = 1.0
    A_full = np.vstack([A_wall, A_pairs])
    c_obj = -np.ones(n)

    def max_radii_given_centers(x, y):
        wall_cap = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        wall_cap = np.maximum(wall_cap, 0.0)
        dx = x[iu] - x[ju]; dy = y[iu] - y[ju]
        d = np.sqrt(dx * dx + dy * dy)
        b = np.concatenate([wall_cap, d])
        try:
            res = linprog(c_obj, A_ub=A_full, b_ub=b,
                          bounds=[(0, None)] * n, method='highs')
            if res.success:
                return np.maximum(res.x, 0.0)
        except Exception:
            pass
        return None

    def shrink_to_feasible(p):
        p = p.copy()
        for _ in range(500):
            if feasible_soft(p):
                return p
            p[:, 2] *= 0.99
        return p

    # Initial SLSQP solve from start.
    z_best = pack(to_z(best), maxiter=1500)
    cand = to_pts(z_best)
    if feasible_soft(cand) and score_of(cand) > score_of(best):
        best = cand
    best_score = score_of(best)

    attempt = 0
    stall = 0
    while time.process_time() < deadline:
        attempt += 1
        mode = attempt % 12

        cand_pts = best.copy()
        if mode == 0:
            cand_pts[:, 0] += rng.normal(0, 0.02, n)
            cand_pts[:, 1] += rng.normal(0, 0.02, n)
        elif mode in (1, 2, 3):
            cand_pts[:, 0] += rng.normal(0, 0.004, n)
            cand_pts[:, 1] += rng.normal(0, 0.004, n)
        elif mode == 4:
            a, b = rng.choice(n, 2, replace=False)
            cand_pts[[a, b], :2] = cand_pts[[b, a], :2]
        elif mode == 5:
            cand_pts[:, 2] *= (1 + rng.normal(0, 0.02, n))
        elif mode == 6:
            idx = rng.choice(n, size=max(3, n // 3), replace=False)
            cand_pts[idx, 0] += rng.normal(0, 0.01, len(idx))
            cand_pts[idx, 1] += rng.normal(0, 0.01, len(idx))
        elif mode == 7:
            idx = rng.choice(n, size=max(2, n // 4), replace=False)
            cx, cy = cand_pts[idx, 0].mean(), cand_pts[idx, 1].mean()
            th = rng.normal(0, 0.08)
            c, s = np.cos(th), np.sin(th)
            dx = cand_pts[idx, 0] - cx; dy = cand_pts[idx, 1] - cy
            cand_pts[idx, 0] = cx + c * dx - s * dy
            cand_pts[idx, 1] = cy + s * dx + c * dy
        elif mode == 8:
            hg = _hex_grid(n)
            hg[:, 0] += rng.normal(0, 0.03, n)
            hg[:, 1] += rng.normal(0, 0.03, n)
            cand_pts = hg
        elif mode == 9:
            # "explosion": expand radii then SLSQP re-balances
            cand_pts[:, 2] *= 1.03
        else:
            cand_pts[:, 0] += rng.normal(0, 0.001, n)
            cand_pts[:, 1] += rng.normal(0, 0.001, n)

        cand_pts[:, 0] = np.clip(cand_pts[:, 0], 1e-4, 1 - 1e-4)
        cand_pts[:, 1] = np.clip(cand_pts[:, 1], 1e-4, 1 - 1e-4)
        cand_pts[:, 2] = np.maximum(cand_pts[:, 2], 1e-6)

        # Always try LP radii from these centers if feasible; else shrink.
        newr = max_radii_given_centers(cand_pts[:, 0], cand_pts[:, 1])
        if newr is not None and newr.sum() > 0:
            cand_pts[:, 2] = 0.999 * newr
        else:
            cand_pts = shrink_to_feasible(cand_pts)

        if not feasible_soft(cand_pts):
            continue

        z = pack(to_z(cand_pts), maxiter=500)
        cand = to_pts(z)
        if feasible_soft(cand):
            s = score_of(cand)
            if s > best_score + 1e-13:
                best = cand
                best_score = s
                stall = 0
            else:
                stall += 1
        else:
            stall += 1

        if stall > 40:
            newr = max_radii_given_centers(best[:, 0], best[:, 1])
            if newr is not None:
                trial = best.copy()
                trial[:, 2] = 0.998 * newr
                if feasible_soft(trial) and score_of(trial) > best_score:
                    best = trial
                    best_score = score_of(trial)
            stall = 0

    # Final polish.
    if time.process_time() < deadline + budget_seconds * 0.08:
        newr = max_radii_given_centers(best[:, 0], best[:, 1])
        if newr is not None:
            trial = best.copy()
            trial[:, 2] = 0.999 * newr
            if feasible_soft(trial) and score_of(trial) > best_score:
                best = trial
                best_score = score_of(trial)
        z = pack(to_z(best), maxiter=2000)
        cand = to_pts(z)
        if feasible_soft(cand) and score_of(cand) > best_score:
            best = cand
            best_score = score_of(cand)

    # Strict final validation / shrink.
    best = best.copy()
    best[:, 2] = np.maximum(best[:, 2], 1e-9)
    for _ in range(20000):
        x = best[:, 0]; y = best[:, 1]; r = best[:, 2]
        ok = np.all(r > 0)
        ok = ok and np.all(x - r >= 0) and np.all(x + r <= 1)
        ok = ok and np.all(y - r >= 0) and np.all(y + r <= 1)
        if ok:
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d2 = dx * dx + dy * dy
            rs = r[:, None] + r[None, :]
            np.fill_diagonal(d2, np.inf)
            ok = not np.any(d2 < rs * rs)
        if ok:
            break
        best[:, 2] *= (1 - 1e-12)
    return best
