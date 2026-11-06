import numpy as np
import time
from scipy.optimize import minimize

N = 32


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.82
    rng = np.random.default_rng(987654321)

    iu = np.triu_indices(N, 1)
    npairs = len(iu[0])
    ar = np.arange(npairs)
    idx = np.arange(N)

    def unpack(v):
        return v[:N], v[N:2 * N], v[2 * N:]

    def pack(x, y, r):
        return np.concatenate([x, y, r])

    def obj(v):
        return -np.sum(v[2 * N:])

    def obj_grad(v):
        g = np.zeros_like(v)
        g[2 * N:] = -1.0
        return g

    def cons_fun(v):
        x, y, r = v[:N], v[N:2 * N], v[2 * N:]
        c = np.empty(4 * N + npairs)
        c[0:N] = x - r
        c[N:2 * N] = 1.0 - x - r
        c[2 * N:3 * N] = y - r
        c[3 * N:4 * N] = 1.0 - y - r
        dx = x[iu[0]] - x[iu[1]]
        dy = y[iu[0]] - y[iu[1]]
        d = np.sqrt(dx * dx + dy * dy)
        c[4 * N:] = d - (r[iu[0]] + r[iu[1]])
        return c

    def cons_jac(v):
        x, y, r = v[:N], v[N:2 * N], v[2 * N:]
        J = np.zeros((4 * N + npairs, 3 * N))
        J[idx, idx] = 1.0
        J[idx, 2 * N + idx] = -1.0
        J[N + idx, idx] = -1.0
        J[N + idx, 2 * N + idx] = -1.0
        J[2 * N + idx, N + idx] = 1.0
        J[2 * N + idx, 2 * N + idx] = -1.0
        J[3 * N + idx, N + idx] = -1.0
        J[3 * N + idx, 2 * N + idx] = -1.0
        dx = x[iu[0]] - x[iu[1]]
        dy = y[iu[0]] - y[iu[1]]
        d = np.sqrt(dx * dx + dy * dy)
        d = np.maximum(d, 1e-12)
        base = 4 * N
        J[base + ar, iu[0]] = dx / d
        J[base + ar, iu[1]] = -dx / d
        J[base + ar, N + iu[0]] = dy / d
        J[base + ar, N + iu[1]] = -dy / d
        J[base + ar, 2 * N + iu[0]] = -1.0
        J[base + ar, 2 * N + iu[1]] = -1.0
        return J

    cons = [{'type': 'ineq', 'fun': cons_fun, 'jac': cons_jac}]
    bounds = [(0.0, 1.0)] * (2 * N) + [(1e-7, 0.5)] * N

    def max_violation(x, y, r):
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        np.fill_diagonal(d, np.inf)
        rs = r[:, None] + r[None, :]
        ov = (rs - d).max()
        wv = max((-x + r).max(), (x + r - 1).max(),
                 (-y + r).max(), (y + r - 1).max())
        return max(ov, wv)

    def make_feasible(v, margin=1e-11):
        x, y, r = unpack(v)
        r = np.maximum(r, 1e-7)
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
        for _ in range(400):
            vv = max_violation(x, y, r)
            if vv <= margin:
                break
            s = 1.0 - min(0.05, max(1e-7, vv * 1.1))
            r = r * s
            x = np.clip(x, r, 1.0 - r)
            y = np.clip(y, r, 1.0 - r)
        return pack(x, y, r)

    def slsqp(v0, maxiter, ftol=1e-13):
        try:
            res = minimize(obj, v0, jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter': maxiter, 'ftol': ftol})
            return res.x
        except Exception:
            return v0

    # --- init ---
    if start is not None and np.shape(start) == (N, 3):
        v = pack(start[:, 0].astype(float).copy(),
                 start[:, 1].astype(float).copy(),
                 start[:, 2].astype(float).copy())
    else:
        pts = []
        for j in range(6):
            for i in range(6):
                if len(pts) >= N:
                    break
                x = (i + 0.5 + (0.5 if j % 2 else 0.0)) / 6
                y = (j + 0.5) / 6
                pts.append((x, y))
        pts = pts[:N]
        v = pack(np.array([p[0] for p in pts]),
                 np.array([p[1] for p in pts]),
                 np.full(N, 0.04))

    v_best = make_feasible(v)
    best_score = v_best[2 * N:].sum()

    # Initial polish
    vp = slsqp(v_best, maxiter=800, ftol=1e-15)
    vp = make_feasible(vp)
    if vp[2 * N:].sum() > best_score:
        v_best = vp
        best_score = vp[2 * N:].sum()

    # --- main loop ---
    it = 0
    while time.process_time() < deadline:
        it += 1
        x, y, r = unpack(v_best)

        # Strategy: alternate between
        # (1) global small inflation + SLSQP
        # (2) targeted subset perturbation
        # (3) random "cluster move" - translate a subset of circles

        mode = it % 4
        if mode == 0:
            # Small uniform inflation
            infl = 1.0 + rng.random() * 0.008
            v0 = pack(x, y, r * infl)
            vn = slsqp(v0, maxiter=300, ftol=1e-14)
            vn = make_feasible(vn)
            s = vn[2 * N:].sum()
            if s > best_score + 1e-14:
                best_score = s
                v_best = vn.copy()

        elif mode == 1:
            # Slightly larger inflation
            infl = 1.005 + rng.random() * 0.02
            v0 = pack(x, y, r * infl)
            vn = slsqp(v0, maxiter=250)
            vn = make_feasible(vn)
            s = vn[2 * N:].sum()
            if s > best_score + 1e-14:
                best_score = s
                v_best = vn.copy()

        elif mode == 2:
            # Targeted: pick small subset, inflate those, jitter
            k = int(rng.integers(1, 5))
            pick = rng.choice(N, size=k, replace=False)
            r2 = r.copy()
            r2[pick] *= (1.0 + 0.03 + 0.05 * rng.random(k))
            x2 = x.copy()
            y2 = y.copy()
            x2[pick] += rng.normal(0, 0.008, k)
            y2[pick] += rng.normal(0, 0.008, k)
            v0 = make_feasible(pack(x2, y2, r2))
            vn = slsqp(v0, maxiter=200)
            vn = make_feasible(vn)
            s = vn[2 * N:].sum()
            if s > best_score + 1e-14:
                best_score = s
                v_best = vn.copy()

        else:
            # Cluster move: translate a group of nearby circles
            # find a random circle's nearest neighbors and shift them together
            ci = int(rng.integers(0, N))
            d2 = (x - x[ci]) ** 2 + (y - y[ci]) ** 2
            order = np.argsort(d2)
            k = int(rng.integers(2, 7))
            pick = order[:k]
            x2 = x.copy()
            y2 = y.copy()
            r2 = r.copy()
            dx = rng.normal(0, 0.015)
            dy = rng.normal(0, 0.015)
            x2[pick] += dx
            y2[pick] += dy
            # also slightly inflate those
            r2[pick] *= (1.0 + 0.01 + 0.02 * rng.random(k))
            v0 = make_feasible(pack(x2, y2, r2))
            vn = slsqp(v0, maxiter=250)
            vn = make_feasible(vn)
            s = vn[2 * N:].sum()
            if s > best_score + 1e-14:
                best_score = s
                v_best = vn.copy()

    # Final intensive polish
    if time.process_time() < deadline:
        v_fin = slsqp(v_best, maxiter=1500, ftol=1e-16)
        v_fin = make_feasible(v_fin)
        if v_fin[2 * N:].sum() > best_score:
            v_best = v_fin
            best_score = v_fin[2 * N:].sum()

    # Safety
    x, y, r = unpack(v_best)
    r = np.maximum(r, 1e-9)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    for _ in range(500):
        if max_violation(x, y, r) <= -1e-12:
            break
        r = r * (1.0 - 1e-9)
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
    r = np.maximum(r * (1.0 - 1e-10), 1e-9)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    return np.column_stack([x, y, r])
