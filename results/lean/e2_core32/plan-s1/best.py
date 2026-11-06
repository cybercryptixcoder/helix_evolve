import numpy as np
import time
from scipy.optimize import minimize, linprog


def _feasible_fix(x, n):
    x = np.array(x, dtype=float).reshape(n, 3)
    x[:, 2] = np.maximum(x[:, 2], 1e-6)
    x[:, 0] = np.clip(x[:, 0], x[:, 2], 1.0 - x[:, 2])
    x[:, 1] = np.clip(x[:, 1], x[:, 2], 1.0 - x[:, 2])
    for _ in range(100):
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                dx = x[i, 0] - x[j, 0]
                dy = x[i, 1] - x[j, 1]
                d = np.hypot(dx, dy)
                s = x[i, 2] + x[j, 2]
                if d < s:
                    changed = True
                    excess = s - d + 1e-11
                    x[i, 2] -= excess / 2
                    x[j, 2] -= excess / 2
        x[:, 2] = np.maximum(x[:, 2], 1e-6)
        x[:, 0] = np.clip(x[:, 0], x[:, 2], 1.0 - x[:, 2])
        x[:, 1] = np.clip(x[:, 1], x[:, 2], 1.0 - x[:, 2])
        if not changed:
            break
    x[:, 2] *= (1.0 - 1e-12)
    return x


def _lp_radii(centers, n):
    c = -np.ones(n)
    A_ub = []
    b_ub = []
    for i in range(n):
        for w in (centers[i, 0], 1.0 - centers[i, 0],
                  centers[i, 1], 1.0 - centers[i, 1]):
            row = np.zeros(n)
            row[i] = 1.0
            A_ub.append(row)
            b_ub.append(max(w, 0.0))
    for i in range(n):
        for j in range(i + 1, n):
            d = np.hypot(centers[i, 0] - centers[j, 0],
                         centers[i, 1] - centers[j, 1])
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            A_ub.append(row)
            b_ub.append(max(d, 0.0))
    bounds = [(1e-6, None)] * n
    try:
        res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub),
                      bounds=bounds, method='highs',
                      options={'primal_feasibility_tolerance': 1e-10,
                               'dual_feasibility_tolerance': 1e-10})
        if res.success:
            return np.maximum(res.x, 1e-6)
    except Exception:
        pass
    return None


def _slsqp_polish(x_init, n, maxiter, ftol=1e-14):
    def obj(v):
        return -np.sum(v[2::3])

    def obj_grad(v):
        g = np.zeros_like(v)
        g[2::3] = -1.0
        return g

    bounds = []
    for i in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-4, 0.5))

    cons = []
    for i in range(n):
        for kind in range(4):
            def make_wall(i, kind):
                def f(v):
                    X = v.reshape(n, 3)
                    if kind == 0:
                        return X[i, 0] - X[i, 2]
                    elif kind == 1:
                        return 1.0 - X[i, 0] - X[i, 2]
                    elif kind == 2:
                        return X[i, 1] - X[i, 2]
                    else:
                        return 1.0 - X[i, 1] - X[i, 2]
                def jac(v):
                    g = np.zeros(3 * n)
                    if kind == 0:
                        g[3 * i] = 1.0
                    elif kind == 1:
                        g[3 * i] = -1.0
                    elif kind == 2:
                        g[3 * i + 1] = 1.0
                    else:
                        g[3 * i + 1] = -1.0
                    g[3 * i + 2] = -1.0
                    return g
                return f, jac
            f, j = make_wall(i, kind)
            cons.append({'type': 'ineq', 'fun': f, 'jac': j})

    for i in range(n):
        for j in range(i + 1, n):
            def make_pair(i, j):
                def f(v):
                    X = v.reshape(n, 3)
                    dx = X[i, 0] - X[j, 0]
                    dy = X[i, 1] - X[j, 1]
                    return dx * dx + dy * dy - (X[i, 2] + X[j, 2]) ** 2
                def jac(v):
                    X = v.reshape(n, 3)
                    dx = X[i, 0] - X[j, 0]
                    dy = X[i, 1] - X[j, 1]
                    s = X[i, 2] + X[j, 2]
                    g = np.zeros(3 * n)
                    g[3 * i] = 2.0 * dx
                    g[3 * i + 1] = 2.0 * dy
                    g[3 * i + 2] = -2.0 * s
                    g[3 * j] = -2.0 * dx
                    g[3 * j + 1] = -2.0 * dy
                    g[3 * j + 2] = -2.0 * s
                    return g
                return f, jac
            f, j = make_pair(i, j)
            cons.append({'type': 'ineq', 'fun': f, 'jac': j})

    v0 = x_init.reshape(-1).copy()
    v0[2::3] = np.clip(v0[2::3], 1e-4, 0.5)
    v0[0::3] = np.clip(v0[0::3], 0.0, 1.0)
    v0[1::3] = np.clip(v0[1::3], 0.0, 1.0)
    try:
        res = minimize(obj, v0, jac=obj_grad, method='SLSQP',
                       bounds=bounds, constraints=cons,
                       options={'maxiter': maxiter, 'ftol': ftol})
        return res.x.reshape(n, 3)
    except Exception:
        return x_init


