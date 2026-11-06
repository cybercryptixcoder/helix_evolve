import numpy as np
import time
from scipy.optimize import minimize, linprog


def _project(xyr, n):
    x = xyr[:, 0]; y = xyr[:, 1]; r = xyr[:, 2]
    box = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    need = r[:, None] + r[None, :]
    np.fill_diagonal(d, 1e300)
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = d / need
        t = ratio.min()
        tb = (box / r).min() if np.all(r > 0) else 0.0
        if tb < t:
            t = tb
    return max(t, 0.0)


def _score_of(a, n):
    a = a.copy()
    a[:, 0] = np.clip(a[:, 0], 1e-6, 1 - 1e-6)
    a[:, 1] = np.clip(a[:, 1], 1e-6, 1 - 1e-6)
    a[:, 2] = np.maximum(a[:, 2], 1e-6)
    t = _project(a, n)
    a[:, 2] *= t
    return a, a[:, 2].sum()


def _lp_radii_exact(a):
    n = a.shape[0]
    x = a[:, 0].copy(); y = a[:, 1].copy()
    c = -np.ones(n)
    A_ub = []; b_ub = []
    for i in range(n):
        for j in range(i + 1, n):
            dij = np.hypot(x[i] - x[j], y[i] - y[j])
            row = np.zeros(n); row[i] = 1.0; row[j] = 1.0
            A_ub.append(row); b_ub.append(dij)
    for i in range(n):
        row = np.zeros(n); row[i] = 1.0
        A_ub.append(row)
        b_ub.append(min(x[i], 1.0 - x[i], y[i], 1.0 - y[i]))
    A_ub = np.array(A_ub); b_ub = np.array(b_ub)
    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=[(0.0, None)] * n, method='highs')
    except Exception:
        return a.copy()
    if not res.success or res.x is None:
        return a.copy()
    out = a.copy()
    out[:, 2] = np.maximum(res.x, 1e-12)
    return out


def _slsqp(xyr, n, iters):
    x0 = xyr.copy()

    def cons(v):
        a = v.reshape(n, 3)
        x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
        return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])

    def cons_jac(v):
        J = np.zeros((4 * n, 3 * n))
        for i in range(n):
            c = 3 * i
            J[i, c] = 1.0; J[i, c + 2] = -1.0
            J[n + i, c] = -1.0; J[n + i, c + 2] = -1.0
            J[2 * n + i, c + 1] = 1.0; J[2 * n + i, c + 2] = -1.0
            J[3 * n + i, c + 1] = -1.0; J[3 * n + i, c + 2] = -1.0
        return J

    def cons_pairs(v):
        a = v.reshape(n, 3)
        x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy + 1e-30)
        val = d - (r[:, None] + r[None, :])
        np.fill_diagonal(val, 1.0)
        return val.ravel()

    def cons_pairs_jac(v):
        a = v.reshape(n, 3)
        x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
        J = np.zeros((n * n, 3 * n))
        for i in range(n):
            dx = x[i] - x; dy = y[i] - y
            d = np.sqrt(dx * dx + dy * dy + 1e-30)
            for j in range(n):
                row = i * n + j
                if i == j:
                    continue
                ci = 3 * i; cj = 3 * j
                J[row, ci] = dx[j] / d[j]
                J[row, ci + 1] = dy[j] / d[j]
                J[row, ci + 2] = -1.0
                J[row, cj] = -dx[j] / d[j]
                J[row, cj + 1] = -dy[j] / d[j]
                J[row, cj + 2] = -1.0
        return J

    def obj(v):
        return -v.reshape(n, 3)[:, 2].sum()

    def obj_jac(v):
        g = np.zeros((n, 3))
        g[:, 2] = -1.0
        return g.ravel()

    bounds = [(0, 1)] * (2 * n) + [(1e-6, 0.5)] * n
    try:
        res = minimize(obj, x0.ravel(), method='SLSQP', bounds=bounds,
                       jac=obj_jac,
                       constraints=[{'type': 'ineq', 'fun': cons, 'jac': cons_jac},
                                    {'type': 'ineq', 'fun': cons_pairs, 'jac': cons_pairs_jac}],
                       options={'maxiter': iters, 'ftol': 1e-13})
        return res.x.reshape(n, 3)
    except Exception:
        return x0


