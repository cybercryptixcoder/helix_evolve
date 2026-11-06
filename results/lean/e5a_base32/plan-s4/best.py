import numpy as np
import time
from scipy.optimize import minimize, linprog, root


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.6
    n = 32
    idx_i, idx_j = np.triu_indices(n, k=1)
    n_pairs = len(idx_i)

    def margin(p):
        x, y, r = p[:, 0], p[:, 1], p[:, 2]
        m = min((x - r).min(), (1 - x - r).min(),
                (y - r).min(), (1 - y - r).min())
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy) - r[:, None] - r[None, :]
        np.fill_diagonal(d, 1e9)
        return min(m, d.min())

    if start is not None:
        p = np.asarray(start, dtype=float).copy()
        if p.shape != (n, 3):
            p = None
    else:
        p = None
    if p is None:
        k = int(np.ceil(np.sqrt(n)))
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        p = np.array([[x, y, 0.02] for x, y in pts])

    p[:, 2] = np.maximum(p[:, 2] - 1e-7, 1e-6)
    p[:, 0] = np.clip(p[:, 0], p[:, 2], 1 - p[:, 2])
    p[:, 1] = np.clip(p[:, 1], p[:, 2], 1 - p[:, 2])

    def unpack(z):
        return z.reshape(n, 3)

    def objective(z):
        return -np.sum(z[2::3])

    def obj_grad(z):
        g = np.zeros_like(z)
        g[2::3] = -1.0
        return g

    bounds = []
    for _ in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 0.5))

    def wall_con(z):
        q = unpack(z)
        x, y, r = q[:, 0], q[:, 1], q[:, 2]
        return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])

    def wall_jac(z):
        J = np.zeros((4 * n, 3 * n))
        for i in range(n):
            J[i, 3 * i] = 1.0; J[i, 3 * i + 2] = -1.0
            J[n + i, 3 * i] = -1.0; J[n + i, 3 * i + 2] = -1.0
            J[2 * n + i, 3 * i + 1] = 1.0; J[2 * n + i, 3 * i + 2] = -1.0
            J[3 * n + i, 3 * i + 1] = -1.0; J[3 * n + i, 3 * i + 2] = -1.0
        return J

    def pair_con(z):
        q = unpack(z)
        xi, yi, ri = q[idx_i, 0], q[idx_i, 1], q[idx_i, 2]
        xj, yj, rj = q[idx_j, 0], q[idx_j, 1], q[idx_j, 2]
        dx = xi - xj; dy = yi - yj
        return dx * dx + dy * dy - (ri + rj) ** 2

    def pair_jac(z):
        q = unpack(z)
        xi, yi, ri = q[idx_i, 0], q[idx_i, 1], q[idx_i, 2]
        xj, yj, rj = q[idx_j, 0], q[idx_j, 1], q[idx_j, 2]
        dx = xi - xj; dy = yi - yj
        J = np.zeros((n_pairs, 3 * n))
        rows = np.arange(n_pairs)
        J[rows, 3 * idx_i] = 2 * dx
        J[rows, 3 * idx_i + 1] = 2 * dy
        J[rows, 3 * idx_i + 2] = -2 * (ri + rj)
        J[rows, 3 * idx_j] = -2 * dx
        J[rows, 3 * idx_j + 1] = -2 * dy
        J[rows, 3 * idx_j + 2] = -2 * (ri + rj)
        return J

    cons = [
        {'type': 'ineq', 'fun': wall_con, 'jac': wall_jac},
        {'type': 'ineq', 'fun': pair_con, 'jac': pair_jac},
    ]

    best = p.copy()
    best_score = p[:, 2].sum() if margin(p) >= -1e-9 else -1e9

    def lp_radii(centers):
        x = centers[:, 0]; y = centers[:, 1]
        wall_cap = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        wall_cap = np.maximum(wall_cap, 0.0)
        c = -np.ones(n)
        dx = x[idx_i] - x[idx_j]
        dy = y[idx_i] - y[idx_j]
        d = np.hypot(dx, dy)
        A_pair = np.zeros((n_pairs, n))
        A_pair[np.arange(n_pairs), idx_i] = 1.0
        A_pair[np.arange(n_pairs), idx_j] = 1.0
        bounds_lp = [(0.0, wall_cap[i]) for i in range(n)]
        try:
            res = linprog(c, A_ub=A_pair, b_ub=d, bounds=bounds_lp,
                          method='highs')
            if res.success:
                return np.maximum(res.x, 0.0)
        except Exception:
            pass
        rr = wall_cap.copy()
        for i in range(n):
            for j in range(i + 1, n):
                dij = np.hypot(x[i] - x[j], y[i] - y[j])
                if rr[i] + rr[j] > dij:
                    s = (rr[i] + rr[j] - dij) / 2.0
                    rr[i] = max(rr[i] - s, 0.0)
                    rr[j] = max(rr[j] - s, 0.0)
        return rr

    def full_slsqp(z0, deadline_local):
        class TimeUp(Exception):
            pass

        def cb(_z):
            if time.process_time() > deadline_local:
                raise TimeUp()

        try:
            res = minimize(objective, z0, jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter': 1000, 'ftol': 1e-14},
                           callback=cb)
            return res.x
        except TimeUp:
            return None
        except Exception:
            return None

    def clean(q):
        q = q.copy()
        q[:, 2] = np.maximum(q[:, 2], 1e-12)
        q[:, 0] = np.clip(q[:, 0], q[:, 2], 1 - q[:, 2])
        q[:, 1] = np.clip(q[:, 1], q[:, 2], 1 - q[:, 2])
        for i in range(n):
            for j in range(i + 1, n):
                dx = q[i, 0] - q[j, 0]; dy = q[i, 1] - q[j, 1]
                d = np.hypot(dx, dy)
                s = q[i, 2] + q[j, 2]
                if d < s and s > 0:
                    shrink = (s - d) / 2.0 + 1e-12
                    q[i, 2] = max(q[i, 2] - shrink, 1e-12)
                    q[j, 2] = max(q[j, 2] - shrink, 1e-12)
        q[:, 0] = np.clip(q[:, 0], q[:, 2], 1 - q[:, 2])
        q[:, 1] = np.clip(q[:, 1], q[:, 2], 1 - q[:, 2])
        return q

    # ---- NEW: basin-hopping / random-restart descent on centers+LP radii ----
    # Key idea: the previous program spent most time polishing a single basin.
    # Here we spend the budget systematically exploring many basins by
    # randomizing centers, then taking LP-optimal radii, then a short SLSQP.

    rng = np.random.default_rng(2024)

    def try_from_centers(centers, tlimit):
        q0 = np.zeros((n, 3))
        q0[:, :2] = centers
        rr = lp_radii(centers)
        q0[:, 2] = np.maximum(rr - 1e-10, 1e-9)
        q0[:, 0] = np.clip(q0[:, 0], q0[:, 2], 1 - q0[:, 2])
        q0[:, 1] = np.clip(q0[:, 1], q0[:, 2], 1 - q0[:, 2])
        z = full_slsqp(q0.reshape(-1).copy(), tlimit)
        if z is None:
            return None
        q = clean(unpack(z))
        if margin(q) >= -1e-9:
            return q
        return None

    # Baseline: polish start directly
    if time.process_time() < deadline - 0.2:
        q = try_from_centers(best[:, :2].copy(), deadline - 0.15)
        if q is not None and q[:, 2].sum() > best_score:
            best = q
            best_score = q[:, 2].sum()

    # Structured perturbations: swap circles, jitter the largest/smallest
    base_centers = best[:, :2].copy()
    attempt = 0
    while time.process_time() < deadline - 0.25:
        attempt += 1
        centers = base_centers.copy()
        r_est = lp_radii(base_centers)
        # Pick a random strategy
        mode = attempt % 4
        if mode == 0:
            # global jitter, magnitude proportional to mean radius
            scale = 0.04 * rng.random()
            centers += rng.normal(0, scale, centers.shape)
        elif mode == 1:
            # jitter only a subset of circles (perturb a cluster)
            k = rng.integers(3, 10)
            idxs = rng.choice(n, size=k, replace=False)
            scale = 0.06
            centers[idxs] += rng.normal(0, scale, (k, 2))
        elif mode == 2:
            # swap positions of two circles (different radii to break symmetry)
            i, j = rng.choice(n, size=2, replace=False)
            centers[[i, j]] = centers[[j, i]]
        else:
            # local compression toward a random attractor point
            ax, ay = rng.random(), rng.random()
            centers = 0.5 * centers + 0.5 * np.array([ax, ay])
            centers += rng.normal(0, 0.02, centers.shape)
        centers = np.clip(centers, 0.0, 1.0)
        tlimit = min(deadline - 0.2, time.process_time() + 0.5)
        q = try_from_centers(centers, tlimit)
        if q is not None:
            sc = q[:, 2].sum()
            if sc > best_score - 1e-6:
                # accept as new base even if slightly worse, to diversify
                base_centers = q[:, :2].copy()
                if sc > best_score:
                    best = q
                    best_score = sc

    # ---- Exact-polish: Newton on active contact set with multipliers ----
    def exact_polish(qin, deadline_local):
        q = qin.copy()
        x, y, r = q[:, 0], q[:, 1], q[:, 2]
        dx = x[idx_i] - x[idx_j]
        dy = y[idx_i] - y[idx_j]
        d = np.hypot(dx, dy)
        pair_gaps = d - (r[idx_i] + r[idx_j])
        tol = 1e-6
        ap = np.where(pair_gaps < tol)[0]
        wg = np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])
        aw = np.where(wg < tol)[0]
        m = len(ap) + len(aw)
        if m == 0:
            return q

        def cons_all(z):
            parts = []
            if len(ap):
                parts.append(pair_con(z)[ap])
            if len(aw):
                parts.append(wall_con(z)[aw])
            return np.concatenate(parts)

        def cons_jac_all(z):
            rows = []
            if len(ap):
                rows.append(pair_jac(z)[ap])
            if len(aw):
                rows.append(wall_jac(z)[aw])
            return np.vstack(rows)

        z = q.reshape(-1).copy()
        J = cons_jac_all(z)
        g = obj_grad(z)
        try:
            lam, *_ = np.linalg.lstsq(J.T, -g, rcond=None)
        except Exception:
            lam = np.zeros(m)

        def F(u):
            zz = u[:3 * n]
            ll = u[3 * n:]
            c = cons_all(zz)
            Jz = cons_jac_all(zz)
            grad = obj_grad(zz) + Jz.T @ ll
            return np.concatenate([c, grad])

        u0 = np.concatenate([z, lam])
        try:
            sol = root(F, u0, method='hybr',
                       options={'xtol': 1e-14, 'maxfev': 2000})
            if not np.all(np.isfinite(sol.x)):
                return q
            zz = sol.x[:3 * n]
            qq = unpack(zz).copy()
        except Exception:
            return q
        qq[:, 2] = lp_radii(qq[:, :2])
        qq[:, 0] = np.clip(qq[:, 0], qq[:, 2], 1 - qq[:, 2])
        qq[:, 1] = np.clip(qq[:, 1], qq[:, 2], 1 - qq[:, 2])

        def feasible(scale):
            ql = qq.astype(np.longdouble).copy()
            ql[:, 2] *= scale
            xx, yy, rr = ql[:, 0], ql[:, 1], ql[:, 2]
            if np.any(xx - rr < 0) or np.any(xx + rr > 1):
                return False
            if np.any(yy - rr < 0) or np.any(yy + rr > 1):
                return False
            for i in range(n):
                ddx = xx[i] - xx[i + 1:]
                ddy = yy[i] - yy[i + 1:]
                dd = np.sqrt(ddx * ddx + ddy * ddy)
                if np.any(dd < rr[i] + rr[i + 1:]):
                    return False
            return True

        lo, hi = 0.0, 1.0
        if feasible(1.0):
            scale = 1.0
        else:
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                if feasible(mid):
                    lo = mid
                else:
                    hi = mid
            scale = lo
        qq[:, 2] *= scale
        for _ in range(200):
            if margin(qq) >= 0.0:
                break
            qq[:, 2] *= (1.0 - 1e-15)
        return qq

    if time.process_time() < deadline - 0.05:
        try:
            qp = exact_polish(best, deadline)
            if qp is not None and margin(qp) >= 0.0 and np.all(qp[:, 2] > 0):
                sc = qp[:, 2].sum()
                if sc > best_score:
                    best = qp
                    best_score = sc
        except Exception:
            pass

    q = best.copy()
    q[:, 2] = np.maximum(q[:, 2] - 1e-15, 1e-12)
    q[:, 0] = np.clip(q[:, 0], q[:, 2], 1 - q[:, 2])
    q[:, 1] = np.clip(q[:, 1], q[:, 2], 1 - q[:, 2])
    for _ in range(500):
        if margin(q) >= 0.0:
            break
        q[:, 2] *= (1.0 - 1e-15)
        q[:, 0] = np.clip(q[:, 0], q[:, 2], 1 - q[:, 2])
        q[:, 1] = np.clip(q[:, 1], q[:, 2], 1 - q[:, 2])
    return q
