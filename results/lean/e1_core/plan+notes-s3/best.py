import numpy as np
import time
from scipy.optimize import minimize, linprog


def _score_of(a):
    a = a.copy()
    a[:, 0] = np.clip(a[:, 0], 1e-9, 1 - 1e-9)
    a[:, 1] = np.clip(a[:, 1], 1e-9, 1 - 1e-9)
    a[:, 2] = np.maximum(a[:, 2], 1e-12)
    x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
    box = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
    tb = (box / r).min()
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx * dx + dy * dy)
    s = r[:, None] + r[None, :]
    np.fill_diagonal(d, 1e300)
    pm = (d / s).min()
    t = min(tb, pm, 1.0)
    a[:, 2] = r * max(t, 0.0)
    return a, a[:, 2].sum()


def _lp_radii_exact(a):
    n = a.shape[0]
    x = a[:, 0]; y = a[:, 1]
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


def _finalize(a):
    a = a.copy()
    a[:, 0] = np.clip(a[:, 0], 1e-9, 1 - 1e-9)
    a[:, 1] = np.clip(a[:, 1], 1e-9, 1 - 1e-9)
    a[:, 2] = np.maximum(a[:, 2], 1e-12)
    for _ in range(400):
        x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
        wall = np.stack([x - r, 1 - x - r, y - r, 1 - y - r], axis=1)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        pair = d - (r[:, None] + r[None, :])
        np.fill_diagonal(pair, 1e300)
        wmin = wall.min(); pmin = pair.min()
        if wmin >= 0 and pmin >= 0:
            break
        if wmin <= pmin:
            idx = np.unravel_index(np.argmin(wall), wall.shape)
            i, _ = idx
            a[i, 2] -= (-wall[i, _]) + 1e-13
        else:
            idx = np.unravel_index(np.argmin(pair), pair.shape)
            i, j = idx
            v = (-pair[i, j]) * 0.5 + 1e-13
            a[i, 2] -= v; a[j, 2] -= v
        if np.any(a[:, 2] <= 0):
            a[:, 2] = np.maximum(a[:, 2] * 0.999, 1e-9)
    return a


def _safe_shrink(a):
    """Guarantee exact feasibility: shrink radii until all constraints hold in float."""
    a = _finalize(a)
    for _ in range(200):
        x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
        viol_w = np.maximum.reduce([r - x, x + r - 1, r - y, y + r - 1])
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        need = r[:, None] + r[None, :]
        np.fill_diagonal(d, 1e300)
        viol_p = (need - d)
        np.fill_diagonal(viol_p, -1e300)
        vw = viol_w.max(); vp = viol_p.max()
        if vw <= 0 and vp <= 0:
            break
        if vw >= vp:
            i = int(np.argmax(viol_w))
            a[i, 2] -= (viol_w[i] + 1e-13)
        else:
            i, j = np.unravel_index(np.argmax(viol_p), viol_p.shape)
            v = viol_p[i, j] * 0.5 + 1e-13
            a[i, 2] -= v; a[j, 2] -= v
        a[:, 2] = np.maximum(a[:, 2], 1e-12)
    return a


def _ulp_grow(a):
    a = a.copy()
    n = a.shape[0]
    for _pass in range(6):
        changed = False
        order = np.argsort(a[:, 2])
        for i in order:
            old = a[i, 2]
            new = np.nextafter(old, np.inf)
            if not np.isfinite(new) or new <= old:
                continue
            a[i, 2] = new
            x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
            xi = x[i]; yi = y[i]; ri = r[i]
            if xi - ri < 0 or 1 - xi - ri < 0 or yi - ri < 0 or 1 - yi - ri < 0:
                a[i, 2] = old; continue
            dx = xi - x; dy = yi - y
            d = np.sqrt(dx * dx + dy * dy)
            slack = d - (ri + r)
            slack[i] = 1e300
            if slack.min() < 0:
                a[i, 2] = old; continue
            changed = True
        if not changed:
            break
    return a


def _polish(a):
    b = _lp_radii_exact(a)
    b = _safe_shrink(b)
    b = _ulp_grow(b)
    b = _safe_shrink(b)
    return b


def _slsqp(xyr, iters):
    n = xyr.shape[0]
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
        need = r[:, None] + r[None, :]
        val = d - need
        np.fill_diagonal(val, 1.0)
        return val.ravel()

    def cons_pairs_jac(v):
        a = v.reshape(n, 3)
        x = a[:, 0]; y = a[:, 1]; r = a[:, 2]
        J = np.zeros((n * n, 3 * n))
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy + 1e-30)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                row = i * n + j
                ci = 3 * i; cj = 3 * j
                J[row, ci] = dx[i, j] / d[i, j]
                J[row, ci + 1] = dy[i, j] / d[i, j]
                J[row, ci + 2] = -1.0
                J[row, cj] = -dx[i, j] / d[i, j]
                J[row, cj + 1] = -dy[i, j] / d[i, j]
                J[row, cj + 2] = -1.0
        return J

    def obj(v):
        return -v.reshape(n, 3)[:, 2].sum()

    def obj_jac(v):
        g = np.zeros((n, 3)); g[:, 2] = -1.0
        return g.ravel()

    bounds = [(0, 1)] * (2 * n) + [(1e-8, 0.5)] * n
    try:
        res = minimize(obj, x0.ravel(), method='SLSQP', bounds=bounds, jac=obj_jac,
                       constraints=[{'type': 'ineq', 'fun': cons, 'jac': cons_jac},
                                    {'type': 'ineq', 'fun': cons_pairs, 'jac': cons_pairs_jac}],
                       options={'maxiter': iters, 'ftol': 1e-14})
        return res.x.reshape(n, 3)
    except Exception:
        return x0


