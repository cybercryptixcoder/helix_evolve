import numpy as np
import time
from scipy.optimize import minimize

def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    deadline = budget_seconds - 0.7

    def elapsed():
        return time.process_time() - t0

    def pack(x, y, r):
        return np.concatenate([x, y, r])

    def unpack(v):
        return v[:n].copy(), v[n:2*n].copy(), v[2*n:].copy()

    iu = np.triu_indices(n, 1)

    def make_feasible(x, y, r):
        x = np.clip(x, 0.0, 1.0)
        y = np.clip(y, 0.0, 1.0)
        r = np.clip(r, 1e-6, 0.5)
        for _ in range(200):
            r = np.minimum(r, np.minimum(np.minimum(x, 1.0 - x),
                                         np.minimum(y, 1.0 - y)))
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            d = np.sqrt(dx*dx + dy*dy)
            np.fill_diagonal(d, np.inf)
            slack = d - (r[:, None] + r[None, :])
            if slack.min() >= 0:
                break
            iu_bad = np.argwhere(np.triu(slack < 0, 1))
            if len(iu_bad) == 0:
                break
            scale = np.ones(n)
            for i, j in iu_bad:
                need = r[i] + r[j]
                if need > 0:
                    fac = max(d[i, j] / need, 0.0) * 0.999
                    scale[i] = min(scale[i], fac)
                    scale[j] = min(scale[j], fac)
            r = np.maximum(r * scale, 1e-6)
        return x, y, r

    def scale_up(x, y, r):
        m = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        best = np.min(m / np.maximum(r, 1e-12))
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx*dx + dy*dy)
        np.fill_diagonal(d, np.inf)
        rs = r[:, None] + r[None, :]
        ratio = d / np.maximum(rs, 1e-12)
        best = min(best, np.min(ratio))
        if not np.isfinite(best) or best <= 0:
            best = 1.0
        return r * best

    def obj(v):
        return -np.sum(v[2*n:])

    def cons_fun(v):
        x = v[:n]; y = v[n:2*n]; r = v[2*n:]
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx*dx + dy*dy + 1e-18)
        rs = r[:, None] + r[None, :]
        c0 = x - r
        c1 = 1.0 - x - r
        c2 = y - r
        c3 = 1.0 - y - r
        c4 = (d - rs)[iu]
        return np.concatenate([c0, c1, c2, c3, c4])

    bounds = [(0.0, 1.0)] * (2*n) + [(1e-6, 0.5)] * n
    cons = [{'type': 'ineq', 'fun': cons_fun}]

    if start is not None:
        s = np.asarray(start, dtype=float)
        x = s[:, 0].copy(); y = s[:, 1].copy(); r = s[:, 2].copy()
    else:
        x, y, r = [], [], []
        k = 6
        for j in range(k):
            for i in range(k):
                if len(x) >= n:
                    break
                x.append((i + 0.5 + 0.5*(j % 2)) / k)
                y.append((j + 0.5) / k)
                r.append(0.5 / k)
        x = np.array(x[:n]); y = np.array(y[:n]); r = np.array(r[:n])

    x, y, r = make_feasible(x, y, r)
    r = scale_up(x, y, r) * (1.0 - 1e-9)

    best_v = pack(x, y, r)
    best_val = np.sum(r)

    rng = np.random.default_rng(20240607)

    def polish(vstart, maxiter):
        try:
            res = minimize(obj, vstart, method='SLSQP', constraints=cons,
                           bounds=bounds,
                           options={'maxiter': maxiter, 'ftol': 1e-15})
            xs, ys, rs = unpack(res.x)
            xs, ys, rs = make_feasible(xs, ys, rs)
            rs2 = scale_up(xs, ys, rs)
            if np.sum(rs2) > np.sum(rs):
                rs = rs2
            return pack(xs, ys, rs), np.sum(rs)
        except Exception:
            return vstart, -np.inf

    v, val = polish(best_v.copy(), 800)
    if val > best_val:
        best_v, best_val = v, val

    attempt = 0
    stall = 0
    while elapsed() < deadline:
        if stall < 2:
            amp = 0.0015; maxiter = 250
        elif stall < 5:
            amp = 0.005; maxiter = 250
        elif stall < 10:
            amp = 0.012; maxiter = 300
        elif stall < 18:
            amp = 0.025; maxiter = 350
        else:
            amp = 0.04; maxiter = 350

        vstart = best_v + rng.standard_normal(3*n) * amp
        vstart[2*n:] = np.abs(vstart[2*n:])
        if stall >= 18:
            k = 2 + (stall % 3)
            idx = rng.choice(n, size=k, replace=False)
            vstart[idx] = rng.random(k)
            vstart[n + idx] = rng.random(k)
            vstart[2*n + idx] = 0.03
        xs, ys, rs = make_feasible(vstart[:n], vstart[n:2*n], vstart[2*n:])
        rs = scale_up(xs, ys, rs)
        vstart = pack(xs, ys, rs)

        v, val = polish(vstart, maxiter)
        if val > best_val + 1e-13:
            best_val = val
            best_v = v
            stall = 0
        else:
            stall += 1
        attempt += 1

    x, y, r = unpack(best_v)

    # Final safety shrink
    for _ in range(400):
        r = np.minimum(r, np.minimum(np.minimum(x, 1 - x),
                                     np.minimum(y, 1 - y)))
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx*dx + dy*dy)
        np.fill_diagonal(d, np.inf)
        slack = d - (r[:, None] + r[None, :])
        if slack.min() >= 1e-11:
            break
        need = r[:, None] + r[None, :]
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = np.where(need > 0, d / need, np.inf)
        f = np.where(slack < 0, ratio * (1.0 - 1e-12), 1.0)
        rowmin = np.min(f, axis=1)
        r = r * np.minimum(rowmin, 1.0)

    r = r * (1.0 - 1e-11)
    return np.column_stack([x, y, r])
