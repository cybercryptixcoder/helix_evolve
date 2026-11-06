import numpy as np
import time
from scipy.optimize import minimize, linprog


def _shrink_validate(p, n):
    p = p.copy()
    p[:, 2] = np.maximum(p[:, 2], 1e-12)
    p[:, 0] = np.clip(p[:, 0], p[:, 2], 1.0 - p[:, 2])
    p[:, 1] = np.clip(p[:, 1], p[:, 2], 1.0 - p[:, 2])
    for _ in range(200):
        worst = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                dx = p[i, 0] - p[j, 0]
                dy = p[i, 1] - p[j, 1]
                d = np.hypot(dx, dy)
                s = p[i, 2] + p[j, 2]
                excess = s - d
                if excess > 0:
                    worst = max(worst, excess)
                    tot = p[i, 2] + p[j, 2]
                    if tot > 0:
                        p[i, 2] -= excess * (p[i, 2] / tot) + 1e-15
                        p[j, 2] -= excess * (p[j, 2] / tot) + 1e-15
                    else:
                        p[i, 2] -= excess * 0.5 + 1e-15
                        p[j, 2] -= excess * 0.5 + 1e-15
                    p[i, 2] = max(p[i, 2], 1e-12)
                    p[j, 2] = max(p[j, 2], 1e-12)
        p[:, 0] = np.clip(p[:, 0], p[:, 2], 1.0 - p[:, 2])
        p[:, 1] = np.clip(p[:, 1], p[:, 2], 1.0 - p[:, 2])
        if worst < 1e-14:
            break
    return p


def _exact_validate(p, n):
    p = p.copy()
    p[:, 2] = np.maximum(p[:, 2], 1e-12)
    for _ in range(50):
        changed = False
        for i in range(n):
            r = p[i, 2]
            if p[i, 0] - r < 0:
                p[i, 2] = np.nextafter(p[i, 0], 0.0)
                changed = True
            if p[i, 0] + p[i, 2] > 1.0:
                p[i, 2] = np.nextafter(1.0 - p[i, 0], 0.0)
                changed = True
            if p[i, 1] - p[i, 2] < 0:
                p[i, 2] = np.nextafter(p[i, 1], 0.0)
                changed = True
            if p[i, 1] + p[i, 2] > 1.0:
                p[i, 2] = np.nextafter(1.0 - p[i, 1], 0.0)
                changed = True
            p[i, 2] = max(p[i, 2], 1e-12)
        for i in range(n):
            for j in range(i + 1, n):
                dx = p[i, 0] - p[j, 0]
                dy = p[i, 1] - p[j, 1]
                d = np.hypot(dx, dy)
                s = p[i, 2] + p[j, 2]
                if s > d:
                    excess = s - d
                    tot = p[i, 2] + p[j, 2]
                    if tot > 0:
                        p[i, 2] -= excess * (p[i, 2] / tot)
                        p[j, 2] -= excess * (p[j, 2] / tot)
                    p[i, 2] = np.nextafter(p[i, 2], 0.0)
                    p[j, 2] = np.nextafter(p[j, 2], 0.0)
                    p[i, 2] = max(p[i, 2], 1e-12)
                    p[j, 2] = max(p[j, 2], 1e-12)
                    changed = True
        if not changed:
            break
    return p


def _lp_final_radii(p, safety=1e-12):
    n = p.shape[0]
    x = p[:, 0]
    y = p[:, 1]
    c = -np.ones(n)
    A_ub = []
    b_ub = []
    for i in range(n):
        for j in range(i + 1, n):
            d = np.hypot(x[i] - x[j], y[i] - y[j])
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            A_ub.append(row)
            b_ub.append(d * (1.0 - safety))
    for i in range(n):
        w = min(x[i], 1.0 - x[i], y[i], 1.0 - y[i])
        row = np.zeros(n)
        row[i] = 1.0
        A_ub.append(row)
        b_ub.append(w * (1.0 - safety))
    A_ub = np.array(A_ub)
    b_ub = np.array(b_ub)
    bounds = [(0.0, None)] * n
    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if res.success:
            r = res.x
            r = np.maximum(r, 1e-12)
            return r
    except Exception:
        pass
    return None