def _slp(arr, delta=0.02, max_iter=80):
    n = arr.shape[0]
    cur = arr.copy()
    best = cur.copy()
    _, best_score = _score_of(best)
    d_xy = delta; d_r = delta
    dmin = 1e-5; dmax = 0.05
    for _ in range(max_iter):
        if d_xy < dmin and d_r < dmin:
            break
        x = cur[:, 0]; y = cur[:, 1]; r = cur[:, 2]
        nv = 3 * n
        c = np.zeros(nv); c[2 * n:] = -1.0
        rows = []; rhs = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = x[i] - x[j]; dy = y[i] - y[j]
                dij = np.hypot(dx, dy) + 1e-30
                gx = dx / dij; gy = dy / dij
                row = np.zeros(nv)
                row[2 * i] = -gx; row[2 * i + 1] = -gy
                row[2 * j] = gx; row[2 * j + 1] = gy
                row[2 * n + i] = 1.0; row[2 * n + j] = 1.0
                rows.append(row); rhs.append(dij - r[i] - r[j])
        for i in range(n):
            row = np.zeros(nv); row[2 * i] = -1.0; row[2 * n + i] = 1.0
            rows.append(row); rhs.append(x[i] - r[i])
            row = np.zeros(nv); row[2 * i] = 1.0; row[2 * n + i] = 1.0
            rows.append(row); rhs.append(1.0 - x[i] - r[i])
            row = np.zeros(nv); row[2 * i + 1] = -1.0; row[2 * n + i] = 1.0
            rows.append(row); rhs.append(y[i] - r[i])
            row = np.zeros(nv); row[2 * i + 1] = 1.0; row[2 * n + i] = 1.0
            rows.append(row); rhs.append(1.0 - y[i] - r[i])
        A_ub = np.array(rows); b_ub = np.array(rhs)
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
        new[:, 0] += v[:n]; new[:, 1] += v[n:2 * n]; new[:, 2] += v[2 * n:]
        new[:, 2] = np.maximum(new[:, 2], 1e-8)
        new, sc = _score_of(new)
        if sc > best_score + 1e-12:
            best_score = sc; best = new.copy(); cur = new
            d_xy = min(d_xy * 1.5, dmax); d_r = min(d_r * 1.2, dmax)
        else:
            d_xy *= 0.5; d_r *= 0.5
    return best


def _reinsert(arr, deleted_idx, rng, n_samples=3000):
    n = arr.shape[0]
    keep = np.ones(n, dtype=bool); keep[deleted_idx] = False
    kx = arr[keep, 0]; ky = arr[keep, 1]; kr = arr[keep, 2]
    P = rng.random((n_samples, 2))
    if kx.size:
        d = np.sqrt((P[:, None, 0] - kx[None, :]) ** 2 + (P[:, None, 1] - ky[None, :]) ** 2)
        free = (d - kr[None, :]).min(axis=1)
    else:
        free = np.ones(n_samples)
    wall = np.minimum(np.minimum(P[:, 0], 1 - P[:, 0]), np.minimum(P[:, 1], 1 - P[:, 1]))
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


def _inflate_center_relax(a, rng):
    """Inflate radii, relax centers only (L-BFGS-B), then exact LP radii."""
    n = a.shape[0]
    factor = float(rng.choice([1.01, 1.02, 1.03, 1.04, 1.05]))
    b = a.copy()
    b[:, 2] = b[:, 2] * factor
    r = b[:, 2].copy()
    x0 = np.concatenate([b[:, 0], b[:, 1]])

    def obj(v):
        x = v[:n]; y = v[n:]
        wall = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        vw = np.maximum(0.0, r - wall)
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy)
        need = r[:, None] + r[None, :]
        vp = np.maximum(0.0, need - d)
        np.fill_diagonal(vp, 0.0)
        return float((vw * vw).sum() + (vp * vp).sum())

    bounds = [(1e-6, 1 - 1e-6)] * (2 * n)
    try:
        res = minimize(obj, x0, method='L-BFGS-B', bounds=bounds,
                       options={'maxiter': 200, 'ftol': 1e-16, 'gtol': 1e-12})
        v = res.x
    except Exception:
        return a.copy()
    c = a.copy()
    c[:, 0] = v[:n]
    c[:, 1] = v[n:]
    c[:, 2] = r
    c = _lp_radii_exact(c)
    c = _safe_shrink(c)
    c = _ulp_grow(c)
    c = _safe_shrink(c)
    return c


