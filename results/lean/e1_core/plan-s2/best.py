import numpy as np
import time
from scipy.optimize import minimize, linprog


def _initial():
    pts = []
    for j in range(5):
        for i in range(5):
            pts.append(((i + 0.5) / 5.0, (j + 0.5) / 5.0))
    pts.append((0.5, 0.5))
    r0 = 0.09
    arr = np.array([[x, y, r0] for x, y in pts], dtype=float)
    return arr


def _feasible(arr):
    arr = np.asarray(arr, dtype=float).copy()
    for i in range(arr.shape[0]):
        r = arr[i, 2]
        arr[i, 0] = min(max(arr[i, 0], r), 1.0 - r)
        arr[i, 1] = min(max(arr[i, 1], r), 1.0 - r)
    n = arr.shape[0]
    for _ in range(50):
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                dx = arr[i, 0] - arr[j, 0]
                dy = arr[i, 1] - arr[j, 1]
                d = np.hypot(dx, dy)
                s = arr[i, 2] + arr[j, 2]
                if d < s:
                    excess = s - d
                    arr[i, 2] -= excess * 0.5 + 1e-12
                    arr[j, 2] -= excess * 0.5 + 1e-12
                    changed = True
        for i in range(n):
            r = arr[i, 2]
            if arr[i, 0] - r < 0:
                arr[i, 2] = arr[i, 0]
            if 1 - arr[i, 0] - r < 0:
                arr[i, 2] = 1 - arr[i, 0]
            if arr[i, 1] - r < 0:
                arr[i, 2] = min(arr[i, 2], arr[i, 1])
            if 1 - arr[i, 1] - r < 0:
                arr[i, 2] = min(arr[i, 2], 1 - arr[i, 1])
            arr[i, 2] = max(arr[i, 2], 1e-9)
        if not changed:
            break
    return arr


def _lp_radii(centers):
    n = centers.shape[0]
    c = -np.ones(n)
    A = []
    b = []
    for i in range(n):
        x, y = centers[i]
        w = min(x, 1 - x, y, 1 - y)
        row = np.zeros(n)
        row[i] = 1.0
        A.append(row)
        b.append(max(w, 0.0))
    for i in range(n):
        for j in range(i + 1, n):
            d = np.hypot(centers[i, 0] - centers[j, 0], centers[i, 1] - centers[j, 1])
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            A.append(row)
            b.append(d)
    A = np.array(A)
    b = np.array(b)
    bounds = [(0.0, None)] * n
    try:
        res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method='highs')
        if res.success:
            return np.maximum(res.x, 1e-6)
    except Exception:
        pass
    return np.full(n, 0.05)


