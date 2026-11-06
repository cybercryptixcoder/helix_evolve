import numpy as np
import time
from scipy.optimize import minimize

def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90
    n = 32

    if start is not None:
        X = np.array(start, dtype=float).copy()
    else:
        X = np.zeros((n, 3))
        k = 6
        pts = []
        for j in range(k):
            for i in range(k):
                x = (i + 0.5 + (0.5 if j % 2 else 0.0)) / (k + 0.5)
                y = (j + 0.5) / k
                pts.append((x, y))
        for idx, (x, y) in enumerate(pts[:n]):
            X[idx] = [x, y, 0.02]

    X[:, 2] = np.maximum(X[:, 2], 1e-4)

    def repair(Xin, safety=1e-9):
        Xc = Xin.copy()
        x, y, r = Xc[:, 0], Xc[:, 1], Xc[:, 2]
        r = np.minimum(r, np.minimum(x, 1 - x))
        r = np.minimum(r, np.minimum(y, 1 - y)) - safety
        r = np.maximum(r, 1e-8)
        for _ in range(300):
            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            dist = np.sqrt(dx * dx + dy * dy)
            np.fill_diagonal(dist, np.inf)
            s = r[:, None] + r[None, :]
            over = np.maximum(s - dist + safety, 0.0)
            np.fill_diagonal(over, 0.0)
            if over.max() < 1e-15:
                break
            shrink = over.sum(axis=1) * 0.55
            r = np.maximum(r - shrink, 1e-8)
            r = np.minimum(r, np.minimum(x, 1 - x) - safety)
            r = np.minimum(r, np.minimum(y, 1 - y) - safety)
            r = np.maximum(r, 1e-8)
        Xc[:, 2] = r
        return Xc

    X = repair(X, safety=1e-7)
    best = X.copy()
    best_score = X[:, 2].sum()

    def obj(v):
        return -np.sum(v[2::3])

    def obj_jac(v):
        g = np.zeros_like(v)
        g[2::3] = -1.0
        return g

    iu, ju = np.triu_indices(n, 1)
    m = len(iu)

    bnds = []
    for _ in range(n):
        bnds.append((0.0, 1.0))
        bnds.append((0.0, 1.0))
        bnds.append((1e-8, 0.5))

    def cons_fun(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        dx = x[iu] - x[ju]
        dy = y[iu] - y[ju]
        dist = np.sqrt(dx * dx + dy * dy)
        c = np.empty(4 * n + m)
        c[0:n] = x - r
        c[n:2*n] = 1 - x - r
        c[2*n:3*n] = y - r
        c[3*n:4*n] = 1 - y - r
        c[4*n:] = dist - (r[iu] + r[ju])
        return c

    def cons_jac(v):
        x = v[0::3]; y = v[1::3]; r = v[2::3]
        J = np.zeros((4 * n + m, 3 * n))
        for i in range(n):
            J[i, 3*i] = 1.0
            J[i, 3*i+2] = -1.0
            J[n+i, 3*i] = -1.0
            J[n+i, 3*i+2] = -1.0
            J[2*n+i, 3*i+1] = 1.0
            J[2*n+i, 3*i+2] = -1.0
            J[3*n+i, 3*i+1] = -1.0
            J[3*n+i, 3*i+2] = -1.0
        dx = x[iu] - x[ju]
        dy = y[iu] - y[ju]
        dist = np.sqrt(dx * dx + dy * dy) + 1e-30
        rows = 4 * n + np.arange(m)
        for k in range(m):
            i = iu[k]; j = ju[k]
            row = rows[k]
            J[row, 3*i] = dx[k] / dist[k]
            J[row, 3*j] = -dx[k] / dist[k]
            J[row, 3*i+1] = dy[k] / dist[k]
            J[row, 3*j+1] = -dy[k] / dist[k]
            J[row, 3*i+2] = -1.0
            J[row, 3*j+2] = -1.0
        return J

    def to_vec(Xc):
        v = np.empty(3 * n)
        v[0::3] = Xc[:, 0]
        v[1::3] = Xc[:, 1]
        v[2::3] = Xc[:, 2]
        return v

    def from_vec(v):
        Xc = np.zeros((n, 3))
        Xc[:, 0] = v[0::3]
        Xc[:, 1] = v[1::3]
        Xc[:, 2] = v[2::3]
        return Xc

    state = {'best': best, 'best_score': best_score}

    def polish(Xcur, maxiter):
        Xsafe = repair(Xcur, safety=1e-7)
        v0 = to_vec(Xsafe)
        try:
            res = minimize(obj, v0, jac=obj_jac, method='SLSQP', bounds=bnds,
                           constraints={'type': 'ineq', 'fun': cons_fun, 'jac': cons_jac},
                           options={'maxiter': maxiter, 'ftol': 1e-16})
            Xc = repair(from_vec(res.x), safety=1e-9)
            sc = Xc[:, 2].sum()
            if sc > state['best_score'] + 1e-12:
                state['best_score'] = sc
                state['best'] = Xc.copy()
                return True
        except Exception:
            pass
        return False

    polish(X, 800)

    rng = np.random.default_rng(int(time.process_time() * 1e6) & 0xFFFFFFFF)
    step = 0.02
    last_score = state['best_score']
    stall = 0

    while time.process_time() < deadline:
        cand = state['best'].copy()
        u = rng.random()
        if u < 0.02:
            cand[:, 0] = rng.random(n)
            cand[:, 1] = rng.random(n)
            cand[:, 2] = 0.03
        elif u < 0.08:
            idxs = rng.choice(n, size=int(rng.integers(2, 6)), replace=False)
            cand[idxs, 2] *= rng.uniform(0.6, 0.95)
        else:
            mm = int(rng.integers(2, 10))
            idxs = rng.choice(n, size=mm, replace=False)
            for i in idxs:
                cand[i, 0] += rng.normal(0, step)
                cand[i, 1] += rng.normal(0, step)
                cand[i, 0] = np.clip(cand[i, 0], 0.0, 1.0)
                cand[i, 1] = np.clip(cand[i, 1], 0.0, 1.0)
        cand = repair(cand, safety=1e-7)
        remaining = deadline - time.process_time()
        if remaining < 0.3:
            break
        polish(cand, 300)
        if state['best_score'] > last_score + 1e-10:
            last_score = state['best_score']
            stall = 0
            step = min(step * 1.15, 0.06)
        else:
            stall += 1
            step = max(step * 0.93, 0.002)
            if stall > 15:
                cand = state['best'].copy()
                idxs = rng.choice(n, size=6, replace=False)
                for i in idxs:
                    cand[i, 0] = np.clip(cand[i, 0] + rng.normal(0, 0.05), 0, 1)
                    cand[i, 1] = np.clip(cand[i, 1] + rng.normal(0, 0.05), 0, 1)
                cand = repair(cand, safety=1e-7)
                polish(cand, 400)
                stall = 0

    remaining = (t0 + budget_seconds * 0.95) - time.process_time()
    if remaining > 0.4:
        polish(state['best'], 3000)

    best = repair(state['best'], safety=1e-7)
    best[:, 2] *= (1 - 1e-9)
    best = repair(best, safety=1e-8)
    return best