def _exact_grow(p, n, rng, passes=30):
    p = p.copy()
    for _ in range(passes):
        order = rng.permutation(n)
        for i in order:
            xi = p[i, 0]
            yi = p[i, 1]
            u = min(xi, 1.0 - xi, yi, 1.0 - yi)
            for j in range(n):
                if j == i:
                    continue
                dx = xi - p[j, 0]
                dy = yi - p[j, 1]
                d = np.hypot(dx, dy)
                cand = d - p[j, 2]
                if cand < u:
                    u = cand
            if u > p[i, 2]:
                p[i, 2] = u
            p[i, 2] = np.nextafter(p[i, 2], 0.0)
            p[i, 2] = np.nextafter(p[i, 2], 0.0)
            p[i, 2] = max(p[i, 2], 1e-12)
    for _ in range(50):
        changed = False
        for i in range(n):
            r = p[i, 2]
            if p[i, 0] - r < 0:
                p[i, 2] = np.nextafter(p[i, 0], 0.0); changed = True
            if p[i, 0] + p[i, 2] > 1.0:
                p[i, 2] = np.nextafter(1.0 - p[i, 0], 0.0); changed = True
            if p[i, 1] - p[i, 2] < 0:
                p[i, 2] = np.nextafter(p[i, 1], 0.0); changed = True
            if p[i, 1] + p[i, 2] > 1.0:
                p[i, 2] = np.nextafter(1.0 - p[i, 1], 0.0); changed = True
            p[i, 2] = max(p[i, 2], 1e-12)
        for i in range(n):
            for j in range(i + 1, n):
                dx = p[i, 0] - p[j, 0]
                dy = p[i, 1] - p[j, 1]
                d = np.hypot(dx, dy)
                s = p[i, 2] + p[j, 2]
                if s > d:
                    excess = s - d
                    tot = p[i, 2] + p[j, 2]
                    if tot > 0:
                        p[i, 2] -= excess * (p[i, 2] / tot)
                        p[j, 2] -= excess * (p[j, 2] / tot)
                    p[i, 2] = np.nextafter(p[i, 2], 0.0)
                    p[j, 2] = np.nextafter(p[j, 2], 0.0)
                    p[i, 2] = max(p[i, 2], 1e-12)
                    p[j, 2] = max(p[j, 2], 1e-12)
                    changed = True
        if not changed:
            break
    return p


_N = 26
_PAIRS = [(i, j) for i in range(_N) for j in range(i + 1, _N)]
_LOG_MIN = np.log(1e-6)
_LOG_MAX = np.log(0.5)


def _make_cons(n, pairs):
    cons = []
    for (i, j) in pairs:
        def make_f(i=i, j=j):
            def f(v):
                dx = v[3 * i] - v[3 * j]
                dy = v[3 * i + 1] - v[3 * j + 1]
                ri = np.exp(v[3 * i + 2])
                rj = np.exp(v[3 * j + 2])
                s = ri + rj
                return dx * dx + dy * dy - s * s
            def jac(v):
                g = np.zeros(3 * n)
                dx = v[3 * i] - v[3 * j]
                dy = v[3 * i + 1] - v[3 * j + 1]
                ri = np.exp(v[3 * i + 2])
                rj = np.exp(v[3 * j + 2])
                s = ri + rj
                g[3 * i] = 2 * dx; g[3 * j] = -2 * dx
                g[3 * i + 1] = 2 * dy; g[3 * j + 1] = -2 * dy
                g[3 * i + 2] = -2 * s * ri
                g[3 * j + 2] = -2 * s * rj
                return g
            return f, jac
        f, jac = make_f()
        cons.append({'type': 'ineq', 'fun': f, 'jac': jac})
    for i in range(n):
        for kind in ('xl', 'xr', 'yl', 'yr'):
            def make_w(i=i, kind=kind):
                def f(v):
                    r = np.exp(v[3 * i + 2])
                    if kind == 'xl': return v[3 * i] - r
                    if kind == 'xr': return 1.0 - v[3 * i] - r
                    if kind == 'yl': return v[3 * i + 1] - r
                    return 1.0 - v[3 * i + 1] - r
                def jac(v):
                    g = np.zeros(3 * n)
                    r = np.exp(v[3 * i + 2])
                    if kind == 'xl':
                        g[3 * i] = 1.0; g[3 * i + 2] = -r
                    elif kind == 'xr':
                        g[3 * i] = -1.0; g[3 * i + 2] = -r
                    elif kind == 'yl':
                        g[3 * i + 1] = 1.0; g[3 * i + 2] = -r
                    else:
                        g[3 * i + 1] = -1.0; g[3 * i + 2] = -r
                    return g
                return f, jac
            f, jac = make_w()
            cons.append({'type': 'ineq', 'fun': f, 'jac': jac})
    return cons


