import numpy as np
import time
from scipy.optimize import minimize, linprog


def _pairwise(x, y):
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    return np.sqrt(dx * dx + dy * dy)


def _max_overlap(x, y, r):
    if len(r) == 0:
        return 0.0
    wall = np.maximum.reduce([r - x, r - (1 - x), r - y, r - (1 - y)])
    m = float(np.max(wall))
    d = _pairwise(x, y)
    np.fill_diagonal(d, np.inf)
    ov = (r[:, None] + r[None, :]) - d
    m = max(m, float(np.max(ov)))
    return m


def _slsqp_refine(x, y, r, maxiter=1500, ftol=1e-16):
    n = len(r)
    v0 = np.concatenate([x, y, r])
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]

    def obj(v):
        return -np.sum(v[2 * n:])

    def obj_jac(v):
        g = np.zeros(3 * n)
        g[2 * n:] = -1.0
        return g

    def make_wall(i, which):
        def fun(v, i=i, which=which):
            if which == 0:
                return v[i] - v[2 * n + i]
            elif which == 1:
                return 1.0 - v[i] - v[2 * n + i]
            elif which == 2:
                return v[n + i] - v[2 * n + i]
            else:
                return 1.0 - v[n + i] - v[2 * n + i]

        def jac(v, i=i, which=which):
            g = np.zeros(3 * n)
            if which == 0:
                g[i] = 1.0
            elif which == 1:
                g[i] = -1.0
            elif which == 2:
                g[n + i] = 1.0
            else:
                g[n + i] = -1.0
            g[2 * n + i] = -1.0
            return g
        return fun, jac

    def make_pair(i, j):
        def fun(v, i=i, j=j):
            dx = v[i] - v[j]
            dy = v[n + i] - v[n + j]
            return np.sqrt(dx * dx + dy * dy) - v[2 * n + i] - v[2 * n + j]

        def jac(v, i=i, j=j):
            dx = v[i] - v[j]
            dy = v[n + i] - v[n + j]
            d = np.sqrt(dx * dx + dy * dy)
            if d < 1e-12:
                d = 1e-12
            g = np.zeros(3 * n)
            ux = dx / d
            uy = dy / d
            g[i] = ux
            g[j] = -ux
            g[n + i] = uy
            g[n + j] = -uy
            g[2 * n + i] = -1.0
            g[2 * n + j] = -1.0
            return g
        return fun, jac

    cons = []
    for i in range(n):
        for which in range(4):
            f, j = make_wall(i, which)
            cons.append({'type': 'ineq', 'fun': f, 'jac': j})
    for (i, j) in pairs:
        f, j = make_pair(i, j)
        cons.append({'type': 'ineq', 'fun': f, 'jac': j})

    bounds = [(0, 1)] * (2 * n) + [(1e-6, 0.5)] * n
    try:
        res = minimize(obj, v0, method='SLSQP', jac=obj_jac, bounds=bounds,
                       constraints=cons,
                       options={'maxiter': maxiter, 'ftol': ftol})
        xr = res.x[:n]
        yr = res.x[n:2 * n]
        rr = res.x[2 * n:]
        if _max_overlap(xr, yr, rr) < 1e-8:
            return xr, yr, rr
    except Exception:
        pass
    return None


