import numpy as np
import time
from scipy.optimize import minimize

N = 26
_IU = np.triu_indices(N, 1)
_NP = len(_IU[0])


def _to_v(a):
    return np.concatenate([a[:, :2].ravel(), a[:, 2]])


def _from_v(v):
    return np.column_stack([v[:2 * N].reshape(N, 2), v[2 * N:]])


def _obj(v):
    return -np.sum(v[2 * N:])


def _obj_grad(v):
    g = np.zeros_like(v)
    g[2 * N:] = -1.0
    return g


def _cons(v):
    c = v[:2 * N].reshape(N, 2)
    r = v[2 * N:]
    x, y = c[:, 0], c[:, 1]
    walls = np.concatenate([x - r, 1.0 - x - r, y - r, 1.0 - y - r])
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d2 = dx * dx + dy * dy
    rs = r[:, None] + r[None, :]
    return np.concatenate([walls, (d2 - rs * rs)[_IU]])


def _cons_jac(v):
    c = v[:2 * N].reshape(N, 2)
    r = v[2 * N:]
    x, y = c[:, 0], c[:, 1]
    J = np.zeros((4 * N + _NP, 3 * N))
    idx = np.arange(N)
    J[idx, 2 * idx] = 1.0
    J[idx, 2 * N + idx] = -1.0
    J[N + idx, 2 * idx] = -1.0
    J[N + idx, 2 * N + idx] = -1.0
    J[2 * N + idx, 2 * idx + 1] = 1.0
    J[2 * N + idx, 2 * N + idx] = -1.0
    J[3 * N + idx, 2 * idx + 1] = -1.0
    J[3 * N + idx, 2 * N + idx] = -1.0
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    rs = r[:, None] + r[None, :]
    ii, jj = _IU
    rows = 4 * N + np.arange(_NP)
    J[rows, 2 * ii] = 2 * dx[ii, jj]
    J[rows, 2 * jj] = -2 * dx[ii, jj]
    J[rows, 2 * ii + 1] = 2 * dy[ii, jj]
    J[rows, 2 * jj + 1] = -2 * dy[ii, jj]
    J[rows, 2 * N + ii] = -2 * rs[ii, jj]
    J[rows, 2 * N + jj] = -2 * rs[ii, jj]
    return J


def _repair(arr):
    arr = np.array(arr, dtype=float, copy=True)
    c = arr[:, :2]
    r = np.maximum(arr[:, 2], 1e-6)
    c[:, 0] = np.clip(c[:, 0], r, 1 - r)
    c[:, 1] = np.clip(c[:, 1], r, 1 - r)
    for _ in range(400):
        dx = c[:, 0][:, None] - c[:, 0][None, :]
        dy = c[:, 1][:, None] - c[:, 1][None, :]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        ov = rs - d
        np.fill_diagonal(ov, -1.0)
        mx = ov.max()
        if mx <= 1e-12:
            break
        i, j = np.unravel_index(np.argmax(ov), ov.shape)
        e = ov[i, j] / 2 + 1e-11
        r[i] = max(1e-6, r[i] - e)
        r[j] = max(1e-6, r[j] - e)
    arr[:, 2] = r
    return arr


def _slsqp_full(v0, maxiter=400):
    bounds = [(0, 1)] * (2 * N) + [(1e-6, 0.5)] * N
    try:
        res = minimize(_obj, v0, jac=_obj_grad, method="SLSQP",
                       bounds=bounds,
                       constraints={"type": "ineq", "fun": _cons, "jac": _cons_jac},
                       options={"maxiter": maxiter, "ftol": 1e-14})
        return res.x
    except Exception:
        return v0


def _greedy_grow(arr):
    c = arr[:, :2].copy()
    r = arr[:, 2].copy()
    for _ in range(150):
        improved = False
        for i in range(N):
            rmax = min(c[i, 0], 1 - c[i, 0], c[i, 1], 1 - c[i, 1])
            dx = c[i, 0] - c[:, 0]
            dy = c[i, 1] - c[:, 1]
            d = np.sqrt(dx * dx + dy * dy)
            d[i] = np.inf
            rmax = min(rmax, (d - r).min())
            if rmax > r[i] + 1e-12:
                r[i] = rmax - 1e-12
                improved = True
        if not improved:
            break
    out = arr.copy()
    out[:, :2] = c
    out[:, 2] = r
    return out