def _slp(arr, n, delta=0.02, max_iter=100):
    a = arr.copy()
    best = a.copy()
    _, best_score = _score_of(best, n)
    cur = a.copy()
    d_xy = delta
    d_r = delta
    dmin = 1e-4
    dmax = 0.05
    for _ in range(max_iter):
        if d_xy < dmin and d_r < dmin:
            break
        x = cur[:, 0]; y = cur[:, 1]; r = cur[:, 2]
        nv = 3 * n
        c = np.zeros(nv)
        c[2 * n:] = -1.0
        A_ub = []
        b_ub = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = x[i] - x[j]; dy = y[i] - y[j]
                dij = np.sqrt(dx * dx + dy * dy) + 1e-30
                gx = dx / dij; gy = dy / dij
                row = np.zeros(nv)
                row[2 * i] = -gx; row[2 * i + 1] = -gy
                row[2 * j] = gx; row[2 * j + 1] = gy
                row[2 * n + i] = 1.0
                row[2 * n + j] = 1.0
                A_ub.append(row)
                b_ub.append(dij - r[i] - r[j])
        for i in range(n):
            row = np.zeros(nv); row[2 * i] = -1.0; row[2 * n + i] = 1.0
            A_ub.append(row); b_ub.append(x[i] - r[i])
            row = np.zeros(nv); row[2 * i] = 1.0; row[2 * n + i] = 1.0
            A_ub.append(row); b_ub.append(1.0 - x[i] - r[i])
            row = np.zeros(nv); row[2 * i + 1] = -1.0; row[2 * n + i] = 1.0
            A_ub.append(row); b_ub.append(y[i] - r[i])
            row = np.zeros(nv); row[2 * i + 1] = 1.0; row[2 * n + i] = 1.0
            A_ub.append(row); b_ub.append(1.0 - y[i] - r[i])
        A_ub = np.array(A_ub); b_ub = np.array(b_ub)
        bounds = [(-d_xy, d_xy)] * (2 * n) + [(-d_r, d_r)] * n
        try:
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        except Exception:
            break
        if not res.success:
            d_xy *= 0.5; d_r *= 0.5
            continue
        v = res.x
        new = cur.copy()
        new[:, 0] += v[:n]
        new[:, 1] += v[n:2 * n]
        new[:, 2] += v[2 * n:]
        new[:, 2] = np.maximum(new[:, 2], 1e-6)
        new, sc = _score_of(new, n)
        if sc > best_score + 1e-12:
            best_score = sc
            best = new.copy()
            cur = new
            d_xy = min(d_xy * 1.5, dmax)
            d_r = min(d_r * 1.2, dmax)
        else:
            d_xy *= 0.5; d_r *= 0.5
    return best


def _reinsert(arr, deleted_idx, rng, n_samples=3000):
    n = arr.shape[0]
    keep_mask = np.ones(n, dtype=bool)
    keep_mask[deleted_idx] = False
    kx = arr[keep_mask, 0]; ky = arr[keep_mask, 1]; kr = arr[keep_mask, 2]

    P = rng.random((n_samples, 2))
    if kx.size:
        d2 = (P[:, None, 0] - kx[None, :]) ** 2 + (P[:, None, 1] - ky[None, :]) ** 2
        d = np.sqrt(d2)
        free = (d - kr[None, :]).min(axis=1)
    else:
        free = np.ones(n_samples)
    wall = np.minimum(np.minimum(P[:, 0], 1 - P[:, 0]),
                      np.minimum(P[:, 1], 1 - P[:, 1]))
    fr = np.minimum(free, wall)
    order = np.argsort(-fr)

    new_arr = arr.copy()
    order_del = sorted(deleted_idx, key=lambda i: -arr[i, 2])
    placed = []
    used = np.zeros(n_samples, dtype=bool)
    for i in order_del:
        chosen = None
        for j in order:
            if used[j]:
                continue
            px, py = P[j]
            ok = True
            for (qx, qy, qr) in placed:
                if np.hypot(px - qx, py - qy) < qr + fr[j] * 0.5:
                    ok = False; break
            if ok:
                chosen = j; break
        if chosen is None:
            chosen = order[0]
        used[chosen] = True
        px, py = P[chosen]
        new_arr[i, 0] = px; new_arr[i, 1] = py
        new_arr[i, 2] = max(fr[chosen] * 0.5, 1e-3)
        placed.append((px, py, new_arr[i, 2]))
    return new_arr


