import numpy as np
import time
from scipy.optimize import minimize, linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    N = 32
    deadline = budget_seconds - 0.8

    iu = np.triu_indices(N, 1)
    ii, jj = iu
    npairs = len(ii)

    def unpack(v):
        return v[:2 * N].reshape(N, 2), v[2 * N:]

    def shrink_feasible(c, r):
        r = r.copy()
        m = np.minimum(np.minimum(c[:, 0], 1 - c[:, 0]),
                       np.minimum(c[:, 1], 1 - c[:, 1]))
        r = np.minimum(r, np.maximum(m, 1e-6))
        for _ in range(500):
            dx = c[:, 0][:, None] - c[:, 0][None, :]
            dy = c[:, 1][:, None] - c[:, 1][None, :]
            d = np.sqrt(dx * dx + dy * dy)
            viol = (r[:, None] + r[None, :]) - d
            np.fill_diagonal(viol, -1)
            mx = np.max(viol)
            if mx > 1e-12:
                i, j = np.unravel_index(np.argmax(viol), viol.shape)
                if r[i] >= r[j]:
                    r[i] -= mx / 2 + 1e-9
                else:
                    r[j] -= mx / 2 + 1e-9
                r = np.maximum(r, 1e-6)
            else:
                break
        return c, r

    # ---- base start ----
    if start is not None:
        arr = np.asarray(start, dtype=float).copy()
        c0 = arr[:, :2].copy()
        r0 = arr[:, 2].copy()
    else:
        k = 6
        pts = []
        for j in range(k):
            for i in range(k):
                x = (i + 0.5 + (0.5 if j % 2 else 0.0)) / k
                y = (j + 0.5) / k
                if 0 < x < 1 and 0 < y < 1:
                    pts.append((x, y))
        pts = pts[:N]
        while len(pts) < N:
            pts.append((0.5, 0.5))
        c0 = np.array(pts)
        r0 = np.full(N, 0.03)

    c0, r0 = shrink_feasible(c0, r0)
    best_c = c0.copy()
    best_r = r0.copy()
    best_obj = float(np.sum(r0))

    # ---- LP: given centers, maximize sum r ----
    # variables: r_0..r_{N-1}  (N vars)
    # maximize sum r  => minimize -sum r
    # constraints (ineq, A_ub x <= b_ub):
    #   r_i <= wall_i  (4 walls) -> r_i <= m_i  (combine into single bound per i)
    #   r_i + r_j <= d_ij
    #   r_i >= 0  (bounds)
    n_pairs = npairs
    A_ub = np.zeros((n_pairs, N))
    A_ub[np.arange(n_pairs), ii] = 1.0
    A_ub[np.arange(n_pairs), jj] = 1.0
    c_obj = -np.ones(N)

    def solve_lp(c, want_dual=False):
        dx = c[ii, 0] - c[jj, 0]
        dy = c[ii, 1] - c[jj, 1]
        d = np.sqrt(dx * dx + dy * dy)
        d = np.maximum(d, 1e-12)
        m = np.minimum(np.minimum(c[:, 0], 1 - c[:, 0]),
                       np.minimum(c[:, 1], 1 - c[:, 1]))
        m = np.maximum(m, 0.0)
        # bounds: 0 <= r_i <= m_i
        bounds = [(0.0, max(m[i], 0.0)) for i in range(N)]
        try:
            res = linprog(c_obj, A_ub=A_ub, b_ub=d, bounds=bounds,
                          method='highs')
            if not res.success:
                return None, None, None
            r = res.x
            if want_dual:
                # marginals for A_ub: res.ineqlin.marginals (<=0 for min)
                lam = -res.ineqlin.marginals  # >=0
                return r, lam, d
            return r, None, d
        except Exception:
            return None, None, None

    def lp_value(c):
        r, _, _ = solve_lp(c, want_dual=False)
        if r is None:
            return 1e9, None
        return -np.sum(r), r

    # ---- gradient of LP value w.r.t. centers ----
    def grad_lp(c):
        r, lam, d = solve_lp(c, want_dual=True)
        if r is None:
            return np.zeros(2 * N)
        g = np.zeros((N, 2))
        # pair terms: d/dc_i of lam_ij * ||c_i - c_j||
        dx = c[ii, 0] - c[jj, 0]
        dy = c[ii, 1] - c[jj, 1]
        ux = dx / d
        uy = dy / d
        np.add.at(g[:, 0], ii, lam * ux)
        np.add.at(g[:, 1], ii, lam * uy)
        np.add.at(g[:, 0], jj, -lam * ux)
        np.add.at(g[:, 1], jj, -lam * uy)
        # wall terms: r_i <= min(cx,1-cx,cy,1-cy). The active wall's marginal
        # contributes to gradient. Determine which wall is binding per circle
        # from the LP bound marginals.
        # We approximate: use the bound marginal from res (upper bound marginal).
        # Re-solve to get bound marginals.
        try:
            dxp = c[ii, 0] - c[jj, 0]
            dyp = c[ii, 1] - c[jj, 1]
            dp = np.sqrt(dxp * dxp + dyp * dyp)
            dp = np.maximum(dp, 1e-12)
            m = np.minimum(np.minimum(c[:, 0], 1 - c[:, 0]),
                           np.minimum(c[:, 1], 1 - c[:, 1]))
            m = np.maximum(m, 0.0)
            bounds = [(0.0, max(m[i], 0.0)) for i in range(N)]
            res = linprog(c_obj, A_ub=A_ub, b_ub=dp, bounds=bounds,
                          method='highs')
            if res.success:
                # upper bound marginals: res.upper.marginals (<=0 for min)
                ub = -res.upper.marginals  # >=0
                # determine active wall per circle
                for i in range(N):
                    if ub[i] > 1e-12:
                        cx, cy = c[i]
                        walls = np.array([cx, 1 - cx, cy, 1 - cy])
                        k = int(np.argmin(walls))
                        if k == 0:
                            g[i, 0] += ub[i]
                        elif k == 1:
                            g[i, 0] -= ub[i]
                        elif k == 2:
                            g[i, 1] += ub[i]
                        else:
                            g[i, 1] -= ub[i]
        except Exception:
            pass
        return g.ravel()

    def neg_obj(x):
        c = x.reshape(N, 2)
        val, _ = lp_value(c)
        return val

    def neg_grad(x):
        c = x.reshape(N, 2)
        return -grad_lp(c)  # we minimize -sum r, so grad of -sum r

    # ---- initial LP from start ----
    r_lp, _, _ = solve_lp(c0)
    if r_lp is not None:
        r_lp = np.maximum(r_lp, 1e-6)
        c0, r_lp = shrink_feasible(c0, r_lp)
        val = float(np.sum(r_lp))
        if val > best_obj:
            best_obj = val
            best_c = c0.copy()
            best_r = r_lp.copy()

    # ---- L-BFGS-B on centers ----
    x = best_c.ravel().copy()
    bounds_c = [(0.0, 1.0)] * (2 * N)

    def time_left():
        return deadline - (time.process_time() - t0)

    # main optimization
    try:
        res = minimize(neg_obj, x, jac=neg_grad, method='L-BFGS-B',
                       bounds=bounds_c,
                       options={'maxiter': 2000, 'ftol': 1e-16,
                                'gtol': 1e-12, 'maxfun': 5000})
        x = res.x
    except Exception:
        pass

    # evaluate
    c_new = x.reshape(N, 2)
    r_new, _, _ = solve_lp(c_new)
    if r_new is not None:
        r_new = np.maximum(r_new, 1e-6)
        c_new, r_new = shrink_feasible(c_new, r_new)
        val = float(np.sum(r_new))
        if val > best_obj:
            best_obj = val
            best_c = c_new.copy()
            best_r = r_new.copy()

    # ---- small random restarts on centers if time ----
    rng = np.random.default_rng(98765)
    attempt = 0
    while time_left() > 0.5:
        attempt += 1
        c = best_c + rng.normal(0, 0.005, size=(N, 2))
        c = np.clip(c, 0.001, 0.999)
        x = c.ravel()
        try:
            res = minimize(neg_obj, x, jac=neg_grad, method='L-BFGS-B',
                           bounds=bounds_c,
                           options={'maxiter': 300, 'ftol': 1e-15,
                                    'gtol': 1e-11, 'maxfun': 800})
            x = res.x
        except Exception:
            continue
        c_new = x.reshape(N, 2)
        r_new, _, _ = solve_lp(c_new)
        if r_new is None:
            continue
        r_new = np.maximum(r_new, 1e-6)
        c_new, r_new = shrink_feasible(c_new, r_new)
        val = float(np.sum(r_new))
        if val > best_obj + 1e-13:
            best_obj = val
            best_c = c_new.copy()
            best_r = r_new.copy()

    # ---- final safety ----
    c, r = best_c, best_r
    c, r = shrink_feasible(c, r)
    r = np.maximum(r - 1e-12, 1e-6)

    # verify
    def ok(c, r):
        if np.any(r <= 0):
            return False
        if np.any(c[:, 0] - r < 0) or np.any(c[:, 0] + r > 1):
            return False
        if np.any(c[:, 1] - r < 0) or np.any(c[:, 1] + r > 1):
            return False
        dx = c[:, 0][:, None] - c[:, 0][None, :]
        dy = c[:, 1][:, None] - c[:, 1][None, :]
        d = np.sqrt(dx * dx + dy * dy)
        gap = d - (r[:, None] + r[None, :])
        np.fill_diagonal(gap, 1.0)
        return not np.any(gap < 0)

    if not ok(c, r):
        # fallback: shrink more
        for _ in range(100):
            r = np.maximum(r - 1e-10, 1e-6)
            c, r = shrink_feasible(c, r)
            if ok(c, r):
                break

    return np.column_stack([c, r])
