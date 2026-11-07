import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    N = 32
    deadline = budget_seconds - 0.5

    def elapsed():
        return time.process_time() - t0

    ii, jj = np.triu_indices(N, 1)
    npair = len(ii)

    def unpack(v):
        return v[0::3].copy(), v[1::3].copy(), v[2::3].copy()

    def pack(x, y, r):
        v = np.empty(3 * N)
        v[0::3] = x
        v[1::3] = y
        v[2::3] = r
        return v

    # --- smooth penalty + gradient (tangent-aware, scaled) ---
    def penalty_and_grad(v, rho):
        x, y, r = unpack(v)
        e1 = np.maximum(0.0, r - x)
        e2 = np.maximum(0.0, r - (1.0 - x))
        e3 = np.maximum(0.0, r - y)
        e4 = np.maximum(0.0, r - (1.0 - y))
        dx = x[ii] - x[jj]
        dy = y[ii] - y[jj]
        d2 = dx * dx + dy * dy
        d = np.sqrt(d2)
        s = r[ii] + r[jj]
        pv = np.maximum(0.0, s - d)
        f = -np.sum(r) + rho * (np.dot(e1, e1) + np.dot(e2, e2) +
                                np.dot(e3, e3) + np.dot(e4, e4) + np.dot(pv, pv))
        gx = rho * (-2.0 * e1 + 2.0 * e2)
        gy = rho * (-2.0 * e3 + 2.0 * e4)
        gr = rho * (2.0 * e1 + 2.0 * e2 + 2.0 * e3 + 2.0 * e4)
        coef = rho * 2.0 * pv
        invd = np.where(d > 1e-12, 1.0 / np.maximum(d, 1e-12), 0.0)
        cx = coef * dx * invd
        cy = coef * dy * invd
        np.add.at(gx, ii, cx)
        np.add.at(gx, jj, -cx)
        np.add.at(gy, ii, cy)
        np.add.at(gy, jj, -cy)
        np.add.at(gr, ii, coef)
        np.add.at(gr, jj, coef)
        gr -= 1.0
        return f, pack(gx, gy, gr)

    def shrink_feasible(x, y, r):
        r = r.copy()
        for _ in range(200):
            r = np.minimum(r, x)
            r = np.minimum(r, 1.0 - x)
            r = np.minimum(r, y)
            r = np.minimum(r, 1.0 - y)
            dx = x[ii] - x[jj]
            dy = y[ii] - y[jj]
            d = np.sqrt(dx * dx + dy * dy)
            s = r[ii] + r[jj]
            viol = s > d
            if np.any(viol):
                idx = np.where(viol)[0]
                a = ii[idx]
                b = jj[idx]
                sc = (d[idx] / (r[a] + r[b])) * (1.0 - 1e-13)
                r[a] *= sc
                r[b] *= sc
            r = r * (1.0 - 1e-13)
            dx = x[ii] - x[jj]
            dy = y[ii] - y[jj]
            d = np.sqrt(dx * dx + dy * dy)
            ok = (np.all(r[ii] + r[jj] <= d) and np.all(r <= x) and
                  np.all(r <= 1 - x) and np.all(r <= y) and
                  np.all(r <= 1 - y) and np.all(r > 0))
            if ok:
                break
        return np.maximum(r, 1e-12)

    def hex_seed():
        k = 6
        pts = []
        for j in range(k):
            for i in range(k):
                x = (i + 0.5 + (0.5 if j % 2 else 0.0)) / k
                y = (j + 0.5) / k
                if x < 1.0:
                    pts.append((x, y))
        pts = pts[:N]
        while len(pts) < N:
            pts.append((0.5, 0.5))
        r0 = 0.4 / k
        return np.array([[x, y, r0] for x, y in pts])

    # --- SLSQP exact polish ---
    def objective(v):
        return -np.sum(v[2::3])

    def objective_grad(v):
        g = np.zeros_like(v)
        g[2::3] = -1.0
        return g

    def constraints(v):
        x, y, r = unpack(v)
        cons = [x - r, 1.0 - x - r, y - r, 1.0 - y - r]
        dx = x[ii] - x[jj]
        dy = y[ii] - y[jj]
        s = r[ii] + r[jj]
        cons.append(dx * dx + dy * dy - s * s)
        return np.concatenate(cons)

    def constraints_jac(v):
        x, y, r = unpack(v)
        rows = []
        idx = np.arange(N)
        J = np.zeros((N, 3 * N))
        J[idx, 3 * idx] = 1.0
        J[idx, 3 * idx + 2] = -1.0
        rows.append(J)
        J = np.zeros((N, 3 * N))
        J[idx, 3 * idx] = -1.0
        J[idx, 3 * idx + 2] = -1.0
        rows.append(J)
        J = np.zeros((N, 3 * N))
        J[idx, 3 * idx + 1] = 1.0
        J[idx, 3 * idx + 2] = -1.0
        rows.append(J)
        J = np.zeros((N, 3 * N))
        J[idx, 3 * idx + 1] = -1.0
        J[idx, 3 * idx + 2] = -1.0
        rows.append(J)
        Jp = np.zeros((npair, 3 * N))
        dx = x[ii] - x[jj]
        dy = y[ii] - y[jj]
        s = r[ii] + r[jj]
        ar = np.arange(npair)
        Jp[ar, 3 * ii] += 2 * dx
        Jp[ar, 3 * jj] -= 2 * dx
        Jp[ar, 3 * ii + 1] += 2 * dy
        Jp[ar, 3 * jj + 1] -= 2 * dy
        Jp[ar, 3 * ii + 2] += -2 * s
        Jp[ar, 3 * jj + 2] += -2 * s
        rows.append(Jp)
        return np.vstack(rows)

    bounds = []
    for i in range(N):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-6, 0.5))
    cons = [{'type': 'ineq', 'fun': constraints, 'jac': constraints_jac}]

    def slsqp_polish(x, y, r, maxiter=300):
        v0 = pack(x, y, r)
        try:
            res = minimize(objective, v0, jac=objective_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter': maxiter, 'ftol': 1e-15, 'disp': False})
            if constraints(res.x).min() >= -1e-8:
                return unpack(res.x)
        except Exception:
            pass
        return x, y, r

    def lbfgs_penalty(x, y, r, rhos, maxiter=800):
        v = pack(x, y, r)
        for rho in rhos:
            if elapsed() > deadline:
                break
            try:
                res = minimize(lambda vv: penalty_and_grad(vv, rho), v, jac=True,
                               method='L-BFGS-B', bounds=bounds,
                               options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-12})
                v = res.x
            except Exception:
                pass
        return unpack(v)

    best_score = -1.0
    best = None

    if start is not None:
        s0 = np.asarray(start, dtype=float)
        x, y, r = s0[:, 0].copy(), s0[:, 1].copy(), s0[:, 2].copy()
        r = shrink_feasible(x, y, r)
        best_score = float(np.sum(r))
        best = (x.copy(), y.copy(), r.copy())
        bx, by, br = x.copy(), y.copy(), r.copy()
    else:
        g = hex_seed()
        bx, by, br = g[:, 0].copy(), g[:, 1].copy(), g[:, 2].copy()
        br = np.maximum(br, 1e-3)

    rng = np.random.default_rng(2024)

    def consider(x, y, r, do_slsqp=True):
        nonlocal best_score, best
        r = shrink_feasible(x, y, r)
        if do_slsqp and elapsed() < deadline - 0.2:
            x2, y2, r2 = slsqp_polish(x, y, r, maxiter=250)
            r2 = shrink_feasible(x2, y2, r2)
            if np.sum(r2) > np.sum(r):
                x, y, r = x2, y2, r2
        sc = float(np.sum(r))
        if sc > best_score:
            best_score = sc
            best = (x.copy(), y.copy(), r.copy())
        return sc

    # Phase 1: strong polish of start
    if elapsed() < deadline - 0.5:
        x, y, r = lbfgs_penalty(bx, by, br, [1e3, 1e4, 1e5, 1e6, 1e7])
        consider(x, y, r)

    # grid for relocation of under-connected circle
    gx = np.linspace(0.0, 1.0, 80)
    gy = np.linspace(0.0, 1.0, 80)
    GX, GY = np.meshgrid(gx, gy)
    GX = GX.ravel()
    GY = GY.ravel()

    def relocate_void(x, y, r):
        # choose circle with fewest contacts, tie-break smallest radius
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        s = r[:, None] + r[None, :]
        contact = (d - s) < 1e-8
        np.fill_diagonal(contact, False)
        ncont = contact.sum(axis=1)
        # score: prefer fewest contacts, then smallest radius
        order = np.lexsort((r, ncont))
        k = int(order[0])
        # clearance at grid points
        wall = np.minimum(np.minimum(GX, 1.0 - GX), np.minimum(GY, 1.0 - GY))
        clear = wall.copy()
        for j in range(N):
            if j == k:
                continue
            dd = np.sqrt((GX - x[j]) ** 2 + (GY - y[j]) ** 2) - r[j]
            clear = np.minimum(clear, dd)
        idx = int(np.argmax(clear))
        c = clear[idx]
        if c <= 0:
            return x, y, r
        x = x.copy()
        y = y.copy()
        r = r.copy()
        x[k] = GX[idx]
        y[k] = GY[idx]
        r[k] = 0.95 * c
        return x, y, r

    # Phase 2: targeted perturbation search with SLSQP polish
    it = 0
    while elapsed() < deadline - 0.15:
        it += 1
        if it % 5 == 0:
            x, y, r = relocate_void(best[0], best[1], best[2])
        else:
            x = best[0].copy()
            y = best[1].copy()
            r = best[2].copy()
            nk = int(rng.integers(1, 4))
            for _ in range(nk):
                w = r / r.sum()
                i = int(rng.choice(N, p=w))
                x[i] += rng.normal(0, 0.015)
                y[i] += rng.normal(0, 0.015)
                r[i] = max(1e-4, r[i] * (1.0 + rng.normal(0, 0.02)))
            x = np.clip(x, 0.0, 1.0)
            y = np.clip(y, 0.0, 1.0)
            r = np.minimum(r, 0.5)

        x, y, r = lbfgs_penalty(x, y, r, [1e4, 1e5, 1e6], maxiter=300)
        consider(x, y, r)

    x, y, r = best
    r = shrink_feasible(x, y, r)
    return np.column_stack([x, y, r])
