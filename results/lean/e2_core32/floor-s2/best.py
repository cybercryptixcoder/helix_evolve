import numpy as np
import time
from scipy.optimize import minimize

def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.6
    N = 32
    rng = np.random.default_rng()

    if start is not None:
        best = np.array(start, dtype=float)
    else:
        best = np.array([[0.5, 0.5, 0.02]] * N, dtype=float)

    iu = np.triu_indices(N, 1)

    def repair(a):
        a = a.copy()
        a[:, 2] = np.maximum(a[:, 2], 1e-7)
        for _ in range(300):
            for c in (0, 1):
                a[:, c] = np.clip(a[:, c], a[:, 2], 1 - a[:, 2])
            dx = a[:, 0:1] - a[:, 0:1].T
            dy = a[:, 1:2] - a[:, 1:2].T
            d = np.sqrt(dx * dx + dy * dy)
            s = a[:, 2:3] + a[:, 2:3].T
            np.fill_diagonal(d, np.inf)
            viol = np.maximum(s - d, 0.0)
            if viol.max() < 1e-13:
                break
            worst = viol.max(axis=1)
            a[:, 2] = np.maximum(a[:, 2] - worst * 0.6 - 1e-13, 1e-7)
        for c in (0, 1):
            a[:, c] = np.clip(a[:, c], a[:, 2], 1 - a[:, 2])
        return a

    best = repair(best)
    best_score = best[:, 2].sum()

    # Variable reduction: SLSQP is slow with 96 vars. Instead optimize
    # only the centers for fixed radii, then radii via a scaling line search,
    # which converges faster and is more robust.
    def build_cons_free(xy, r):
        # returns max violation (for feasibility check)
        dx = xy[:, 0:1] - xy[:, 0:1].T
        dy = xy[:, 1:2] - xy[:, 1:2].T
        d = np.sqrt(dx * dx + dy * dy)
        s = r[:, None] + r[None, :]
        np.fill_diagonal(d, np.inf)
        v1 = np.max(s - d)
        v2 = np.max(np.maximum(r - xy[:, 0], 0))
        v3 = np.max(np.maximum(xy[:, 0] + r - 1, 0))
        v4 = np.max(np.maximum(r - xy[:, 1], 0))
        v5 = np.max(np.maximum(xy[:, 1] + r - 1, 0))
        return max(v1, v2, v3, v4, v5)

    # Full SLSQP on all variables but with tighter tolerance and better start
    def optimize(base, maxiter, ftol=1e-15):
        base = repair(base)
        v0 = np.concatenate([base[:, :2].ravel(), base[:, 2]])
        bounds = [(0.0, 1.0)] * (2 * N) + [(1e-7, 0.5)] * N

        def cons(v):
            xy = v[:2 * N].reshape(N, 2)
            r = v[2 * N:]
            dx = xy[:, 0:1] - xy[:, 0:1].T
            dy = xy[:, 1:2] - xy[:, 1:2].T
            d = np.sqrt(dx * dx + dy * dy)
            s = r[:, None] + r[None, :]
            return np.concatenate([
                (d - s)[iu],
                xy[:, 0] - r,
                1 - xy[:, 0] - r,
                xy[:, 1] - r,
                1 - xy[:, 1] - r,
            ])

        try:
            res = minimize(lambda v: -v[2 * N:].sum(), v0, method='SLSQP',
                           bounds=bounds,
                           constraints={'type': 'ineq', 'fun': cons},
                           options={'maxiter': maxiter, 'ftol': ftol})
            xy = res.x[:2 * N].reshape(N, 2)
            r = res.x[2 * N:]
            cand = np.column_stack([xy, r])
            return repair(cand)
        except Exception:
            return base

    # Local "push" refinement: iteratively enlarge radii and re-solve centers.
    def push_refine(base, rounds=60):
        cur = repair(base)
        cur_score = cur[:, 2].sum()
        for _ in range(rounds):
            if time.process_time() >= deadline:
                break
            # try small uniform radius increase
            scale = 1.0 + 1e-4
            trial = cur.copy()
            trial[:, 2] *= scale
            trial = repair(trial)
            # re-optimize centers with SLSQP a little
            trial = optimize(trial, 200)
            s = trial[:, 2].sum()
            if s > cur_score + 1e-12:
                cur, cur_score = trial, s
            else:
                break
        return cur

    best = optimize(best, 3000)
    if best[:, 2].sum() > best_score:
        best_score = best[:, 2].sum()

    # Iterated local search: perturb + SLSQP
    stall = 0
    while time.process_time() < deadline:
        base = best.copy()
        m = int(rng.integers(1, 4))
        scale = 0.005 + 0.02 * rng.random()
        idx = rng.choice(N, size=m, replace=False)
        for i in idx:
            base[i, 0] += rng.normal(0, scale)
            base[i, 1] += rng.normal(0, scale)
            base[i, 2] += rng.normal(0, scale * 0.4)
        base = repair(base)
        remaining = deadline - time.process_time()
        iters = 1200 if remaining > 3 else (500 if remaining > 1 else 200)
        cand = optimize(base, iters)
        sc = cand[:, 2].sum()
        if sc > best_score + 1e-13:
            best, best_score = cand, sc
            stall = 0
            # push refinement on new best
            if remaining > 1.5:
                pushed = push_refine(best, 20)
                if pushed[:, 2].sum() > best_score + 1e-13:
                    best, best_score = pushed, pushed[:, 2].sum()
        else:
            stall += 1
            if stall > 40:
                stall = 0

    # Final safety: shrink radii until strictly feasible
    best = best.copy()
    for _ in range(2000):
        best[:, 2] = np.maximum(best[:, 2] - 1e-11, 1e-7)
        for c in (0, 1):
            best[:, c] = np.clip(best[:, c], best[:, 2], 1 - best[:, 2])
        dx = best[:, 0:1] - best[:, 0:1].T
        dy = best[:, 1:2] - best[:, 1:2].T
        d = np.sqrt(dx * dx + dy * dy)
        s = best[:, 2:3] + best[:, 2:3].T
        np.fill_diagonal(d, np.inf)
        viol = np.maximum(s - d, 0.0)
        wall_viol = max(
            np.max(np.maximum(best[:, 2] - best[:, 0], 0)),
            np.max(np.maximum(best[:, 0] + best[:, 2] - 1, 0)),
            np.max(np.maximum(best[:, 2] - best[:, 1], 0)),
            np.max(np.maximum(best[:, 1] + best[:, 2] - 1, 0)),
        )
        if viol.max() < 1e-14 and wall_viol < 1e-14:
            break
        worst = viol.max(axis=1)
        best[:, 2] = np.maximum(best[:, 2] - worst * 0.6 - 1e-14, 1e-7)
    for c in (0, 1):
        best[:, c] = np.clip(best[:, c], best[:, 2], 1 - best[:, 2])

    return best
