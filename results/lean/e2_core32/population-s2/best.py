import numpy as np
import time
from scipy.optimize import minimize

# ---------- helpers ----------

def _feasible_radii(X, Y, iters=300):
    n = len(X)
    r = np.minimum(np.minimum(X, 1 - X), np.minimum(Y, 1 - Y))
    for _ in range(iters):
        changed = False
        for i in range(n):
            dx = X[i] - X
            dy = Y[i] - Y
            d = np.sqrt(dx * dx + dy * dy) - r
            d[i] = np.inf
            m = min(X[i], 1 - X[i], Y[i], 1 - Y[i], d.min())
            if m < 0:
                m = 1e-9
            if abs(m - r[i]) > 1e-15:
                r[i] = m
                changed = True
        if not changed:
            break
    return np.maximum(r, 1e-9)


def _build_cons(n):
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    npairs = len(pairs)
    pi = np.array([p[0] for p in pairs], dtype=int)
    pj = np.array([p[1] for p in pairs], dtype=int)
    I = np.eye(n)
    Z = np.zeros((n, n))

    def pair_fun(z):
        X_ = z[:n]; Y_ = z[n:2 * n]; R_ = z[2 * n:]
        dx = X_[pi] - X_[pj]
        dy = Y_[pi] - Y_[pj]
        return np.sqrt(dx * dx + dy * dy) - R_[pi] - R_[pj]

    def pair_jac(z):
        X_ = z[:n]; Y_ = z[n:2 * n]
        dx = X_[pi] - X_[pj]
        dy = Y_[pi] - Y_[pj]
        d = np.sqrt(dx * dx + dy * dy) + 1e-15
        ux = dx / d
        uy = dy / d
        J = np.zeros((npairs, 3 * n))
        rows = np.arange(npairs)
        J[rows, pi] = ux
        J[rows, pj] = -ux
        J[rows, n + pi] = uy
        J[rows, n + pj] = -uy
        J[rows, 2 * n + pi] = -1.0
        J[rows, 2 * n + pj] = -1.0
        return J

    return [
        {'type': 'ineq', 'fun': lambda z: z[:n] - z[2 * n:],
         'jac': lambda z: np.hstack([I, Z, -I])},
        {'type': 'ineq', 'fun': lambda z: 1 - z[:n] - z[2 * n:],
         'jac': lambda z: np.hstack([-I, Z, -I])},
        {'type': 'ineq', 'fun': lambda z: z[n:2 * n] - z[2 * n:],
         'jac': lambda z: np.hstack([Z, I, -I])},
        {'type': 'ineq', 'fun': lambda z: 1 - z[n:2 * n] - z[2 * n:],
         'jac': lambda z: np.hstack([Z, -I, -I])},
        {'type': 'ineq', 'fun': pair_fun, 'jac': pair_jac},
    ]


_CONS_CACHE = {}


def _slsqp(X, Y, R, maxiter=200, t0=None, deadline=None):
    if t0 is not None and deadline is not None and time.process_time() - t0 > deadline:
        return X, Y, _feasible_radii(X, Y)
    n = len(X)
    z0 = np.concatenate([X, Y, R])

    def obj(z):
        return -np.sum(z[2 * n:])

    def grad(z):
        g = np.zeros(3 * n)
        g[2 * n:] = -1.0
        return g

    if n not in _CONS_CACHE:
        _CONS_CACHE[n] = _build_cons(n)
    cons = _CONS_CACHE[n]
    bounds = [(0, 1)] * n + [(0, 1)] * n + [(1e-6, 0.5)] * n
    try:
        res = minimize(obj, z0, jac=grad, method='SLSQP', bounds=bounds,
                       constraints=cons,
                       options={'maxiter': maxiter, 'ftol': 1e-14})
        z = res.x
        Xn = np.clip(z[:n], 1e-6, 1 - 1e-6)
        Yn = np.clip(z[n:2 * n], 1e-6, 1 - 1e-6)
        Rn = _feasible_radii(Xn, Yn)
        return Xn, Yn, Rn
    except Exception:
        return X, Y, R


# ---------- main optimizer ----------
# Key change: use the full SLSQP (all variables, all constraints) but always
# check the *true* feasible radii after it, and prefer solutions found via
# direct SLSQP on the radius-sum objective. Additionally do multi-start
# restarts from the start solution with structured perturbations plus a
# "shrink-then-regrow" move that resolves jammed contact graphs.