def _contacts(arr, tol=1e-6):
    c = arr[:, :2]
    r = arr[:, 2]
    dx = c[:, 0][:, None] - c[:, 0][None, :]
    dy = c[:, 1][:, None] - c[:, 1][None, :]
    d = np.sqrt(dx * dx + dy * dy)
    rs = r[:, None] + r[None, :]
    gap = d - rs
    pairs = [(i, j) for i, j in zip(*_IU) if gap[i, j] < tol]
    walls = []
    for i in range(N):
        if c[i, 0] - r[i] < tol: walls.append((i, 'L'))
        if 1 - c[i, 0] - r[i] < tol: walls.append((i, 'R'))
        if c[i, 1] - r[i] < tol: walls.append((i, 'B'))
        if 1 - c[i, 1] - r[i] < tol: walls.append((i, 'T'))
    return pairs, walls


def _active_slsqp(arr, maxiter=3000, tol=5e-4):
    pairs, walls = _contacts(arr, tol=tol)
    if len(pairs) + len(walls) == 0:
        return _to_v(arr)
    ncons = len(pairs) + len(walls)
    wall_list = walls
    pair_i = np.array([p[0] for p in pairs], dtype=int)
    pair_j = np.array([p[1] for p in pairs], dtype=int)

    def cons(v):
        c2 = v[:2 * N].reshape(N, 2)
        r2 = v[2 * N:]
        out = np.empty(ncons)
        k = 0
        for (i, w) in wall_list:
            if w == 'L': out[k] = c2[i, 0] - r2[i]
            elif w == 'R': out[k] = 1.0 - c2[i, 0] - r2[i]
            elif w == 'B': out[k] = c2[i, 1] - r2[i]
            else: out[k] = 1.0 - c2[i, 1] - r2[i]
            k += 1
        if len(pair_i):
            dx = c2[pair_i, 0] - c2[pair_j, 0]
            dy = c2[pair_i, 1] - c2[pair_j, 1]
            rs = r2[pair_i] + r2[pair_j]
            out[k:] = dx * dx + dy * dy - rs * rs
        return out

    def cons_jac(v):
        c2 = v[:2 * N].reshape(N, 2)
        r2 = v[2 * N:]
        J = np.zeros((ncons, 3 * N))
        k = 0
        for (i, w) in wall_list:
            if w == 'L':
                J[k, 2*i] = 1.0; J[k, 2*N+i] = -1.0
            elif w == 'R':
                J[k, 2*i] = -1.0; J[k, 2*N+i] = -1.0
            elif w == 'B':
                J[k, 2*i+1] = 1.0; J[k, 2*N+i] = -1.0
            else:
                J[k, 2*i+1] = -1.0; J[k, 2*N+i] = -1.0
            k += 1
        if len(pair_i):
            dx = c2[pair_i, 0] - c2[pair_j, 0]
            dy = c2[pair_i, 1] - c2[pair_j, 1]
            rs = r2[pair_i] + r2[pair_j]
            rows = np.arange(k, k + len(pair_i))
            J[rows, 2*pair_i] = 2*dx
            J[rows, 2*pair_j] = -2*dx
            J[rows, 2*pair_i+1] = 2*dy
            J[rows, 2*pair_j+1] = -2*dy
            J[rows, 2*N+pair_i] = -2*rs
            J[rows, 2*N+pair_j] = -2*rs
        return J

    bounds = [(0, 1)] * (2 * N) + [(1e-6, 0.5)] * N
    try:
        res = minimize(_obj, _to_v(arr), jac=_obj_grad, method="SLSQP",
                       bounds=bounds,
                       constraints={"type": "ineq", "fun": cons, "jac": cons_jac},
                       options={"maxiter": maxiter, "ftol": 1e-15})
        return res.x
    except Exception:
        return _to_v(arr)


