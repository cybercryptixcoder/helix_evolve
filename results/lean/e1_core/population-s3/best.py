import numpy as np
import time
from scipy.optimize import minimize
from scipy.optimize import linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 26
    deadline = t0 + budget_seconds - 0.8
    rng = np.random.default_rng(int(t0 * 1e6) & 0xffffffff)

    iu = np.triu_indices(n, 1)
    pi, pj = iu[0], iu[1]
    npairs = len(pi)

    def wall_cap(P):
        P = P.copy()
        x, y, r = P[:, 0], P[:, 1], P[:, 2]
        cap = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        P[:, 2] = np.minimum(r, cap)
        return P

    def repair(P, iters=600):
        P = wall_cap(P)
        P[:, 2] = np.maximum(P[:, 2], 1e-9)
        for _ in range(iters):
            x = P[:, 0]; y = P[:, 1]; r = P[:, 2]
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx * dx + dy * dy)
            s = r[:, None] + r[None, :]
            np.fill_diagonal(d, 1e9)
            np.fill_diagonal(s, 0.0)
            excess = np.maximum(0.0, s - d)
            if excess.max() < 1e-14:
                break
            red = excess.max(axis=1)
            P[:, 2] = np.maximum(P[:, 2] - red, 1e-12)
            P = wall_cap(P)
        return wall_cap(P)

    if start is not None:
        P = np.array(start, dtype=float).copy()
    else:
        P = np.zeros((n, 3))
        cols = 6
        for idx in range(n):
            j, i = divmod(idx, cols)
            P[idx, 0] = (i + 0.5) / cols
            P[idx, 1] = (j + 0.5) / 6
            P[idx, 2] = 0.5 / cols
    P = repair(P)
    best = P.copy()
    best_s = float(best[:, 2].sum())

    def unpack(z):
        return np.column_stack([z[:n], z[n:2*n], z[2*n:]])

    def obj(z):
        return -z[2*n:].sum()

    def jac_obj(z):
        g = np.zeros(3 * n)
        g[2*n:] = -1.0
        return g

    def cons_wall(z):
        Q = unpack(z)
        x, y, r = Q[:, 0], Q[:, 1], Q[:, 2]
        return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])

    def jac_wall(z):
        J = np.zeros((4 * n, 3 * n))
        for i in range(n):
            J[i, i] = 1.0; J[i, 2*n + i] = -1.0
            J[n + i, i] = -1.0; J[n + i, 2*n + i] = -1.0
            J[2*n + i, n + i] = 1.0; J[2*n + i, 2*n + i] = -1.0
            J[3*n + i, n + i] = -1.0; J[3*n + i, 2*n + i] = -1.0
        return J

    def cons_pairs(z):
        Q = unpack(z)
        x, y, r = Q[:, 0], Q[:, 1], Q[:, 2]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.sqrt(dx * dx + dy * dy)
        return d - r[pi] - r[pj]

    def jac_pairs(z):
        Q = unpack(z)
        x, y, r = Q[:, 0], Q[:, 1], Q[:, 2]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.sqrt(dx * dx + dy * dy) + 1e-15
        J = np.zeros((npairs, 3 * n))
        ux = dx / d; uy = dy / d
        ar = np.arange(npairs)
        J[ar, pi] = ux; J[ar, pj] = -ux
        J[ar, n + pi] = uy; J[ar, n + pj] = -uy
        J[ar, 2*n + pi] = -1.0; J[ar, 2*n + pj] = -1.0
        return J

    bounds = [(0.0, 1.0)] * (2 * n) + [(1e-8, 0.5)] * n
    constraints = [
        {'type': 'ineq', 'fun': cons_wall, 'jac': jac_wall},
        {'type': 'ineq', 'fun': cons_pairs, 'jac': jac_pairs},
    ]

    def slsqp(P, maxiter=400, ftol=1e-15):
        z0 = np.concatenate([P[:, 0], P[:, 1], P[:, 2]])
        try:
            res = minimize(obj, z0, jac=jac_obj, method='SLSQP',
                           bounds=bounds, constraints=constraints,
                           options={'maxiter': maxiter, 'ftol': ftol})
            return repair(unpack(res.x))
        except Exception:
            return P

    def gap_matrix(P):
        x = P[:, 0]; y = P[:, 1]; r = P[:, 2]
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        s = r[:, None] + r[None, :]
        gap = d - s
        np.fill_diagonal(gap, 1e9)
        return gap

    # Joint LP: variables are (dr_i >= 0, dx_i, dy_i) for all circles.
    # Pair constraint: d - (r_i+dr_i) - (r_j+dr_j) >= 0, linearized as
    #   dr_i + dr_j - ux*(dx_i-dx_j) - uy*(dy_i-dy_j) <= gap_k
    # Wall: dr_i <= slack + (displacement toward interior).
    # Maximize sum(dr) - eps*sum(|d|^2 approx via L1). This jointly grows radii
    # and slides circles, letting the optimizer break plateau configurations.
    def joint_lp(P, eps=2e-3):
        x = P[:, 0]; y = P[:, 1]; r = P[:, 2]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.sqrt(dx * dx + dy * dy) + 1e-15
        ux = dx / d; uy = dy / d
        gaps = d - r[pi] - r[pj]
        wx0 = x - r; wx1 = 1 - x - r; wy0 = y - r; wy1 = 1 - y - r

        # variables: [dr (n), dx (n), dy (n)]  -> 3n
        nv = 3 * n
        c = np.zeros(nv)
        c[:n] = -1.0
        # small L1-ish penalty via splitting not feasible; use quadratic-ish
        # proxy: penalize |dx|,|dy| via bounds only. Keep c simple.

        A_rows = []
        b_rows = []
        # pair constraints
        for k in range(npairs):
            i, j = pi[k], pj[k]
            row = np.zeros(nv)
            row[i] += 1.0
            row[j] += 1.0
            row[n + i] -= ux[k]
            row[n + j] += ux[k]
            row[2*n + i] -= uy[k]
            row[2*n + j] += uy[k]
            A_rows.append(row); b_rows.append(max(gaps[k], 0.0))
        # wall constraints (linearized): dr_i - dx_i <= wx0 (left)
        #   x - r >= 0 -> (x-r) - (dx_i - dr_i) >= 0 -> dr_i - dx_i <= wx0
        for i in range(n):
            row = np.zeros(nv); row[i] = 1.0; row[n + i] = -1.0
            A_rows.append(row); b_rows.append(max(wx0[i], 0.0))
            row = np.zeros(nv); row[i] = 1.0; row[n + i] = 1.0
            A_rows.append(row); b_rows.append(max(wx1[i], 0.0))
            row = np.zeros(nv); row[i] = 1.0; row[2*n + i] = -1.0
            A_rows.append(row); b_rows.append(max(wy0[i], 0.0))
            row = np.zeros(nv); row[i] = 1.0; row[2*n + i] = 1.0
            A_rows.append(row); b_rows.append(max(wy1[i], 0.0))
        A = np.array(A_rows); b = np.array(b_rows)
        bounds_lp = [(0, None)] * n + [(-0.03, 0.03)] * (2 * n)
        try:
            res = linprog(c, A_ub=A, b_ub=b, bounds=bounds_lp, method='highs')
            if res.success:
                Q = P.copy()
                Q[:, 0] = np.clip(x + res.x[n:2*n], 0, 1)
                Q[:, 1] = np.clip(y + res.x[2*n:], 0, 1)
                Q[:, 2] = np.maximum(r + res.x[:n] * 0.99, 1e-9)
                return repair(Q)
        except Exception:
            pass
        return P

    # Initial strong polish
    Q = slsqp(best, maxiter=1200)
    if Q[:, 2].sum() > best_s:
        best = Q; best_s = float(Q[:, 2].sum())

    stall = 0
    it = 0
    while time.process_time() < deadline:
        it += 1
        progress = (time.process_time() - t0) / max(budget_seconds, 1e-9)
        scale = 0.05 * max(0.05, 1.0 - progress)

        # joint LP growth attempt from best
        if time.process_time() < deadline - 0.5:
            Qg = joint_lp(best)
            if Qg[:, 2].sum() > best_s + 1e-13:
                Qg2 = slsqp(Qg, maxiter=300)
                if Qg2[:, 2].sum() > best_s:
                    best = Qg2; best_s = Qg2[:, 2].sum(); stall = 0

        Q = best.copy()
        mode = rng.integers(0, 5)
        if mode == 0:
            g = gap_matrix(Q)
            ncont = (g < 1e-4).sum(axis=1)
            rs = Q[:, 2]
            score = ncont + (rs.mean() - rs) / max(rs.mean(), 1e-9)
            idx = np.argsort(-score)[:int(rng.integers(2, 6))]
            for i in idx:
                ang = rng.uniform(0, 2 * np.pi)
                Q[i, 0] = np.clip(Q[i, 0] + scale * np.cos(ang), 0, 1)
                Q[i, 1] = np.clip(Q[i, 1] + scale * np.sin(ang), 0, 1)
                Q[i, 2] = max(1e-6, Q[i, 2] * (1 + rng.normal(0, 0.03)))
        elif mode == 1:
            k = int(rng.integers(1, 4))
            idx = rng.choice(n, k, replace=False)
            for i in idx:
                Q[i, 0] = np.clip(Q[i, 0] + rng.normal(0, scale), 0, 1)
                Q[i, 1] = np.clip(Q[i, 1] + rng.normal(0, scale), 0, 1)
                Q[i, 2] = max(1e-6, Q[i, 2] * (1 + rng.normal(0, 0.08)))
        elif mode == 2:
            g = gap_matrix(Q)
            i = int(rng.integers(0, n))
            j = int(np.argmin(g[i]))
            for k in (i, j):
                Q[k, 0] = np.clip(Q[k, 0] + rng.normal(0, scale * 1.5), 0, 1)
                Q[k, 1] = np.clip(Q[k, 1] + rng.normal(0, scale * 1.5), 0, 1)
                Q[k, 2] = max(1e-6, Q[k, 2] * (1 + rng.normal(0, 0.06)))
        elif mode == 3:
            i, j = rng.choice(n, 2, replace=False)
            Q[[i, j], 0] = Q[[j, i], 0]
            Q[[i, j], 1] = Q[[j, i], 1]
        else:
            Q[:, 2] = np.maximum(1e-6, Q[:, 2] * (1 + rng.normal(0, 0.02, n)))
        Q = repair(Q)

        if time.process_time() < deadline - 0.3:
            Qp = slsqp(Q, maxiter=250)
            sp = Qp[:, 2].sum()
            if sp > best_s + 1e-13:
                best = Qp; best_s = sp; stall = 0
            else:
                stall += 1
        else:
            stall += 1

        if stall > 15 and time.process_time() < deadline - 0.5:
            # try a longer joint-LP run from a perturbed best
            Qr = best.copy()
            Qr[:, 0] = np.clip(Qr[:, 0] + rng.normal(0, 0.02, n), 0, 1)
            Qr[:, 1] = np.clip(Qr[:, 1] + rng.normal(0, 0.02, n), 0, 1)
            Qr = repair(Qr)
            Qr = joint_lp(Qr)
            Qr = slsqp(Qr, maxiter=500)
            if Qr[:, 2].sum() > best_s:
                best = Qr; best_s = Qr[:, 2].sum()
            stall = 0

    Qf = slsqp(best, maxiter=1500)
    if Qf[:, 2].sum() > best[:, 2].sum():
        best = Qf
    best = repair(best, iters=1500)
    best[:, 2] *= (1 - 1e-7)
    best = wall_cap(best)
    best[:, 2] = np.maximum(best[:, 2], 1e-9)
    print("iters", it, "score", best[:, 2].sum())
    return best
