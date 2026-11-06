import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = budget_seconds - 1.2

    n = 32
    iu = np.triu_indices(n, 1)
    ii, jj = iu[0], iu[1]
    npair = len(ii)
    idx = np.arange(n)

    def unpack(v):
        return v[:n], v[n:2*n], v[2*n:]

    def objective(v):
        return -np.sum(v[2*n:])

    def objective_jac(v):
        g = np.zeros(3 * n)
        g[2*n:] = -1.0
        return g

    def constraint_ineq(v):
        x, y, r = unpack(v)
        cons = [x - r, 1.0 - x - r, y - r, 1.0 - y - r]
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx*dx + dy*dy)
        rr = r[:, None] + r[None, :]
        cons.append((d - rr)[iu])
        return np.concatenate(cons)

    def constraint_jac(v):
        x, y, r = unpack(v)
        m = 4 * n + npair
        J = np.zeros((m, 3 * n))
        J[idx, idx] = 1.0
        J[idx, 2*n + idx] = -1.0
        J[n + idx, idx] = -1.0
        J[n + idx, 2*n + idx] = -1.0
        J[2*n + idx, n + idx] = 1.0
        J[2*n + idx, 2*n + idx] = -1.0
        J[3*n + idx, n + idx] = -1.0
        J[3*n + idx, 2*n + idx] = -1.0
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx*dx + dy*dy)
        d = np.maximum(d, 1e-12)
        base = 4 * n
        ux = dx[ii, jj] / d[ii, jj]
        uy = dy[ii, jj] / d[ii, jj]
        rows = base + np.arange(npair)
        J[rows, ii] = ux
        J[rows, jj] = -ux
        J[rows, n + ii] = uy
        J[rows, n + jj] = -uy
        J[rows, 2*n + ii] = -1.0
        J[rows, 2*n + jj] = -1.0
        return J

    def repair(v):
        x, y, r = unpack(v.copy())
        r = np.maximum(r, 1e-8)
        x = np.clip(x, r, 1 - r)
        y = np.clip(y, r, 1 - r)
        for _ in range(80):
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx*dx + dy*dy)
            rr = r[:, None] + r[None, :]
            viol = (rr - d)[iu]
            worst = viol.max() if npair else 0.0
            wall_viol = max((r - x).max(), (r - (1 - x)).max(),
                            (r - y).max(), (r - (1 - y)).max())
            w = max(worst, wall_viol)
            if w <= 1e-13:
                break
            scale = 0.9 if w > 1e-3 else 0.999
            r = np.maximum(r * scale, 1e-9)
            x = np.clip(x, r, 1 - r)
            y = np.clip(y, r, 1 - r)
        return np.concatenate([x, y, r])

    def make_start(s):
        if s is not None:
            s = np.asarray(s, dtype=float).copy()
            x, y, r = s[:, 0].copy(), s[:, 1].copy(), s[:, 2].copy()
        else:
            k = 6
            pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
            x = np.array([p[0] for p in pts])
            y = np.array([p[1] for p in pts])
            r = np.full(n, 0.05)
        r = np.clip(r, 1e-6, 0.5)
        x = np.clip(x, r, 1 - r)
        y = np.clip(y, r, 1 - r)
        return np.concatenate([x, y, r])

    bounds = [(0.0, 1.0)] * (2 * n) + [(1e-6, 0.5)] * n
    cons = {'type': 'ineq', 'fun': constraint_ineq, 'jac': constraint_jac}

    def try_solve(x0, maxiter, ftol):
        try:
            res = minimize(objective, x0, jac=objective_jac, method='SLSQP',
                           bounds=bounds, constraints=[cons],
                           options={'maxiter': maxiter, 'ftol': ftol})
            return res.x
        except Exception:
            return None

    best_v = None
    best_score = -np.inf

    def consider(v):
        nonlocal best_v, best_score
        if v is None:
            return
        v = repair(v)
        sc = np.sum(v[2*n:])
        if sc > best_score:
            best_score = sc
            best_v = v.copy()

    x0 = make_start(start)

    # Refine the start.
    if time.process_time() - t0 < deadline:
        consider(try_solve(x0, 3000, 1e-14))

    if best_v is None:
        best_v = repair(x0)
        best_score = np.sum(best_v[2*n:])

    # ---- Cluster ILS: jointly reoptimize a small cluster of 4 circles ----
    cl_rng = np.random.RandomState(4242)

    # Precompute cluster sub-problem machinery lazily per call.
    def solve_cluster(base_v, cluster, maxiter=500, ftol=1e-13):
        # cluster: list of circle indices to reoptimize (others frozen)
        x0_, y0_, r0_ = unpack(base_v.copy())
        k = len(cluster)
        cluster = list(cluster)
        cset = set(cluster)
        frozen = [i for i in range(n) if i not in cset]
        fx = x0_[frozen]; fy = y0_[frozen]; fr = r0_[frozen]
        nf = len(frozen)

        # Variables: [xc(k), yc(k), rc(k)]
        def unpack_c(v):
            return v[:k], v[k:2*k], v[2*k:]

        def obj(v):
            return -np.sum(v[2*k:])

        def obj_jac(v):
            g = np.zeros(3*k)
            g[2*k:] = -1.0
            return g

        # Precompute frozen-frozen distances (constant)
        def cons_fun(v):
            xc, yc, rc = unpack_c(v)
            out = []
            out.append(xc - rc)
            out.append(1.0 - xc - rc)
            out.append(yc - rc)
            out.append(1.0 - yc - rc)
            # cluster-cluster
            if k > 1:
                dx = xc[:, None] - xc[None, :]
                dy = yc[:, None] - yc[None, :]
                d = np.sqrt(dx*dx + dy*dy)
                rr = rc[:, None] + rc[None, :]
                ku = np.triu_indices(k, 1)
                out.append((d - rr)[ku])
            # cluster-frozen
            if nf > 0:
                dx = xc[:, None] - fx[None, :]
                dy = yc[:, None] - fy[None, :]
                d = np.sqrt(dx*dx + dy*dy)
                rr = rc[:, None] + fr[None, :]
                out.append((d - rr).ravel())
            return np.concatenate(out)

        def cons_jac(v):
            xc, yc, rc = unpack_c(v)
            # Count rows
            n_cc = k*(k-1)//2 if k > 1 else 0
            n_cf = k*nf
            m = 4*k + n_cc + n_cf
            J = np.zeros((m, 3*k))
            ci = np.arange(k)
            # walls
            J[ci, ci] = 1.0
            J[ci, 2*k + ci] = -1.0
            J[k + ci, ci] = -1.0
            J[k + ci, 2*k + ci] = -1.0
            J[2*k + ci, k + ci] = 1.0
            J[2*k + ci, 2*k + ci] = -1.0
            J[3*k + ci, k + ci] = -1.0
            J[3*k + ci, 2*k + ci] = -1.0
            row = 4*k
            if k > 1:
                ku = np.triu_indices(k, 1)
                a, b = ku[0], ku[1]
                dx = xc[a] - xc[b]
                dy = yc[a] - yc[b]
                d = np.maximum(np.sqrt(dx*dx + dy*dy), 1e-12)
                ux = dx / d; uy = dy / d
                rows = row + np.arange(n_cc)
                J[rows, a] = ux
                J[rows, b] = -ux
                J[rows, k + a] = uy
                J[rows, k + b] = -uy
                J[rows, 2*k + a] = -1.0
                J[rows, 2*k + b] = -1.0
                row += n_cc
            if nf > 0:
                # cluster-frozen, raveled (k, nf) -> row order matches cons_fun
                dx = xc[:, None] - fx[None, :]
                dy = yc[:, None] - fy[None, :]
                d = np.maximum(np.sqrt(dx*dx + dy*dy), 1e-12)
                ux = dx / d; uy = dy / d
                for a in range(k):
                    rows = row + a*nf + np.arange(nf)
                    J[rows, a] = ux[a]
                    J[rows, k + a] = uy[a]
                    J[rows, 2*k + a] = -1.0
                row += k*nf
            return J

        cbounds = [(0.0, 1.0)] * (2*k) + [(1e-6, 0.5)] * k
        ccons = {'type': 'ineq', 'fun': cons_fun, 'jac': cons_jac}

        v0 = np.concatenate([x0_[cluster], y0_[cluster], r0_[cluster]])
        try:
            res = minimize(obj, v0, jac=obj_jac, method='SLSQP',
                           bounds=cbounds, constraints=[ccons],
                           options={'maxiter': maxiter, 'ftol': ftol})
            vc = res.x
        except Exception:
            return None
        xc, yc, rc = unpack_c(vc)
        # Build full vector
        xf = x0_.copy(); yf = y0_.copy(); rf = r0_.copy()
        for t, i in enumerate(cluster):
            xf[i] = xc[t]; yf[i] = yc[t]; rf[i] = rc[t]
        return np.concatenate([xf, yf, rf])

    def build_cluster(base_v, seed_idx, target=4):
        x_, y_, r_ = unpack(base_v)
        # contact graph
        dx = x_[:, None] - x_[None, :]
        dy = y_[:, None] - y_[None, :]
        d = np.sqrt(dx*dx + dy*dy)
        rr = r_[:, None] + r_[None, :]
        adj = (d <= rr + 0.02)
        np.fill_diagonal(adj, False)
        visited = {seed_idx}
        order = [seed_idx]
        qi = 0
        while qi < len(order) and len(order) < target:
            cur = order[qi]; qi += 1
            nbrs = np.where(adj[cur])[0]
            # prefer smallest radii to keep cluster small
            nbrs = sorted(nbrs.tolist(), key=lambda j: r_[j])
            for j in nbrs:
                if j not in visited:
                    visited.add(j)
                    order.append(j)
                    if len(order) >= target:
                        break
        return order

    # Main cluster-ILS loop
    while time.process_time() - t0 < deadline - 0.5:
        x_, y_, r_ = unpack(best_v)
        order = np.argsort(r_)
        seed = int(order[cl_rng.randint(0, 12)])
        cluster = build_cluster(best_v, seed, target=4)
        if len(cluster) < 2:
            continue
        # bounding box of cluster
        cx = x_[cluster]; cy = y_[cluster]
        xmin, xmax = cx.min() - 0.05, cx.max() + 0.05
        ymin, ymax = cy.min() - 0.05, cy.max() + 0.05
        xmin = max(xmin, 0.0); xmax = min(xmax, 1.0)
        ymin = max(ymin, 0.0); ymax = min(ymax, 1.0)

        best_cluster_v = None
        best_cluster_score = np.sum(r_)

        for restart in range(5):
            if time.process_time() - t0 >= deadline - 0.5:
                break
            cand = best_v.copy()
            xc_, yc_, rc_ = unpack(cand)
            k = len(cluster)
            # randomize cluster centers in bbox
            newx = cl_rng.uniform(xmin, xmax, k)
            newy = cl_rng.uniform(ymin, ymax, k)
            # set radii to half clearance
            frozen = [i for i in range(n) if i not in set(cluster)]
            fx = xc_[frozen]; fy = yc_[frozen]; fr = rc_[frozen]
            for t, i in enumerate(cluster):
                # clearance to frozen circles
                if len(frozen) > 0:
                    dd = np.sqrt((newx[t] - fx)**2 + (newy[t] - fy)**2) - fr
                    clr = dd.min()
                else:
                    clr = 0.5
                wall = min(newx[t], 1.0 - newx[t], newy[t], 1.0 - newy[t])
                clr = min(clr, wall)
                rc_[i] = max(0.5 * clr - 1e-8, 1e-6)
                xc_[i] = np.clip(newx[t], rc_[i], 1.0 - rc_[i])
                yc_[i] = np.clip(newy[t], rc_[i], 1.0 - rc_[i])
            cand = repair(np.concatenate([xc_, yc_, rc_]))
            v = solve_cluster(cand, cluster, maxiter=500, ftol=1e-13)
            if v is not None:
                v = repair(v)
                sc = np.sum(v[2*n:])
                if sc > best_cluster_score + 1e-11:
                    best_cluster_score = sc
                    best_cluster_v = v.copy()

        if best_cluster_v is not None:
            # full polish
            if time.process_time() - t0 < deadline - 0.3:
                v = try_solve(best_cluster_v, 2000, 1e-14)
                consider(v)
            else:
                consider(best_cluster_v)

    # Final polish
    if best_v is not None and time.process_time() - t0 < deadline:
        consider(try_solve(best_v.copy(), 3000, 1e-14))

    if best_v is None:
        best_v = repair(x0)

    x, y, r = unpack(best_v)

    def project(x, y, r):
        x = x.copy(); y = y.copy(); r = r.copy()
        for _ in range(100):
            wall = np.maximum.reduce([
                r - x, r - (1.0 - x), r - y, r - (1.0 - y),
                np.zeros(n)])
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx*dx + dy*dy)
            rr = r[:, None] + r[None, :]
            vmat = rr - d
            np.fill_diagonal(vmat, 0.0)
            pair = np.maximum(vmat, 0.0)
            pair_half = 0.5 * pair.max(axis=1)
            total = np.maximum(wall, pair_half)
            if total.max() <= 5e-13:
                break
            r = np.maximum(r - (total + 1e-13), 1e-12)
            x = np.clip(x, r, 1.0 - r)
            y = np.clip(y, r, 1.0 - r)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx*dx + dy*dy)
        rr = r[:, None] + r[None, :]
        vmat = rr - d
        np.fill_diagonal(vmat, 0.0)
        wall = np.maximum.reduce([
            r - x, r - (1.0 - x), r - y, r - (1.0 - y), np.zeros(n)])
        w = max(wall.max(), vmat.max())
        if w > 0.0:
            r = np.maximum(r - 1e-12, 1e-12)
            x = np.clip(x, r, 1.0 - r)
            y = np.clip(y, r, 1.0 - r)
        return x, y, r

    x, y, r = project(x, y, r)

    return np.column_stack([x, y, r])
