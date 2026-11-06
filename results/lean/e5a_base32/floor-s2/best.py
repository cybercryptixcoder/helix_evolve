import numpy as np
import time
from scipy.optimize import minimize

def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    def time_left():
        return budget_seconds - (time.process_time() - t0)

    rng = np.random.default_rng(12345)
    iu, ju = np.triu_indices(n, k=1)

    if start is not None:
        arr = np.array(start, dtype=float)
        xs = arr[:, 0].copy(); ys = arr[:, 1].copy()
        rs = np.maximum(arr[:, 2].copy(), 1e-6)
    else:
        k = 6
        xs = np.zeros(n); ys = np.zeros(n)
        for i in range(n):
            xs[i] = ((i % k) + 0.5) / k
            ys[i] = ((i // k) + 0.5) / k
        rs = np.full(n, 0.05)

    def repair(x, y, r, iters=400):
        r = np.minimum(r, np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y)))
        r = np.maximum(r, 1e-9)
        for _ in range(iters):
            dx = x[iu] - x[ju]; dy = y[iu] - y[ju]
            dist = np.sqrt(dx*dx + dy*dy) + 1e-12
            viol = r[iu] + r[ju] - dist
            if viol.max() < 1e-14:
                break
            v = np.maximum(viol, 0.0)
            shrink = np.zeros(n)
            np.maximum.at(shrink, iu, v)
            np.maximum.at(shrink, ju, v)
            r = np.maximum(r - shrink * 0.5, 1e-9)
            r = np.minimum(r, np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y)))
        return r

    def pack(x, y, r):
        v = np.empty(3*n); v[0::3]=x; v[1::3]=y; v[2::3]=r; return v
    def unpack(v):
        return v[0::3].copy(), v[1::3].copy(), v[2::3].copy()

    bounds = []
    for i in range(n):
        bounds += [(0.0, 1.0), (0.0, 1.0), (1e-6, 0.5)]

    def obj_pen_grad(v, pen):
        x, y, r = v[0::3], v[1::3], v[2::3]
        g = np.zeros_like(v); g[2::3] = -1.0
        vx = r - x; m = vx > 0
        g[2::3][m] += 2*pen*vx[m]; g[0::3][m] -= 2*pen*vx[m]
        vx = x + r - 1.0; m = vx > 0
        g[2::3][m] += 2*pen*vx[m]; g[0::3][m] += 2*pen*vx[m]
        vy = r - y; m = vy > 0
        g[2::3][m] += 2*pen*vy[m]; g[1::3][m] -= 2*pen*vy[m]
        vy = y + r - 1.0; m = vy > 0
        g[2::3][m] += 2*pen*vy[m]; g[1::3][m] += 2*pen*vy[m]
        dx = x[iu] - x[ju]; dy = y[iu] - y[ju]
        dist = np.sqrt(dx*dx + dy*dy) + 1e-12
        pv = r[iu] + r[ju] - dist
        m = pv > 0
        if np.any(m):
            ii = iu[m]; jj = ju[m]; p = pv[m]; d = dist[m]
            coef = 2*pen*p
            np.add.at(g, 2 + 3*ii, coef); np.add.at(g, 2 + 3*jj, coef)
            c2 = 2*pen*p/d
            ddx = dx[m]; ddy = dy[m]
            np.add.at(g, 0 + 3*ii, -c2*ddx); np.add.at(g, 0 + 3*jj, c2*ddx)
            np.add.at(g, 1 + 3*ii, -c2*ddy); np.add.at(g, 1 + 3*jj, c2*ddy)
        f = -np.sum(r) + pen * (
            np.sum(np.maximum(0, r-x)**2) + np.sum(np.maximum(0, x+r-1)**2) +
            np.sum(np.maximum(0, r-y)**2) + np.sum(np.maximum(0, y+r-1)**2) +
            np.sum(np.maximum(0, pv)**2))
        return f, g

    def greedy_grow(x, y, r, sweeps=50, deadline=None):
        for sweep in range(sweeps):
            if deadline is not None and time.process_time() > deadline:
                break
            dx = x[:, None] - x[None, :]; dy = y[:, None] - y[None, :]
            dist = np.sqrt(dx*dx + dy*dy); np.fill_diagonal(dist, 1e9)
            allowed = (dist - r[None, :]).min(axis=1)
            rmax = np.minimum.reduce([x, 1-x, y, 1-y, allowed])
            rmax = np.maximum(rmax, 1e-9)
            inc = rmax > r + 1e-14
            if not np.any(inc):
                break
            r = np.where(inc, rmax * (1 - 1e-12), r)
        return r

    def slsqp_solve(x, y, r, deadline):
        v0 = pack(x, y, r)
        def full_obj(v):
            return -np.sum(v[2::3])
        def full_grad(v):
            g = np.zeros_like(v); g[2::3] = -1.0; return g
        cons = []
        def mk_bound(idx_off, sgn, wall):
            def c(v):
                t = v[idx_off::3]; rr = v[2::3]
                return wall - (t + sgn*rr) if sgn > 0 else (t - rr) - wall
            def jac(v):
                J = np.zeros((n, 3*n))
                for i in range(n):
                    J[i, 3*i+idx_off] = -1.0 if sgn > 0 else 1.0
                    J[i, 3*i+2] = -sgn if sgn > 0 else -1.0
                return J
            return {'type':'ineq','fun':c,'jac':jac}
        cons.append(mk_bound(0, 1, 1.0))
        cons.append(mk_bound(0, -1, 0.0))
        cons.append(mk_bound(1, 1, 1.0))
        cons.append(mk_bound(1, -1, 0.0))
        def pair_c(v):
            x = v[0::3]; y = v[1::3]; r = v[2::3]
            dx = x[iu]-x[ju]; dy = y[iu]-y[ju]
            d = np.sqrt(dx*dx+dy*dy)
            return d - (r[iu]+r[ju])
        def pair_j(v):
            x = v[0::3]; y = v[1::3]; r = v[2::3]
            dx = x[iu]-x[ju]; dy = y[iu]-y[ju]
            d = np.sqrt(dx*dx+dy*dy) + 1e-12
            m = len(iu)
            J = np.zeros((m, 3*n))
            ux = dx/d; uy = dy/d
            for k in range(m):
                i = iu[k]; j = ju[k]
                J[k, 3*i+0] = ux[k]; J[k, 3*j+0] = -ux[k]
                J[k, 3*i+1] = uy[k]; J[k, 3*j+1] = -uy[k]
                J[k, 3*i+2] = -1.0; J[k, 3*j+2] = -1.0
            return J
        cons.append({'type':'ineq','fun':pair_c,'jac':pair_j})
        try:
            res = minimize(full_obj, v0, jac=full_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter':300,'ftol':1e-15})
            return unpack(res.x)
        except Exception:
            return x, y, r

    rs = repair(xs, ys, rs)
    v = pack(xs, ys, rs)
    best_v = v.copy()
    best_score = np.sum(rs)

    # Phase A: penalty continuation (quick pass)
    for pen in [1e2, 1e4, 1e6, 1e7]:
        if time_left() < budget_seconds * 0.65:
            break
        try:
            res = minimize(lambda vv: obj_pen_grad(vv, pen), v, method='L-BFGS-B',
                           jac=True, bounds=bounds,
                           options={'maxiter': 300, 'ftol': 1e-15, 'gtol': 1e-15, 'maxls': 60})
            v = res.x
        except Exception:
            break
        x, y, r = unpack(v); r = repair(x, y, r); v = pack(x, y, r)
        sc = np.sum(r)
        if sc > best_score:
            best_score = sc; best_v = v.copy()

    # Phase B: SLSQP + grow
    x, y, r = unpack(best_v); r = repair(x, y, r)
    if time_left() > budget_seconds * 0.5:
        x, y, r = slsqp_solve(x, y, r, t0 + budget_seconds*0.7)
        r = repair(x, y, r)
        r = greedy_grow(x, y, r, sweeps=60, deadline=t0 + budget_seconds*0.75)
        sc = np.sum(r)
        if sc > best_score:
            best_score = sc; best_v = pack(x, y, r)

    # Phase C: basin-hopping on the best solution
    x, y, r = unpack(best_v); r = repair(x, y, r)
    best_x, best_y, best_r = x.copy(), y.copy(), r.copy()
    while time_left() > budget_seconds * 0.12:
        xp = best_x.copy(); yp = best_y.copy(); rp = best_r.copy()
        n_mut = 3 + int(rng.integers(0, 6))
        idx = rng.choice(n, size=min(n, n_mut), replace=False)
        scale = 0.03 * rng.uniform(0.5, 1.5)
        xp[idx] += rng.normal(0, scale, size=len(idx))
        yp[idx] += rng.normal(0, scale, size=len(idx))
        xp = np.clip(xp, 0.0, 1.0); yp = np.clip(yp, 0.0, 1.0)
        rp = repair(xp, yp, rp)
        rp = greedy_grow(xp, yp, rp, sweeps=15, deadline=None)
        xp, yp, rp = slsqp_solve(xp, yp, rp, t0 + budget_seconds*0.97)
        rp = repair(xp, yp, rp)
        rp = greedy_grow(xp, yp, rp, sweeps=30, deadline=t0 + budget_seconds*0.98)
        sc = np.sum(rp)
        if sc > best_score:
            best_score = sc
            best_x, best_y, best_r = xp.copy(), yp.copy(), rp.copy()

    x, y, r = best_x, best_y, best_r
    r = repair(x, y, r)
    r = greedy_grow(x, y, r, sweeps=100, deadline=t0 + budget_seconds*0.99)

    # Final safety shrink
    eps = 1e-12
    r = np.minimum(r, np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y)))
    r = np.maximum(r - eps, 1e-9)
    for _ in range(100):
        dx = x[:, None] - x[None, :]; dy = y[:, None] - y[None, :]
        dist = np.sqrt(dx*dx + dy*dy); np.fill_diagonal(dist, 1e9)
        viol = r[:, None] + r[None, :] - dist
        viol = np.maximum(viol, 0.0); np.fill_diagonal(viol, 0.0)
        if viol.max() < 1e-15:
            break
        shrink = viol.max(axis=1) * 0.5 + 1e-15
        r = np.maximum(r - shrink, 1e-9)
        r = np.minimum(r, np.minimum(np.minimum(x, 1-x), np.minimum(y, 1-y)))

    result = np.empty((n, 3))
    result[:, 0] = x; result[:, 1] = y; result[:, 2] = r
    return result
