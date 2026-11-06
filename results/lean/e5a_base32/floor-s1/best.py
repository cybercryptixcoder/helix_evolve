import numpy as np
import time
from scipy.optimize import minimize, linprog


def _constraints_vec(c):
    n = len(c)
    x = c[:, 0]; y = c[:, 1]; r = c[:, 2]
    iu = np.triu_indices(n, 1)
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d2 = (dx * dx + dy * dy)[iu]
    s = (r[:, None] + r[None, :])[iu]
    return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r, d2 - s * s])


def _max_violation(c):
    return float(-np.min(_constraints_vec(c)))


def _score(c):
    return float(np.sum(c[:, 2]))


def _repair(c, n):
    c = c.copy()
    for _ in range(400):
        if _max_violation(c) <= 0:
            break
        x = c[:, 0]; y = c[:, 1]; r = c[:, 2]
        over = (np.maximum(r - x, 0) + np.maximum(x + r - 1, 0)
                + np.maximum(r - y, 0) + np.maximum(y + r - 1, 0))
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        s = r[:, None] + r[None, :]
        viol = np.maximum(s - d, 0)
        np.fill_diagonal(viol, 0)
        over += 0.5 * viol.sum(axis=1)
        c[:, 2] = np.maximum(r - over - 1e-12, 1e-9)
        r = c[:, 2]
        c[:, 0] = np.clip(c[:, 0], r, 1 - r)
        c[:, 1] = np.clip(c[:, 1], r, 1 - r)
    return c


def _slsqp_polish(c, n, maxiter=400, ftol=1e-13):
    def obj(v):
        return -np.sum(v[2::3])

    def cons(v):
        return _constraints_vec(v.reshape(n, 3))

    try:
        res = minimize(obj, c.reshape(-1), method='SLSQP',
                       constraints={'type': 'ineq', 'fun': cons},
                       options={'maxiter': maxiter, 'ftol': ftol})
        return res.x.reshape(n, 3)
    except Exception:
        return None


def _lp_grow(c, n, gap=1e-9):
    x = c[:, 0]; y = c[:, 1]
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    iu = np.triu_indices(n, 1)
    npairs = len(iu[0])
    A_pair = np.zeros((npairs, n))
    A_pair[np.arange(npairs), iu[0]] = 1.0
    A_pair[np.arange(npairs), iu[1]] = 1.0
    b_pair = d[iu] - gap
    A_wall = np.eye(n)
    b_wall = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y)) - gap
    A_ub = np.vstack([A_pair, A_wall])
    b_ub = np.concatenate([b_pair, b_wall])
    c_obj = -np.ones(n)
    bounds = [(1e-9, None)] * n
    try:
        res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if res.success:
            return res.x
    except Exception:
        pass
    return None


def _finalize(best, n):
    result = best.copy()
    for _ in range(400):
        if _max_violation(result) <= 0:
            break
        result[:, 2] *= 0.999999
        r = result[:, 2]
        result[:, 0] = np.clip(result[:, 0], r, 1 - r)
        result[:, 1] = np.clip(result[:, 1], r, 1 - r)
    result[:, 2] *= (1.0 - 1e-9)
    r = result[:, 2]
    result[:, 0] = np.clip(result[:, 0], r, 1 - r)
    result[:, 1] = np.clip(result[:, 1], r, 1 - r)
    return result


