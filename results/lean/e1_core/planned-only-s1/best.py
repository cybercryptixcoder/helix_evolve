import numpy as np
import time
from scipy.optimize import minimize, linprog


def _unpack(z, n):
    c = z[:2 * n].reshape(n, 2)
    r = z[2 * n:]
    return c, r


def _objective(z, n):
    return -np.sum(z[2 * n:])


def _objective_jac(z, n):
    g = np.zeros_like(z)
    g[2 * n:] = -1.0
    return g


def _pair_index(n):
    idx = []
    for i in range(n):
        for j in range(i + 1, n):
            idx.append((i, j))
    return idx


def _constraints(z, n):
    pairs = _pair_index(n)
    npair = len(pairs)

    def wall_xlo(zz):
        c, r = _unpack(zz, n)
        return c[:, 0] - r

    def wall_xlo_jac(zz):
        J = np.zeros((n, 3 * n))
        for i in range(n):
            J[i, 2 * i] = 1.0
            J[i, 2 * n + i] = -1.0
        return J

    def wall_xhi(zz):
        c, r = _unpack(zz, n)
        return 1.0 - c[:, 0] - r

    def wall_xhi_jac(zz):
        J = np.zeros((n, 3 * n))
        for i in range(n):
            J[i, 2 * i] = -1.0
            J[i, 2 * n + i] = -1.0
        return J

    def wall_ylo(zz):
        c, r = _unpack(zz, n)
        return c[:, 1] - r

    def wall_ylo_jac(zz):
        J = np.zeros((n, 3 * n))
        for i in range(n):
            J[i, 2 * i + 1] = 1.0
            J[i, 2 * n + i] = -1.0
        return J

    def wall_yhi(zz):
        c, r = _unpack(zz, n)
        return 1.0 - c[:, 1] - r

    def wall_yhi_jac(zz):
        J = np.zeros((n, 3 * n))
        for i in range(n):
            J[i, 2 * i + 1] = -1.0
            J[i, 2 * n + i] = -1.0
        return J

    def pair_fun(zz):
        c, r = _unpack(zz, n)
        out = np.empty(npair)
        for k, (i, j) in enumerate(pairs):
            dx = c[i, 0] - c[j, 0]
            dy = c[i, 1] - c[j, 1]
            out[k] = dx * dx + dy * dy - (r[i] + r[j]) ** 2
        return out

    def pair_jac(zz):
        c, r = _unpack(zz, n)
        J = np.zeros((npair, 3 * n))
        for k, (i, j) in enumerate(pairs):
            dx = c[i, 0] - c[j, 0]
            dy = c[i, 1] - c[j, 1]
            J[k, 2 * i] = 2.0 * dx
            J[k, 2 * j] = -2.0 * dx
            J[k, 2 * i + 1] = 2.0 * dy
            J[k, 2 * j + 1] = -2.0 * dy
            s = -2.0 * (r[i] + r[j])
            J[k, 2 * n + i] = s
            J[k, 2 * n + j] = s
        return J

    def rpos(zz):
        return _unpack(zz, n)[1]

    def rpos_jac(zz):
        J = np.zeros((n, 3 * n))
        for i in range(n):
            J[i, 2 * n + i] = 1.0
        return J

    cons = [
        {'type': 'ineq', 'fun': wall_xlo, 'jac': wall_xlo_jac},
        {'type': 'ineq', 'fun': wall_xhi, 'jac': wall_xhi_jac},
        {'type': 'ineq', 'fun': wall_ylo, 'jac': wall_ylo_jac},
        {'type': 'ineq', 'fun': wall_yhi, 'jac': wall_yhi_jac},
        {'type': 'ineq', 'fun': pair_fun, 'jac': pair_jac},
        {'type': 'ineq', 'fun': rpos, 'jac': rpos_jac},
    ]
    return cons


def _pack(c, r):
    return np.concatenate([c.ravel(), r])


def _run_slsqp(c0, r0, n, maxiter=400, ftol=1e-12):
    z0 = _pack(c0, r0)
    cons = _constraints(z0, n)
    try:
        res = minimize(_objective, z0, args=(n,), jac=_objective_jac, method='SLSQP',
                       constraints=cons,
                       options={'maxiter': maxiter, 'ftol': ftol})
        z = res.x
    except Exception:
        z = z0
    c, r = _unpack(z, n)
    return c, r


def _lp_radii(c, n):
    cA = []
    bA = []
    for i in range(n):
        row = np.zeros(n)
        row[i] = 1.0
        cA.append(row)
        bA.append(min(c[i, 0], 1.0 - c[i, 0], c[i, 1], 1.0 - c[i, 1]))
    for i in range(n):
        for j in range(i + 1, n):
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            cA.append(row)
            bA.append(np.hypot(c[i, 0] - c[j, 0], c[i, 1] - c[j, 1]))
    cA = np.array(cA)
    bA = np.array(bA)
    try:
        res = linprog(-np.ones(n), A_ub=cA, b_ub=bA,
                      bounds=[(0, None)] * n, method='highs')
        if res.success:
            return res.x
    except Exception:
        pass
    return None


