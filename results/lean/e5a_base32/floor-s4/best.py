import numpy as np
import time
from scipy.optimize import linprog, minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    N = 32
    deadline = t0 + budget_seconds - 0.4
    rng = np.random.default_rng(1234567)

    def clamp_walls(x):
        r = x[:, 2]
        np.clip(x[:, 0], r, 1.0 - r, out=x[:, 0])
        np.clip(x[:, 1], r, 1.0 - r, out=x[:, 1])

    def pair_overlap(x):
        dx = x[:, None, 0] - x[None, :, 0]
        dy = x[:, None, 1] - x[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy)
        need = x[:, None, 2] + x[None, :, 2]
        over = need - d
        np.fill_diagonal(over, 0.0)
        return over

    def repair(x, iters=200):
        x = np.asarray(x, dtype=float).copy()
        x[:, 2] = np.maximum(x[:, 2], 1e-9)
        for _ in range(iters):
            clamp_walls(x)
            dx = x[:, None, 0] - x[None, :, 0]
            dy = x[:, None, 1] - x[None, :, 1]
            d = np.sqrt(dx * dx + dy * dy)
            need = x[:, None, 2] + x[None, :, 2]
            over = need - d
            np.fill_diagonal(over, 0.0)
            if over.max() <= 1e-12:
                break
            mask = over > 0
            d_safe = np.where(d < 1e-12, 1.0, d)
            ux = np.where(mask, dx / d_safe, 0.0)
            uy = np.where(mask, dy / d_safe, 0.0)
            push = np.where(mask, over * 0.5, 0.0)
            x[:, 0] += (ux * push).sum(axis=1) * 0.7
            x[:, 1] += (uy * push).sum(axis=1) * 0.7
        clamp_walls(x)
        return x

    ii, jj = np.triu_indices(N, 1)

    def optimal_radii(x):
        cx = x[:, 0].copy()
        cy = x[:, 1].copy()
        c = -np.ones(N)
        A_ub = np.zeros((4 * N + len(ii), N))
        b_ub = np.zeros(4 * N + len(ii))
        for i in range(N):
            A_ub[4*i, i] = 1.0;   b_ub[4*i] = cx[i]
            A_ub[4*i+1, i] = 1.0; b_ub[4*i+1] = 1.0 - cx[i]
            A_ub[4*i+2, i] = 1.0; b_ub[4*i+2] = cy[i]
            A_ub[4*i+3, i] = 1.0; b_ub[4*i+3] = 1.0 - cy[i]
        dxp = cx[ii] - cx[jj]
        dyp = cy[ii] - cy[jj]
        dp = np.sqrt(dxp * dxp + dyp * dyp)
        base = 4 * N
        A_ub[base + np.arange(len(ii)), ii] = 1.0
        A_ub[base + np.arange(len(ii)), jj] = 1.0
        b_ub[base:] = dp
        bounds = [(1e-9, None)] * N
        try:
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
            if res.success:
                y = x.copy()
                y[:, 2] = np.maximum(res.x, 1e-9)
                return y
        except Exception:
            pass
        return x

    def score(x):
        return float(x[:, 2].sum())

    # ---- Init ----
    if start is not None:
        best = repair(np.asarray(start, dtype=float).copy())
    else:
        k = 6
        pts = []
        for j in range(k):
            for i in range(k):
                ox = 0.5 / k if (j % 2) else 0.0
                pts.append(((i + 0.5) / k + ox * 0.5, (j + 0.5) / k))
        pts = pts[:N]
        best = np.array([[p[0], p[1], 0.04] for p in pts])
        best = repair(best)

    best = optimal_radii(best)
    best = repair(best)
    best_s = score(best)

    # ---- Main loop: basin hopping with LP radii ----
    stall = 0
    step = 0.02
    while time.process_time() < deadline - 0.3:
        x = best.copy()
        mode = rng.random()
        if mode < 0.55:
            i = int(rng.integers(N))
            s = step * (0.3 + rng.random())
            x[i, 0] += rng.normal(0, s)
            x[i, 1] += rng.normal(0, s)
        elif mode < 0.88:
            idx = rng.permutation(N)[:rng.integers(2, 6)]
            s = step * (0.5 + rng.random())
            x[idx, 0] += rng.normal(0, s, len(idx))
            x[idx, 1] += rng.normal(0, s, len(idx))
        else:
            idx = rng.permutation(N)[:rng.integers(6, 16)]
            x[idx, 0] += rng.normal(0, step * 2.0, len(idx))
            x[idx, 1] += rng.normal(0, step * 2.0, len(idx))

        x = optimal_radii(x)
        x = repair(x, iters=120)
        s = score(x)
        if s > best_s + 1e-12:
            best = x
            best_s = s
            stall = 0
            step = min(step * 1.05, 0.05)
        else:
            stall += 1
            if stall > 25:
                step = max(step * 0.9, 0.003)
                stall = 0

    # ---- Final SLSQP polish on smooth form (radii joint variables) ----
    rem = deadline - time.process_time()
    if rem > 0.2:
        v0 = best.flatten().astype(float)

        def obj(v):
            return -v[2::3].sum()

        def obj_grad(v):
            g = np.zeros_like(v)
            g[2::3] = -1.0
            return g

        def make_wall(i, kind):
            if kind == 0:
                return (lambda v: v[3*i] - v[3*i+2]), (lambda v: (lambda g: (g.__setitem__(3*i,1.0), g.__setitem__(3*i+2,-1.0), g)[-1])(np.zeros_like(v)))
            if kind == 1:
                return (lambda v: 1.0 - v[3*i] - v[3*i+2]), (lambda v: (lambda g: (g.__setitem__(3*i,-1.0), g.__setitem__(3*i+2,-1.0), g)[-1])(np.zeros_like(v)))
            if kind == 2:
                return (lambda v: v[3*i+1] - v[3*i+2]), (lambda v: (lambda g: (g.__setitem__(3*i+1,1.0), g.__setitem__(3*i+2,-1.0), g)[-1])(np.zeros_like(v)))
            return (lambda v: 1.0 - v[3*i+1] - v[3*i+2]), (lambda v: (lambda g: (g.__setitem__(3*i+1,-1.0), g.__setitem__(3*i+2,-1.0), g)[-1])(np.zeros_like(v)))

        cons = []
        for i in range(N):
            for kind in range(4):
                f, jf = make_wall(i, kind)
                cons.append({'type': 'ineq', 'fun': f, 'jac': jf})

        for i in range(N):
            for j in range(i + 1, N):
                def f_p(v, i=i, j=j):
                    dx = v[3*i] - v[3*j]; dy = v[3*i+1] - v[3*j+1]
                    return np.sqrt(dx*dx + dy*dy) - v[3*i+2] - v[3*j+2]
                def f_pg(v, i=i, j=j):
                    g = np.zeros_like(v)
                    dx = v[3*i] - v[3*j]; dy = v[3*i+1] - v[3*j+1]
                    d = np.sqrt(dx*dx + dy*dy)
                    if d < 1e-12: d = 1e-12
                    g[3*i] = dx/d; g[3*i+1] = dy/d
                    g[3*j] = -dx/d; g[3*j+1] = -dy/d
                    g[3*i+2] = -1.0; g[3*j+2] = -1.0
                    return g
                cons.append({'type': 'ineq', 'fun': f_p, 'jac': f_pg})

        try:
            res = minimize(obj, v0, jac=obj_grad, constraints=cons,
                           method='SLSQP',
                           options={'maxiter': 300, 'ftol': 1e-16})
            v = res.x.copy()
            v[2::3] = np.maximum(v[2::3], 1e-9)
            cand = v.reshape(N, 3)
            cand = repair(cand)
            cand = optimal_radii(cand)
            cand = repair(cand)
            if score(cand) > best_s:
                best = cand
        except Exception:
            pass

    # ---- Safety ----
    best = repair(best)
    best = optimal_radii(best)
    best = repair(best)
    best[:, 2] = np.maximum(best[:, 2] - 1e-6, 1e-9)
    clamp_walls(best)
    over = pair_overlap(best).max()
    if over > 0:
        best[:, 2] = np.maximum(best[:, 2] - over - 1e-6, 1e-9)
        clamp_walls(best)
    return best