def construct(budget_seconds, start):
    n = 26
    t0 = time.process_time()
    deadline = budget_seconds - max(0.4, budget_seconds * 0.04)
    rng = np.random.default_rng(20240517)

    best_arr = None
    best_score = -1.0
    if start is not None:
        s = np.asarray(start, dtype=float).copy()
        if s.shape == (n, 3):
            s, sc = _score_of(s)
            if sc > best_score:
                best_arr = s; best_score = sc

    if best_arr is None:
        arr = np.zeros((n, 3))
        rows = 5; cols = 6
        k = 0
        for j in range(rows):
            for i in range(cols):
                if k >= n: break
                arr[k, 0] = (i + 0.5) / cols
                arr[k, 1] = (j + 0.5) / rows
                arr[k, 2] = 0.05
                k += 1
        best_arr, best_score = _score_of(arr)

    cand = _polish(best_arr)
    _, sc = _score_of(cand)
    if sc > best_score:
        best_score = sc; best_arr = cand

    if time.process_time() - t0 < deadline - 1.5:
        fit = _slsqp(best_arr, iters=600)
        fit, s = _score_of(fit)
        if s > best_score + 1e-11:
            best_score = s; best_arr = fit

    stale = 0
    iteration = 0
    while time.process_time() - t0 < deadline - 0.3:
        iteration += 1
        base = best_arr.copy()

        mode = iteration % 7
        if stale >= 5:
            mode = 6

        if mode == 6:
            # Inflate-center-relax attempts when stale
            improved = False
            for _ in range(10):
                if time.process_time() - t0 > deadline - 0.5:
                    break
                cand = _inflate_center_relax(best_arr, rng)
                _, cs = _score_of(cand)
                if cs > best_score + 1e-11:
                    best_arr = cand; best_score = cs
                    improved = True
                    break
            if not improved:
                jit = best_arr.copy()
                jit[:, 0] += rng.normal(0, 0.008, n)
                jit[:, 1] += rng.normal(0, 0.008, n)
                jit[:, 2] *= np.exp(rng.normal(0, 0.05, n))
                jit[:, 0] = np.clip(jit[:, 0], 0.005, 0.995)
                jit[:, 1] = np.clip(jit[:, 1], 0.005, 0.995)
                jit, _ = _score_of(jit)
                fit = _slp(jit, delta=0.015, max_iter=90)
                fit, s = _score_of(fit)
                fit2 = _slsqp(fit, iters=350)
                fit2, s2 = _score_of(fit2)
                if s2 > best_score + 1e-11:
                    cand = _polish(fit2)
                    _, ps = _score_of(cand)
                    if ps > s2:
                        best_arr = cand; best_score = ps
                    else:
                        best_arr = fit2; best_score = s2
                    improved = True
                elif s > best_score + 1e-11:
                    cand = _polish(fit)
                    _, ps = _score_of(cand)
                    if ps > s:
                        best_arr = cand; best_score = ps
                    else:
                        best_arr = fit; best_score = s
                    improved = True
            stale = 0 if improved else stale + 1
            continue

        k = int(rng.integers(2, 8))
        if mode == 0:
            order = np.argsort(base[:, 2])
            deleted = order[:k].copy()
        elif mode == 1:
            deleted = rng.choice(n, size=k, replace=False)
        elif mode == 2:
            ci = rng.integers(0, n)
            d = np.hypot(base[:, 0] - base[ci, 0], base[:, 1] - base[ci, 1])
            deleted = np.argsort(d)[:k]
        elif mode == 3:
            order = np.argsort(base[:, 2])
            deleted = order[:k]
        elif mode == 4:
            cx, cy = rng.random(), rng.random()
            d = np.hypot(base[:, 0] - cx, base[:, 1] - cy)
            deleted = np.argsort(d)[:k]
        else:
            order = np.argsort(base[:, 2])
            deleted = np.concatenate([order[:k], order[-1:]])

        new_arr = _reinsert(base, np.unique(deleted), rng, n_samples=3000)
        new_arr, _ = _score_of(new_arr)

        remaining = deadline - (time.process_time() - t0)
        if remaining < 0.3:
            break

        if iteration % 2 == 0:
            fit = _slp(new_arr, delta=0.02, max_iter=100)
            fit, s = _score_of(fit)
            if s > best_score + 1e-11:
                cand = _polish(fit)
                _, ps = _score_of(cand)
                if ps > s:
                    best_arr = cand; best_score = ps
                else:
                    best_arr = fit; best_score = s
                stale = 0
            else:
                stale += 1
        else:
            iters = 400 if remaining > 3.0 else (250 if remaining > 1.2 else 150)
            fit = _slsqp(new_arr, iters=iters)
            fit, s = _score_of(fit)
            if s > best_score + 1e-11:
                best_arr = fit; best_score = s
                stale = 0
            else:
                stale += 1

    a = _polish(best_arr)
    _, sa = _score_of(a)
    b = _safe_shrink(best_arr)
    b = _ulp_grow(b)
    b = _safe_shrink(b)
    _, sb = _score_of(b)
    out = a if sa >= sb else b
    out = _safe_shrink(out)
    return out
