import numpy as np
import time
from scipy.optimize import linprog, minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + 0.82 * budget_seconds
    n = 26
    pair_list = [(i, j) for i in range(n) for j in range(i + 1, n)]
    npairs = len(pair_list)
    pi = np.array([p[0] for p in pair_list])
    pj = np.array([p[1] for p in pair_list])

    A_ub = np.zeros((npairs + n, n))
    A_ub[np.arange(npairs), pi] = 1.0
    A_ub[np.arange(npairs), pj] = 1.0
    for i in range(n):
        A_ub[npairs + i, i] = 1.0
    c_lp = -np.ones(n)
    bounds_lp = [(0.0, None)] * n

    def feasible(p, tol=1e-11):
        r = p[:, 2]
        if np.any(r <= 0):
            return False
        if np.any(p[:, 0] - r < -tol) or np.any(p[:, 0] + r > 1 + tol):
            return False
        if np.any(p[:, 1] - r < -tol) or np.any(p[:, 1] + r > 1 + tol):
            return False
        dx = p[:, 0][:, None] - p[:, 0][None, :]
        dy = p[:, 1][:, None] - p[:, 1][None, :]
        d2 = dx * dx + dy * dy
        np.fill_diagonal(d2, 1e18)
        rs = r[:, None] + r[None, :]
        return not np.any(d2 < rs * rs - tol)

    def lp_radii(centers):
        x = centers[:, 0]
        y = centers[:, 1]
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        D = np.sqrt(dx * dx + dy * dy)
        b = np.empty(npairs + n)
        b[:npairs] = D[pi, pj]
        wall = np.minimum(np.minimum(x, 1.0 - x), np.minimum(y, 1.0 - y))
        b[npairs:] = np.maximum(wall, 0.0)
        try:
            res = linprog(c_lp, A_ub=A_ub, b_ub=b, bounds=bounds_lp, method='highs')
            if res.success:
                return np.maximum(res.x, 1e-9)
        except Exception:
            pass
        return None

    # --- SLSQP polish on (x,y,r) ---
    def obj(z):
        return -np.sum(z[2::3])

    def obj_grad(z):
        g = np.zeros_like(z)
        g[2::3] = -1.0
        return g

    bounds = []
    for i in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-6, 0.5))

    cons = []
    for i in range(n):
        for comp in (0, 1):
            for sign in (1, -1):
                a = 3 * i + comp
                b = 3 * i + 2
                off = 0.0 if sign > 0 else 1.0

                def makef(a, b, sign, off):
                    def f(z):
                        return sign * z[a] - z[b] + off

                    def j(z):
                        g = np.zeros_like(z)
                        g[a] = sign
                        g[b] = -1.0
                        return g
                    return f, j
                f, j = makef(a, b, sign, off)
                cons.append({'type': 'ineq', 'fun': f, 'jac': j})

    for (i, j) in pair_list:
        ai, aj = 3 * i, 3 * j

        def makep(ai, aj):
            def f(z):
                dx = z[ai] - z[aj]
                dy = z[ai + 1] - z[aj + 1]
                rr = z[ai + 2] + z[aj + 2]
                return dx * dx + dy * dy - rr * rr

            def j(z):
                g = np.zeros_like(z)
                dx = z[ai] - z[aj]
                dy = z[ai + 1] - z[aj + 1]
                rr = z[ai + 2] + z[aj + 2]
                g[ai] = 2 * dx
                g[aj] = -2 * dx
                g[ai + 1] = 2 * dy
                g[aj + 1] = -2 * dy
                g[ai + 2] = -2 * rr
                g[aj + 2] = -2 * rr
                return g
            return f, j
        f, j = makep(ai, aj)
        cons.append({'type': 'ineq', 'fun': f, 'jac': j})

    def polish(z, maxiter=300):
        try:
            res = minimize(obj, z, jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter': maxiter, 'ftol': 1e-14})
            return res.x
        except Exception:
            return None

    best = None
    best_val = -1.0

    def try_accept(p):
        nonlocal best, best_val
        if p is None:
            return False
        if not feasible(p, tol=1e-9):
            return False
        val = float(np.sum(p[:, 2]))
        if val > best_val + 1e-13:
            best_val = val
            best = p.copy()
            return True
        return False

    if start is not None:
        s = np.asarray(start, dtype=float).reshape(n, 3).copy()
        s[:, 2] = np.maximum(s[:, 2], 1e-6)
        if feasible(s, tol=1e-8):
            best = s.copy()
            best_val = float(np.sum(s[:, 2]))

    rng = np.random.RandomState(2024)

    # --- contact-aware analysis of best solution ---
    def contact_info(p):
        x = p[:, 0]
        y = p[:, 1]
        r = p[:, 2]
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        np.fill_diagonal(d, 1e9)
        contacts = (np.abs(d - rs) < 1e-6).sum(axis=1)
        wall = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        contacts += (np.abs(wall - r) < 1e-6).astype(int)
        return contacts

    def reinsert(p, rng):
        contacts = contact_info(p)
        idx = int(np.argmin(contacts))
        others = np.delete(np.arange(n), idx)
        ox = p[others, 0]
        oy = p[others, 1]
        orr = p[others, 2]
        m = 3000
        pts = rng.uniform(0.0, 1.0, size=(m, 2))
        dx = pts[:, 0][:, None] - ox[None, :]
        dy = pts[:, 1][:, None] - oy[None, :]
        d = np.sqrt(dx * dx + dy * dy) - orr[None, :]
        wall = np.minimum(np.minimum(pts[:, 0], 1 - pts[:, 0]),
                          np.minimum(pts[:, 1], 1 - pts[:, 1]))
        score = np.minimum(d.min(axis=1), wall)
        k = int(np.argmax(score))
        cand = p.copy()
        cand[idx, 0] = pts[k, 0]
        cand[idx, 1] = pts[k, 1]
        cand[idx, 2] = 0.0
        return cand

    # --- Main SA loop on centers with LP re-solve ---
    if best is not None:
        cur = best.copy()
        cur_val = best_val
        T0 = 3e-4
        T1 = 1e-8
        t_start = time.process_time()
        total = max(1e-6, deadline - t_start)
        step = 0.03
        last_polish = 0.0
        while time.process_time() < deadline:
            now = time.process_time()
            frac = min(1.0, max(0.0, (now - t_start) / total))
            T = T0 * (T1 / T0) ** frac
            # adaptive step: shrink over time
            step = 0.03 * (0.15 ** frac) + 0.002
            mode = rng.rand()
            cand = cur.copy()
            if mode < 0.18:
                cand = reinsert(cur, rng)
            elif mode < 0.55:
                k = int(rng.randint(2, 6))
                idxs = rng.choice(n, k, replace=False)
                cand[idxs, 0] += rng.normal(0, step, k)
                cand[idxs, 1] += rng.normal(0, step, k)
            elif mode < 0.85:
                i = int(rng.randint(n))
                cand[i, 0] += rng.normal(0, step * 1.5)
                cand[i, 1] += rng.normal(0, step * 1.5)
            else:
                k = int(rng.randint(3, 7))
                idxs = rng.choice(n, k, replace=False)
                cx = cur[idxs, 0].mean()
                cy = cur[idxs, 1].mean()
                ang = rng.uniform(-np.pi, np.pi)
                ca, sa = np.cos(ang), np.sin(ang)
                refl = 1.0 if rng.rand() < 0.5 else -1.0
                dx = cur[idxs, 0] - cx
                dy = cur[idxs, 1] - cy
                dx2 = refl * (ca * dx - sa * dy)
                dy2 = sa * dx + ca * dy
                cand[idxs, 0] = cx + dx2
                cand[idxs, 1] = cy + dy2
            cand[:, 0] = np.clip(cand[:, 0], 0.0, 1.0)
            cand[:, 1] = np.clip(cand[:, 1], 0.0, 1.0)
            new_r = lp_radii(cand[:, :2])
            if new_r is None:
                continue
            cand[:, 2] = np.maximum(new_r - 1e-12, 1e-9)
            if not feasible(cand, tol=1e-9):
                continue
            cand_val = float(np.sum(cand[:, 2]))
            dE = cand_val - cur_val
            if dE > 0 or rng.rand() < np.exp(dE / max(T, 1e-12)):
                cur = cand
                cur_val = cand_val
                if cand_val > best_val + 1e-12:
                    # throttle polishing
                    if now - last_polish > 0.15:
                        zp = polish(cur.reshape(-1).copy(), maxiter=200)
                        last_polish = now
                        if zp is not None:
                            pp = zp.reshape(n, 3)
                            if feasible(pp, tol=1e-9) and np.sum(pp[:, 2]) > best_val:
                                best = pp.copy()
                                best_val = float(np.sum(pp[:, 2]))
                                cur = pp.copy()
                                cur_val = best_val
                                continue
                    best = cand.copy()
                    best_val = cand_val
            if rng.rand() < 0.003:
                cur = best.copy()
                cur_val = best_val

    if best is None:
        k = int(np.ceil(np.sqrt(n)))
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        best = np.array([[x, y, 0.02] for x, y in pts])

    out = best.reshape(n, 3).copy()

    # final LP + polish
    r = lp_radii(out[:, :2])
    if r is not None:
        q = out.copy()
        q[:, 2] = np.maximum(r - 1e-12, 1e-9)
        if feasible(q, tol=1e-9):
            out = q
    zp = polish(out.reshape(-1).copy(), maxiter=400)
    if zp is not None:
        pp = zp.reshape(n, 3)
        if feasible(pp, tol=1e-9) and np.sum(pp[:, 2]) >= np.sum(out[:, 2]) - 1e-10:
            out = pp

    # --- safety shrink to guarantee exact feasibility ---
    for _ in range(500):
        changed = False
        for i in range(n):
            x, y, rr = out[i]
            m = min(x - rr, 1 - x - rr, y - rr, 1 - y - rr)
            if m < 0:
                out[i, 2] = max(rr + m - 1e-12, 1e-9)
                changed = True
        for i in range(n):
            for j in range(i + 1, n):
                dd = np.hypot(out[i, 0] - out[j, 0], out[i, 1] - out[j, 1])
                rs2 = out[i, 2] + out[j, 2]
                if dd < rs2 - 1e-14:
                    excess = rs2 - dd
                    out[i, 2] -= excess / 2 + 1e-12
                    out[j, 2] -= excess / 2 + 1e-12
                    changed = True
        out[:, 2] = np.maximum(out[:, 2], 1e-9)
        if not changed:
            break

    out[:, 2] = np.maximum(out[:, 2] - 1e-10, 1e-9)
    return out