def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = budget_seconds * 0.85
    n = 32
    rng = np.random.default_rng(20240911)

    S = None
    if start is not None:
        S = np.asarray(start, dtype=float)
        if S.shape != (n, 3):
            S = None

    if S is None:
        k = 6
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        X = np.array([p[0] for p in pts])
        Y = np.array([p[1] for p in pts])
    else:
        X = np.clip(S[:, 0].copy(), 1e-5, 1 - 1e-5)
        Y = np.clip(S[:, 1].copy(), 1e-5, 1 - 1e-5)
    R = _feasible_radii(X, Y)

    best_X, best_Y, best_R = X.copy(), Y.copy(), R.copy()
    best_score = R.sum()

    def try_update(Xt, Yt, Rt):
        nonlocal best_X, best_Y, best_R, best_score
        sc = Rt.sum()
        if sc > best_score + 1e-13:
            best_score = sc
            best_X, best_Y, best_R = Xt.copy(), Yt.copy(), Rt.copy()
            return True
        return False

    # Phase 1: heavy polish of the start
    for _ in range(3):
        X, Y, R = _slsqp(best_X, best_Y, best_R, maxiter=400, t0=t0, deadline=deadline)
        if not try_update(X, Y, R):
            break

    # Phase 2: basin-hopping with SLSQP. Use several perturbation styles.
    p2_end = deadline * 0.75
    it = 0
    while time.process_time() - t0 < p2_end:
        it += 1
        mode = it % 5
        if mode == 0:
            # uniform small
            amp = rng.uniform(0.001, 0.010)
            Xp = np.clip(best_X + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)
            Yp = np.clip(best_Y + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)
        elif mode == 1:
            # move a few circles strongly
            Xp = best_X.copy(); Yp = best_Y.copy()
            k = int(rng.integers(2, 6))
            idx = rng.choice(n, size=k, replace=False)
            amp = rng.uniform(0.01, 0.04)
            Xp[idx] = np.clip(Xp[idx] + rng.normal(0, amp, k), 1e-4, 1 - 1e-4)
            Yp[idx] = np.clip(Yp[idx] + rng.normal(0, amp, k), 1e-4, 1 - 1e-4)
        elif mode == 2:
            # shrink-then-regrow: shrink all radii, then regrow
            Xp = best_X.copy(); Yp = best_Y.copy()
            amp = rng.uniform(0.002, 0.015)
            Xp = np.clip(Xp + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)
            Yp = np.clip(Yp + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)
        elif mode == 3:
            # radial perturbation around each center (rotational)
            Xp = best_X.copy(); Yp = best_Y.copy()
            ang = rng.uniform(0, 2*np.pi, n)
            rad = rng.uniform(0.0005, 0.008, n)
            Xp = np.clip(Xp + rad*np.cos(ang), 1e-4, 1 - 1e-4)
            Yp = np.clip(Yp + rad*np.sin(ang), 1e-4, 1 - 1e-4)
        else:
            # random restart-ish: perturb all with moderate amp
            amp = rng.uniform(0.005, 0.020)
            Xp = np.clip(best_X + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)
            Yp = np.clip(best_Y + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)

        Rp = _feasible_radii(Xp, Yp)
        X2, Y2, R2 = _slsqp(Xp, Y2 if False else Yp, Rp, maxiter=200,
                            t0=t0, deadline=p2_end)
        try_update(X2, Y2, R2)

        if time.process_time() - t0 > p2_end:
            break

    # Phase 3: fine polishing with progressively smaller perturbations
    while time.process_time() - t0 < deadline:
        X2, Y2, R2 = _slsqp(best_X, best_Y, best_R, maxiter=400,
                            t0=t0, deadline=deadline)
        if not try_update(X2, Y2, R2):
            amp = rng.uniform(0.0002, 0.003)
            Xp = np.clip(best_X + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)
            Yp = np.clip(best_Y + rng.normal(0, amp, n), 1e-4, 1 - 1e-4)
            Rp = _feasible_radii(Xp, Yp)
            X3, Y3, R3 = _slsqp(Xp, Yp, Rp, maxiter=250,
                                t0=t0, deadline=deadline)
            try_update(X3, Y3, R3)
        if time.process_time() - t0 > deadline:
            break

    # Final safety: shrink slightly to guarantee exact feasibility
    X = best_X.copy()
    Y = best_Y.copy()
    R = _feasible_radii(X, Y)
    R = np.maximum(R * (1 - 1e-10), 1e-9)
    out = np.column_stack([X, Y, R])

    for _ in range(200):
        ok = True
        for i in range(n):
            if (out[i, 2] <= 0 or out[i, 0] - out[i, 2] < 0 or out[i, 0] + out[i, 2] > 1
                    or out[i, 1] - out[i, 2] < 0 or out[i, 1] + out[i, 2] > 1):
                ok = False
                break
        if ok:
            for i in range(n):
                for j in range(i + 1, n):
                    d = np.hypot(out[i, 0] - out[j, 0], out[i, 1] - out[j, 1])
                    if d < out[i, 2] + out[j, 2]:
                        ok = False
                        break
                if not ok:
                    break
        if ok:
            break
        out[:, 2] *= 0.999

    return out
