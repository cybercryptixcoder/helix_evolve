import numpy as np
import time
from scipy.optimize import linprog, minimize


def _solve_lp(centers):
    n = len(centers)
    c = -np.ones(n)
    A_ub = []
    b_ub = []
    for i in range(n):
        x, y = centers[i]
        for bound in (x, 1.0 - x, y, 1.0 - y):
            row = np.zeros(n)
            row[i] = 1.0
            A_ub.append(row)
            b_ub.append(bound)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.hypot(centers[i, 0] - centers[j, 0], centers[i, 1] - centers[j, 1])
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            A_ub.append(row)
            b_ub.append(d)
    try:
        res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub),
                      bounds=[(0, None)] * n, method='highs')
    except Exception:
        return None
    if not res.success:
        return None
    return res.x


def _validate(sol):
    n = len(sol)
    for i in range(n):
        x, y, r = sol[i]
        if r <= 0:
            return False
        if x - r < -1e-12 or x + r > 1 + 1e-12:
            return False
        if y - r < -1e-12 or y + r > 1 + 1e-12:
            return False
    for i in range(n):
        for j in range(i + 1, n):
            d = np.hypot(sol[i, 0] - sol[j, 0], sol[i, 1] - sol[j, 1])
            if d < sol[i, 2] + sol[j, 2] - 1e-12:
                return False
    return True


def _shrink_to_feasible(sol, tol=1e-11):
    sol = np.asarray(sol, dtype=float).copy()
    n = len(sol)
    for i in range(n):
        x, y, r = sol[i]
        r = max(r, 1e-9)
        x = min(max(x, r), 1.0 - r)
        y = min(max(y, r), 1.0 - r)
        sol[i, 0] = x
        sol[i, 1] = y
    for _ in range(80):
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                d = np.hypot(sol[i, 0] - sol[j, 0], sol[i, 1] - sol[j, 1])
                s = sol[i, 2] + sol[j, 2]
                if d < s:
                    excess = s - d
                    ri, rj = sol[i, 2], sol[j, 2]
                    tot = ri + rj
                    if tot > 0:
                        sol[i, 2] = max(ri - excess * ri / tot - tol, 1e-9)
                        sol[j, 2] = max(rj - excess * rj / tot - tol, 1e-9)
                    changed = True
        for i in range(n):
            x, y, r = sol[i]
            x = min(max(x, r), 1.0 - r)
            y = min(max(y, r), 1.0 - r)
            sol[i, 0] = x
            sol[i, 1] = y
        if not changed:
            break
    sol[:, 2] = np.maximum(sol[:, 2] - 1e-12, 1e-9)
    return sol


def _slp_polish(sol, deadline, max_stall=5, delta0=0.01):
    sol = sol.copy()
    n = len(sol)
    delta = delta0
    best = sol.copy()
    best_sum = sol[:, 2].sum()
    stall = 0
    it = 0
    while time.process_time() < deadline:
        it += 1
        x = sol[:, 0]; y = sol[:, 1]; r = sol[:, 2]
        nv = 3 * n
        c = np.zeros(nv); c[2 * n:] = -1.0
        A_ub = []; b_ub = []
        for i in range(n):
            row = np.zeros(nv); row[i] = -1.0; row[2*n+i] = 1.0
            A_ub.append(row); b_ub.append(x[i] - r[i])
            row = np.zeros(nv); row[i] = 1.0; row[2*n+i] = 1.0
            A_ub.append(row); b_ub.append(1.0 - x[i] - r[i])
            row = np.zeros(nv); row[n+i] = -1.0; row[2*n+i] = 1.0
            A_ub.append(row); b_ub.append(y[i] - r[i])
            row = np.zeros(nv); row[n+i] = 1.0; row[2*n+i] = 1.0
            A_ub.append(row); b_ub.append(1.0 - y[i] - r[i])
        for i in range(n):
            for j in range(i + 1, n):
                dxij = x[i] - x[j]; dyij = y[i] - y[j]
                d = np.hypot(dxij, dyij)
                if d < 1e-12:
                    ux, uy = 1.0, 0.0
                else:
                    ux, uy = dxij / d, dyij / d
                row = np.zeros(nv)
                row[i] = -ux; row[j] = ux
                row[n+i] = -uy; row[n+j] = uy
                row[2*n+i] = 1.0; row[2*n+j] = 1.0
                A_ub.append(row); b_ub.append(d - r[i] - r[j])
        for k in range(nv):
            row = np.zeros(nv); row[k] = 1.0
            A_ub.append(row); b_ub.append(delta)
            row = np.zeros(nv); row[k] = -1.0
            A_ub.append(row); b_ub.append(delta)
        try:
            res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub),
                          bounds=[(None, None)] * nv, method='highs')
        except Exception:
            break
        if not res.success:
            delta *= 0.5
            if delta < 1e-8:
                break
            continue
        d = res.x
        new_sol = sol.copy()
        new_sol[:, 0] = x + d[:n]
        new_sol[:, 1] = y + d[n:2*n]
        new_sol[:, 2] = r + d[2*n:]
        new_sol[:, 2] = np.maximum(new_sol[:, 2], 1e-9)
        for i in range(n):
            xi, yi, ri = new_sol[i]
            new_sol[i, 0] = min(max(xi, ri), 1.0 - ri)
            new_sol[i, 1] = min(max(yi, ri), 1.0 - ri)
        new_sol = _shrink_to_feasible(new_sol)
        s = new_sol[:, 2].sum()
        if s > best_sum + 1e-10:
            best_sum = s
            best = new_sol.copy()
            sol = new_sol
            stall = 0
        else:
            sol = new_sol
            stall += 1
        if stall >= max_stall or it % 25 == 0:
            delta *= 0.5
            stall = 0
            if delta < 1e-8:
                break
    return best