def _lp_radii(x, y, rmax=0.5):
    n = len(x)
    d = _pairwise(x, y)
    np.fill_diagonal(d, np.inf)
    wall = np.minimum.reduce([x, 1 - x, y, 1 - y])
    A_ub = []
    b_ub = []
    for i in range(n):
        for j in range(i + 1, n):
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            A_ub.append(row)
            b_ub.append(d[i, j])
    A_ub = np.array(A_ub) if A_ub else None
    b_ub = np.array(b_ub) if b_ub else None
    bounds = [(1e-6, min(rmax, wall[i])) for i in range(n)]
    try:
        res = linprog(-np.ones(n), A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if res.success:
            return np.maximum(res.x, 1e-6)
    except Exception:
        pass
    return np.minimum(np.full(n, 0.05), wall)


def _grow(x, y, r, growth=1.002, sweeps=8, max_steps=800):
    g = growth
    best = (x.copy(), y.copy(), r.copy())
    for _ in range(max_steps):
        rn = r * g
        if np.any(rn > 0.5):
            g = 1.0 + (g - 1.0) * 0.5
            if g - 1.0 < 1e-9:
                break
            continue
        x2, y2 = x.copy(), y.copy()
        for _ in range(sweeps):
            d = _pairwise(x2, y2)
            np.fill_diagonal(d, np.inf)
            s = rn[:, None] + rn[None, :]
            ov = s - d
            iu, ju = np.where(ov > 1e-12)
            if len(iu) == 0:
                x2 = np.clip(x2, rn, 1 - rn)
                y2 = np.clip(y2, rn, 1 - rn)
                break
            mask = iu < ju
            iu, ju = iu[mask], ju[mask]
            if len(iu) == 0:
                break
            dx = x2[ju] - x2[iu]
            dy = y2[ju] - y2[iu]
            dd = np.sqrt(dx * dx + dy * dy)
            dd = np.where(dd > 1e-12, dd, 1e-9)
            ux = dx / dd
            uy = dy / dd
            f = 0.5 * ov[iu, ju]
            np.add.at(x2, iu, -f * ux)
            np.add.at(y2, iu, -f * uy)
            np.add.at(x2, ju, f * ux)
            np.add.at(y2, ju, f * uy)
            x2 = np.clip(x2, rn, 1 - rn)
            y2 = np.clip(y2, rn, 1 - rn)
        ov = _max_overlap(x2, y2, rn)
        if ov < 1e-9:
            x, y, r = x2, y2, rn
            best = (x.copy(), y.copy(), r.copy())
            g = min(g * 1.0015, 1.02)
        else:
            g = 1.0 + (g - 1.0) * 0.5
            if g - 1.0 < 1e-9:
                break
    return best


def _repair(x, y, r, sweeps=20):
    x = x.copy(); y = y.copy(); r = r.copy()
    for _ in range(sweeps):
        d = _pairwise(x, y)
        np.fill_diagonal(d, np.inf)
        s = r[:, None] + r[None, :]
        ov = s - d
        iu, ju = np.where(ov > 1e-12)
        mask = iu < ju
        iu, ju = iu[mask], ju[mask]
        if len(iu) > 0:
            dx = x[ju] - x[iu]
            dy = y[ju] - y[iu]
            dd = np.sqrt(dx * dx + dy * dy)
            dd = np.where(dd > 1e-12, dd, 1e-9)
            ux = dx / dd; uy = dy / dd
            f = 0.5 * ov[iu, ju]
            np.add.at(x, iu, -f * ux)
            np.add.at(y, iu, -f * uy)
            np.add.at(x, ju, f * ux)
            np.add.at(y, ju, f * uy)
        x = np.clip(x, r, 1 - r)
        y = np.clip(y, r, 1 - r)
        if _max_overlap(x, y, r) < 1e-10:
            break
    return x, y, r


def _best_empty_spot(x, y, r, n_cand=500, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    cand = rng.random((n_cand, 2))
    wd = np.minimum.reduce([cand[:, 0], 1 - cand[:, 0], cand[:, 1], 1 - cand[:, 1]])
    if len(x) > 0:
        dx = cand[:, 0:1] - x[None, :]
        dy = cand[:, 1:2] - y[None, :]
        d = np.sqrt(dx * dx + dy * dy) - r[None, :]
        cd = np.min(d, axis=1)
    else:
        cd = np.full(n_cand, np.inf)
    score = np.minimum(wd, cd)
    i = int(np.argmax(score))
    return cand[i, 0], cand[i, 1]


def _hex_init(n, r0):
    pts = []
    row = 0
    y = r0
    while len(pts) < n:
        x = r0 if (row % 2 == 0) else 2 * r0
        while x + r0 <= 1 and len(pts) < n:
            pts.append((x, y))
            x += 2 * r0
        y += np.sqrt(3) * r0
        row += 1
        if y > 1:
            break
    while len(pts) < n:
        pts.append((0.5, 0.5))
    pts = np.array(pts[:n])
    return pts[:, 0].copy(), pts[:, 1].copy()


def _structured_start(pattern):
    rows = len(pattern)
    max_cols = max(pattern)
    dx_w = 1.0 / max_cols
    dx_h = 1.0 / ((rows - 1) * np.sqrt(3) / 2 + 1)
    dx = min(dx_w, dx_h)
    r = dx / 2
    pts = []
    total_w = max_cols * dx
    total_h = ((rows - 1) * np.sqrt(3) / 2 + 1) * dx
    ox = (1.0 - total_w) / 2 + r
    oy = (1.0 - total_h) / 2 + r
    for ri, cnt in enumerate(pattern):
        y = oy + ri * np.sqrt(3) / 2 * dx
        row_w = cnt * dx
        x0 = (1.0 - row_w) / 2 + r
        for ci in range(cnt):
            pts.append((x0 + ci * dx, y))
    pts = np.array(pts[:32])
    if len(pts) < 32:
        for _ in range(32 - len(pts)):
            pts = np.vstack([pts, [0.5, 0.5]])
    return pts[:, 0].copy(), pts[:, 1].copy(), np.full(32, r)


def _grid_start():
    pts = []
    for j in range(6):
        for i in range(6):
            if (i in (0, 5)) and (j in (0, 5)):
                continue
            pts.append((i, j))
    pts = np.array(pts, dtype=float)
    dx = 1.0 / 6.0
    r = dx / 2
    ox = (1.0 - 6 * dx) / 2 + r
    oy = (1.0 - 6 * dx) / 2 + r
    x = ox + pts[:, 0] * dx
    y = oy + pts[:, 1] * dx
    return x, y, np.full(len(x), r)


def _perturb(x, y, r, scale, rng, k):
    """Jitter k circles' centers and add small random radius noise."""
    x2 = x.copy(); y2 = y.copy(); r2 = r.copy()
    idx = rng.choice(len(r), size=k, replace=False)
    x2[idx] += rng.normal(0, scale, k)
    y2[idx] += rng.normal(0, scale, k)
    r2 *= (1.0 + rng.normal(0, scale * 0.5, len(r)))
    x2 = np.clip(x2, r2, 1 - r2)
    y2 = np.clip(y2, r2, 1 - r2)
    return x2, y2, r2


def _active_set_polish(x, y, r, tol=1e-9, iters=200, deadline=None):
    """Equality-constrained SQP on the active constraint graph."""
    n = len(r)
    x = x.copy(); y = y.copy(); r = r.copy()

    def active_rows(x, y, r):
        rows = []
        for i in range(n):
            for which in range(4):
                if which == 0:
                    g = x[i] - r[i]
                elif which == 1:
                    g = 1.0 - x[i] - r[i]
                elif which == 2:
                    g = y[i] - r[i]
                else:
                    g = 1.0 - y[i] - r[i]
                if g < tol:
                    row = np.zeros(3 * n)
                    if which == 0:
                        row[i] = 1.0
                    elif which == 1:
                        row[i] = -1.0
                    elif which == 2:
                        row[n + i] = 1.0
                    else:
                        row[n + i] = -1.0
                    row[2 * n + i] = -1.0
                    rows.append(row)
        d = _pairwise(x, y)
        np.fill_diagonal(d, np.inf)
        gap = d - (r[:, None] + r[None, :])
        iu, ju = np.where(gap < tol)
        mask = iu < ju
        iu, ju = iu[mask], ju[mask]
        for i, j in zip(iu, ju):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            dd = np.sqrt(dx * dx + dy * dy)
            if dd < 1e-12:
                dd = 1e-12
            ux = dx / dd; uy = dy / dd
            row = np.zeros(3 * n)
            row[i] = ux
            row[j] = -ux
            row[n + i] = uy
            row[n + j] = -uy
            row[2 * n + i] = -1.0
            row[2 * n + j] = -1.0
            rows.append(row)
        if rows:
            return np.array(rows)
        return np.zeros((0, 3 * n))

    def all_feasible(x, y, r, eps=1e-12):
        if np.any(r <= 0):
            return False
        if np.any(x - r < -eps) or np.any(x + r > 1 + eps):
            return False
        if np.any(y - r < -eps) or np.any(y + r > 1 + eps):
            return False
        d = _pairwise(x, y)
        np.fill_diagonal(d, np.inf)
        if np.any(d < r[:, None] + r[None, :] - eps):
            return False
        return True

    c = np.zeros(3 * n)
    c[2 * n:] = -1.0

    for _ in range(iters):
        if deadline is not None and time.process_time() > deadline:
            break
        A = active_rows(x, y, r)
        if A.shape[0] == 0:
            break
        g = []
        for i in range(n):
            gv = [x[i] - r[i], 1.0 - x[i] - r[i], y[i] - r[i], 1.0 - y[i] - r[i]]
            for which in range(4):
                if gv[which] < tol:
                    g.append(gv[which])
        d = _pairwise(x, y)
        np.fill_diagonal(d, np.inf)
        gap = d - (r[:, None] + r[None, :])
        iu, ju = np.where(gap < tol)
        mask = iu < ju
        iu, ju = iu[mask], ju[mask]
        for i, j in zip(iu, ju):
            g.append(gap[i, j])
        g = np.array(g) if g else np.zeros(0)

        m = A.shape[0]
        K = np.zeros((3 * n + m, 3 * n + m))
        K[:3 * n, :3 * n] = np.eye(3 * n)
        K[:3 * n, 3 * n:] = A.T
        K[3 * n:, :3 * n] = A
        rhs = np.concatenate([-c, -g])
        try:
            sol = np.linalg.lstsq(K, rhs, rcond=None)[0]
        except Exception:
            break
        dv = sol[:3 * n]
        step = 1.0
        accepted = False
        for _ls in range(30):
            xn = x + step * dv[:n]
            yn = y + step * dv[n:2 * n]
            rn = r + step * dv[2 * n:]
            if all_feasible(xn, yn, rn):
                x, y, r = xn, yn, rn
                accepted = True
                break
            step *= 0.5
        if not accepted:
            break
        if np.max(np.abs(dv)) < 1e-14:
            break
    return x, y, r


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.82
    rng = np.random.default_rng(13579)

    n = 32
    best_x = best_y = best_r = None
    best_score = -1.0

    def consider(x, y, r):
        nonlocal best_x, best_y, best_r, best_score
        if _max_overlap(x, y, r) > 1e-8:
            return False
        sc = float(np.sum(r))
        if sc > best_score:
            best_score = sc
            best_x, best_y, best_r = x.copy(), y.copy(), r.copy()
            return True
        return False

    if start is not None:
        s = np.asarray(start, dtype=float)
        x = s[:, 0].copy()
        y = s[:, 1].copy()
        r = s[:, 2].copy()
        r = np.minimum(r, np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y)) - 1e-9)
        r = np.maximum(r, 1e-6)
        consider(x, y, r)
    else:
        x, y = _hex_init(n, 0.08)
        r = np.full(n, 0.08)
        x, y, r = _repair(x, y, r)
        consider(x, y, r)

    patterns = [(6, 5, 6, 5, 6, 4), (5, 6, 5, 6, 5, 5), (6, 6, 5, 5, 5, 5)]
    for pat in patterns:
        if time.process_time() > deadline - budget_seconds * 0.5:
            break
        sx, sy, sr = _structured_start(pat)
        rlp = _lp_radii(sx, sy)
        x2, y2, r2 = _repair(sx, sy, rlp)
        gx, gy, gr = _grow(x2, y2, r2, growth=1.003, sweeps=10, max_steps=600)
        consider(gx, gy, gr)

    if best_x is None:
        k = 6
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        best_x = np.array([p[0] for p in pts])
        best_y = np.array([p[1] for p in pts])
        best_r = np.full(n, 0.02)

    it = 0
    while time.process_time() < deadline:
        it += 1
        frac = (time.process_time() - t0) / max(budget_seconds, 1e-9)
        scale = 0.03 * (1.0 - 0.6 * frac)
        k = int(rng.integers(3, 8))

        x2, y2, r2 = _perturb(best_x, best_y, best_r, scale, rng, k)
        x2, y2, r2 = _repair(x2, y2, r2, sweeps=15)
        gx, gy, gr = _grow(x2, y2, r2, growth=1.003, sweeps=10, max_steps=500)
        improved = consider(gx, gy, gr)
        if time.process_time() > deadline:
            break
        if improved or rng.random() < 0.5:
            res = _slsqp_refine(gx, gy, gr, maxiter=400, ftol=1e-15)
            if res is not None:
                consider(*res)

    if time.process_time() < deadline + budget_seconds * 0.05:
        res = _slsqp_refine(best_x, best_y, best_r, maxiter=2000, ftol=1e-16)
        if res is not None:
            consider(*res)

    # Active-set polish with tight tolerance and more iterations.
    if best_x is not None and time.process_time() < deadline + budget_seconds * 0.1:
        try:
            px, py, pr = _active_set_polish(best_x, best_y, best_r, tol=1e-9,
                                            iters=200, deadline=deadline + budget_seconds * 0.1)
            if _max_overlap(px, py, pr) < 1e-9:
                consider(px, py, pr)
        except Exception:
            pass

    # NEW: re-solve LP radii on final centers, then gentle grow.
    if best_x is not None and time.process_time() < deadline + budget_seconds * 0.15:
        try:
            rlp = _lp_radii(best_x, best_y)
            x2, y2, r2 = _repair(best_x, best_y, rlp, sweeps=20)
            gx, gy, gr = _grow(x2, y2, r2, growth=1.0005, sweeps=12, max_steps=400)
            consider(gx, gy, gr)
        except Exception:
            pass

    # Safety: shrink slightly and clip to guarantee feasibility.
    best_r = np.maximum(best_r - 1e-10, 1e-8)
    best_x = np.clip(best_x, best_r, 1 - best_r)
    best_y = np.clip(best_y, best_r, 1 - best_r)
    for _ in range(60):
        if _max_overlap(best_x, best_y, best_r) < 1e-11:
            break
        d = _pairwise(best_x, best_y)
        np.fill_diagonal(d, np.inf)
        ov = (best_r[:, None] + best_r[None, :]) - d
        wall = np.maximum.reduce([best_r - best_x, best_r - (1 - best_x),
                                  best_r - best_y, best_r - (1 - best_y)])
        m = max(float(np.max(ov)), float(np.max(wall)))
        if m <= 0:
            break
        best_r = np.maximum(best_r - m - 1e-10, 1e-8)
        best_x = np.clip(best_x, best_r, 1 - best_r)
        best_y = np.clip(best_y, best_r, 1 - best_r)

    return np.column_stack([best_x, best_y, best_r])
