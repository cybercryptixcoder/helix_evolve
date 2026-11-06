import numpy as np
import time
from scipy.optimize import minimize


def _feasible(P, tol=0.0):
    X = P[:, 0]; Y = P[:, 1]; R = P[:, 2]
    if np.any(R <= 0):
        return False
    if np.any(X - R < -tol) or np.any(X + R > 1 + tol) or \
       np.any(Y - R < -tol) or np.any(Y + R > 1 + tol):
        return False
    dx = X[:, None] - X[None, :]
    dy = Y[:, None] - Y[None, :]
    d2 = dx * dx + dy * dy
    rs = R[:, None] + R[None, :]
    np.fill_diagonal(d2, 1e9)
    return not np.any(d2 < rs * rs - tol)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85
    rng = np.random.default_rng(24680)
    N = 32

    def repair_radii(x, y, r):
        lim = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        r = np.minimum(r, lim)
        r = np.maximum(r, 1e-6)
        for _ in range(100):
            dxm = x[:, None] - x[None, :]
            dym = y[:, None] - y[None, :]
            d = np.sqrt(dxm * dxm + dym * dym)
            np.fill_diagonal(d, 1e9)
            rsum = r[:, None] + r[None, :]
            viol = rsum - d
            np.fill_diagonal(viol, 0)
            if viol.max() <= 1e-14:
                break
            scale = np.ones(N)
            for i in range(N):
                jj = np.where(viol[i] > 1e-14)[0]
                for j in jj:
                    if j > i:
                        s = r[i] + r[j]
                        if s > 0:
                            sc = d[i, j] / s
                            if sc < scale[i]:
                                scale[i] = sc
                            if sc < scale[j]:
                                scale[j] = sc
            r = r * np.minimum(scale, 1.0)
            r = np.maximum(r, 1e-9)
        return r

    P0 = None
    if start is not None:
        try:
            S = np.array(start, dtype=float, copy=True)
            if S.shape == (N, 3) and _feasible(S, tol=1e-9):
                P0 = S
        except Exception:
            P0 = None

    if P0 is None:
        P0 = np.zeros((N, 3))
        idx = 0
        for j in range(6):
            for i in range(6):
                if idx >= N:
                    break
                x = (i + 0.5 + (0.5 if j % 2 else 0.0)) / 6
                y = (j + 0.5) / 6
                if x >= 1.0:
                    x -= 1.0 / 6
                P0[idx] = (x, y, 0.03)
                idx += 1
        P0 = P0[:N]

    x0 = np.clip(P0[:, 0], 0.0, 1.0)
    y0 = np.clip(P0[:, 1], 0.0, 1.0)
    r0 = np.maximum(P0[:, 2], 1e-3)
    r0 = repair_radii(x0, y0, r0)

    iu_i, iu_j = np.triu_indices(N, 1)
    M = len(iu_i)

    def get_xy_r(z):
        return z[0:N], z[N:2 * N], np.exp(z[2 * N:3 * N])

    def obj(z):
        return -np.exp(z[2 * N:3 * N]).sum()

    def obj_grad(z):
        g = np.zeros_like(z)
        g[2 * N:3 * N] = -np.exp(z[2 * N:3 * N])
        return g

    def cons_fun(z):
        x, y, r = get_xy_r(z)
        res = np.empty(4 * N + M)
        res[0:N] = x - r
        res[N:2 * N] = 1 - x - r
        res[2 * N:3 * N] = y - r
        res[3 * N:4 * N] = 1 - y - r
        dx = x[iu_i] - x[iu_j]
        dy = y[iu_i] - y[iu_j]
        rs = r[iu_i] + r[iu_j]
        res[4 * N:] = dx * dx + dy * dy - rs * rs
        return res

    def cons_jac(z):
        x, y, r = get_xy_r(z)
        J = np.zeros((4 * N + M, 3 * N))
        ar = np.arange(N)
        J[ar, ar] = 1.0; J[ar, 2 * N + ar] = -r
        J[N + ar, ar] = -1.0; J[N + ar, 2 * N + ar] = -r
        J[2 * N + ar, N + ar] = 1.0; J[2 * N + ar, 2 * N + ar] = -r
        J[3 * N + ar, N + ar] = -1.0; J[3 * N + ar, 2 * N + ar] = -r
        dx = x[iu_i] - x[iu_j]
        dy = y[iu_i] - y[iu_j]
        rs = r[iu_i] + r[iu_j]
        base = 4 * N + np.arange(M)
        J[base, iu_i] = 2 * dx
        J[base, iu_j] = -2 * dx
        J[base, N + iu_i] = 2 * dy
        J[base, N + iu_j] = -2 * dy
        J[base, 2 * N + iu_i] = -2 * rs * r[iu_i]
        J[base, 2 * N + iu_j] = -2 * rs * r[iu_j]
        return J

    cons = [{'type': 'ineq', 'fun': cons_fun, 'jac': cons_jac}]

    def unpack(x, y, r):
        return np.concatenate([x, y, np.log(np.maximum(r, 1e-12))])

    def polish(z, maxiter=300):
        if time.process_time() > deadline:
            return z, -obj(z)
        try:
            res = minimize(obj, z, jac=obj_grad, method='SLSQP',
                           constraints=cons,
                           options={'maxiter': maxiter, 'ftol': 1e-14})
            if np.all(np.isfinite(res.x)):
                s = -obj(res.x)
                if s > -obj(z) - 1e-10:
                    return res.x, s
        except Exception:
            pass
        return z, -obj(z)

    best_z = unpack(x0, y0, r0)
    best_score = r0.sum()
    z, s = polish(best_z, maxiter=800)
    if s > best_score:
        best_z, best_score = z.copy(), s

    # --- Local search with L-BFGS-free approach via SLSQP on perturbed basins ---
    it = 0
    stall = 0
    base_amp = 0.006
    while time.process_time() < deadline - 0.15:
        it += 1
        z = best_z.copy()
        mode = it % 10
        amp = base_amp * (0.3 + 0.7 * rng.random())
        r_now = np.exp(z[2 * N:3 * N])

        if mode == 0:
            z[0:N] += rng.normal(0, amp, N)
            z[N:2 * N] += rng.normal(0, amp, N)
            z[2 * N:3 * N] += rng.normal(0, 0.006, N)
        elif mode == 1:
            k = int(rng.integers(2, 6))
            idxs = rng.choice(N, k, replace=False)
            z[idxs] += rng.normal(0, amp * 8, k)
            z[N + idxs] += rng.normal(0, amp * 8, k)
            z[2 * N + idxs] += rng.normal(0, 0.05, k)
        elif mode == 2:
            i, j = rng.choice(N, 2, replace=False)
            z[i], z[j] = z[j], z[i]
            z[N + i], z[N + j] = z[N + j], z[N + i]
            z[2 * N:3 * N] += rng.normal(0, 0.012, N)
        elif mode == 3:
            z[2 * N:3 * N] += 0.025
            z[0:N] += rng.normal(0, amp * 0.8, N)
            z[N:2 * N] += rng.normal(0, amp * 0.8, N)
        elif mode == 4:
            small = np.argsort(r_now)[:6]
            z[small] += rng.normal(0, amp * 6, 6)
            z[N + small] += rng.normal(0, amp * 6, 6)
            z[2 * N + small] += rng.normal(0, 0.04, 6)
        elif mode == 5:
            c = int(rng.integers(N))
            d = np.hypot(best_z[0:N] - best_z[c], best_z[N:2 * N] - best_z[N + c])
            near = np.argsort(d)[:7]
            z[near] += rng.normal(0, amp * 5, len(near))
            z[N + near] += rng.normal(0, amp * 5, len(near))
            z[2 * N + near] += rng.normal(0, 0.04, len(near))
        elif mode == 6:
            k = int(rng.integers(4, 10))
            idxs = rng.choice(N, k, replace=False)
            z[2 * N + idxs] -= 0.06
            z[0:N] += rng.normal(0, amp * 0.8, N)
            z[N:2 * N] += rng.normal(0, amp * 0.8, N)
        elif mode == 7:
            c = int(rng.integers(N))
            d = np.hypot(best_z[0:N] - best_z[c], best_z[N:2 * N] - best_z[N + c])
            near = np.argsort(d)[:8]
            ang = rng.normal(0, 0.08)
            ca, sa = np.cos(ang), np.sin(ang)
            for i in near:
                px = z[i] - z[c]; py = z[N + i] - z[N + c]
                z[i] = z[c] + ca * px - sa * py
                z[N + i] = z[N + c] + sa * px + ca * py
            z[2 * N:3 * N] += rng.normal(0, 0.01, N)
        elif mode == 8:
            z[0:N] += rng.normal(0, 0.025, N)
            z[N:2 * N] += rng.normal(0, 0.025, N)
            z[2 * N:3 * N] += rng.normal(0, 0.025, N)
        else:
            cx = z[0:N] - 0.5; cy = z[N:2 * N] - 0.5
            nrm = np.hypot(cx, cy) + 1e-9
            z[0:N] += amp * cx / nrm
            z[N:2 * N] += amp * cy / nrm
            z[2 * N:3 * N] += rng.normal(0, 0.01, N)

        x = np.clip(z[0:N], 0.001, 0.999)
        y = np.clip(z[N:2 * N], 0.001, 0.999)
        r = np.exp(z[2 * N:3 * N])
        r = repair_radii(x, y, r)
        z = unpack(x, y, r)
        zc, sc = polish(z, maxiter=200)
        if sc > best_score + 1e-10:
            best_z, best_score = zc.copy(), sc
            stall = 0
        else:
            stall += 1

        if stall > 40 and time.process_time() < deadline - 0.5:
            zc, sc = polish(best_z, maxiter=600)
            if sc > best_score + 1e-10:
                best_z, best_score = zc.copy(), sc
            stall = 0

    # Final polish
    if time.process_time() < deadline:
        zc, sc = polish(best_z, maxiter=800)
        if sc > best_score:
            best_z, best_score = zc.copy(), sc

    x, y, r = get_xy_r(best_z)
    r = repair_radii(x, y, r)
    P = np.column_stack([x, y, r])
    for _ in range(400):
        if _feasible(P, tol=0.0):
            break
        P[:, 2] *= 0.999
        P[:, 0] = np.clip(P[:, 0], P[:, 2], 1 - P[:, 2])
        P[:, 1] = np.clip(P[:, 1], P[:, 2], 1 - P[:, 2])
    P[:, 2] *= (1 - 1e-10)
    P[:, 0] = np.clip(P[:, 0], P[:, 2], 1 - P[:, 2])
    P[:, 1] = np.clip(P[:, 1], P[:, 2], 1 - P[:, 2])
    return P