def _gradient_descent(sol, deadline, iters=400):
    sol = sol.copy()
    n = len(sol)
    centers = sol[:, :2].copy()
    best = sol.copy()
    best_sum = sol[:, 2].sum()
    for it in range(iters):
        if time.process_time() >= deadline:
            break
        radii = _solve_lp(centers)
        if radii is None:
            break
        cand = np.column_stack([centers, radii])
        cand = _shrink_to_feasible(cand)
        s = cand[:, 2].sum()
        if s > best_sum + 1e-11:
            best_sum = s
            best = cand.copy()
        disp = np.zeros_like(centers)
        for i in range(n):
            xi, yi = centers[i]
            ri = radii[i]
            for (val, axis, sign) in ((xi, 0, 1.0), (1.0 - xi, 0, -1.0),
                                      (yi, 1, 1.0), (1.0 - yi, 1, -1.0)):
                if val - ri < 1e-4:
                    disp[i, axis] += sign * 1e-3
            for j in range(n):
                if i == j:
                    continue
                dx = xi - centers[j, 0]; dy = yi - centers[j, 1]
                d = np.hypot(dx, dy)
                if d < 1e-12:
                    dx, dy, d = 1e-6, 0.0, 1e-6
                if d < ri + radii[j] + 1e-4:
                    disp[i, 0] += 1e-3 * dx / d
                    disp[i, 1] += 1e-3 * dy / d
        centers = centers + disp
        centers = np.clip(centers, 0.0, 1.0)
    return best


