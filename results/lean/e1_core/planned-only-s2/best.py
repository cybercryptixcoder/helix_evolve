import numpy as np
import time
import math
from scipy.optimize import minimize

N = 26


def _unpack(z):
    return z[0::3], z[1::3], z[2::3]


def _neg_sum(z):
    return -np.sum(z[2::3])


def _neg_sum_grad(z):
    g = np.zeros_like(z)
    g[2::3] = -1.0
    return g


def _make_constraints(active_pairs=None, active_walls=None):
    pairs = [(i, j) for i in range(N) for j in range(i + 1, N)]

    def wall(z):
        x, y, r = _unpack(z)
        return np.concatenate([x - r, 1 - x - r, y - r, 1 - y - r])

    def wall_jac(z):
        J = np.zeros((4 * N, 3 * N))
        for i in range(N):
            J[i, 3 * i] = 1.0; J[i, 3 * i + 2] = -1.0
            J[N + i, 3 * i] = -1.0; J[N + i, 3 * i + 2] = -1.0
            J[2 * N + i, 3 * i + 1] = 1.0; J[2 * N + i, 3 * i + 2] = -1.0
            J[3 * N + i, 3 * i + 1] = -1.0; J[3 * N + i, 3 * i + 2] = -1.0
        return J

    def pair(z):
        x, y, r = _unpack(z)
        out = np.empty(len(pairs))
        for k, (i, j) in enumerate(pairs):
            dx = x[i] - x[j]; dy = y[i] - y[j]
            out[k] = dx * dx + dy * dy - (r[i] + r[j]) ** 2
        return out

    def pair_jac(z):
        x, y, r = _unpack(z)
        J = np.zeros((len(pairs), 3 * N))
        for k, (i, j) in enumerate(pairs):
            dx = x[i] - x[j]; dy = y[i] - y[j]
            J[k, 3 * i] = 2 * dx; J[k, 3 * i + 1] = 2 * dy
            J[k, 3 * j] = -2 * dx; J[k, 3 * j + 1] = -2 * dy
            s = -2 * (r[i] + r[j])
            J[k, 3 * i + 2] = s; J[k, 3 * j + 2] = s
        return J

    cons = [
        {'type': 'ineq', 'fun': wall, 'jac': wall_jac},
        {'type': 'ineq', 'fun': pair, 'jac': pair_jac},
    ]

    # Active pair equalities
    if active_pairs:
        def apair(z):
            x, y, r = _unpack(z)
            out = np.empty(len(active_pairs))
            for k, (i, j) in enumerate(active_pairs):
                dx = x[i] - x[j]; dy = y[i] - y[j]
                out[k] = dx * dx + dy * dy - (r[i] + r[j]) ** 2
            return out

        def apair_jac(z):
            x, y, r = _unpack(z)
            J = np.zeros((len(active_pairs), 3 * N))
            for k, (i, j) in enumerate(active_pairs):
                dx = x[i] - x[j]; dy = y[i] - y[j]
                J[k, 3 * i] = 2 * dx; J[k, 3 * i + 1] = 2 * dy
                J[k, 3 * j] = -2 * dx; J[k, 3 * j + 1] = -2 * dy
                s = -2 * (r[i] + r[j])
                J[k, 3 * i + 2] = s; J[k, 3 * j + 2] = s
            return J

        cons.append({'type': 'eq', 'fun': apair, 'jac': apair_jac})

    # Active wall equalities: each is (index, sign) meaning x-r=0, 1-x-r=0, y-r=0, 1-y-r=0
    if active_walls:
        def awall(z):
            x, y, r = _unpack(z)
            out = np.empty(len(active_walls))
            for k, (i, kind) in enumerate(active_walls):
                if kind == 0:
                    out[k] = x[i] - r[i]
                elif kind == 1:
                    out[k] = 1.0 - x[i] - r[i]
                elif kind == 2:
                    out[k] = y[i] - r[i]
                else:
                    out[k] = 1.0 - y[i] - r[i]
            return out

        def awall_jac(z):
            J = np.zeros((len(active_walls), 3 * N))
            for k, (i, kind) in enumerate(active_walls):
                if kind == 0:
                    J[k, 3 * i] = 1.0; J[k, 3 * i + 2] = -1.0
                elif kind == 1:
                    J[k, 3 * i] = -1.0; J[k, 3 * i + 2] = -1.0
                elif kind == 2:
                    J[k, 3 * i + 1] = 1.0; J[k, 3 * i + 2] = -1.0
                else:
                    J[k, 3 * i + 1] = -1.0; J[k, 3 * i + 2] = -1.0
            return J

        cons.append({'type': 'eq', 'fun': awall, 'jac': awall_jac})

    return cons


def _run_slsqp(z0, cons, maxiter, ftol):
    try:
        res = minimize(_neg_sum, z0, jac=_neg_sum_grad, method='SLSQP',
                       constraints=cons,
                       options={'maxiter': maxiter, 'ftol': ftol})
        return res.x
    except Exception:
        return z0


def _to_z(arr):
    z = np.empty(3 * N)
    z[0::3] = arr[:, 0]
    z[1::3] = arr[:, 1]
    z[2::3] = arr[:, 2]
    return z


def _exact_clean(arr):
    x = arr[:, 0].copy()
    y = arr[:, 1].copy()
    r = arr[:, 2].copy()
    r = np.maximum(r, 1e-9)
    for _ in range(8):
        m = np.minimum(np.minimum(x, 1.0 - x), np.minimum(y, 1.0 - y))
        for i in range(N):
            dx = x[i] - x
            dy = y[i] - y
            d = np.sqrt(dx * dx + dy * dy) - r
            d[i] = np.inf
            mi = np.min(d)
            if mi < m[i]:
                m[i] = mi
        r = np.minimum(r, m)
        r = np.nextafter(r, -np.inf)
        r = np.maximum(r, 1e-12)
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
    return np.column_stack([x, y, r])


