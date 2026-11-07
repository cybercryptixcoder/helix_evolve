import numpy as np
import time
from scipy.optimize import minimize

N = 32


def _unpack(z):
    return z[0:N], z[N:2*N], z[2*N:3*N]


def _repair(z):
    x, y, r = _unpack(z.copy())
    r = np.maximum(r, 1e-6)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    for _ in range(300):
        changed = False
        for i in range(N):
            for j in range(i+1, N):
                d = np.hypot(x[i]-x[j], y[i]-y[j])
                s = r[i] + r[j]
                if d < s:
                    ex = (s - d) * 0.5 + 1e-12
                    r[i] = max(r[i] - ex, 1e-6)
                    r[j] = max(r[j] - ex, 1e-6)
                    changed = True
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
        if not changed:
            break
    return np.concatenate([x, y, r])


def _penalty_obj_grad(z, P):
    x = z[0:N]; y = z[N:2*N]; r = z[2*N:3*N]
    g = np.zeros(3*N)
    g[2*N:3*N] = -1.0
    f = -np.sum(r)
    v = x - r
    mask = v < 0
    if np.any(mask):
        f += P * np.sum(v[mask]**2)
        g[0:N][mask] += 2*P*v[mask]
        g[2*N:3*N][mask] -= 2*P*v[mask]
    v = 1.0 - x - r
    mask = v < 0
    if np.any(mask):
        f += P * np.sum(v[mask]**2)
        g[0:N][mask] -= 2*P*v[mask]
        g[2*N:3*N][mask] -= 2*P*v[mask]
    v = y - r
    mask = v < 0
    if np.any(mask):
        f += P * np.sum(v[mask]**2)
        g[N:2*N][mask] += 2*P*v[mask]
        g[2*N:3*N][mask] -= 2*P*v[mask]
    v = 1.0 - y - r
    mask = v < 0
    if np.any(mask):
        f += P * np.sum(v[mask]**2)
        g[N:2*N][mask] -= 2*P*v[mask]
        g[2*N:3*N][mask] -= 2*P*v[mask]
    for i in range(N):
        for j in range(i+1, N):
            dx = x[i] - x[j]; dy = y[i] - y[j]
            d = np.hypot(dx, dy)
            s = r[i] + r[j]
            v = s - d
            if v > 0:
                f += P * v * v
                if d > 1e-12:
                    coef = 2*P*v / d
                    g[i] += -coef * dx
                    g[j] += coef * dx
                    g[N+i] += -coef * dy
                    g[N+j] += coef * dy
                g[2*N+i] += 2*P*v
                g[2*N+j] += 2*P*v
    return f, g


def _build_cons():
    cons = []
    for i in range(N):
        for kind in range(4):
            def make(i, kind):
                def f(z):
                    x, y, r = _unpack(z)
                    if kind == 0:
                        return x[i] - r[i]
                    if kind == 1:
                        return 1.0 - x[i] - r[i]
                    if kind == 2:
                        return y[i] - r[i]
                    return 1.0 - y[i] - r[i]

                def j(z):
                    g = np.zeros(3*N)
                    if kind == 0:
                        g[i] = 1.0; g[2*N+i] = -1.0
                    elif kind == 1:
                        g[i] = -1.0; g[2*N+i] = -1.0
                    elif kind == 2:
                        g[N+i] = 1.0; g[2*N+i] = -1.0
                    else:
                        g[N+i] = -1.0; g[2*N+i] = -1.0
                    return g
                return f, j
            f, j = make(i, kind)
            cons.append({'type': 'ineq', 'fun': f, 'jac': j})

    for i in range(N):
        for j in range(i+1, N):
            def make(i, j):
                def f(z):
                    x, y, r = _unpack(z)
                    dx = x[i] - x[j]; dy = y[i] - y[j]
                    return dx*dx + dy*dy - (r[i] + r[j])**2

                def jac(z):
                    x, y, r = _unpack(z)
                    g = np.zeros(3*N)
                    dx = x[i] - x[j]; dy = y[i] - y[j]
                    g[i] = 2*dx; g[j] = -2*dx
                    g[N+i] = 2*dy; g[N+j] = -2*dy
                    sr = 2*(r[i] + r[j])
                    g[2*N+i] = -sr; g[2*N+j] = -sr
                    return g
                return f, jac
            f, jac = make(i, j)
            cons.append({'type': 'ineq', 'fun': f, 'jac': jac})
    return cons


