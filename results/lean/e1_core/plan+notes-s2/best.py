import numpy as np
import time
from scipy.optimize import minimize, linprog


def _pt():
    return time.process_time()


def _pair_con(v, n):
    x = v[0::3]; y = v[1::3]; r = v[2::3]
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    s = r[:, None] + r[None, :]
    iu = np.triu_indices(n, 1)
    return (dx * dx + dy * dy - s * s)[iu]


def _pair_jac(v, n):
    x = v[0::3]; y = v[1::3]; r = v[2::3]
    iu = np.triu_indices(n, 1)
    i = iu[0]; j = iu[1]
    dx = x[i] - x[j]; dy = y[i] - y[j]; sr = r[i] + r[j]
    m = i.shape[0]
    J = np.zeros((m, 3 * n))
    a = np.arange(m)
    J[a, 3 * i] = 2 * dx; J[a, 3 * i + 1] = 2 * dy; J[a, 3 * i + 2] = -2 * sr
    J[a, 3 * j] = -2 * dx; J[a, 3 * j + 1] = -2 * dy; J[a, 3 * j + 2] = -2 * sr
    return J


def _wall_jac(n, axis, sign):
    J = np.zeros((n, 3 * n))
    idx = np.arange(n)
    J[idx, 3 * idx + axis] = sign
    J[idx, 3 * idx + 2] = -1.0
    return J


def _make_cons(n):
    return [
        {'type': 'ineq', 'fun': lambda v: v[0::3] - v[2::3],
         'jac': lambda v: _wall_jac(n, 0, 1.0)},
        {'type': 'ineq', 'fun': lambda v: 1 - v[0::3] - v[2::3],
         'jac': lambda v: _wall_jac(n, 0, -1.0)},
        {'type': 'ineq', 'fun': lambda v: v[1::3] - v[2::3],
         'jac': lambda v: _wall_jac(n, 1, 1.0)},
        {'type': 'ineq', 'fun': lambda v: 1 - v[1::3] - v[2::3],
         'jac': lambda v: _wall_jac(n, 1, -1.0)},
        {'type': 'ineq', 'fun': lambda v: _pair_con(v, n),
         'jac': lambda v: _pair_jac(v, n)},
    ]


def _obj(v):
    return -np.sum(v[2::3])


def _obj_jac(v):
    g = np.zeros(v.shape[0]); g[2::3] = -1.0
    return g


def _slsqp(v0, cons, maxiter=400, ftol=1e-12):
    try:
        res = minimize(_obj, v0, method='SLSQP', jac=_obj_jac, constraints=cons,
                       options={'maxiter': maxiter, 'ftol': ftol})
        if np.all(np.isfinite(res.x)):
            return res.x
    except Exception:
        pass
    return None


def _score(v, n):
    x = v[0::3]; y = v[1::3]; r = v[2::3]
    if np.any(r <= 0):
        return -np.inf
    if np.any(x - r < -1e-9) or np.any(x + r > 1 + 1e-9):
        return -np.inf
    if np.any(y - r < -1e-9) or np.any(y + r > 1 + 1e-9):
        return -np.inf
    if np.any(_pair_con(v, n) < -1e-9):
        return -np.inf
    return float(np.sum(r))


def _worst_violation(x, y, r):
    n = r.shape[0]
    iu = np.triu_indices(n, 1)
    i = iu[0]; j = iu[1]
    dx = x[i] - x[j]; dy = y[i] - y[j]
    d = np.sqrt(dx * dx + dy * dy)
    vp = np.max(r[i] + r[j] - d)
    vw = max(np.max(r - x), np.max(x + r - 1.0),
             np.max(r - y), np.max(y + r - 1.0))
    return max(vp, vw)


def _max_radii_for_positions(x, y, n):
    iu = np.triu_indices(n, 1)
    ii = iu[0]; jj = iu[1]
    dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
    d = np.sqrt(dx * dx + dy * dy)
    wall = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
    A = np.zeros((ii.shape[0], n))
    a = np.arange(ii.shape[0])
    A[a, ii] = 1.0; A[a, jj] = 1.0
    A_ub = np.vstack([A, np.eye(n)])
    b_ub = np.concatenate([d, wall])
    try:
        res = linprog(-np.ones(n), A_ub=A_ub, b_ub=b_ub, bounds=(0, None),
                      method='highs')
        if res.success:
            return np.maximum(res.x, 1e-6)
    except Exception:
        pass
    return None


