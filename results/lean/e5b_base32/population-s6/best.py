import numpy as np
import time
from scipy.optimize import minimize, linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85
    n = 32
    rng = np.random.default_rng(777)

    iu = np.triu_indices(n, 1)
    m = len(iu[0])

    def build_v(x, y, r):
        v = np.empty(3 * n)
        v[0::3] = x; v[1::3] = y; v[2::3] = r
        return v

    def unpack(v):
        return v[0::3].copy(), v[1::3].copy(), v[2::3].copy()

    def constraints(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        cons = np.empty(4 * n + m)
        cons[0:n] = x - r
        cons[n:2 * n] = 1 - x - r
        cons[2 * n:3 * n] = y - r
        cons[3 * n:4 * n] = 1 - y - r
        dx = x[iu[0]] - x[iu[1]]
        dy = y[iu[0]] - y[iu[1]]
        d = np.sqrt(dx * dx + dy * dy)
        cons[4 * n:] = d - r[iu[0]] - r[iu[1]]
        return cons

    def max_violation(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        wall = max(np.max(r - x), np.max(x + r - 1),
                   np.max(r - y), np.max(y + r - 1))
        dx = x[iu[0]] - x[iu[1]]
        dy = y[iu[0]] - y[iu[1]]
        d = np.sqrt(dx * dx + dy * dy)
        pair = np.max(r[iu[0]] + r[iu[1]] - d)
        return max(wall, pair)

    def objective(v):
        return -np.sum(v[2::3])

    def repair(v, iters=200):
        x = v[0::3].copy(); y = v[1::3].copy(); r = np.maximum(v[2::3].copy(), 1e-7)
        for _ in range(iters):
            x = np.clip(x, r, 1 - r)
            y = np.clip(y, r, 1 - r)
            dx = x[iu[0]] - x[iu[1]]
            dy = y[iu[0]] - y[iu[1]]
            d = np.sqrt(dx * dx + dy * dy)
            need = r[iu[0]] + r[iu[1]]
            over = need - d
            bad = over > 1e-12
            if not bad.any():
                break
            inv = np.where(bad, 1.0 / np.maximum(d, 1e-9), 0.0)
            fx = np.where(bad, over * dx * inv, 0.0) * 0.5
            fy = np.where(bad, over * dy * inv, 0.0) * 0.5
            np.add.at(x, iu[0], fx)
            np.add.at(x, iu[1], -fx)
            np.add.at(y, iu[0], fy)
            np.add.at(y, iu[1], -fy)
            x = np.clip(x, r, 1 - r)
            y = np.clip(y, r, 1 - r)
            dx = x[iu[0]] - x[iu[1]]
            dy = y[iu[0]] - y[iu[1]]
            d = np.sqrt(dx * dx + dy * dy)
            over = (r[iu[0]] + r[iu[1]]) - d
            bad = over > 1e-12
            if not bad.any():
                break
            r[iu[0][bad]] -= over[bad] * 0.5
            r[iu[1][bad]] -= over[bad] * 0.5
            r = np.maximum(r, 1e-7)
        return build_v(x, y, r)

    def lp_radii(x, y):
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        wall = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        A = np.zeros((m + n, n))
        b = np.zeros(m + n)
        A[np.arange(m), iu[0]] = 1.0
        A[np.arange(m), iu[1]] = 1.0
        b[:m] = d[iu]
        A[np.arange(m, m + n), np.arange(n)] = 1.0
        b[m:] = wall
        try:
            res = linprog(-np.ones(n), A_ub=A, b_ub=b,
                          bounds=[(0, None)] * n, method='highs')
            if res.success:
                return np.maximum(res.x, 1e-9)
        except Exception:
            pass
        return np.full(n, 1e-3)

    def lp_improve(v):
        x, y, r = unpack(v)
        return build_v(x, y, lp_radii(x, y))

    bounds = []
    for _ in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-6, 0.5))

    def run_slsqp(v_init, maxiter, ftol=1e-13):
        try:
            res = minimize(objective, v_init, method='SLSQP', bounds=bounds,
                           constraints={'type': 'ineq', 'fun': constraints},
                           options={'maxiter': maxiter, 'ftol': ftol})
            v = res.x
            if max_violation(v) < 1e-8:
                return v, -objective(v)
        except Exception:
            pass
        return v_init, -objective(v_init)

    def finalize(v):
        x, y, r = unpack(v)
        r = np.maximum(r, 1e-9)
        for _ in range(300):
            r = np.minimum(r, x - 1e-10)
            r = np.minimum(r, 1 - x - 1e-10)
            r = np.minimum(r, y - 1e-10)
            r = np.minimum(r, 1 - y - 1e-10)
            r = np.maximum(r, 1e-9)
            dx = x[iu[0]] - x[iu[1]]
            dy = y[iu[0]] - y[iu[1]]
            d = np.sqrt(dx * dx + dy * dy)
            over = (r[iu[0]] + r[iu[1]] + 1e-10) - d
            bad = over > 0
            if not bad.any():
                break
            r[iu[0][bad]] -= over[bad] * 0.5
            r[iu[1][bad]] -= over[bad] * 0.5
            r = np.maximum(r, 1e-9)
        r *= (1 - 1e-10)
        x = np.clip(x, r, 1 - r)
        y = np.clip(y, r, 1 - r)
        return np.column_stack([x, y, r])

    best_v = None
    best_score = -1.0

    def record(v):
        nonlocal best_v, best_score
        if max_violation(v) > 1e-7:
            return
        sc = float(np.sum(v[2::3]))
        if sc > best_score:
            best_score = sc
            best_v = v.copy()

    # Seeds
    seeds = []
    if start is not None:
        try:
            a = np.asarray(start, dtype=float)
            if a.shape == (n, 3):
                seeds.append(build_v(a[:, 0], a[:, 1], np.maximum(a[:, 2], 1e-6)))
        except Exception:
            pass

    for k, off in [(6, 0.0), (6, 0.5), (5, 0.0)]:
        pts = []
        for j in range(k):
            for i in range(k):
                xx = (i + 0.5 + (0.5 if j % 2 else 0.0) + off) / k
                yy = (j + 0.5) / k
                if 0.0 < xx < 1.0 and 0.0 < yy < 1.0:
                    pts.append((xx, yy))
        pts = pts[:n]
        while len(pts) < n:
            pts.append((rng.random(), rng.random()))
        xy = np.array(pts)
        seeds.append(build_v(xy[:, 0], xy[:, 1], np.full(n, 0.045)))

    for seed in seeds:
        v = repair(seed, iters=200)
        v = lp_improve(v)
        v = repair(v, iters=80)
        v = lp_improve(v)
        v, sc = run_slsqp(v, maxiter=800)
        record(v)
        if time.process_time() > deadline * 0.5:
            break

    if best_v is None:
        if start is not None:
            return np.asarray(start, dtype=float)
        return np.column_stack([np.full(n, 0.5), np.full(n, 0.5), np.full(n, 0.01)])

    cur = best_v.copy()
    cur_s = best_score

    # Basin hopping
    scales = [0.005, 0.01, 0.02, 0.04]
    attempt = 0
    while time.process_time() < deadline:
        s = scales[min(attempt // 6, len(scales) - 1)]
        cand = best_v.copy()
        cand[0::3] += rng.normal(0, s, n)
        cand[1::3] += rng.normal(0, s, n)
        cand[0::3] = np.clip(cand[0::3], 1e-3, 1 - 1e-3)
        cand[1::3] = np.clip(cand[1::3], 1e-3, 1 - 1e-3)
        cand = lp_improve(cand)
        cand = repair(cand, iters=80)
        cand = lp_improve(cand)

        remaining = deadline - time.process_time()
        if remaining > 0.3:
            mi = int(min(600, max(150, remaining * 250)))
            v, sc = run_slsqp(cand, maxiter=mi, ftol=1e-12)
        else:
            v, sc = cand, -objective(cand)

        record(v)
        if sc > cur_s + 1e-9:
            cur, cur_s = v, sc
            attempt = 0
        else:
            attempt += 1

    # Final polish
    if time.process_time() < deadline:
        v = lp_improve(best_v)
        v = repair(v, iters=80)
        v = lp_improve(v)
        v, sc = run_slsqp(v, maxiter=1500)
        record(v)

    return finalize(best_v)