def _make_initial(n, rng):
    best = None; best_score = -1
    for trial in range(6):
        pts = []
        rows = int(np.ceil(np.sqrt(n)))
        cols = int(np.ceil(n / rows))
        for j in range(rows + 2):
            for i in range(cols + 2):
                x = (i + 0.5 + 0.5 * (j % 2)) / (cols + 1)
                y = (j + 0.5) / (rows + 1)
                if 0 < x < 1 and 0 < y < 1:
                    pts.append((x, y))
        pts = pts[:n]
        while len(pts) < n:
            pts.append((rng.random(), rng.random()))
        arr = np.zeros((n, 3))
        arr[:, 0] = [p[0] for p in pts]
        arr[:, 1] = [p[1] for p in pts]
        arr[:, 2] = 0.05
        arr[:, 0] += rng.normal(0, 0.01, n)
        arr[:, 1] += rng.normal(0, 0.01, n)
        arr[:, 0] = np.clip(arr[:, 0], 0.01, 0.99)
        arr[:, 1] = np.clip(arr[:, 1], 0.01, 0.99)
        t = _project(arr, n)
        arr[:, 2] = 0.05 * t
        score = arr[:, 2].sum()
        if score > best_score:
            best_score = score; best = arr
    return best


def _finalize(a, n):
    a = a.copy()
    a[:, 0] = np.clip(a[:, 0], 1e-9, 1 - 1e-9)
    a[:, 1] = np.clip(a[:, 1], 1e-9, 1 - 1e-9)
    a[:, 2] = np.maximum(a[:, 2], 1e-12)
    for _ in range(300):
        x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
        wall = np.stack([x - r, 1 - x - r, y - r, 1 - y - r], axis=1)
        dx = x[:, None] - x[None, :]; dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        need = r[:, None] + r[None, :]
        pair = d - need
        np.fill_diagonal(pair, 1e300)
        wmin = wall.min(); pmin = pair.min()
        if wmin >= 0 and pmin >= 0:
            break
        if wmin <= pmin:
            i, k = np.unravel_index(np.argmin(wall), wall.shape)
            a[i, 2] -= (-wall[i, k])
        else:
            i, j = np.unravel_index(np.argmin(pair), pair.shape)
            v = -pair[i, j]
            a[i, 2] -= v * 0.5; a[j, 2] -= v * 0.5
        if np.any(a[:, 2] <= 0):
            a[:, 2] = np.maximum(a[:, 2], 1e-12) * (1 - 1e-6)
    # shave ulps for safety
    x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
    wall = np.stack([x - r, 1 - x - r, y - r, 1 - y - r], axis=1)
    dx = x[:, None] - x[None, :]; dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    need = r[:, None] + r[None, :]
    pair = d - need; np.fill_diagonal(pair, 1e300)
    incident = (wall < 1e-14).any(axis=1) | (pair < 1e-14).any(axis=1)
    for i in range(n):
        if incident[i]:
            a[i, 2] = np.nextafter(a[i, 2], 0.0)
    return a


