import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    deadline = t0 + budget_seconds * 0.85
    iu = np.triu_indices(n, 1)
    i0, i1 = iu[0], iu[1]
    m_pair = len(i0)
    idx_all = np.arange(n)

    def cons(v):
        xy = v[:2 * n].reshape(n, 2)
        r = v[2 * n:]
        x, y = xy[:, 0], xy[:, 1]
        dx = x[i0] - x[i1]
        dy = y[i0] - y[i1]
        d = np.sqrt(dx * dx + dy * dy + 1e-30)
        return np.concatenate([x - r, 1.0 - x - r, y - r, 1.0 - y - r,
                               d - r[i0] - r[i1]])

    def jac(v):
        xy = v[:2 * n].reshape(n, 2)
        m = 4 * n + m_pair
        J = np.zeros((m, 3 * n))
        i = idx_all
        J[i, 2 * i] = 1.0; J[i, 2 * n + i] = -1.0
        J[n + i, 2 * i] = -1.0; J[n + i, 2 * n + i] = -1.0
        J[2 * n + i, 2 * i + 1] = 1.0; J[2 * n + i, 2 * n + i] = -1.0
        J[3 * n + i, 2 * i + 1] = -1.0; J[3 * n + i, 2 * n + i] = -1.0
        dx = xy[i0, 0] - xy[i1, 0]
        dy = xy[i0, 1] - xy[i1, 1]
        d = np.sqrt(dx * dx + dy * dy + 1e-30)
        row = 4 * n + np.arange(m_pair)
        ux = dx / d; uy = dy / d
        J[row, 2 * i0] = ux; J[row, 2 * i0 + 1] = uy
        J[row, 2 * i1] = -ux; J[row, 2 * i1 + 1] = -uy
        J[row, 2 * n + i0] = -1.0; J[row, 2 * n + i1] = -1.0
        return J

    def mincons(xy, r):
        x, y = xy[:, 0], xy[:, 1]
        m = min(np.min(x - r), np.min(1 - x - r),
                np.min(y - r), np.min(1 - y - r))
        dx = x[i0] - x[i1]; dy = y[i0] - y[i1]
        d = np.sqrt(dx * dx + dy * dy)
        return min(m, np.min(d - r[i0] - r[i1]))

    def feasible(xy, r, eps=1e-12):
        return mincons(xy, r) >= -eps

    best = None
    best_score = -1.0

    def consider(xy, r):
        nonlocal best, best_score
        xy = np.array(xy, dtype=float, copy=True)
        r = np.maximum(np.asarray(r, dtype=float), 1e-9)
        xy[:, 0] = np.clip(xy[:, 0], r, 1.0 - r)
        xy[:, 1] = np.clip(xy[:, 1], r, 1.0 - r)
        for _ in range(300):
            if feasible(xy, r, 1e-12):
                break
            r = np.maximum(r * (1.0 - 1e-5), 1e-8)
        else:
            return
        s = float(r.sum())
        if s > best_score:
            best_score = s
            best = np.column_stack([xy, r]).copy()

    def slsqp(xy, r, maxiter=400):
        v0 = np.concatenate([xy.ravel(), np.maximum(r, 1e-6)])
        try:
            res = minimize(
                lambda v: -np.sum(v[2 * n:]),
                v0,
                jac=lambda v: np.concatenate([np.zeros(2 * n), -np.ones(n)]),
                method="SLSQP",
                constraints=[{"type": "ineq", "fun": cons, "jac": jac}],
                options={"maxiter": maxiter, "ftol": 1e-15},
            )
            if res.x is not None:
                consider(res.x[:2 * n].reshape(n, 2), res.x[2 * n:])
                return True
        except Exception:
            pass
        return False

    rng = np.random.default_rng(int(t0 * 1000) & 0xFFFFFF)

    if start is not None:
        s = np.asarray(start, dtype=float)
        consider(s[:, :2].copy(), s[:, 2].copy())
        if time.process_time() < deadline:
            slsqp(s[:, :2].copy(), s[:, 2].copy(), maxiter=600)

    if best is None:
        for rows in [5, 6, 7]:
            if time.process_time() > deadline * 0.5:
                break
            cols = int(np.ceil(n / rows))
            pts = []
            for j in range(rows):
                for i in range(cols):
                    x = (i + 0.5 + 0.5 * (j % 2)) / (cols + 0.5)
                    y = (j + 0.5) / rows
                    pts.append([x, y])
            pts = np.array(pts)
            if len(pts) < n:
                continue
            sel = np.linspace(0, len(pts) - 1, n).astype(int)
            pts = pts[sel]
            lo, hi = 0.0, 0.5
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                if mincons(pts, np.full(n, mid)) >= 1e-12:
                    lo = mid
                else:
                    hi = mid
            slsqp(pts, np.full(n, max(lo * 0.9, 1e-3)), maxiter=500)

    def slack(xy, r):
        x, y = xy[:, 0], xy[:, 1]
        dx = x[i0] - x[i1]; dy = y[i0] - y[i1]
        d = np.sqrt(dx * dx + dy * dy + 1e-30)
        sl = d - r[i0] - r[i1]
        per = np.full(n, 1e9)
        np.minimum.at(per, i0, sl)
        np.minimum.at(per, i1, sl)
        np.minimum(per, x - r, out=per)
        np.minimum(per, 1.0 - x - r, out=per)
        np.minimum(per, y - r, out=per)
        np.minimum(per, 1.0 - y - r, out=per)
        return per

    # Population-based ILS: keep a small archive of diverse good solutions.
    archive = []
    if best is not None:
        archive.append(best.copy())

    stall = 0
    while best is not None and time.process_time() < deadline:
        stall += 1
        # pick from archive sometimes for diversity
        if len(archive) > 1 and rng.random() < 0.3:
            src = archive[int(rng.integers(0, len(archive)))]
        else:
            src = best
        xy = src[:, :2].copy()
        r = src[:, 2].copy()
        per = slack(xy, r)
        order = np.argsort(per)
        tight = order[:8]
        loose = order[-8:]
        mode = int(rng.integers(0, 8))

        if mode == 0:
            k = int(rng.integers(2, 5))
            idx = rng.choice(tight, size=min(k, len(tight)), replace=False)
            sigma = 0.005 * (1.0 + 0.25 * min(stall, 40))
            xy[idx] += rng.normal(0, sigma, size=(len(idx), 2))
        elif mode == 1:
            a = int(rng.choice(tight)); b = int(rng.choice(loose))
            tr = r[a] * rng.uniform(0.03, 0.10)
            r[a] += tr; r[b] = max(r[b] - tr * 0.9, 1e-3)
        elif mode == 2:
            a = int(rng.choice(tight)); b = int(rng.integers(0, n))
            if a != b:
                xy[[a, b]] = xy[[b, a]]
                r[[a, b]] = r[[b, a]]
        elif mode == 3:
            r *= rng.uniform(1.005, 1.02)
        elif mode == 4:
            k = int(rng.integers(1, 4))
            idx = np.argsort(r)[-k:]
            r[idx] *= rng.uniform(1.02, 1.05)
        elif mode == 5:
            k = int(rng.integers(3, 8))
            idx = rng.choice(n, size=k, replace=False)
            xy[idx] += rng.normal(0, 0.006, size=(k, 2))
            r[idx] *= rng.uniform(0.94, 1.06, size=k)
        elif mode == 6:
            xy += rng.normal(0, 0.004, size=(n, 2))
            r *= rng.uniform(0.97, 1.03, size=n)
        else:
            a = int(rng.integers(0, n))
            dx = xy[:, 0] - xy[a, 0]; dy = xy[:, 1] - xy[a, 1]
            d = np.sqrt(dx * dx + dy * dy)
            d[a] = 1e9
            b = int(np.argmin(d))
            tr = r[a] * rng.uniform(0.02, 0.06)
            r[a] = max(r[a] - tr, 1e-3); r[b] += tr

        if stall > 40 and stall % 10 == 0:
            r *= rng.uniform(0.82, 0.92)
            xy += rng.normal(0, 0.02, size=(n, 2))

        xy[:, 0] = np.clip(xy[:, 0], r, 1.0 - r)
        xy[:, 1] = np.clip(xy[:, 1], r, 1.0 - r)
        for _ in range(150):
            if feasible(xy, r, 1e-11):
                break
            r *= 0.985
        prev = best_score
        slsqp(xy, r, maxiter=350)
        if best_score > prev + 1e-10:
            stall = 0
        # Update archive: keep up to 4 diverse good solutions
        if best is not None and best_score > prev - 1e-6:
            archive.append(best.copy())
            if len(archive) > 4:
                # keep best plus a couple others; drop oldest
                archive.pop(0)

    if best is not None and time.process_time() < deadline:
        slsqp(best[:, :2].copy(), best[:, 2].copy(), maxiter=800)

    if best is None:
        k = 6
        pts = np.array([[(i + 0.5) / k, (j + 0.5) / k]
                        for j in range(k) for i in range(k)][:n])
        r = np.full(n, 0.03)
        for _ in range(500):
            if feasible(pts, r, 1e-11):
                break
            r *= 0.95
        best = np.column_stack([pts, r])

    xy = best[:, :2].copy()
    r = best[:, 2].copy()
    for _ in range(500):
        if feasible(xy, r, 1e-13):
            break
        r = r * (1.0 - 1e-7)
    r = np.maximum(r, 1e-9)
    while not feasible(xy, r, 1e-13):
        r *= 0.99999
    return np.column_stack([xy, r])
