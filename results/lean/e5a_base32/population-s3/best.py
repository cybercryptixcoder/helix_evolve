import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 1.0
    N = 32
    rng = np.random.default_rng(24680)
    i0, i1 = np.triu_indices(N, 1)

    def pack(c):
        z = np.empty(3 * N)
        z[0::3] = c[:, 0]; z[1::3] = c[:, 1]; z[2::3] = c[:, 2]
        return z

    def unpack(z):
        c = np.empty((N, 3))
        c[:, 0] = z[0::3]; c[:, 1] = z[1::3]; c[:, 2] = z[2::3]
        return c

    def obj(z):
        return -np.sum(z[2::3])

    def obj_grad(z):
        g = np.zeros(3 * N)
        g[2::3] = -1.0
        return g

    def cons(z):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        dx = x[i0] - x[i1]; dy = y[i0] - y[i1]
        d = np.sqrt(dx * dx + dy * dy)
        return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r,
                               d - (r[i0] + r[i1])])

    def cons_jac(z):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        M = i0.size
        J = np.zeros((4 * N + M, 3 * N))
        idx = np.arange(N)
        J[idx, 3 * idx] = 1.0
        J[idx, 3 * idx + 2] = -1.0
        J[N + idx, 3 * idx] = -1.0
        J[N + idx, 3 * idx + 2] = -1.0
        J[2 * N + idx, 3 * idx + 1] = 1.0
        J[2 * N + idx, 3 * idx + 2] = -1.0
        J[3 * N + idx, 3 * idx + 1] = -1.0
        J[3 * N + idx, 3 * idx + 2] = -1.0
        dx = x[i0] - x[i1]; dy = y[i0] - y[i1]
        d = np.sqrt(dx * dx + dy * dy)
        d = np.maximum(d, 1e-12)
        ux = dx / d; uy = dy / d
        rows = 4 * N + np.arange(M)
        J[rows, 3 * i0] = ux
        J[rows, 3 * i1] = -ux
        J[rows, 3 * i0 + 1] = uy
        J[rows, 3 * i1 + 1] = -uy
        J[rows, 3 * i0 + 2] = -1.0
        J[rows, 3 * i1 + 2] = -1.0
        return J

    bounds = [(0.0, 1.0), (0.0, 1.0), (1e-6, 0.5)] * N
    cons_dict = [{'type': 'ineq', 'fun': cons, 'jac': cons_jac}]

    def shrink(c):
        c = c.copy()
        c[:, 2] = np.maximum(c[:, 2], 1e-6)
        m = np.minimum.reduce([c[:, 0], 1 - c[:, 0], c[:, 1], 1 - c[:, 1]])
        c[:, 2] = np.minimum(c[:, 2], np.maximum(m, 1e-6))
        c[:, 0] = np.clip(c[:, 0], c[:, 2], 1 - c[:, 2])
        c[:, 1] = np.clip(c[:, 1], c[:, 2], 1 - c[:, 2])
        for _ in range(400):
            dx = c[:, 0:1] - c[:, 0:1].T
            dy = c[:, 1:2] - c[:, 1:2].T
            d = np.sqrt(dx * dx + dy * dy)
            rr = c[:, 2:3] + c[:, 2:3].T
            np.fill_diagonal(d, 1e9)
            viol = rr - d
            if viol.max() <= 1e-13:
                break
            excess = np.where(viol > 1e-13, viol * 0.5 + 1e-13, 0.0)
            c[:, 2] -= excess.sum(axis=1) * 0.5
            c[:, 2] = np.maximum(c[:, 2], 1e-6)
        return c

    def hex_seed():
        best = None
        for gy in range(4, 9):
            for gx in range(4, 11):
                if gx * gy < N:
                    continue
                pts = []
                for j in range(gy):
                    for i in range(gx):
                        x = (i + 0.5 + (0.5 if j % 2 else 0)) / gx
                        y = (j + 0.5) / gy
                        pts.append((x, y))
                pts = pts[:N]
                r = min(0.5 / gx, 0.5 / gy) * 0.95
                cand = np.array([[x, y, r] for x, y in pts])
                if best is None or cand[:, 2].sum() > best[:, 2].sum():
                    best = cand
        return best

    if start is not None:
        s = np.asarray(start, dtype=float)
        seed = s.copy() if s.shape == (N, 3) and np.all(s[:, 2] > 0) else hex_seed()
    else:
        seed = hex_seed()

    seed = shrink(seed)
    best_c = seed.copy()
    best_s = best_c[:, 2].sum()

    def run_slsqp(c0, maxiter, ftol):
        try:
            res = minimize(obj, pack(c0), jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=cons_dict,
                           options={'maxiter': maxiter, 'ftol': ftol})
            c = shrink(unpack(res.x))
            return c, c[:, 2].sum()
        except Exception:
            return None, -1.0

    # Initial polish
    c, v = run_slsqp(best_c, 2000, 1e-14)
    if c is not None and v > best_s:
        best_s = v; best_c = c

    # Inflate-relax inner loop (kept from p0074, it is the main driver).
    def inflate_relax(base_c, inflate, iters, maxiter, ftol):
        cur_c = base_c.copy()
        cur_v = cur_c[:, 2].sum()
        for _ in range(iters):
            if time.process_time() > deadline:
                break
            trial = cur_c.copy()
            trial[:, 2] = np.minimum(trial[:, 2] * (1.0 + inflate), 0.5)
            trial = shrink(trial)
            c2, v2 = run_slsqp(trial, maxiter, ftol)
            if c2 is not None and v2 > cur_v + 1e-12:
                cur_c, cur_v = c2, v2
            else:
                trial = cur_c.copy()
                trial[:, 2] = np.minimum(trial[:, 2] * (1.0 + inflate * 0.3), 0.5)
                trial = shrink(trial)
                c2, v2 = run_slsqp(trial, maxiter, ftol)
                if c2 is not None and v2 > cur_v + 1e-12:
                    cur_c, cur_v = c2, v2
                else:
                    break
        return cur_c, cur_v

    c, v = inflate_relax(best_c, 0.005, 30, 400, 1e-13)
    if v > best_s:
        best_s = v; best_c = c

    # ---- NEW: coordinate-descent "grow one circle at a time" pass ----
    # For each circle, try to enlarge it (and re-solve) while keeping the
    # rest as an anchor.  This is cheap and targets the binding constraints
    # that uniform inflation cannot unlock.
    def single_grow(base_c, factor, maxiter, ftol):
        cur_c = base_c.copy()
        cur_v = cur_c[:, 2].sum()
        order = np.argsort(cur_c[:, 2])
        for j in order:
            if time.process_time() > deadline:
                break
            trial = cur_c.copy()
            trial[j, 2] = min(trial[j, 2] * factor, 0.5)
            trial = shrink(trial)
            c2, v2 = run_slsqp(trial, maxiter, ftol)
            if c2 is not None and v2 > cur_v + 1e-13:
                cur_c, cur_v = c2, v2
        return cur_c, cur_v

    c, v = single_grow(best_c, 1.05, 300, 1e-13)
    if v > best_s:
        best_s = v; best_c = c

    # Random perturbation loop with inflate-relax finishing.
    tries = 0
    stall = 0
    while time.process_time() < deadline:
        tries += 1
        c = best_c.copy()
        mode = tries % 9
        order = np.argsort(c[:, 2])
        if mode == 0:
            k = int(rng.integers(1, 4))
            sel = order[:k]
            c[sel, 2] *= (1 + rng.uniform(0.05, 0.2, k))
        elif mode == 1:
            k = int(rng.integers(1, 3))
            sel = order[:k]
            c[sel, 0] = np.clip(c[sel, 0] + rng.normal(0, 0.006, k), 0.005, 0.995)
            c[sel, 1] = np.clip(c[sel, 1] + rng.normal(0, 0.006, k), 0.005, 0.995)
        elif mode == 2:
            k = int(rng.integers(2, 5))
            sel = rng.choice(N, size=k, replace=False)
            c[sel, 0] += rng.normal(0, 0.015, k)
            c[sel, 1] += rng.normal(0, 0.015, k)
            c[sel, 2] *= (1 + rng.normal(0, 0.03, k))
        elif mode == 3:
            a = int(rng.integers(0, N))
            c[a, 0] += rng.normal(0, 0.025)
            c[a, 1] += rng.normal(0, 0.025)
        elif mode == 4:
            k = int(rng.integers(4, 8))
            sel = rng.choice(N, size=k, replace=False)
            c[sel, 0] += rng.normal(0, 0.03, k)
            c[sel, 1] += rng.normal(0, 0.03, k)
            c[sel, 2] *= (1 + rng.normal(0, 0.05, k))
        elif mode == 5:
            a, b = rng.choice(N, size=2, replace=False)
            c[a, 0], c[b, 0] = c[b, 0], c[a, 0]
            c[a, 1], c[b, 1] = c[b, 1], c[a, 1]
        elif mode == 6:
            k = int(rng.integers(1, 3))
            sel = order[:k]
            c[sel, 0] = rng.uniform(0.1, 0.9, k)
            c[sel, 1] = rng.uniform(0.1, 0.9, k)
        elif mode == 7:
            c[:, 2] *= 1.0 + rng.uniform(0.01, 0.04)
        else:
            # NEW mode: swap radii between two circles (structural jump)
            a, b = rng.choice(N, size=2, replace=False)
            c[a, 2], c[b, 2] = c[b, 2], c[a, 2]

        c[:, 0] = np.clip(c[:, 0], 0.005, 0.995)
        c[:, 1] = np.clip(c[:, 1], 0.005, 0.995)
        c[:, 2] = np.clip(c[:, 2], 1e-4, 0.3)
        c = shrink(c)
        c2, v2 = run_slsqp(c, 400, 1e-13)
        improved = False
        if c2 is not None and v2 > best_s + 1e-11:
            best_s = v2; best_c = c2
            improved = True
        if improved:
            c3, v3 = inflate_relax(best_c, 0.004, 8, 400, 1e-13)
            if v3 > best_s:
                best_s = v3; best_c = c3
            stall = 0
        else:
            stall += 1
            if stall > 40:
                c = best_c.copy()
                c[:, 0] += rng.normal(0, 0.008, N)
                c[:, 1] += rng.normal(0, 0.008, N)
                c = shrink(c)
                c2, v2 = run_slsqp(c, 500, 1e-13)
                if c2 is not None and v2 > best_s:
                    best_s = v2; best_c = c2
                stall = 0

    # Final aggressive inflate-relax squeezing the last bits.
    c, v = inflate_relax(best_c, 0.002, 40, 800, 1e-14)
    if v > best_s:
        best_s = v; best_c = c

    # Final single-grow sweep with tiny factors.
    if time.process_time() < deadline - 0.05:
        c, v = single_grow(best_c, 1.01, 400, 1e-14)
        if v > best_s:
            best_s = v; best_c = c

    if time.process_time() < deadline - 0.05:
        c2, v2 = run_slsqp(best_c, 3000, 1e-15)
        if c2 is not None and v2 > best_s:
            best_s = v2; best_c = c2

    out = shrink(best_c)
    out[:, 2] = np.maximum(out[:, 2], 1e-6)
    out[:, 2] *= (1 - 1e-9)
    return out
