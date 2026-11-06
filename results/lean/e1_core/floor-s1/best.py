import numpy as np
import time
from scipy.optimize import linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 26
    rng = np.random.default_rng(12345)

    if start is not None:
        s = np.asarray(start, dtype=float)
        x = s[:, 0].copy(); y = s[:, 1].copy()
    else:
        # hexagonal-ish initial layout
        pts = []
        for k in range(n):
            ang = 2*np.pi*k/n
            pts.append((0.5 + 0.35*np.cos(ang), 0.5 + 0.35*np.sin(ang)))
        x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])

    pairs = [(i, j) for i in range(n) for j in range(i+1, n)]
    npairs = len(pairs)
    pi = np.array([p[0] for p in pairs])
    pj = np.array([p[1] for p in pairs])

    # Preallocate pairwise constraint matrix (sparse structure: 2 ones per row)
    Ap = np.zeros((npairs, n))
    Ap[np.arange(npairs), pi] = 1.0
    Ap[np.arange(npairs), pj] = 1.0
    Aw = np.eye(n)
    A_full = np.vstack([Ap, Aw])

    def max_radii(xv, yv):
        dx = xv[pi] - xv[pj]; dy = yv[pi] - yv[pj]
        d = np.sqrt(dx*dx + dy*dy)
        wall = np.minimum(np.minimum(xv, 1-xv), np.minimum(yv, 1-yv))
        b_ub = np.concatenate([d, wall])
        c = -np.ones(n)
        try:
            res = linprog(c, A_ub=A_full, b_ub=b_ub, bounds=[(0, None)]*n,
                          method='highs')
            if res.success:
                return res.x
        except Exception:
            pass
        rv = np.maximum(np.minimum(wall, 0.05), 1e-9)
        for _ in range(200):
            dx = xv[pi] - xv[pj]; dy = yv[pi] - yv[pj]
            dd = np.sqrt(dx*dx + dy*dy)
            ssum = rv[pi] + rv[pj]
            bad = dd < ssum
            if not np.any(bad):
                break
            ov = (ssum - dd)[bad] * 0.5
            np.add.at(rv, pi[bad], -ov)
            np.add.at(rv, pj[bad], -ov)
            rv = np.maximum(rv, 1e-9)
        return rv

    # Analytic gradient of LP value wrt centers is not available; use
    # a smoothed surrogate: for fixed centers, the LP's dual gives sensitivity.
    # Instead, do coordinate descent on centers using LP value + finite diff.

    best_x = x.copy(); best_y = y.copy()
    best_r = max_radii(best_x, best_y)
    best_score = float(np.sum(best_r))

    deadline = t0 + budget_seconds * 0.85

    def evaluate(xv, yv):
        rv = max_radii(xv, yv)
        return float(np.sum(rv)), rv

    # Coordinate descent with adaptive step sizes
    step = 0.02
    while time.process_time() < deadline and step > 1e-5:
        improved = False
        # shuffle order
        order = rng.permutation(n)
        for i in order:
            if time.process_time() >= deadline:
                break
            for axis in (0, 1):
                for sign in (1, -1):
                    nx = best_x.copy(); ny = best_y.copy()
                    if axis == 0:
                        nx[i] += sign * step
                    else:
                        ny[i] += sign * step
                    nx = np.clip(nx, 0.001, 0.999)
                    ny = np.clip(ny, 0.001, 0.999)
                    sc, rv = evaluate(nx, ny)
                    if sc > best_score + 1e-10:
                        best_score = sc; best_x = nx; best_y = ny; best_r = rv
                        improved = True
                        break
                else:
                    continue
                break
        if not improved:
            step *= 0.5

    # Final polish: small random perturbations with coordinate refinement
    while time.process_time() < deadline:
        scale = 0.005
        nx = np.clip(best_x + rng.normal(0, scale, n), 0.001, 0.999)
        ny = np.clip(best_y + rng.normal(0, scale, n), 0.001, 0.999)
        sc, rv = evaluate(nx, ny)
        if sc > best_score:
            best_score = sc; best_x = nx; best_y = ny; best_r = rv
            # refine
            for _ in range(3):
                for i in range(n):
                    if time.process_time() >= deadline:
                        break
                    for axis in (0, 1):
                        for sign in (1, -1):
                            tx = best_x.copy(); ty = best_y.copy()
                            if axis == 0:
                                tx[i] += sign * 0.003
                            else:
                                ty[i] += sign * 0.003
                            tx = np.clip(tx, 0.001, 0.999)
                            ty = np.clip(ty, 0.001, 0.999)
                            s2, r2 = evaluate(tx, ty)
                            if s2 > best_score + 1e-12:
                                best_score = s2; best_x = tx; best_y = ty; best_r = r2

    xv = best_x.copy(); yv = best_y.copy(); rv = best_r.copy()

    # Safety shrink for zero-tolerance validation
    eps = 1e-9
    m = np.minimum(np.minimum(xv, 1-xv), np.minimum(yv, 1-yv))
    rv = np.minimum(rv, m - eps)
    for _ in range(2000):
        dx = xv[pi] - xv[pj]; dy = yv[pi] - yv[pj]
        d = np.sqrt(dx*dx + dy*dy)
        ssum = rv[pi] + rv[pj]
        bad = d < ssum + 1e-10
        if not np.any(bad):
            break
        ov = (ssum + 1e-10 - d)[bad] * 0.5
        np.add.at(rv, pi[bad], -ov)
        np.add.at(rv, pj[bad], -ov)
        rv = np.maximum(rv, 1e-8)
    rv = np.maximum(rv, 1e-8)

    return np.column_stack([xv, yv, rv])