def _slp_step(x, n, delta=2e-3):
    """Solve tangent-space LP over v=[dcx,dcy,dr] for active constraints.
    Returns (v, opt) or (None, 0)."""
    tol = 1e-6
    A_ub = []
    b_ub = []
    for i in range(n):
        for j in range(i + 1, n):
            dx = x[i, 0] - x[j, 0]
            dy = x[i, 1] - x[j, 1]
            d = np.hypot(dx, dy)
            gap = d - x[i, 2] - x[j, 2]
            if gap < tol:
                if d < 1e-12:
                    continue
                ux = dx / d
                uy = dy / d
                row = np.zeros(3 * n)
                # -(u.dc_i)+(u.dc_j)+dr_i+dr_j <= 0
                row[3 * i] = -ux
                row[3 * i + 1] = -uy
                row[3 * i + 2] = 1.0
                row[3 * j] = ux
                row[3 * j + 1] = uy
                row[3 * j + 2] = 1.0
                A_ub.append(row)
                b_ub.append(0.0)
    for i in range(n):
        # left: x_i - r_i >= 0 -> -dcx_i + dr_i <= 0
        if abs(x[i, 0] - x[i, 2]) < tol:
            row = np.zeros(3 * n)
            row[3 * i] = -1.0
            row[3 * i + 2] = 1.0
            A_ub.append(row); b_ub.append(0.0)
        # right: 1 - x_i - r_i >= 0 -> dcx_i + dr_i <= 0
        if abs(1.0 - x[i, 0] - x[i, 2]) < tol:
            row = np.zeros(3 * n)
            row[3 * i] = 1.0
            row[3 * i + 2] = 1.0
            A_ub.append(row); b_ub.append(0.0)
        # bottom: y_i - r_i >= 0 -> -dcy_i + dr_i <= 0
        if abs(x[i, 1] - x[i, 2]) < tol:
            row = np.zeros(3 * n)
            row[3 * i + 1] = -1.0
            row[3 * i + 2] = 1.0
            A_ub.append(row); b_ub.append(0.0)
        # top: 1 - y_i - r_i >= 0 -> dcy_i + dr_i <= 0
        if abs(1.0 - x[i, 1] - x[i, 2]) < tol:
            row = np.zeros(3 * n)
            row[3 * i + 1] = 1.0
            row[3 * i + 2] = 1.0
            A_ub.append(row); b_ub.append(0.0)
    if not A_ub:
        return None, 0.0
    c = np.zeros(3 * n)
    c[2::3] = -1.0
    bounds = [(-delta, delta)] * (3 * n)
    try:
        res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub),
                      bounds=bounds, method='highs',
                      options={'primal_feasibility_tolerance': 1e-10,
                               'dual_feasibility_tolerance': 1e-10})
        if res.success:
            return res.x, -res.fun
    except Exception:
        pass
    return None, 0.0


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    rng = np.random.default_rng(12345)
    HARD = min(budget_seconds * 0.82, budget_seconds - 1.2)

    def elapsed():
        return time.process_time() - t0

    best = None
    best_score = -1.0

    def score(x):
        return float(np.sum(x[:, 2]))

    if start is not None:
        try:
            s = _feasible_fix(start, n)
            best = s
            best_score = score(s)
        except Exception:
            pass

    def hex_init(rows, cols):
        pts = []
        for j in range(rows):
            y = (j + 0.5) / rows
            off = 0.5 if j % 2 == 0 else 1.0
            cnt = cols if j % 2 == 0 else cols - 1
            for i in range(cnt):
                x = (i + off) / cols
                pts.append((x, y))
        return pts

    def grid_init(g):
        pts = []
        for j in range(g):
            for i in range(g):
                pts.append(((i + 0.5) / g, (j + 0.5) / g))
        return pts

    inits = []
    for rows, cols in [(6, 6), (5, 7), (7, 5), (6, 7), (8, 4)]:
        p = hex_init(rows, cols)
        if len(p) >= n:
            inits.append(np.array(p[:n]))
    for g in (6, 7):
        p = grid_init(g)
        if len(p) >= n:
            inits.append(np.array(p[:n]))

    def make_cand(centers):
        rlp = _lp_radii(centers, n)
        if rlp is None:
            rlp = np.full(n, 0.05)
        c = np.column_stack([centers, rlp])
        return _feasible_fix(c, n)

    def consider(cand):
        nonlocal best, best_score
        cand = _feasible_fix(cand, n)
        if score(cand) > best_score:
            best_score = score(cand)
            best = cand

    # Polish the start first
    if best is not None and elapsed() < HARD:
        pol = _slsqp_polish(best, n, maxiter=3000, ftol=1e-16)
        pol = _feasible_fix(pol, n)
        if score(pol) > best_score:
            best_score = score(pol)
            best = pol

    for centers in inits:
        if elapsed() > 0.5 * budget_seconds:
            break
        try:
            cand = make_cand(centers)
            consider(cand)
            if elapsed() < 0.5 * budget_seconds:
                pol = _slsqp_polish(cand, n, maxiter=1200)
                pol = _feasible_fix(pol, n)
                if score(pol) > best_score:
                    best_score = score(pol)
                    best = pol
        except Exception:
            pass

    # Random restarts / perturbations around best
    while best is not None and elapsed() < HARD:
        try:
            cand = best.copy()
            scale = rng.uniform(0.01, 0.05)
            cand[:, 0] += rng.normal(0, scale, n)
            cand[:, 1] += rng.normal(0, scale, n)
            cand = _feasible_fix(cand, n)
            newc = make_cand(cand[:, :2])
            pol = _slsqp_polish(newc, n, maxiter=1200)
            pol = _feasible_fix(pol, n)
            if score(pol) > best_score:
                best_score = score(pol)
                best = pol
        except Exception:
            break

    if best is None:
        if start is not None:
            return _feasible_fix(start, n)
        p = hex_init(6, 6)
        return make_cand(np.array(p[:n]))

    # Final LP re-solve at final centers with tight tolerances
    try:
        centers = best[:, :2].copy()
        r = _lp_radii(centers, n)
        if r is not None:
            cand = np.column_stack([centers, r])
            cand = _feasible_fix(cand, n)
            if score(cand) > best_score:
                best = cand
                best_score = score(cand)
    except Exception:
        pass

    # SLP tangent-space improvement loop
    margin = 1.5
    it = 0
    while best is not None and it < 40 and elapsed() < budget_seconds - margin:
        it += 1
        try:
            v, opt = _slp_step(best, n, delta=2e-3)
        except Exception:
            break
        if v is None or opt < 1e-12:
            break
        try:
            x_new = best.reshape(-1) + 0.5 * v
            x_new = x_new.reshape(n, 3)
            x_new = _feasible_fix(x_new, n)
            pol = _slsqp_polish(x_new, n, maxiter=2000)
            pol = _feasible_fix(pol, n)
            if score(pol) > best_score:
                best = pol
                best_score = score(pol)
            else:
                # no improvement; try smaller step once then stop
                x_new2 = best.reshape(-1) + 0.25 * v
                x_new2 = _feasible_fix(x_new2.reshape(n, 3), n)
                pol2 = _slsqp_polish(x_new2, n, maxiter=2000)
                pol2 = _feasible_fix(pol2, n)
                if score(pol2) > best_score:
                    best = pol2
                    best_score = score(pol2)
                else:
                    break
        except Exception:
            break

    return best