def _perturb(arr, rng, sigma, nr):
    t = arr.copy()
    idx = rng.choice(N, size=nr, replace=False)
    t[idx, 0] += rng.normal(0, sigma, nr)
    t[idx, 1] += rng.normal(0, sigma, nr)
    t[:, 0] = np.clip(t[:, 0], 0.0, 1.0)
    t[:, 1] = np.clip(t[:, 1], 0.0, 1.0)
    return _repair(t)


def _final_safe(arr):
    out = np.array(arr, dtype=float, copy=True)
    out[:, 2] = np.maximum(out[:, 2] - 1e-10, 1e-8)
    out = _repair(out)
    c = out[:, :2]; r = out[:, 2]
    for _ in range(50):
        dx = c[:, 0][:, None] - c[:, 0][None, :]
        dy = c[:, 1][:, None] - c[:, 1][None, :]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        gap = d - rs
        np.fill_diagonal(gap, np.inf)
        viol = np.maximum(0.0, -(gap).min(axis=1))
        wallv = np.maximum.reduce([r - c[:, 0], c[:, 0] + r - 1,
                                   r - c[:, 1], c[:, 1] + r - 1])
        viol = np.maximum(viol, wallv)
        if viol.max() <= 0:
            break
        r = np.maximum(r - (viol + 1e-12), 1e-9)
    out[:, 2] = r
    return out


def _full_polish(arr, rounds, deadline):
    cur = arr.copy()
    for _ in range(rounds):
        if time.process_time() > deadline:
            break
        v = _slsqp_full(_to_v(cur), maxiter=1500)
        nxt = _from_v(v)
        v2 = _active_slsqp(nxt, maxiter=4000)
        nxt2 = _from_v(v2)
        if nxt2[:, 2].sum() >= cur[:, 2].sum() - 1e-14:
            cur = nxt2
        else:
            break
    return cur


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + max(0.5, budget_seconds - 1.2)
    rng = np.random.default_rng(20240117 + int(t0 * 1000) % 100000)

    best = None
    best_s = -1.0

    def consider(a):
        nonlocal best, best_s
        a = _repair(a)
        s = float(a[:, 2].sum())
        if s > best_s + 1e-13:
            best_s = s
            best = a.copy()
            return True
        return False

    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.shape == (N, 3) and np.all(np.isfinite(s)):
            consider(s)
            polished = _full_polish(_greedy_grow(_repair(s)), 3, deadline)
            consider(polished)

    if best is None:
        x = np.linspace(0.1, 0.9, 6)
        pts = [(a, b) for a in x for b in x][:N]
        arr = np.array([[p[0], p[1], 0.03] for p in pts], dtype=float)
        consider(arr)

    # Main loop: perturb, greedy-grow, SLSQP; accept improvements.
    stall = 0
    while time.process_time() < deadline:
        base = best.copy()
        sigma = float(rng.choice([0.002, 0.005, 0.01, 0.02, 0.04, 0.08]))
        nr = int(rng.integers(1, 12))
        trial = _perturb(base, rng, sigma, nr)
        trial = _greedy_grow(trial)

        v = _slsqp_full(_to_v(trial), maxiter=800)
        cand = _from_v(v)
        improved = consider(cand)
        if improved:
            stall = 0
            if time.process_time() < deadline:
                v2 = _active_slsqp(cand, maxiter=3000)
                consider(_from_v(v2))
        else:
            stall += 1
            if stall >= 8 and time.process_time() < deadline:
                kick = best.copy()
                m = int(rng.integers(4, 16))
                idxs = rng.choice(N, size=m, replace=False)
                kick[idxs, 0] += rng.normal(0, 0.1, m)
                kick[idxs, 1] += rng.normal(0, 0.1, m)
                kick[:, 0] = np.clip(kick[:, 0], 0.01, 0.99)
                kick[:, 1] = np.clip(kick[:, 1], 0.01, 0.99)
                kick = _greedy_grow(_repair(kick))
                v = _slsqp_full(_to_v(kick), maxiter=1000)
                consider(_from_v(v))
                stall = 0

    # Final polish with full + active-set SLSQP.
    polished = _full_polish(best, 20, deadline + 0.5)
    consider(polished)

    return _final_safe(best)