def _check_zero_tol(arr):
    x = arr[:, 0]; y = arr[:, 1]; r = arr[:, 2]
    if np.any(r <= 0):
        return False
    if np.any(x - r < 0) or np.any(x + r > 1):
        return False
    if np.any(y - r < 0) or np.any(y + r > 1):
        return False
    for i in range(N):
        for j in range(i + 1, N):
            dx = x[i] - x[j]; dy = y[i] - y[j]
            if dx * dx + dy * dy < (r[i] + r[j]) ** 2:
                return False
    return True


def _feasible_loose(arr, tol=1e-7):
    x = arr[:, 0]; y = arr[:, 1]; r = arr[:, 2]
    if np.any(r <= 0):
        return False
    if np.any(x - r < -tol) or np.any(x + r > 1 + tol):
        return False
    if np.any(y - r < -tol) or np.any(y + r > 1 + tol):
        return False
    for i in range(N):
        for j in range(i + 1, N):
            dx = x[i] - x[j]; dy = y[i] - y[j]
            if dx * dx + dy * dy < (r[i] + r[j]) ** 2 - tol:
                return False
    return True


def _fallback():
    k = int(np.ceil(np.sqrt(N)))
    pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:N]
    return np.array([[x, y, 0.02] for x, y in pts])


def _find_active(arr, tol=1e-9):
    x = arr[:, 0]; y = arr[:, 1]; r = arr[:, 2]
    active_pairs = []
    for i in range(N):
        for j in range(i + 1, N):
            dx = x[i] - x[j]; dy = y[i] - y[j]
            d = math.sqrt(dx * dx + dy * dy)
            gap = d - (r[i] + r[j])
            if gap < tol:
                active_pairs.append((i, j))
    active_walls = []
    for i in range(N):
        if x[i] - r[i] < tol:
            active_walls.append((i, 0))
        if 1.0 - x[i] - r[i] < tol:
            active_walls.append((i, 1))
        if y[i] - r[i] < tol:
            active_walls.append((i, 2))
        if 1.0 - y[i] - r[i] < tol:
            active_walls.append((i, 3))
    return active_pairs, active_walls


def construct(budget_seconds, start):
    t0 = time.process_time()

    best = None
    best_score = -np.inf

    if start is not None:
        s = np.array(start, dtype=float)
        if s.shape == (N, 3) and _feasible_loose(s):
            s = _exact_clean(s)
            if _check_zero_tol(s):
                best = s
                best_score = float(np.sum(s[:, 2]))

    if best is None:
        best = _exact_clean(_fallback())
        best_score = float(np.sum(best[:, 2]))

    deadline = budget_seconds * 0.85

    # Phase 1: equality-constrained polish of the start's contact graph
    try:
        ap, aw = _find_active(best, tol=1e-9)
        cons_eq = _make_constraints(ap, aw)
        z0 = _to_z(best)
        z = _run_slsqp(z0, cons_eq, 3000, 1e-14)
        arr = np.column_stack([z[0::3], z[1::3], z[2::3]])
        arr = _exact_clean(arr)
        if _check_zero_tol(arr):
            sc = float(np.sum(arr[:, 2]))
            if sc > best_score:
                best = arr
                best_score = sc
    except Exception:
        pass

    # Phase 2: inequality-only SLSQP polish (no random perturbation)
    if time.process_time() - t0 < deadline:
        try:
            cons = _make_constraints()
            z0 = _to_z(best)
            z = _run_slsqp(z0, cons, 3000, 1e-14)
            arr = np.column_stack([z[0::3], z[1::3], z[2::3]])
            arr = _exact_clean(arr)
            if _check_zero_tol(arr):
                sc = float(np.sum(arr[:, 2]))
                if sc > best_score:
                    best = arr
                    best_score = sc
        except Exception:
            pass

    # Phase 3: small random restarts with equality constraints on current active set
    rng = np.random.default_rng(12345)
    while time.process_time() - t0 < deadline:
        try:
            ap, aw = _find_active(best, tol=1e-9)
            cons_eq = _make_constraints(ap, aw)
            sigma = math.exp(rng.uniform(math.log(1e-4), math.log(1e-2)))
            cand = best.copy()
            cand[:, 0] += rng.normal(0.0, sigma, N)
            cand[:, 1] += rng.normal(0.0, sigma, N)
            cand[:, 2] += rng.normal(0.0, 0.5 * sigma, N)
            cand[:, 2] = np.maximum(cand[:, 2], 1e-6)
            cand[:, 0] = np.clip(cand[:, 0], cand[:, 2], 1.0 - cand[:, 2])
            cand[:, 1] = np.clip(cand[:, 1], cand[:, 2], 1.0 - cand[:, 2])
            z0 = _to_z(cand)
            z = _run_slsqp(z0, cons_eq, 3000, 1e-14)
            arr = np.column_stack([z[0::3], z[1::3], z[2::3]])
            arr = _exact_clean(arr)
            if not _check_zero_tol(arr):
                continue
            sc = float(np.sum(arr[:, 2]))
            if sc > best_score:
                best = arr
                best_score = sc
        except Exception:
            continue

    best = _exact_clean(best)
    if not _check_zero_tol(best):
        best[:, 2] = np.maximum(best[:, 2] - 1e-7, 1e-9)
        best[:, 0] = np.clip(best[:, 0], best[:, 2], 1.0 - best[:, 2])
        best[:, 1] = np.clip(best[:, 1], best[:, 2], 1.0 - best[:, 2])
        best = _exact_clean(best)
    return best