def _slsqp_polish(sol, deadline):
    """Exact SLSQP on the true nonlinear constraints, looping until deadline."""
    best = sol.copy()
    best_sum = best[:, 2].sum()
    n = len(best)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    npairs = len(pairs)

    def unpack(z):
        return z[:n], z[n:2*n], z[2*n:]

    def obj(z):
        return -z[2*n:].sum()

    def jac(z):
        g = np.zeros(3 * n)
        g[2*n:] = -1.0
        return g

    # constraints g(z) >= 0
    def cons(z):
        x, y, r = unpack(z)
        out = np.empty(4 * n + npairs)
        out[0:4*n:4] = x - r
        out[1:4*n:4] = 1.0 - x - r
        out[2:4*n:4] = y - r
        out[3:4*n:4] = 1.0 - y - r
        k = 4 * n
        for (i, j) in pairs:
            dx = x[i] - x[j]; dy = y[i] - y[j]
            out[k] = np.hypot(dx, dy) - r[i] - r[j]
            k += 1
        return out

    def cons_jac(z):
        x, y, r = unpack(z)
        J = np.zeros((4 * n + npairs, 3 * n))
        for i in range(n):
            J[4*i, i] = 1.0;     J[4*i, 2*n+i] = -1.0
            J[4*i+1, i] = -1.0;  J[4*i+1, 2*n+i] = -1.0
            J[4*i+2, n+i] = 1.0; J[4*i+2, 2*n+i] = -1.0
            J[4*i+3, n+i] = -1.0; J[4*i+3, 2*n+i] = -1.0
        k = 4 * n
        for (i, j) in pairs:
            dx = x[i] - x[j]; dy = y[i] - y[j]
            d = np.hypot(dx, dy)
            if d < 1e-12:
                ux, uy = 1.0, 0.0
            else:
                ux, uy = dx / d, dy / d
            J[k, i] = ux;  J[k, j] = -ux
            J[k, n+i] = uy; J[k, n+j] = -uy
            J[k, 2*n+i] = -1.0; J[k, 2*n+j] = -1.0
            k += 1
        return J

    bounds = [(0.0, 1.0)] * (2 * n) + [(1e-9, 0.5)] * n
    constraints = [{'type': 'ineq', 'fun': cons, 'jac': cons_jac}]

    z0 = np.concatenate([best[:, 0], best[:, 1], best[:, 2]])

    while time.process_time() < deadline:
        try:
            res = minimize(obj, z0, jac=jac, method='SLSQP',
                           bounds=bounds, constraints=constraints,
                           options={'ftol': 1e-14, 'maxiter': 500})
        except Exception:
            break
        if res.x is None:
            break
        x, y, r = unpack(res.x)
        cand = np.column_stack([x, y, np.maximum(r, 1e-9)])
        cand = _shrink_to_feasible(cand)
        s = cand[:, 2].sum()
        if s > best_sum + 1e-13:
            best = cand
            best_sum = s
            z0 = np.concatenate([best[:, 0], best[:, 1], best[:, 2]])
        else:
            # try a tiny perturbation to escape
            z0 = np.concatenate([best[:, 0], best[:, 1], best[:, 2]])
            z0[:2*n] += np.random.uniform(-1e-7, 1e-7, 2*n)
            z0[:2*n] = np.clip(z0[:2*n], 0.0, 1.0)
            if time.process_time() >= deadline:
                break
            # one more attempt then stop if no progress
            try:
                res2 = minimize(obj, z0, jac=jac, method='SLSQP',
                                bounds=bounds, constraints=constraints,
                                options={'ftol': 1e-14, 'maxiter': 500})
                if res2.x is not None:
                    x, y, r = unpack(res2.x)
                    cand = np.column_stack([x, y, np.maximum(r, 1e-9)])
                    cand = _shrink_to_feasible(cand)
                    s = cand[:, 2].sum()
                    if s > best_sum + 1e-13:
                        best = cand
                        best_sum = s
                        continue
            except Exception:
                pass
            break
    return best


def construct(budget_seconds, start):
    t0 = time.process_time()
    hard_deadline = t0 + budget_seconds - 0.35

    if start is not None:
        base = _shrink_to_feasible(np.asarray(start, dtype=float).copy())
    else:
        pts = []
        rows = 6
        for j in range(rows):
            y = (j + 0.5) / rows
            cols = 6 if j % 2 == 0 else 5
            for i in range(cols):
                x = (i + 0.5) / cols
                if j % 2 == 1:
                    x = (i + 1.0) / (cols + 1)
                pts.append((x, y))
        pts = pts[:32]
        while len(pts) < 32:
            pts.append((0.5, 0.5))
        centers = np.array(pts)
        radii = _solve_lp(centers)
        if radii is None:
            radii = np.full(32, 0.001)
        base = _shrink_to_feasible(np.column_stack([centers, radii]))

    best = base.copy()
    best_sum = best[:, 2].sum()

    # Phase 1: SLP polish
    p1 = min(time.process_time() + 0.35 * budget_seconds, hard_deadline)
    pol = _slp_polish(best, p1, max_stall=6, delta0=0.01)
    if pol[:, 2].sum() > best_sum:
        best = pol
        best_sum = pol[:, 2].sum()

    # Phase 2: gradient-descent + LP
    p2 = min(time.process_time() + 0.20 * budget_seconds, hard_deadline)
    gd = _gradient_descent(best, p2)
    if gd[:, 2].sum() > best_sum:
        best = gd
        best_sum = gd[:, 2].sum()
    pol = _slp_polish(best, min(time.process_time() + 0.4, hard_deadline),
                      max_stall=4, delta0=0.004)
    if pol[:, 2].sum() > best_sum:
        best = pol
        best_sum = pol[:, 2].sum()

    # Phase 3: fine SLP
    while time.process_time() < hard_deadline - 1.0:
        pol = _slp_polish(best, min(time.process_time() + 0.6, hard_deadline - 1.0),
                          max_stall=3, delta0=0.001)
        s = pol[:, 2].sum()
        if s > best_sum + 1e-11:
            best = pol
            best_sum = s
        else:
            break

    # Phase 4: exact SLSQP final polish
    sls = _slsqp_polish(best, hard_deadline)
    if sls[:, 2].sum() > best_sum:
        best = sls
        best_sum = sls[:, 2].sum()

    best = _shrink_to_feasible(best)
    if _validate(best):
        return best
    fb = _shrink_to_feasible(base)
    if _validate(fb):
        return fb
    return best
