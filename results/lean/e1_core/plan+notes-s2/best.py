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


def _hex_pattern(rows):
    n = sum(rows)
    xy = np.zeros((n, 2))
    nr = len(rows)
    idx = 0
    for j, cnt in enumerate(rows):
        yc = (j + 0.5) / nr
        off = 0.5 / cnt if (j % 2 == 1) else 0.0
        for i in range(cnt):
            xc = (i + 0.5) / cnt + off
            if xc > 1.0:
                xc -= 1.0 / cnt
            xy[idx, 0] = xc
            xy[idx, 1] = yc
            idx += 1
    return xy[:n]


def _final_shrink(result):
    x = result[:, 0].copy()
    y = result[:, 1].copy()
    r = result[:, 2].copy()
    v0 = _worst_violation(x, y, r)
    if v0 <= 0.0:
        s = 1.0
    else:
        lo_s, hi_s = 1.0 - 1e-6, 1.0
        s = lo_s
        for _ in range(50):
            mid = 0.5 * (lo_s + hi_s)
            if _worst_violation(x, y, mid * r) <= 0.0:
                lo_s = mid
                s = mid
            else:
                hi_s = mid
    result[:, 2] = s * r
    if _worst_violation(result[:, 0], result[:, 1], result[:, 2]) > 0.0:
        result[:, 2] *= (1 - 1e-14)
    return result


def construct(budget_seconds, start):
    n = 26
    t0 = _pt()
    # use more of the budget, but stay safe
    deadline = t0 + budget_seconds * 0.70
    final_deadline = t0 + budget_seconds * 0.90
    cons = _make_cons(n)
    rng = np.random.default_rng(90210)

    best_v = None
    best_score = -np.inf

    # --- seed from start ---
    if start is not None:
        base = np.asarray(start, dtype=float).reshape(n, 3).copy()
        base[:, 2] = np.maximum(base[:, 2], 1e-4)
        base[:, 0] = np.clip(base[:, 0], base[:, 2], 1 - base[:, 2])
        base[:, 1] = np.clip(base[:, 1], base[:, 2], 1 - base[:, 2])
        xy0 = base[:, :2].copy()
        r0 = _max_radii_for_positions(xy0[:, 0], xy0[:, 1], n)
        if r0 is not None:
            base = np.column_stack([xy0, r0])
        v = base.ravel().copy()
        pol = _slsqp(v, cons, maxiter=800, ftol=1e-14)
        if pol is not None and _score(pol, n) > _score(v, n):
            v = pol
        sc = _score(v, n)
        if np.isfinite(sc):
            best_v = v.copy(); best_score = sc

    # --- also try hex patterns if time allows / no start ---
    if best_v is None or _pt() < t0 + budget_seconds * 0.12:
        for rows in [(5, 6, 5, 6, 4), (5, 5, 6, 5, 5), (4, 6, 5, 6, 5)]:
            if _pt() > t0 + budget_seconds * 0.20:
                break
            xy = _hex_pattern(rows)
            xy = np.clip(xy, 1e-4, 1 - 1e-4)
            r = _max_radii_for_positions(xy[:, 0], xy[:, 1], n)
            if r is None:
                continue
            cand = np.column_stack([xy, r]).ravel()
            pol = _slsqp(cand, cons, maxiter=600, ftol=1e-13)
            if pol is not None:
                sc = _score(pol, n)
                if np.isfinite(sc) and sc > best_score:
                    best_v = pol.copy(); best_score = sc

    if best_v is None:
        base = np.zeros((n, 3))
        idx = 0
        for j in range(6):
            for i in range(5):
                if idx >= n:
                    break
                base[idx] = [(i + 0.5) / 5, (j + 0.5) / 6, 0.06]
                idx += 1
        best_v = base.ravel().copy()
        best_score = _score(best_v, n)

    # --- SA loop on positions with LP max-radii objective ---
    cur_v = best_v.reshape(n, 3).copy()
    cur_xy = cur_v[:, :2].copy()
    cur_r = _max_radii_for_positions(cur_xy[:, 0], cur_xy[:, 1], n)
    if cur_r is None:
        cur_r = cur_v[:, 2].copy()
    cur_score = float(np.sum(cur_r))

    sigmas = [0.001, 0.003, 0.008, 0.02, 0.04]
    T0 = 4e-4
    it = 0
    while _pt() < deadline:
        it += 1
        u = rng.random()
        if u < 0.55:
            sigma = sigmas[int(rng.integers(0, len(sigmas)))]
            idx = int(rng.integers(n))
            xy_new = cur_xy.copy()
            xy_new[idx] += rng.normal(0, sigma, size=2)
        elif u < 0.88:
            ci = int(rng.integers(n))
            R = rng.uniform(0.12, 0.32)
            d = np.sqrt((cur_xy[:, 0] - cur_xy[ci, 0]) ** 2 +
                        (cur_xy[:, 1] - cur_xy[ci, 1]) ** 2)
            sel = d <= R
            sigma = rng.uniform(0.003, 0.02)
            xy_new = cur_xy.copy()
            xy_new[sel] += rng.normal(0, sigma, size=(int(sel.sum()), 2))
        else:
            sigma = rng.uniform(0.002, 0.015)
            xy_new = cur_xy + rng.normal(0, sigma, size=cur_xy.shape)
        xy_new = np.clip(xy_new, 1e-4, 1 - 1e-4)

        r_lp = _max_radii_for_positions(xy_new[:, 0], xy_new[:, 1], n)
        if r_lp is None:
            continue
        cand_score = float(np.sum(r_lp))
        T = T0 * (0.9996 ** it)
        accept = cand_score >= cur_score
        if not accept and T > 1e-12:
            try:
                accept = rng.random() < np.exp((cand_score - cur_score) / T)
            except Exception:
                accept = False
        if accept:
            cur_xy = xy_new
            cur_score = cand_score

        # polish + update best on improvement
        if cand_score > best_score + 1e-9:
            cand = np.column_stack([xy_new, r_lp]).ravel()
            rc = _slsqp(cand, cons, maxiter=500, ftol=1e-14)
            if rc is not None:
                sc = _score(rc, n)
                if np.isfinite(sc) and sc > best_score:
                    best_v = rc.copy(); best_score = sc
                    cur_xy = rc.reshape(n, 3)[:, :2].copy()
                    rr = _max_radii_for_positions(cur_xy[:, 0], cur_xy[:, 1], n)
                    if rr is not None:
                        cur_score = float(np.sum(rr))

    # --- final polish ---
    if _pt() < final_deadline:
        pol2 = _slsqp(best_v.copy(), cons, maxiter=800, ftol=1e-15)
        if pol2 is not None:
            sc2 = _score(pol2, n)
            if np.isfinite(sc2) and sc2 > best_score:
                best_v = pol2; best_score = sc2

    result = best_v.reshape(n, 3).copy()
    result[:, 2] = np.maximum(result[:, 2], 1e-6)
    result = _final_shrink(result)
    return result