def _cluster_reinsert(p, n, rng):
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dx = p[i, 0] - p[j, 0]
            dy = p[i, 1] - p[j, 1]
            d = np.hypot(dx, dy)
            if d < p[i, 2] + p[j, 2] + 1e-6:
                adj[i].append(j)
                adj[j].append(i)
    seed = int(rng.integers(0, n))
    order = [seed]
    seen = {seed}
    qi = 0
    while qi < len(order):
        u = order[qi]; qi += 1
        for w in adj[u]:
            if w not in seen:
                seen.add(w)
                order.append(w)
    target = int(rng.integers(2, 5))
    cluster = order[:min(target, len(order))]
    if len(cluster) < 2:
        other = int(rng.integers(0, n))
        if other == seed:
            other = (seed + 1) % n
        cluster = [seed, other]
    p = p.copy()
    for idx in cluster:
        p[idx, 0] = rng.uniform(0.0, 1.0)
        p[idx, 1] = rng.uniform(0.0, 1.0)
        p[idx, 2] = 1e-3
    if rng.random() < 0.3:
        idx = cluster[int(rng.integers(0, len(cluster)))]
        wall = int(rng.integers(0, 4))
        if wall == 0:
            p[idx, 0] = 0.0
        elif wall == 1:
            p[idx, 0] = 1.0
        elif wall == 2:
            p[idx, 1] = 0.0
        else:
            p[idx, 1] = 1.0
    return p


