import numpy as np
import time
from scipy.optimize import minimize, linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    iu = np.triu_indices(n, k=1)
    iu0, iu1 = iu

    if start is not None:
        init = np.asarray(start, dtype=float).copy()
        init[:, 2] = np.maximum(init[:, 2], 1e-4)
    else:
        k = 6
        pts = [((i + 0.5 + (0.5 if j % 2 else 0)) / k, (j + 0.5) / k)
               for j in range(k) for i in range(k)][:n]
        init = np.array([[x, y, 0.02] for x, y in pts])

    def unpack(z):
        return z[:n], z[n:2 * n], z[2 * n:]

    def objective(z):
        return -np.sum(z[2 * n:])

    def objective_grad(z):
        g = np.zeros_like(z)
        g[2 * n:] = -1.0
        return g

    def constraints(z):
        x, y, r = unpack(z)
        cons = [x - r, 1.0 - x - r, y - r, 1.0 - y - r]
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        rr = r[:, None] + r[None, :]
        d2 = dx * dx + dy * dy - rr * rr
        cons.append(d2[iu])
        return np.concatenate(cons)

    def constraints_jac(z):
        x, y, r = unpack(z)
        m_wall = 4 * n
        m_pair = n * (n - 1) // 2
        J = np.zeros((m_wall + m_pair, 3 * n))
        idx = 0
        for i in range(n):
            J[idx, i] = 1.0; J[idx, 2 * n + i] = -1.0; idx += 1
        for i in range(n):
            J[idx, i] = -1.0; J[idx, 2 * n + i] = -1.0; idx += 1
        for i in range(n):
            J[idx, n + i] = 1.0; J[idx, 2 * n + i] = -1.0; idx += 1
        for i in range(n):
            J[idx, n + i] = -1.0; J[idx, 2 * n + i] = -1.0; idx += 1
        for i, j in zip(iu0, iu1):
            dx = x[i] - x[j]; dy = y[i] - y[j]; rr = r[i] + r[j]
            J[idx, i] = 2.0 * dx; J[idx, j] = -2.0 * dx
            J[idx, n + i] = 2.0 * dy; J[idx, n + j] = -2.0 * dy
            J[idx, 2 * n + i] = -2.0 * rr; J[idx, 2 * n + j] = -2.0 * rr
            idx += 1
        return J

    bounds = [(0.0, 1.0)] * (2 * n) + [(1e-6, 0.5)] * n
    cons = {'type': 'ineq', 'fun': constraints, 'jac': constraints_jac}

    def repair(z):
        x, y, r = unpack(z)
        r = np.maximum(r, 1e-6)
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
        for _ in range(200):
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx * dx + dy * dy)
            rr = r[:, None] + r[None, :]
            np.fill_diagonal(d, 1e9)
            viol = rr - d
            m = viol.max()
            if m <= 0:
                break
            r = np.maximum(r - 0.5 * m, 1e-9)
            x = np.clip(x, r, 1.0 - r)
            y = np.clip(y, r, 1.0 - r)
        return np.concatenate([x, y, r])

    def is_feasible(z, tol=1e-12):
        x, y, r = unpack(z)
        if np.any(r <= 0):
            return False
        if np.any(x - r < -tol) or np.any(1 - x - r < -tol):
            return False
        if np.any(y - r < -tol) or np.any(1 - y - r < -tol):
            return False
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        rr = r[:, None] + r[None, :]
        d2 = dx * dx + dy * dy - rr * rr
        return not np.any(d2[iu] < -tol)

    def run_slsqp(z, maxiter=800):
        try:
            res = minimize(
                objective, z, jac=objective_grad,
                method='SLSQP', bounds=bounds, constraints=[cons],
                options={'maxiter': maxiter, 'ftol': 1e-13},
            )
            if res.x is not None and np.all(np.isfinite(res.x)):
                return res.x
        except Exception:
            pass
        return z

    z0 = np.concatenate([init[:, 0], init[:, 1], init[:, 2]])
    z0 = repair(z0)
    best_z = run_slsqp(z0)
    if not is_feasible(best_z, tol=1e-9):
        best_z = z0
    best_score = np.sum(best_z[2 * n:])

    deadline = t0 + budget_seconds - 0.45
    rng = np.random.default_rng(20240521)

    while time.process_time() < deadline:
        z = best_z.copy()
        mode = rng.integers(0, 4)
        if mode == 0:
            idx = rng.choice(n, size=rng.integers(3, 8), replace=False)
            s = rng.uniform(0.01, 0.05)
            z[idx] += rng.normal(0, s, len(idx))
            z[n + idx] += rng.normal(0, s, len(idx))
            z[2 * n + idx] += rng.normal(0, s * 0.3, len(idx))
        elif mode == 1:
            f = 1.0 - rng.uniform(0.005, 0.03)
            z[:n] = 0.5 + (z[:n] - 0.5) * f
            z[n:2 * n] = 0.5 + (z[n:2 * n] - 0.5) * f
            z[2 * n:] *= (1.0 / f) * (1.0 + rng.normal(0, 0.005, n))
        elif mode == 2:
            s = rng.uniform(0.005, 0.02)
            z[:2 * n] += rng.normal(0, s, 2 * n)
            z[2 * n:] *= (1.0 + rng.normal(0, s * 0.5, n))
        else:
            i = int(np.argmin(z[2 * n:]))
            j = int(rng.integers(0, n))
            ang = rng.uniform(0, 2 * np.pi)
            z[i] = np.clip(z[j] + 0.12 * np.cos(ang), 0.02, 0.98)
            z[n + i] = np.clip(z[n + j] + 0.12 * np.sin(ang), 0.02, 0.98)
            z[2 * n + i] = np.log(0.04)
        z[:2 * n] = np.clip(z[:2 * n], 0.001, 0.999)
        z[2 * n:] = np.clip(z[2 * n:], 1e-5, 0.5)
        z = repair(z)
        z = run_slsqp(z)
        if is_feasible(z, tol=1e-9):
            s = np.sum(z[2 * n:])
            if s > best_score + 1e-13:
                best_score = s
                best_z = z

    # ---- Active-set LP polish with equality-solve (Newton-like) ----
    polish_deadline = t0 + budget_seconds - 0.09
    try:
        z = best_z.copy()
        for outer in range(40):
            if time.process_time() >= polish_deadline:
                break
            x, y, r = unpack(z)
            gw = np.concatenate([x - r, 1.0 - x - r, y - r, 1.0 - y - r])
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            gp = np.sqrt(dx * dx + dy * dy)[iu] - (r[:, None] + r[None, :])[iu]
            wall_act = gw < 1e-8
            pair_act = gp < 1e-8
            if not (np.any(wall_act) or np.any(pair_act)):
                break
            Jfull = constraints_jac(z)
            Ffull = constraints(z)
            act = np.concatenate([wall_act, pair_act])
            if not np.any(act):
                break
            J = Jfull[act]
            F = Ffull[act]
            m = J.shape[0]
            A_eq = np.hstack([J, np.zeros((m, 3 * n))])
            b_eq = -F
            step_lim = 2e-3
            A_ub = np.vstack([
                np.hstack([np.eye(3 * n), -np.eye(3 * n)]),
                np.hstack([-np.eye(3 * n), -np.eye(3 * n)]),
                np.hstack([np.zeros((3 * n, 3 * n)), np.eye(3 * n)]),
            ])
            b_ub = np.concatenate([np.zeros(6 * n), np.full(3 * n, step_lim)])
            c_lp = np.zeros(6 * n)
            c_lp[2 * n:3 * n] = -1.0
            try:
                res = linprog(c_lp, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                              bounds=[(None, None)] * (6 * n), method='highs')
            except Exception:
                break
            if not res.success or res.x is None:
                break
            dz = res.x[:3 * n]
            if np.max(np.abs(dz)) < 1e-14:
                break
            improved = False
            step = 1.0
            for _ in range(25):
                zc = z + step * dz
                zc = repair(zc)
                if is_feasible(zc, tol=1e-11):
                    sc = np.sum(zc[2 * n:])
                    if sc > np.sum(z[2 * n:]) + 1e-16:
                        z = zc
                        improved = True
                        break
                step *= 0.5
            if not improved:
                break
            if is_feasible(z, tol=1e-11) and np.sum(z[2 * n:]) > best_score + 1e-14:
                best_score = np.sum(z[2 * n:])
                best_z = z.copy()
    except Exception:
        pass

    # ---- Newton refinement on active set (solve equality-constrained KKT) ----
    newton_deadline = t0 + budget_seconds - 0.02
    try:
        z = best_z.copy()
        for _ in range(30):
            if time.process_time() >= newton_deadline:
                break
            x, y, r = unpack(z)
            gw = np.concatenate([x - r, 1.0 - x - r, y - r, 1.0 - y - r])
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            gp = np.sqrt(dx * dx + dy * dy)[iu] - (r[:, None] + r[None, :])[iu]
            act = np.concatenate([gw < 1e-7, gp < 1e-7])
            if not np.any(act):
                break
            Jfull = constraints_jac(z)
            Ffull = constraints(z)
            J = Jfull[act]
            F = Ffull[act]
            # Solve min ||dz||^2 s.t. J dz = -F (minimum-norm Newton step)
            # dz = J^T (J J^T)^{-1} (-F)
            JJt = J @ J.T + 1e-14 * np.eye(J.shape[0])
            try:
                lam = np.linalg.solve(JJt, -F)
            except Exception:
                break
            dz = J.T @ lam
            # scale to keep step bounded
            mx = np.max(np.abs(dz))
            if mx > 1e-3:
                dz *= 1e-3 / mx
            if mx < 1e-15:
                break
            improved = False
            step = 1.0
            for _ in range(20):
                zc = z + step * dz
                zc = repair(zc)
                if is_feasible(zc, tol=1e-12):
                    sc = np.sum(zc[2 * n:])
                    if sc > np.sum(z[2 * n:]) + 1e-15:
                        z = zc
                        improved = True
                        break
                step *= 0.5
            if not improved:
                break
            if np.sum(z[2 * n:]) > best_score + 1e-15:
                best_score = np.sum(z[2 * n:])
                best_z = z.copy()
    except Exception:
        pass

    x, y, r = unpack(best_z)
    r = np.maximum(r, 1e-9)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    for _ in range(200):
        if is_feasible(np.concatenate([x, y, r]), tol=0.0):
            break
        r = r * (1.0 - 1e-12)
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
    return np.column_stack([x, y, r])