def _clean(c, r, n):
    r = np.maximum(r, 1e-6)
    for i in range(n):
        r[i] = min(r[i], c[i, 0], 1.0 - c[i, 0], c[i, 1], 1.0 - c[i, 1])
    r = np.maximum(r, 1e-6)
    for _ in range(50):
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                d = np.hypot(c[i, 0] - c[j, 0], c[i, 1] - c[j, 1])
                s = r[i] + r[j]
                if d < s:
                    excess = s - d
                    r[i] -= excess / 2 + 1e-12
                    r[j] -= excess / 2 + 1e-12
                    changed = True
        r = np.maximum(r, 1e-6)
        if not changed:
            break
    return c, r


def _score(c, r):
    return np.sum(r)


def _init_rows(rows, n, r0=0.06):
    pts = []
    k = len(rows)
    for j, cnt in enumerate(rows):
        y = (j + 0.5) / k
        for i in range(cnt):
            x = (i + 0.5) / cnt
            if j % 2 == 1:
                x = (x + 0.5 / cnt) % 1.0
            pts.append((x, y))
    pts = pts[:n]
    c = np.array(pts)
    r = np.full(n, r0)
    return c, r


def _contact_graph(c, r, n, tol=1e-6):
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = np.hypot(c[i, 0] - c[j, 0], c[i, 1] - c[j, 1])
            if d - r[i] - r[j] < tol:
                adj[i].append(j)
                adj[j].append(i)
    return adj


def _bfs_prefix(adj, start_i, size):
    order = []
    seen = set([start_i])
    queue = [start_i]
    while queue and len(order) < size:
        u = queue.pop(0)
        order.append(u)
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
    return order


def _cycle_perturb(best_c, best_r, n, rng, n_restarts=8):
    """Remove a high-value contact cycle, restart centers, reoptimize."""
    c = best_c.copy()
    r = best_r.copy()
    adj = _contact_graph(c, r, n)

    # Sample 10 candidate seeds, BFS each to a 6-circle prefix,
    # pick the prefix with the largest sum of current radii.
    n_cand = min(10, n)
    seeds = rng.choice(n, size=n_cand, replace=False)
    best_chosen = None
    best_val = -1.0
    for s_i in seeds:
        s_i = int(s_i)
        prefix = _bfs_prefix(adj, s_i, 6)
        if len(prefix) < 5:
            continue
        val = float(np.sum(r[prefix]))
        if val > best_val:
            best_val = val
            best_chosen = prefix

    if best_chosen is None:
        d2 = np.sum((c - c[0]) ** 2, axis=1)
        chosen = list(np.argsort(d2)[:5])
    else:
        chosen = list(best_chosen)

    remove = list(chosen)
    centroid = c[remove].mean(axis=0)

    best_local = None
    best_local_s = -1.0

    for _ in range(n_restarts):
        new_c = c.copy()
        new_r = r.copy()
        # structured hexagon placement around centroid
        rot = rng.uniform(0.0, 2.0 * np.pi)
        scale = rng.uniform(0.04, 0.10)
        k = len(remove)
        for m, idx in enumerate(remove):
            ang = rot + 2.0 * np.pi * m / k
            pt = centroid + scale * np.array([np.cos(ang), np.sin(ang)])
            pt = pt + rng.normal(0.0, 0.005, size=2)
            new_c[idx] = pt
        new_c[:, 0] = np.clip(new_c[:, 0], 0.002, 0.998)
        new_c[:, 1] = np.clip(new_c[:, 1], 0.002, 0.998)
        rr = _lp_radii(new_c, n)
        if rr is None:
            continue
        new_r = np.maximum(rr, 1e-6)
        new_c, new_r = _clean(new_c, new_r, n)
        c2, r2 = _run_slsqp(new_c, new_r, n, maxiter=400)
        c2, r2 = _clean(c2, r2, n)
        s2 = _score(c2, r2)
        if s2 > best_local_s:
            best_local_s = s2
            best_local = (c2, r2)

    return best_local


def construct(budget_seconds, start):
    t_start = time.process_time()
    n = 26
    rng = np.random.default_rng(987654321)

    best_c = None
    best_r = None
    best_s = -1.0

    if start is not None:
        s_arr = np.asarray(start, dtype=float)
        c0 = s_arr[:, :2].copy()
        r0 = s_arr[:, 2].copy()
        c, r = _run_slsqp(c0, r0, n, maxiter=2000, ftol=1e-15)
        c, r = _clean(c, r, n)
        s = _score(c, r)
        if s > best_s:
            best_s = s
            best_c = c.copy()
            best_r = r.copy()

    if best_c is None:
        best_c, best_r = _init_rows([5, 5, 5, 5, 6], n)
        best_c, best_r = _clean(best_c, best_r, n)
        best_s = _score(best_c, best_r)

    deadline = budget_seconds - 1.0
    tries = 0
    while time.process_time() - t_start < deadline:
        res = _cycle_perturb(best_c, best_r, n, rng, n_restarts=8)
        tries += 1
        if res is not None:
            c2, r2 = res
            s2 = _score(c2, r2)
            if s2 > best_s:
                best_s = s2
                best_c = c2.copy()
                best_r = r2.copy()
        if tries > 500:
            break

    best_r = best_r - 1e-9
    best_r = np.maximum(best_r, 1e-9)
    best_c, best_r = _clean(best_c, best_r, n)
    best_r = np.maximum(best_r - 1e-12, 1e-9)

    out = np.column_stack([best_c, best_r])
    return out