def _tangency_polish(v, n, cons, iters=30):
    """Iteratively push the active constraints to equality and re-solve.
    This escapes the SLSQP plateau where many pairs are barely slack."""
    best = v.copy()
    best_sc = _score(best, n)
    cur = v.copy()
    for _ in range(iters):
        xy = cur.reshape(n, 3)[:, :2]
        r_lp = _max_radii_for_positions(xy[:, 0], xy[:, 1], n)
        if r_lp is None:
            break
        # blend: take LP radii (which sit exactly on constraints) and re-polish
        cand = cur.reshape(n, 3).copy()
        cand[:, 2] = r_lp
        cand = cand.ravel()
        rc = _slsqp(cand, cons, maxiter=300, ftol=1e-14)
        if rc is None:
            break
        sc = _score(rc, n)
        if np.isfinite(sc) and sc > best_sc + 1e-12:
            best = rc.copy(); best_sc = sc
            cur = rc.copy()
        else:
            cur = rc.copy() if sc > best_sc - 1e-6 else cur
            if sc < best_sc - 1e-9:
                break
    return best, best_sc


def construct(budget_seconds, start):
    n = 26
    t0 = _pt()
    hard_deadline = t0 + budget_seconds * 0.93
    deadline = t0 + budget_seconds * 0.62

    if start is not None:
        base = np.asarray(start, dtype=float).reshape(n, 3).copy()
    else:
        base = np.zeros((n, 3))
        cols, rows = 5, 6
        idx = 0
        for j in range(rows):
            for i in range(cols):
                if idx >= n:
                    break
                base[idx] = [(i + 0.5) / cols, (j + 0.5) / rows, 0.06]
                idx += 1

    base[:, 2] = np.maximum(base[:, 2], 1e-4)
    base[:, 0] = np.clip(base[:, 0], base[:, 2], 1 - base[:, 2])
    base[:, 1] = np.clip(base[:, 1], base[:, 2], 1 - base[:, 2])

    cons = _make_cons(n)
    rng = np.random.default_rng(98765)

    # Recompute max radii from given centres (LP on r) so we start on the
    # constraint manifold, then polish.
    xy0 = base[:, :2].copy()
    r0 = _max_radii_for_positions(xy0[:, 0], xy0[:, 1], n)
    if r0 is not None:
        base = np.column_stack([xy0, r0])
    v = base.ravel().copy()
    pol = _slsqp(v, cons, maxiter=600, ftol=1e-13)
    if pol is not None and _score(pol, n) > _score(v, n):
        v = pol
    best_v = v.copy()
    best_score = _score(best_v, n)
    if not np.isfinite(best_score):
        best_v = base.ravel().copy()
        best_score = float(np.sum(best_v[2::3]))

    # --- Main SA loop on LP objective (positions only) ---
    cur_xy = best_v.reshape(n, 3)[:, :2].copy()
    cur_r = _max_radii_for_positions(cur_xy[:, 0], cur_xy[:, 1], n)
    cur_score = float(np.sum(cur_r)) if cur_r is not None else best_score
    sigmas = [0.003, 0.012, 0.04, 0.001]
    it = 0
    T0 = 3e-4
    while _pt() < deadline:
        it += 1
        xy = cur_xy
        u = rng.random()
        if u < 0.55:
            sigma = sigmas[int(rng.integers(0, len(sigmas)))]
            idx = int(rng.integers(n))
            xy_new = xy.copy()
            xy_new[idx] += rng.normal(0, sigma, size=2)
        elif u < 0.85:
            ci = int(rng.integers(n))
            R = rng.uniform(0.15, 0.32)
            d = np.sqrt((xy[:, 0] - xy[ci, 0]) ** 2 + (xy[:, 1] - xy[ci, 1]) ** 2)
            sel = d <= R
            sigma = rng.uniform(0.004, 0.02)
            xy_new = xy.copy()
            xy_new[sel] += rng.normal(0, sigma, size=(sel.sum(), 2))
        else:
            sigma = rng.uniform(0.003, 0.015)
            xy_new = xy + rng.normal(0, sigma, size=xy.shape)
        xy_new = np.clip(xy_new, 1e-4, 1 - 1e-4)

        r_lp = _max_radii_for_positions(xy_new[:, 0], xy_new[:, 1], n)
        if r_lp is None:
            continue
        cand_score = float(np.sum(r_lp))
        T = T0 * (0.9997 ** it)
        accept = cand_score >= cur_score
        if not accept and T > 0:
            try:
                accept = rng.random() < np.exp((cand_score - cur_score) / T)
            except Exception:
                accept = False
        if accept:
            cur_xy = xy_new
            cur_score = cand_score
        if cand_score > best_score + 1e-12:
            cand = np.column_stack([xy_new, r_lp])
            rc = _slsqp(cand.ravel().copy(), cons, maxiter=400, ftol=1e-13)
            if rc is not None:
                sc = _score(rc, n)
                if np.isfinite(sc) and sc > best_score:
                    best_v = rc
                    best_score = sc

    # --- Tangency polish: fix positions, use LP radii, SLSQP re-solve ---
    if _pt() < t0 + budget_seconds * 0.78:
        pv, ps = _tangency_polish(best_v, n, cons, iters=25)
        if ps > best_score:
            best_v = pv
            best_score = ps

    # --- Scale-bisection refinement ---
    scale_deadline = t0 + budget_seconds * 0.87
    try:
        cur = best_v.reshape(n, 3).copy()
        xy = cur[:, :2].copy()
        r = cur[:, 2].copy()

        iu = np.triu_indices(n, 1)
        i_ = iu[0]; j_ = iu[1]

        def f(z):
            x = z[0::2]; y = z[1::2]
            dx = x[i_] - x[j_]; dy = y[i_] - y[j_]
            d = np.sqrt(dx * dx + dy * dy)
            vp = np.maximum(0.0, (r[i_] + r[j_]) - d)
            vw = (np.maximum(0.0, r - x) ** 2 + np.maximum(0.0, x + r - 1.0) ** 2
                  + np.maximum(0.0, r - y) ** 2 + np.maximum(0.0, y + r - 1.0) ** 2)
            return float(np.sum(vp * vp) + np.sum(vw))

        lo, hi = 1.0, 1.10
        best_t = 1.0
        best_xy = xy.copy()
        for _ in range(12):
            if _pt() > scale_deadline:
                break
            mid = 0.5 * (lo + hi)
            res = minimize(f, xy.ravel(), method='L-BFGS-B',
                           options={'maxiter': 200, 'ftol': 1e-16})
            if np.isfinite(res.fun) and res.fun < 1e-12:
                lo = mid; best_t = mid; best_xy = res.x.reshape(n, 2)
            else:
                hi = mid
        if best_t > 1.0:
            cand = np.column_stack([best_xy, best_t * r])
            rc = _slsqp(cand.ravel().copy(), cons, maxiter=500, ftol=1e-14)
            if rc is not None:
                sc = _score(rc, n)
                if np.isfinite(sc) and sc > best_score:
                    best_v = rc
                    best_score = sc
    except Exception:
        pass

    # Final polish
    if _pt() < t0 + budget_seconds * 0.94:
        pol2 = _slsqp(best_v.copy(), cons, maxiter=500, ftol=1e-14)
        if pol2 is not None:
            sc2 = _score(pol2, n)
            if np.isfinite(sc2) and sc2 > best_score:
                best_v = pol2
                best_score = sc2

    # --- Exact worst-violation repair ---
    result = best_v.reshape(n, 3).copy()
    result[:, 2] = np.maximum(result[:, 2], 1e-6)
    x = result[:, 0].copy()
    y = result[:, 1].copy()
    r = result[:, 2].copy()

    v0 = _worst_violation(x, y, r)
    if v0 <= 0.0:
        s = 1.0
    else:
        lo_s, hi_s = 1.0 - 1e-6, 1.0
        s = lo_s
        for _ in range(60):
            mid = 0.5 * (lo_s + hi_s)
            if _worst_violation(x, y, mid * r) <= 0.0:
                lo_s = mid; s = mid
            else:
                hi_s = mid
    result[:, 2] = s * r
    if _worst_violation(result[:, 0], result[:, 1], result[:, 2]) > 0.0:
        result[:, 2] *= (1 - 1e-14)
    return result