def _fps_centers(n, grid=40):
    xs = (np.arange(grid) + 0.5) / grid
    cand = np.array([[x, y] for y in xs for x in xs])
    chosen = []
    seeds = [(0.5, 0.5), (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
    for s in seeds:
        idx = np.argmin(np.hypot(cand[:, 0] - s[0], cand[:, 1] - s[1]))
        chosen.append(cand[idx])
    chosen = np.array(chosen)
    for _ in range(n - len(seeds)):
        d = np.min(np.hypot(cand[:, 0:1] - chosen[:, 0][None, :],
                            cand[:, 1:2] - chosen[:, 1][None, :]), axis=1)
        idx = np.argmax(d)
        chosen = np.vstack([chosen, cand[idx]])
    return chosen[:n]


def _build_cons(n):
    cons = []
    for i in range(n):
        cons.append({'type': 'ineq',
                     'fun': (lambda v, i=i: v[3 * i] - v[3 * i + 2]),
                     'jac': (lambda v, i=i: _jac_wall_x(v, i))})
        cons.append({'type': 'ineq',
                     'fun': (lambda v, i=i: 1.0 - v[3 * i] - v[3 * i + 2]),
                     'jac': (lambda v, i=i: _jac_wall_x2(v, i))})
        cons.append({'type': 'ineq',
                     'fun': (lambda v, i=i: v[3 * i + 1] - v[3 * i + 2]),
                     'jac': (lambda v, i=i: _jac_wall_y(v, i))})
        cons.append({'type': 'ineq',
                     'fun': (lambda v, i=i: 1.0 - v[3 * i + 1] - v[3 * i + 2]),
                     'jac': (lambda v, i=i: _jac_wall_y2(v, i))})
    for i in range(n):
        for j in range(i + 1, n):
            cons.append({'type': 'ineq',
                         'fun': (lambda v, i=i, j=j: _pair(v, i, j)),
                         'jac': (lambda v, i=i, j=j: _pair_jac(v, i, j))})
    return cons


def _obj(v):
    return -np.sum(v.reshape(-1, 3)[:, 2])


def _obj_grad(v):
    g = np.zeros_like(v)
    g.reshape(-1, 3)[:, 2] = -1.0
    return g


def _slsqp(arr, cons, maxiter, ftol=1e-12):
    n = arr.shape[0]
    bounds = []
    for i in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-6, 0.5))
    v0 = arr.reshape(-1).copy()
    v0 = np.clip(v0, 0.0, 1.0)
    for i in range(n):
        v0[3 * i + 2] = min(max(v0[3 * i + 2], 1e-6), 0.5)
    try:
        res = minimize(_obj, v0, jac=_obj_grad, method='SLSQP',
                       bounds=bounds, constraints=cons,
                       options={'maxiter': maxiter, 'ftol': ftol, 'disp': False})
        if res.x is not None and np.all(np.isfinite(res.x)):
            return res.x.reshape(-1, 3).copy()
    except Exception:
        pass
    return arr.copy()


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 26
    cons = _build_cons(n)

    # Candidate A: from start (or initial)
    if start is not None:
        arrA = np.asarray(start, dtype=float).copy()
        if arrA.shape != (n, 3):
            arrA = _initial()
    else:
        arrA = _initial()
    arrA = _feasible(arrA)
    bestA = _slsqp(arrA, cons, 1000)
    if _obj(bestA.reshape(-1)) > _obj(arrA.reshape(-1)):
        bestA = arrA
    if time.process_time() - t0 < budget_seconds * 0.5:
        cand = _slsqp(bestA, cons, 500, 1e-13)
        if _obj(cand.reshape(-1)) < _obj(bestA.reshape(-1)):
            bestA = cand

    # Candidate B: farthest-point sampling + LP radii
    bestB = None
    if time.process_time() - t0 < budget_seconds * 0.85:
        centers = _fps_centers(n)
        radii = _lp_radii(centers)
        arrB = np.column_stack([centers, radii])
        arrB = _feasible(arrB)
        candB = _slsqp(arrB, cons, 2000)
        if _obj(candB.reshape(-1)) < _obj(arrB.reshape(-1)):
            bestB = candB
        else:
            bestB = arrB

    # Choose best
    best = bestA
    if bestB is not None and np.sum(bestB[:, 2]) > np.sum(bestA[:, 2]):
        best = bestB

    # Perturbation + re-optimization loop
    rng = np.random.default_rng(12345)
    it = 0
    while time.process_time() - t0 < 0.90 * budget_seconds:
        arr = best.copy()
        arr[:, 0:2] += rng.normal(0.0, 0.010, size=(n, 2))
        arr[:, 2] += rng.normal(0.0, 0.005, size=n)
        arr[:, 2] = np.clip(arr[:, 2], 1e-6, 0.5)
        arr = _feasible(arr)
        arr = _slsqp(arr, cons, 400, 1e-12)

        centers = arr[:, :2].copy()
        r = _lp_radii(centers)
        arr2 = np.column_stack([centers, r])
        arr2 = _feasible(arr2)
        arr2 = _slsqp(arr2, cons, 300, 1e-12)

        if np.sum(arr2[:, 2]) > np.sum(best[:, 2]):
            best = arr2
        it += 1
        if it >= 20 and time.process_time() - t0 >= 0.90 * budget_seconds:
            break

    # Exact per-constraint float-level polish
    centers = best[:, :2].copy()
    r = _lp_radii(centers)
    for _ in range(100):
        violated = False
        for i in range(n):
            x, y = centers[i, 0], centers[i, 1]
            for dist in (x, 1.0 - x, y, 1.0 - y):
                if r[i] > dist:
                    r[i] -= (r[i] - dist) + 1e-15
                    violated = True
        for i in range(n):
            for j in range(i + 1, n):
                dx = centers[i, 0] - centers[j, 0]
                dy = centers[i, 1] - centers[j, 1]
                d = np.hypot(dx, dy)
                s = r[i] + r[j]
                if s > d:
                    corr = (s - d) / 2.0 + 1e-15
                    r[i] -= corr
                    r[j] -= corr
                    violated = True
        if not violated:
            break
    r = np.maximum(r, 1e-9)
    return np.column_stack([centers, r])


def _jac_wall_x(v, i):
    g = np.zeros_like(v); g[3 * i] = 1.0; g[3 * i + 2] = -1.0; return g

def _jac_wall_x2(v, i):
    g = np.zeros_like(v); g[3 * i] = -1.0; g[3 * i + 2] = -1.0; return g

def _jac_wall_y(v, i):
    g = np.zeros_like(v); g[3 * i + 1] = 1.0; g[3 * i + 2] = -1.0; return g

def _jac_wall_y2(v, i):
    g = np.zeros_like(v); g[3 * i + 1] = -1.0; g[3 * i + 2] = -1.0; return g

def _pair(v, i, j):
    xi, yi, ri = v[3 * i], v[3 * i + 1], v[3 * i + 2]
    xj, yj, rj = v[3 * j], v[3 * j + 1], v[3 * j + 2]
    dx = xi - xj; dy = yi - yj
    return dx * dx + dy * dy - (ri + rj) ** 2

def _pair_jac(v, i, j):
    xi, yi, ri = v[3 * i], v[3 * i + 1], v[3 * i + 2]
    xj, yj, rj = v[3 * j], v[3 * j + 1], v[3 * j + 2]
    dx = xi - xj; dy = yi - yj; s = ri + rj
    g = np.zeros_like(v)
    g[3 * i] = 2 * dx; g[3 * i + 1] = 2 * dy; g[3 * i + 2] = -2 * s
    g[3 * j] = -2 * dx; g[3 * j + 1] = -2 * dy; g[3 * j + 2] = -2 * s
    return g
