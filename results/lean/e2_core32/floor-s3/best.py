import numpy as np
import time
from scipy.optimize import linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.6
    N = 32
    rng = np.random.default_rng(20240617)

    if start is not None:
        A0 = np.array(start, dtype=float)
        if A0.shape != (N, 3):
            A0 = None
    else:
        A0 = None

    if A0 is None:
        A0 = np.zeros((N, 3))
        r0 = 0.08
        idx = 0
        for j in range(6):
            for i in range(6):
                if idx >= N:
                    break
                A0[idx] = ((i + 0.5) / 6, (j + 0.5) / 6, r0)
                idx += 1

    iu = np.triu_indices(N, 1)
    n_pairs = len(iu[0])
    ii, jj = iu
    A_pair = np.zeros((n_pairs, N))
    A_pair[np.arange(n_pairs), ii] = 1.0
    A_pair[np.arange(n_pairs), jj] = 1.0
    A_wall = np.eye(N)
    A_ub = np.vstack([A_pair, A_wall])
    bounds = [(0, None)] * N
    c = -np.ones(N)

    def pair_dist(P):
        dx = P[:, None, 0] - P[None, :, 0]
        dy = P[:, None, 1] - P[None, :, 1]
        return np.sqrt(dx * dx + dy * dy)

    def lp_max_radii_fast(P):
        d = pair_dist(P)
        wall = np.minimum(np.minimum(P[:, 0], 1 - P[:, 0]),
                          np.minimum(P[:, 1], 1 - P[:, 1]))
        b_ub = np.concatenate([d[ii, jj], wall])
        try:
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
            if res.success:
                return np.maximum(res.x, 1e-7)
        except Exception:
            pass
        return np.maximum(wall * 0.5, 1e-7)

    def repair(A, iters=100, tol=1e-13):
        A = A.copy()
        A[:, 2] = np.maximum(A[:, 2], 1e-7)
        P = A[:, :2]
        R = A[:, 2]
        for _ in range(iters):
            wall = np.maximum.reduce([
                R - P[:, 0], P[:, 0] + R - 1,
                R - P[:, 1], P[:, 1] + R - 1,
                np.zeros(N)])
            dx = P[:, None, 0] - P[None, :, 0]
            dy = P[:, None, 1] - P[None, :, 1]
            d = np.sqrt(dx * dx + dy * dy)
            np.fill_diagonal(d, 1e18)
            rs = R[:, None] + R[None, :]
            overlap = np.maximum(0.0, rs - d)
            np.fill_diagonal(overlap, 0.0)
            worst = max(wall.max(), overlap.max())
            if worst < tol:
                break
            shrink = wall + overlap.sum(axis=1)
            R = np.maximum(R - shrink * 0.5, 1e-7)
            ux = dx / np.maximum(d, 1e-12)
            uy = dy / np.maximum(d, 1e-12)
            fx = (ux * overlap).sum(axis=1)
            fy = (uy * overlap).sum(axis=1)
            fx += np.where(P[:, 0] - R < 0, (R - P[:, 0]), 0)
            fx -= np.where(P[:, 0] + R > 1, (P[:, 0] + R - 1), 0)
            fy += np.where(P[:, 1] - R < 0, (R - P[:, 1]), 0)
            fy -= np.where(P[:, 1] + R > 1, (P[:, 1] + R - 1), 0)
            P = np.clip(P + np.stack([fx, fy], axis=1) * 0.4, 0, 1)
        A[:, :2] = P
        A[:, 2] = R
        return A

    A0 = repair(A0, iters=150)
    A0[:, 2] = lp_max_radii_fast(A0[:, :2])
    A0 = repair(A0, iters=150)
    best = A0.copy()
    best_s = float(best[:, 2].sum())

    def lp_with_dual(P):
        d = pair_dist(P)
        wall = np.minimum(np.minimum(P[:, 0], 1 - P[:, 0]),
                          np.minimum(P[:, 1], 1 - P[:, 1]))
        b_ub = np.concatenate([d[ii, jj], wall])
        try:
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
            if res.success:
                R = np.maximum(res.x, 1e-9)
                lam = -res.ineqlin.marginals
                return R, lam
        except Exception:
            pass
        return np.maximum(wall * 0.5, 1e-7), np.zeros(len(b_ub))

    def grad_from_dual(P, lam):
        lam_pair = lam[:n_pairs]
        lam_wall = lam[n_pairs:]
        gx = np.zeros(N)
        gy = np.zeros(N)
        dx = P[:, None, 0] - P[None, :, 0]
        dy = P[:, None, 1] - P[None, :, 1]
        dist = np.sqrt(dx * dx + dy * dy) + 1e-12
        ux = dx / dist
        uy = dy / dist
        w = lam_pair
        np.add.at(gx, ii, w * ux[ii, jj])
        np.add.at(gy, ii, w * uy[ii, jj])
        np.add.at(gx, jj, -w * ux[ii, jj])
        np.add.at(gy, jj, -w * uy[ii, jj])
        for i in range(N):
            if lam_wall[i] != 0:
                opts = [(P[i, 0], 1, 0), (1 - P[i, 0], -1, 0),
                        (P[i, 1], 0, 1), (1 - P[i, 1], 0, -1)]
                k = int(np.argmin([o[0] for o in opts]))
                _, sx, sy = opts[k]
                gx[i] += lam_wall[i] * sx
                gy[i] += lam_wall[i] * sy
        return gx, gy

    # --- Subgradient ascent (main phase)
    cur = best.copy()
    cur_s = best_s
    step = 1.5e-3
    stall = 0
    while time.process_time() < deadline * 0.72 and stall < 80:
        R, lam = lp_with_dual(cur[:, :2])
        gx, gy = grad_from_dual(cur[:, :2], lam)
        gn = np.sqrt((gx * gx + gy * gy).sum())
        if gn < 1e-15:
            stall += 1
            step *= 0.6
            if step < 1e-8:
                break
            continue
        moved = False
        for mult in (1.0, 0.6, 0.35, 0.2, 0.1, 0.05, 0.02):
            T = cur.copy()
            T[:, 0] = np.clip(T[:, 0] + mult * step * gx, 1e-4, 1 - 1e-4)
            T[:, 1] = np.clip(T[:, 1] + mult * step * gy, 1e-4, 1 - 1e-4)
            R2 = lp_max_radii_fast(T[:, :2])
            s2 = float(R2.sum())
            if s2 > cur_s + 1e-12:
                T[:, 2] = R2
                T = repair(T, iters=20)
                s3 = float(T[:, 2].sum())
                if s3 > cur_s + 1e-12:
                    cur = T
                    cur_s = s3
                    moved = True
                    if cur_s > best_s + 1e-11:
                        best = cur.copy()
                        best_s = cur_s
                    break
        if not moved:
            stall += 1
            step *= 0.65
            if step < 1e-8:
                break
        else:
            stall = 0
            step = min(step * 1.2, 4e-3)

    # --- Coordinate descent polish: perturb single coords, accept LP improvement
    def try_move(T, i, dx, dy, thresh):
        T[i, 0] = np.clip(T[i, 0] + dx, 1e-4, 1 - 1e-4)
        T[i, 1] = np.clip(T[i, 1] + dy, 1e-4, 1 - 1e-4)
        R2 = lp_max_radii_fast(T[:, :2])
        s2 = float(R2.sum())
        if s2 > thresh:
            T[:, 2] = R2
            return T, s2
        return None, None

    polish_steps = [1e-3, 5e-4, 2e-4, 1e-4, 5e-5, 2e-5, 1e-5, 5e-6, 2e-6, 1e-6, 5e-7, 2e-7]
    for stp in polish_steps:
        if time.process_time() >= deadline * 0.88:
            break
        improved = False
        for i in rng.permutation(N):
            if time.process_time() >= deadline * 0.88:
                break
            for dx, dy in ((stp, 0), (-stp, 0), (0, stp), (0, -stp),
                           (stp, stp), (-stp, -stp), (stp, -stp), (-stp, stp)):
                T = best.copy()
                Tn, s2 = try_move(T, i, dx, dy, best_s + 1e-13)
                if Tn is not None:
                    best = Tn
                    best_s = s2
                    improved = True
                    break
        if not improved:
            continue

    # --- Random perturbation phase with focus on tight pairs
    while time.process_time() < deadline:
        T = best.copy()
        k = rng.integers(1, 4)
        idxs = rng.choice(N, size=k, replace=False)
        scale = rng.choice([5e-4, 1e-3, 2e-3, 5e-3])
        T[idxs, 0] += rng.normal(0, scale, k)
        T[idxs, 1] += rng.normal(0, scale, k)
        T[:, :2] = np.clip(T[:, :2], 1e-4, 1 - 1e-4)
        R2 = lp_max_radii_fast(T[:, :2])
        T[:, 2] = R2
        T = repair(T, iters=40)
        s = float(T[:, 2].sum())
        if s > best_s + 1e-11:
            best, best_s = T, s

    # Final safety: strict feasibility with margin
    best = repair(best, iters=400, tol=1e-16)
    best[:, 2] = np.maximum(best[:, 2] - 1e-7, 1e-7)
    best = repair(best, iters=400, tol=1e-16)
    best[:, 2] = np.maximum(best[:, 2] - 1e-8, 1e-8)
    return best