def _active_set_newton(p, n, max_steps=50, tol=1e-8):
    """Long-double active-set Newton on the exact contact graph.

    Variables z = (x_i, y_i, r_i).  Objective: maximize sum r_i.
    Equalities: active pair contacts and active wall contacts.
    We solve the KKT system for a step that increases sum r subject to
    keeping active constraints satisfied, with a line search that rejects
    any inequality violation.
    """
    ld = np.longdouble
    # Work in long double
    x = p[:, 0].astype(ld)
    y = p[:, 1].astype(ld)
    r = p[:, 2].astype(ld)

    def build_active(x, y, r):
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = x[i] - x[j]
                dy = y[i] - y[j]
                d = np.sqrt(dx * dx + dy * dy)
                if d - (r[i] + r[j]) < tol:
                    pairs.append((i, j))
        walls = []
        for i in range(n):
            # (i, kind) kind: 0=xl,1=xr,2=yl,3=yr
            if x[i] - r[i] < tol:
                walls.append((i, 0))
            if 1 - x[i] - r[i] < tol:
                walls.append((i, 1))
            if y[i] - r[i] < tol:
                walls.append((i, 2))
            if 1 - y[i] - r[i] < tol:
                walls.append((i, 3))
        return pairs, walls

    def violation(x, y, r):
        v = ld(0)
        for i in range(n):
            v = max(v, r[i] - x[i])
            v = max(v, x[i] + r[i] - 1)
            v = max(v, r[i] - y[i])
            v = max(v, y[i] + r[i] - 1)
        for i in range(n):
            for j in range(i + 1, n):
                dx = x[i] - x[j]
                dy = y[i] - y[j]
                d = np.sqrt(dx * dx + dy * dy)
                v = max(v, r[i] + r[j] - d)
        return v

    best_x = x.copy(); best_y = y.copy(); best_r = r.copy()
    best_sum = float(np.sum(r))

    for step in range(max_steps):
        pairs, walls = build_active(x, y, r)
        m = len(pairs) + len(walls)
        # Unknowns: dx, dy, dr (3n) and multipliers lambda (m)
        # We want: maximize sum dr subject to J * dz = -g (residual of active constraints)
        # and stationarity: sum dr - lambda^T J = 0
        # Solve KKT: [0  J^T; J  0] [dz; -lambda] = [c; -res]
        # where c = (0,0,1) per circle for objective sum r
        nv = 3 * n
        K = np.zeros((nv + m, nv + m), dtype=ld)
        rhs = np.zeros(nv + m, dtype=ld)
        # objective gradient: d(sum r)/dz = (0,0,1) per circle
        cvec = np.zeros(nv, dtype=ld)
        cvec[2::3] = 1.0
        K[:nv, :nv] = 0.0
        K[:nv, nv:] = 0.0
        K[nv:, :nv] = 0.0
        K[nv:, nv:] = 0.0
        # Fill J rows
        row = 0
        for (i, j) in pairs:
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            d = np.sqrt(dx * dx + dy * dy)
            if d < ld(1e-30):
                d = ld(1e-30)
            # constraint: d - r_i - r_j = 0, gradient wrt (x_i,y_i,r_i,x_j,y_j,r_j)
            gx = dx / d
            gy = dy / d
            K[nv + row, 3 * i] = gx
            K[nv + row, 3 * i + 1] = gy
            K[nv + row, 3 * i + 2] = -1.0
            K[nv + row, 3 * j] = -gx
            K[nv + row, 3 * j + 1] = -gy
            K[nv + row, 3 * j + 2] = -1.0
            # residual
            rhs[nv + row] = -(d - r[i] - r[j])
            row += 1
        for (i, kind) in walls:
            if kind == 0:
                K[nv + row, 3 * i] = 1.0
                K[nv + row, 3 * i + 2] = -1.0
                rhs[nv + row] = -(x[i] - r[i])
            elif kind == 1:
                K[nv + row, 3 * i] = -1.0
                K[nv + row, 3 * i + 2] = -1.0
                rhs[nv + row] = -(1 - x[i] - r[i])
            elif kind == 2:
                K[nv + row, 3 * i + 1] = 1.0
                K[nv + row, 3 * i + 2] = -1.0
                rhs[nv + row] = -(y[i] - r[i])
            else:
                K[nv + row, 3 * i + 1] = -1.0
                K[nv + row, 3 * i + 2] = -1.0
                rhs[nv + row] = -(1 - y[i] - r[i])
            row += 1
        # Stationarity block: c - J^T lambda = 0  =>  J^T lambda = c
        # In KKT form: [0 J^T; J 0][dz; -lambda] = [c; -res]
        # So top-right = J^T, bottom-left = J
        K[:nv, nv:] = K[nv:, :nv].T
        rhs[:nv] = cvec

        try:
            sol = np.linalg.solve(K.astype(np.float64), rhs.astype(np.float64))
        except np.linalg.LinAlgError:
            break
        dz = sol[:nv]
        # line search
        alpha = ld(1.0)
        improved = False
        for _ in range(40):
            nx = x + alpha * dz[0::3]
            ny = y + alpha * dz[1::3]
            nr = r + alpha * dz[2::3]
            if np.any(nr <= 0):
                alpha *= ld(0.5)
                continue
            v = violation(nx, ny, nr)
            if v <= ld(1e-12):
                x, y, r = nx, ny, nr
                improved = True
                break
            alpha *= ld(0.5)
        if not improved:
            break
        s = float(np.sum(r))
        if s > best_sum:
            best_sum = s
            best_x = x.copy(); best_y = y.copy(); best_r = r.copy()
        if np.max(np.abs(dz)) < ld(1e-15):
            break

    out = np.column_stack([np.array(best_x, dtype=np.float64),
                           np.array(best_y, dtype=np.float64),
                           np.array(best_r, dtype=np.float64)])
    return out


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.80

    n = 26

    if start is not None and start.shape == (n, 3):
        p_init = start.copy()
    else:
        k = 5
        r0 = 0.5 / k * 0.99
        pts = []
        for j in range(k):
            for i in range(k):
                pts.append([(i + 0.5) / k, (j + 0.5) / k, r0])
        pts.append([0.5, 0.5, r0])
        p_init = np.array(pts[:n], dtype=float)

    p_init = _shrink_validate(p_init, n)

    def to_w(p):
        w = np.empty(3 * n)
        w[0::3] = p[:, 0]
        w[1::3] = p[:, 1]
        w[2::3] = np.log(np.maximum(p[:, 2], 1e-6))
        return w

    def from_w(w):
        r = np.exp(w[2::3])
        return np.column_stack([w[0::3], w[1::3], r])

    def objective(w):
        return -np.sum(np.exp(w[2::3]))

    def obj_grad(w):
        g = np.zeros_like(w)
        g[2::3] = -np.exp(w[2::3])
        return g

    cons = _make_cons(n, _PAIRS)

    bounds = []
    for i in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((_LOG_MIN, _LOG_MAX))

    best = p_init.copy()
    best_score = float(np.sum(best[:, 2]))

    rng = np.random.default_rng(12345)
    attempts = 0

    def refine(p_try, maxiter, ftol=1e-14):
        w0 = to_w(p_try)
        try:
            res = minimize(objective, w0, jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=cons,
                           options={'maxiter': maxiter, 'ftol': ftol, 'disp': False})
            return from_w(res.x)
        except Exception:
            return None

    cand = refine(p_init, 1000)
    if cand is not None:
        cand = _shrink_validate(cand, n)
        sc = float(np.sum(cand[:, 2]))
        if sc > best_score:
            best = cand; best_score = sc

    while time.process_time() < deadline:
        attempts += 1
        if attempts % 4 == 0:
            p_try = _cluster_reinsert(best, n, rng)
        elif attempts % 7 == 0:
            p_try = best.copy()
            p_try[:, 0] += rng.normal(0, 0.06, n)
            p_try[:, 1] += rng.normal(0, 0.06, n)
            p_try[:, 2] *= (1.0 + rng.normal(0, 0.05, n))
        else:
            p_try = best.copy()
            scale = 0.008 + 0.02 * (attempts % 5) / 5.0
            p_try[:, 0] += rng.normal(0, scale, n)
            p_try[:, 1] += rng.normal(0, scale, n)
            p_try[:, 2] *= (1.0 + rng.normal(0, scale * 1.2, n))
            if attempts % 3 == 0:
                i, j = rng.integers(0, n, 2)
                p_try[i, 2], p_try[j, 2] = p_try[j, 2], p_try[i, 2]
        p_try[:, 0] = np.clip(p_try[:, 0], 0, 1)
        p_try[:, 1] = np.clip(p_try[:, 1], 0, 1)
        p_try = _shrink_validate(p_try, n)

        cand = refine(p_try, 400)
        if cand is not None:
            cand = _shrink_validate(cand, n)
            sc = float(np.sum(cand[:, 2]))
            if sc > best_score + 1e-12:
                best_score = sc
                best = cand

    remaining = deadline + budget_seconds * 0.10 - time.process_time()
    if remaining > 0.2:
        cand = refine(best, 2000, ftol=1e-15)
        if cand is not None:
            cand = _shrink_validate(cand, n)
            sc = float(np.sum(cand[:, 2]))
            if sc > best_score:
                best_score = sc
                best = cand

    best = _exact_validate(best, n)

    # LP re-solve of radii at fixed centers (with safety margin), no SLSQP after.
    r_lp = _lp_final_radii(best, safety=1e-12)
    if r_lp is not None:
        best_lp = best.copy()
        best_lp[:, 2] = r_lp
        best_lp = _shrink_validate(best_lp, n)
        if float(np.sum(best_lp[:, 2])) >= float(np.sum(best[:, 2])):
            best = best_lp

    best = _exact_validate(best, n)

    score_before = float(np.sum(best[:, 2]))
    print("score before exact_grow: %.12f" % score_before)

    best = _exact_grow(best, n, rng, passes=30)

    score_after = float(np.sum(best[:, 2]))
    print("score after exact_grow:  %.12f" % score_after)

    # --- New: long-double active-set Newton on the exact contact graph ---
    try:
        p_asn = _active_set_newton(best, n, max_steps=50, tol=1e-8)
        p_asn = _shrink_validate(p_asn, n)
        # LP with safety=0 at fixed centers
        r_lp0 = _lp_final_radii(p_asn, safety=0.0)
        if r_lp0 is not None:
            p_lp0 = p_asn.copy()
            p_lp0[:, 2] = r_lp0
            p_lp0 = _shrink_validate(p_lp0, n)
            if float(np.sum(p_lp0[:, 2])) > float(np.sum(p_asn[:, 2])):
                p_asn = p_lp0
        p_asn = _exact_validate(p_asn, n)
        p_asn = _exact_grow(p_asn, n, rng, passes=10)
        sc_asn = float(np.sum(p_asn[:, 2]))
        print("score after active-set Newton: %.12f" % sc_asn)
        if sc_asn > float(np.sum(best[:, 2])):
            best = p_asn
    except Exception as e:
        print("active-set Newton failed: %s" % e)

    best = _exact_validate(best, n)
    print("final score: %.12f" % float(np.sum(best[:, 2])))
    return best
