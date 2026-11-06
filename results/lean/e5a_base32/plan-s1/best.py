import numpy as np
import time
from scipy.optimize import minimize, linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32

    pairs_arr = np.array([(i, j) for i in range(n) for j in range(i + 1, n)])
    pi = pairs_arr[:, 0]
    pj = pairs_arr[:, 1]
    npair = len(pi)
    n_wall = 4 * n
    n_con = n_wall + npair

    lb = np.zeros(3 * n); ub = np.ones(3 * n)
    ub[2::3] = 0.5
    lb[2::3] = 1e-8
    bounds = list(zip(lb, ub))

    def exact_feasible(p):
        x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
        if np.any(r <= 0): return False
        if np.any(x - r < 0) or np.any(x + r > 1): return False
        if np.any(y - r < 0) or np.any(y + r > 1): return False
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        rs = r[pi] + r[pj]
        return not np.any(dx * dx + dy * dy < rs * rs)

    def validate_and_shrink(z, safety=1e-11):
        p = z.reshape(n, 3).copy()
        if exact_feasible(p): return p
        lo, hi = 0.0, 1.0
        base_r = p[:, 2].copy()
        for _ in range(60):
            mid = 0.5 * (lo + hi); p[:, 2] = base_r * mid
            if exact_feasible(p): lo = mid
            else: hi = mid
        if lo <= 0.0: return None
        p[:, 2] = base_r * lo * (1.0 - safety)
        if exact_feasible(p): return p
        for _ in range(80):
            p[:, 2] *= 0.999
            if exact_feasible(p): return p
        return None

    c_lp = -np.ones(n)

    def lp_radii(C):
        x = C[:, 0]; y = C[:, 1]
        A = np.zeros((4 * n + npair, n)); b = np.zeros(4 * n + npair)
        for i in range(n):
            A[4*i, i] = 1.0; b[4*i] = x[i]
            A[4*i+1, i] = 1.0; b[4*i+1] = 1.0 - x[i]
            A[4*i+2, i] = 1.0; b[4*i+2] = y[i]
            A[4*i+3, i] = 1.0; b[4*i+3] = 1.0 - y[i]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.sqrt(dx * dx + dy * dy)
        for k in range(npair):
            A[4*n+k, pi[k]] = 1.0; A[4*n+k, pj[k]] = 1.0; b[4*n+k] = d[k]
        try:
            res = linprog(c_lp, A_ub=A, b_ub=np.maximum(b, 0.0),
                          bounds=[(0, None)] * n, method='highs')
        except Exception:
            return None
        if not res.success: return None
        return res.x

    def con_fun(z):
        p = z.reshape(n, 3)
        x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
        out = np.empty(n_con)
        out[0:4*n:4] = x - r
        out[1:4*n:4] = 1.0 - x - r
        out[2:4*n:4] = y - r
        out[3:4*n:4] = 1.0 - y - r
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        out[n_wall:] = dx * dx + dy * dy - (r[pi] + r[pj]) ** 2
        return out

    def con_jac(z):
        p = z.reshape(n, 3)
        x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
        J = np.zeros((n_con, 3 * n))
        J[0:4*n:4, 0::3] = np.eye(n)
        J[0:4*n:4, 2::3] = -np.eye(n)
        J[1:4*n:4, 0::3] = -np.eye(n)
        J[1:4*n:4, 2::3] = -np.eye(n)
        J[2:4*n:4, 1::3] = np.eye(n)
        J[2:4*n:4, 2::3] = -np.eye(n)
        J[3:4*n:4, 1::3] = -np.eye(n)
        J[3:4*n:4, 2::3] = -np.eye(n)
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        rows = np.arange(n_wall, n_con)
        J[rows, 3*pi] = 2*dx; J[rows, 3*pj] = -2*dx
        J[rows, 3*pi+1] = 2*dy; J[rows, 3*pj+1] = -2*dy
        s = -2 * (r[pi] + r[pj])
        J[rows, 3*pi+2] = s; J[rows, 3*pj+2] = s
        return J

    constraints = [{'type': 'ineq', 'fun': con_fun, 'jac': con_jac}]

    def obj(z): return -np.sum(z[2::3])

    def jac(z):
        g = np.zeros_like(z); g[2::3] = -1.0; return g

    def slsqp(z, maxiter=300, ftol=1e-14):
        try:
            res = minimize(obj, z, method='SLSQP', jac=jac, bounds=bounds,
                           constraints=constraints,
                           options={'maxiter': maxiter, 'ftol': ftol})
            return res.x
        except Exception:
            return z

    # ---- init ----
    best_p = None; best_score = -1.0
    if start is not None:
        p0 = np.asarray(start, dtype=float).reshape(n, 3).copy()
        p0[:, 0] = np.clip(p0[:, 0], 0.001, 0.999)
        p0[:, 1] = np.clip(p0[:, 1], 0.001, 0.999)
        p0[:, 2] = np.clip(p0[:, 2], 1e-4, 0.5)
        cand = validate_and_shrink(p0.reshape(-1))
        if cand is not None:
            best_p = cand; best_score = float(np.sum(cand[:, 2]))
    if best_p is None:
        k = 6
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        C = np.array(pts)
        r_lp = lp_radii(C)
        if r_lp is None: r_lp = np.full(n, 0.01)
        pt = np.column_stack([C, r_lp])
        cand = validate_and_shrink(pt.reshape(-1))
        best_p = cand if cand is not None else np.column_stack([C, np.full(n, 0.01)])
        best_score = float(np.sum(best_p[:, 2]))

    def try_update(p_new, thresh=1e-11):
        nonlocal best_p, best_score
        if p_new is None: return False
        sc = float(np.sum(p_new[:, 2]))
        if sc > best_score + thresh:
            best_p = p_new.copy(); best_score = sc; return True
        return False

    hard_deadline = t0 + budget_seconds - 0.15
    loop_deadline = t0 + budget_seconds - 0.8

    # initial SLSQP polish
    if time.process_time() < loop_deadline:
        z = slsqp(best_p.reshape(-1).copy(), 400, 1e-15)
        cand = validate_and_shrink(z)
        if cand is not None: try_update(cand, 0.0)

    rng = np.random.default_rng(int(1e6 * (best_score - 2.9)) + 987654)

    # ---- simulated annealing on centers ----
    cur_p = best_p.copy()
    cur_score = best_score
    T_start = 1e-4
    T_end = 1e-8
    t_loop_start = time.process_time()
    loop_span = max(1e-6, loop_deadline - t_loop_start)

    it = 0
    while time.process_time() < loop_deadline:
        it += 1
        frac = min(1.0, (time.process_time() - t_loop_start) / loop_span)
        T = T_start * (T_end / T_start) ** frac

        # propose perturbation of 1-3 random circles
        k = rng.integers(1, 4)
        idx = rng.choice(n, size=k, replace=False)
        scale = 0.005 + 0.025 * rng.random()
        Cd = cur_p[:, :2].copy()
        Cd[idx] += rng.normal(0, scale, (k, 2))
        Cd = np.clip(Cd, 0.005, 0.995)
        r_lp = lp_radii(Cd)
        if r_lp is None: continue
        pt = np.column_stack([Cd, r_lp])
        c0 = validate_and_shrink(pt.reshape(-1))
        if c0 is None: continue
        z = slsqp(c0.reshape(-1).copy(), 80, 1e-12)
        cand = validate_and_shrink(z)
        if cand is None: continue
        new_score = float(np.sum(cand[:, 2]))

        # accept / reject
        if new_score >= cur_score:
            cur_p = cand; cur_score = new_score
        else:
            dE = new_score - cur_score
            if rng.random() < np.exp(dE / max(T, 1e-14)):
                cur_p = cand; cur_score = new_score

        # always keep global best
        if new_score > best_score + 1e-11:
            best_p = cand.copy(); best_score = new_score
            cur_p = cand.copy(); cur_score = new_score

    # final heavy polish of global best
    if time.process_time() < hard_deadline:
        z = slsqp(best_p.reshape(-1).copy(), 600, 1e-15)
        cand = validate_and_shrink(z)
        if cand is not None: try_update(cand, 0.0)

    # tiny inflation loop (uses remaining time)
    p = best_p.copy()
    while time.process_time() < hard_deadline:
        x = p[:, 0]; y = p[:, 1]; r = p[:, 2]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]
        d = np.sqrt(dx * dx + dy * dy)
        g = min(float(np.min(d - r[pi] - r[pj])),
                float(np.min(np.concatenate([x-r, 1-x-r, y-r, 1-y-r]))))
        if g <= 1e-13: break
        inc = 0.999 * g; ok = False
        for _t in range(60):
            pt = p.copy(); pt[:, 2] += inc
            if exact_feasible(pt): p = pt; ok = True; break
            inc *= 0.5
            if inc <= 1e-16: break
        if not ok: break
    if float(np.sum(p[:, 2])) > best_score:
        best_p = p; best_score = float(np.sum(p[:, 2]))

    # safety shrink
    p = best_p.copy()
    p[:, 2] *= (1.0 - 1e-9)
    if not exact_feasible(p):
        c = validate_and_shrink(best_p.reshape(-1))
        p = c if c is not None else best_p * np.array([1, 1, 0.999])
    return p