def _refine(c, n, deadline, rng, rounds=60):
    c = c.copy()
    order = list(range(n))
    for _ in range(rounds):
        if time.process_time() > deadline:
            break
        rng.shuffle(order)
        improved = False
        for i in order:
            x = c[:, 0]; y = c[:, 1]; r = c[:, 2]
            xi, yi, ri = x[i], y[i], r[i]
            wall = min(xi, 1 - xi, yi, 1 - yi)
            dx = xi - x; dy = yi - y
            d = np.sqrt(dx * dx + dy * dy)
            d[i] = 1e9
            pair_cap = (d - r).min() if n > 1 else 1e9
            new_r = min(wall, pair_cap) - 1e-12
            if new_r > ri + 1e-12:
                c[i, 2] = new_r
                improved = True
            best_r = c[i, 2]; best_xy = (c[i, 0], c[i, 1])
            for _ in range(6):
                px = rng.uniform(max(best_r, 0.0), 1 - max(best_r, 0.0))
                py = rng.uniform(max(best_r, 0.0), 1 - max(best_r, 0.0))
                w = min(px, 1 - px, py, 1 - py)
                dd = np.sqrt((x - px) ** 2 + (y - py) ** 2)
                dd[i] = 1e9
                cap = (dd - r).min()
                nr = min(w, cap) - 1e-12
                if nr > best_r + 1e-12:
                    best_r = nr; best_xy = (px, py)
            if best_r > c[i, 2] + 1e-12:
                c[i, 0], c[i, 1], c[i, 2] = best_xy[0], best_xy[1], best_r
                improved = True
        if not improved:
            break
    return c