def construct(budget_seconds, start):
    n = 26
    t0 = time.process_time()
    deadline = budget_seconds - max(0.5, budget_seconds * 0.05)
    rng = np.random.default_rng(20240517)

    candidates = []
    if start is not None:
        s = np.asarray(start, dtype=float).copy()
        if s.shape == (n, 3):
            candidates.append(s)
    candidates.append(_make_initial(n, rng))

    scored = []
    for c in candidates:
        a, sc = _score_of(c, n)
        scored.append((sc, a))
    scored.sort(key=lambda z: -z[0])
    best_score, best_arr = scored[0]

    # Strong initial polish with SLP + SLSQP
    remaining = deadline - (time.process_time() - t0)
    if remaining > 1.0:
        p = _slp(best_arr, n, delta=0.01, max_iter=150)
        p, s = _score_of(p, n)
        if s > best_score:
            best_score, best_arr = s, p
    remaining = deadline - (time.process_time() - t0)
    if remaining > 1.0:
        fit = _slsqp(best_arr, n, iters=1000)
        fit, sc = _score_of(fit, n)
        if sc > best_score:
            best_score, best_arr = sc, fit

    iteration = 0
    stale = 0
    while time.process_time() - t0 < deadline - 0.3:
        iteration += 1

        if stale >= 6:
            jit = best_arr.copy()
            jit[:, 0] += rng.normal(0, 0.01, n)
            jit[:, 1] += rng.normal(0, 0.01, n)
            jit[:, 2] *= np.exp(rng.normal(0, 0.06, n))
            jit[:, 0] = np.clip(jit[:, 0], 0.01, 0.99)
            jit[:, 1] = np.clip(jit[:, 1], 0.01, 0.99)
            jit[:, 2] = np.clip(jit[:, 2], 0.01, 0.3)
            jit, _ = _score_of(jit, n)
            fit = _slp(jit, n, delta=0.02, max_iter=120)
            fit, s = _score_of(fit, n)
            fit2 = _slsqp(fit, n, iters=400)
            fit2, s2 = _score_of(fit2, n)
            if s2 > best_score + 1e-10:
                best_score = s2
                best_arr = fit2
                stale = 0
            elif s > best_score + 1e-10:
                best_score = s
                best_arr = fit
                stale = 0
            else:
                stale += 1
            continue

        base = best_arr.copy()

        if stale > 6:
            k = int(rng.integers(6, 14))
        else:
            k = int(rng.integers(3, 9))
        mode = iteration % 5
        if mode == 0:
            order = np.argsort(base[:, 2])
            deleted = order[:k].copy()
            extra = rng.choice(n, size=min(3, k), replace=False)
            deleted = np.unique(np.concatenate([deleted, extra]))[:k]
        elif mode == 1:
            deleted = rng.choice(n, size=k, replace=False)
        elif mode == 2:
            ci = rng.integers(0, n)
            d = np.hypot(base[:, 0] - base[ci, 0], base[:, 1] - base[ci, 1])
            deleted = np.argsort(d)[:k]
        elif mode == 3:
            order = np.argsort(base[:, 2])
            deleted = order[:k]
        else:
            cx, cy = rng.random(), rng.random()
            d = np.hypot(base[:, 0] - cx, base[:, 1] - cy)
            deleted = np.argsort(d)[:k]

        new_arr = _reinsert(base, deleted, rng, n_samples=3000)
        new_arr, _ = _score_of(new_arr, n)

        remaining = deadline - (time.process_time() - t0)
        if remaining < 0.3:
            break

        if iteration % 2 == 0:
            fit = _slp(new_arr, n, delta=0.02, max_iter=120)
            fit, s = _score_of(fit, n)
            if s > best_score + 1e-10:
                best_score = s
                best_arr = fit
                stale = 0
            else:
                stale += 1
            if remaining > 0.6:
                fit2 = _slsqp(fit, n, iters=400)
                fit2, s2 = _score_of(fit2, n)
                if s2 > best_score + 1e-10:
                    best_score = s2
                    best_arr = fit2
                    stale = 0
        else:
            iters = 500 if remaining > 3.0 else (300 if remaining > 1.2 else 150)
            fit = _slsqp(new_arr, n, iters=iters)
            fit, s = _score_of(fit, n)
            if s > best_score + 1e-10:
                best_score = s
                best_arr = fit
                stale = 0
            else:
                stale += 1

    # Final exact LP radius optimisation at fixed centers, then safe finalize
    remaining = deadline - (time.process_time() - t0)
    if remaining > 0.1:
        lp = _lp_radii_exact(best_arr)
        lp, s = _score_of(lp, n)
        if s > best_score:
            best_score = s
            best_arr = lp

    a = _finalize(best_arr, n)
    return a