def _obj(z):
    return -np.sum(z[2*N:3*N])


def _obj_jac(z):
    g = np.zeros(3*N)
    g[2*N:3*N] = -1.0
    return g


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.6

    if start is not None:
        s = np.asarray(start, dtype=float)
        z_best = np.concatenate([s[:, 0], s[:, 1], s[:, 2]])
    else:
        k = 6
        pts = [((i + 0.5 + 0.5*(j % 2)) / k, (j + 0.5) / k)
               for j in range(k) for i in range(k)][:N]
        z_best = np.concatenate([np.array([p[0] for p in pts]),
                                 np.array([p[1] for p in pts]),
                                 np.full(N, 0.05)])
    z_best = _repair(z_best)
    best_val = float(np.sum(z_best[2*N:3*N]))

    bounds = [(0.0, 1.0)] * (2*N) + [(1e-6, 0.5)] * N

    # L-BFGS-B with increasing penalty
    z = z_best.copy()
    P = 1e2
    while P <= 1e8 and time.process_time() < deadline:
        def fun(zz):
            return _penalty_obj_grad(zz, P)
        try:
            res = minimize(fun, z, jac=True, method='L-BFGS-B',
                           bounds=bounds,
                           options={'maxiter': 200, 'ftol': 1e-15, 'gtol': 1e-12})
            z = res.x
        except Exception:
            break
        zr = _repair(z)
        val = float(np.sum(zr[2*N:3*N]))
        if val > best_val:
            best_val = val
            z_best = zr.copy()
        P *= 10.0

    # Final SLSQP polish from best feasible
    cons = _build_cons()
    if time.process_time() < deadline:
        class TimeUp(Exception):
            pass
        def cb(zz):
            if time.process_time() > deadline:
                raise TimeUp()
        try:
            res = minimize(_obj, z_best.copy(), jac=_obj_jac, method='SLSQP',
                           constraints=cons, bounds=bounds,
                           options={'maxiter': 1000, 'ftol': 1e-13},
                           callback=cb)
            zr = _repair(res.x)
            val = float(np.sum(zr[2*N:3*N]))
            if val > best_val:
                best_val = val
                z_best = zr.copy()
        except Exception:
            pass

    # Experiment: force non-touching pairs into contact, then SLSQP polish.
    rng = np.random.RandomState(12345)
    while time.process_time() < deadline:
        x, y, r = _unpack(z_best.copy())
        # find non-touching pairs
        pairs = []
        for i in range(N):
            for j in range(i+1, N):
                d = np.hypot(x[i]-x[j], y[i]-y[j])
                if d > r[i] + r[j] + 1e-4:
                    pairs.append((i, j))
        if not pairs:
            break
        i, j = pairs[rng.randint(len(pairs))]
        # move i towards j by 0.02 or until touching
        dx = x[j] - x[i]; dy = y[j] - y[i]
        d = np.hypot(dx, dy)
        if d < 1e-12:
            continue
        target = min(0.02, max(0.0, d - (r[i] + r[j])))
        step = target / d
        z = z_best.copy()
        z[i] += dx * step
        z[N+i] += dy * step
        z = _repair(z)
        # SLSQP polish with limited iterations
        try:
            def cb2(zz):
                if time.process_time() > deadline:
                    raise TimeUp()
            res = minimize(_obj, z, jac=_obj_jac, method='SLSQP',
                           constraints=cons, bounds=bounds,
                           options={'maxiter': 200, 'ftol': 1e-13},
                           callback=cb2)
            zr = _repair(res.x)
            val = float(np.sum(zr[2*N:3*N]))
            if val > best_val + 1e-12:
                best_val = val
                z_best = zr.copy()
        except Exception:
            pass

    x, y, r = _unpack(z_best)
    r = r - 1e-12
    r = np.maximum(r, 1e-12)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    return np.column_stack([x, y, r])