def _slsqp_free_centers(c, n, maxiter=300, ftol=1e-13):
    """SLSQP optimizing centers only (radii fixed) to open up space."""
    r = c[:, 2].copy()

    def obj(v):
        return 0.0

    def cons(v):
        cc = np.empty((n, 3))
        cc[:, 0] = v[0::2]
        cc[:, 1] = v[1::2]
        cc[:, 2] = r
        return _constraints_vec(cc)

    x0 = np.empty(2 * n)
    x0[0::2] = c[:, 0]
    x0[1::2] = c[:, 1]
    try:
        res = minimize(obj, x0, method='SLSQP',
                       constraints={'type': 'ineq', 'fun': cons},
                       options={'maxiter': maxiter, 'ftol': ftol})
        out = c.copy()
        out[:, 0] = res.x[0::2]
        out[:, 1] = res.x[1::2]
        return out
    except Exception:
        return None


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85
    n = 32
    rng = np.random.default_rng(24680)

    if start is not None:
        best = np.asarray(start, dtype=float).copy()
    else:
        best = np.zeros((n, 3))
        cols, rows = 6, 6
        idx = 0
        for j in range(rows):
            for i in range(cols):
                if idx >= n:
                    break
                x = (i + 0.5 + (0.5 if j % 2 else 0.0)) / cols
                y = (j + 0.5) / rows
                best[idx] = (min(max(x, 0.05), 0.95),
                             min(max(y, 0.05), 0.95), 0.05)
                idx += 1
            if idx >= n:
                break

    best = _repair(best, n)

    r_g = _lp_grow(best, n)
    if r_g is not None:
        cand = best.copy(); cand[:, 2] = r_g
        cand = _repair(cand, n)
        if _max_violation(cand) <= 0 and _score(cand) > _score(best):
            best = cand
    best_score = _score(best)

    c = _slsqp_polish(best, n, maxiter=800, ftol=1e-14)
    if c is not None:
        c = _repair(c, n)
        if _max_violation(c) <= 0 and _score(c) > best_score:
            best = c.copy(); best_score = _score(c)

    c2 = _refine(best, n, deadline, rng, rounds=40)
    c2 = _repair(c2, n)
    if _max_violation(c2) <= 0 and _score(c2) > best_score:
        best = c2.copy(); best_score = _score(c2)

    it = 0
    while time.process_time() < deadline:
        it += 1
        c0 = best.copy()
        mode = it % 10

        if mode == 0:
            c0[:, 0] += rng.normal(0, 0.003, n)
            c0[:, 1] += rng.normal(0, 0.003, n)
        elif mode == 1:
            nk = int(rng.integers(2, 5))
            idxs = rng.choice(n, size=nk, replace=False)
            c0[idxs, 0] += rng.normal(0, 0.008, size=nk)
            c0[idxs, 1] += rng.normal(0, 0.008, size=nk)
        elif mode == 2:
            k = int(rng.integers(1, 4))
            idxs = rng.choice(n, size=k, replace=False)
            c0[idxs, 2] *= 1.0 - rng.uniform(0.02, 0.06, size=k)
        elif mode == 3:
            i, j = rng.choice(n, size=2, replace=False)
            c0[[i, j], 0] = c0[[j, i], 0]
            c0[[i, j], 1] = c0[[j, i], 1]
        elif mode == 4:
            nk = int(rng.integers(3, 7))
            idxs = rng.choice(n, size=nk, replace=False)
            c0[idxs, 0] += rng.normal(0, 0.015, size=nk)
            c0[idxs, 1] += rng.normal(0, 0.015, size=nk)
        elif mode == 5:
            k = int(np.argmax(c0[:, 2]))
            c0[k, 2] *= 1.0 - rng.uniform(0.03, 0.08)
        elif mode == 6:
            k = int(np.argmin(c0[:, 2]))
            x = c0[:, 0]; y = c0[:, 1]; r = c0[:, 2]
            best_pos = (x[k], y[k]); best_min = -1e9
            for _ in range(30):
                px = rng.uniform(r[k], 1 - r[k])
                py = rng.uniform(r[k], 1 - r[k])
                dd = np.sqrt((x - px) ** 2 + (y - py) ** 2) - (r + r[k])
                dd[k] = 1e9
                mn = dd.min()
                if mn > best_min:
                    best_min = mn; best_pos = (px, py)
            c0[k, 0], c0[k, 1] = best_pos
        elif mode == 7:
            k = int(rng.integers(0, n))
            c0[k, 2] *= 1.0 - rng.uniform(0.01, 0.04)
        elif mode == 8:
            # NEW: free-center SLSQP to open up gaps, then grow via LP
            cf = _slsqp_free_centers(best, n, maxiter=200)
            if cf is not None:
                cf = _repair(cf, n)
                if _max_violation(cf) <= 0:
                    c0 = cf
                else:
                    c0[:, 0] += rng.normal(0, 0.006, n)
                    c0[:, 1] += rng.normal(0, 0.006, n)
            else:
                c0[:, 0] += rng.normal(0, 0.006, n)
                c0[:, 1] += rng.normal(0, 0.006, n)
        else:
            c0[:, 0] += rng.normal(0, 0.006, n)
            c0[:, 1] += rng.normal(0, 0.006, n)

        r_new = _lp_grow(c0, n)
        if r_new is not None:
            c0[:, 2] = r_new
        c0 = _repair(c0, n)

        c0 = _refine(c0, n, deadline, rng, rounds=15)
        c0 = _repair(c0, n)
        c = _slsqp_polish(c0, n, maxiter=400, ftol=1e-13)
        if c is None:
            c = c0
        c = _repair(c, n)
        if _max_violation(c) <= 0:
            sc = _score(c)
            if sc > best_score + 1e-13:
                best = c.copy(); best_score = sc

    # Final polish: alternate free-center SLSQP with LP-grow + SLSQP
    budget_end = t0 + budget_seconds * 0.95
    for _ in range(4):
        if time.process_time() > budget_end:
            break
        cf = _slsqp_free_centers(best, n, maxiter=400)
        if cf is not None:
            cf = _repair(cf, n)
            if _max_violation(cf) <= 0:
                r_new = _lp_grow(cf, n, gap=1e-10)
                if r_new is not None:
                    cf[:, 2] = r_new
                cf = _repair(cf, n)
                cp = _slsqp_polish(cf, n, maxiter=800, ftol=1e-14)
                if cp is not None:
                    cp = _repair(cp, n)
                    if _max_violation(cp) <= 0 and _score(cp) > best_score:
                        best = cp.copy(); best_score = _score(cp)
        rb = _refine(best, n, budget_end, rng, rounds=25)
        rb = _repair(rb, n)
        if _max_violation(rb) <= 0 and _score(rb) > best_score:
            best = rb.copy(); best_score = _score(rb)

    return _finalize(best, n)
