import numpy as np
import time
from scipy.optimize import linprog
from scipy.sparse import csr_matrix


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    rng = np.random.default_rng(int(time.time() * 1e9) % (2**31))

    ii, jj = np.triu_indices(n, 1)
    ii = ii.astype(np.int64); jj = jj.astype(np.int64)
    npair = len(ii)
    m = npair + n

    rows = np.concatenate([np.arange(npair), np.arange(npair),
                           npair + np.arange(n)])
    cols = np.concatenate([ii, jj, np.arange(n)])
    vals = np.ones(len(rows))
    A = csr_matrix((vals, (rows, cols)), shape=(m, n))
    c = -np.ones(n)
    bounds = [(0, None)] * n

    def solve_radii(x, y):
        wall = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
        wall = np.maximum(wall, 1e-9)
        b = np.empty(m)
        b[:npair] = np.hypot(x[ii] - x[jj], y[ii] - y[jj])
        b[npair:] = wall
        res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method='highs')
        if not res.success:
            return wall
        return np.maximum(res.x, 0.0)

    if start is not None:
        P = np.array(start, dtype=float)
        x = P[:, 0].copy(); y = P[:, 1].copy()
    else:
        x = np.zeros(n); y = np.zeros(n)
        k = 6; idx = 0
        for j in range(k):
            for i in range(k):
                if idx >= n: break
                x[idx] = (i + 0.5 + 0.5 * (j % 2)) / (k + 0.4)
                y[idx] = (j + 0.5) / (k + 0.4)
                idx += 1

    r = solve_radii(x, y)
    bx, by, br = x.copy(), y.copy(), r.copy()
    bs = r.sum()

    def relax(x, y, r, iters, step):
        x = x.copy(); y = y.copy()
        for _ in range(iters):
            dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
            d = np.sqrt(dx * dx + dy * dy) + 1e-12
            s = r[ii] + r[jj]
            ov = np.maximum(0.0, s - d)
            push = ov / d * 0.5
            fx = np.zeros(n); fy = np.zeros(n)
            np.add.at(fx, ii, dx * push)
            np.add.at(fx, jj, -dx * push)
            np.add.at(fy, ii, dy * push)
            np.add.at(fy, jj, -dy * push)
            fx += np.where(x - r < 0, (r - x), 0.0)
            fx -= np.where(x + r > 1, (x + r - 1), 0.0)
            fy += np.where(y - r < 0, (r - y), 0.0)
            fy -= np.where(y + r > 1, (y + r - 1), 0.0)
            x += step * fx
            y += step * fy
            x = np.clip(x, r, 1 - r)
            y = np.clip(y, r, 1 - r)
        return x, y

    def tightness(x, y, r):
        dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
        d = np.sqrt(dx * dx + dy * dy)
        slack = d - r[ii] - r[jj]
        s = np.full(n, np.inf)
        np.minimum.at(s, ii, slack)
        np.minimum.at(s, jj, slack)
        wall = np.minimum(np.minimum(x - r, 1 - x - r),
                          np.minimum(y - r, 1 - y - r))
        return np.minimum(s, wall)

    # ---------- Phase 1: SA on centers via relax ----------
    deadline1 = t0 + budget_seconds * 0.12
    temp = 0.004
    while time.process_time() < deadline1:
        target = r * (1.0 + rng.uniform(0.002, 0.02))
        xx, yy = relax(x, y, target, iters=30, step=0.35)
        rr = solve_radii(xx, yy)
        s = rr.sum()
        if s > r.sum() - 1e-9 or rng.random() < np.exp((s - r.sum()) / max(temp, 1e-6)):
            x, y, r = xx, yy, rr
            if s > bs:
                bs = s; bx, by, br = xx.copy(), yy.copy(), rr.copy()
        temp = max(temp * 0.999, 5e-5)

    # ---------- Phase 2: single-circle LP polish ----------
    x, y, r = bx.copy(), by.copy(), br.copy()
    cur_sum = r.sum()
    deadline2 = t0 + budget_seconds * 0.40
    improved = True
    while improved and time.process_time() < deadline2:
        improved = False
        slack = tightness(x, y, r)
        order = np.argsort(-slack)
        for i in order:
            if time.process_time() > deadline2:
                break
            step = 0.004 + 0.30 * r[i]
            best_s = cur_sum
            best_xy = (x[i], y[i])
            for _ in range(5):
                nx = min(max(x[i] + rng.normal(0, step), 0.005), 0.995)
                ny = min(max(y[i] + rng.normal(0, step), 0.005), 0.995)
                xt = x.copy(); yt = y.copy()
                xt[i] = nx; yt[i] = ny
                rt = solve_radii(xt, yt)
                s = rt.sum()
                if s > best_s + 1e-11:
                    best_s = s; best_xy = (nx, ny)
            if best_s > cur_sum + 1e-11:
                x[i], y[i] = best_xy
                r = solve_radii(x, y)
                cur_sum = r.sum()
                if cur_sum > bs:
                    bs = cur_sum; bx, by, br = x.copy(), y.copy(), r.copy()
                improved = True

    # ---------- Phase 3: pairwise LP polish ----------
    x, y, r = bx.copy(), by.copy(), br.copy()
    cur_sum = r.sum()
    deadline3 = t0 + budget_seconds * 0.62
    improved = True
    while improved and time.process_time() < deadline3:
        improved = False
        order = rng.permutation(n)
        for oi in range(0, n - 1, 2):
            if time.process_time() > deadline3:
                break
            a = order[oi]; b = order[oi + 1]
            best_s = cur_sum
            best = (x[a], y[a], x[b], y[b])
            base_step = 0.3 * (r[a] + r[b]) + 0.005
            for _ in range(6):
                ax = min(max(x[a] + rng.normal(0, base_step), 0.005), 0.995)
                ay = min(max(y[a] + rng.normal(0, base_step), 0.005), 0.995)
                bxp = min(max(x[b] + rng.normal(0, base_step), 0.005), 0.995)
                byp = min(max(y[b] + rng.normal(0, base_step), 0.005), 0.995)
                xt = x.copy(); yt = y.copy()
                xt[a] = ax; yt[a] = ay; xt[b] = bxp; yt[b] = byp
                rt = solve_radii(xt, yt)
                s = rt.sum()
                if s > best_s + 1e-11:
                    best_s = s; best = (ax, ay, bxp, byp)
            if best_s > cur_sum + 1e-11:
                x[a], y[a], x[b], y[b] = best
                r = solve_radii(x, y)
                cur_sum = r.sum()
                if cur_sum > bs:
                    bs = cur_sum; bx, by, br = x.copy(), y.copy(), r.copy()
                improved = True

    # ---------- Phase 4: grow-relax SA polish ----------
    x, y, r = bx.copy(), by.copy(), br.copy()
    deadline4 = t0 + budget_seconds * 0.85
    temp = 0.002
    while time.process_time() < deadline4:
        target = r * (1.0 + rng.uniform(0.001, 0.012))
        xx, yy = relax(x, y, target, iters=40, step=0.30)
        rr = solve_radii(xx, yy)
        s = rr.sum()
        if s > r.sum() - 1e-9 or rng.random() < np.exp((s - r.sum()) / max(temp, 1e-6)):
            x, y, r = xx, yy, rr
            if s > bs:
                bs = s; bx, by, br = xx.copy(), yy.copy(), rr.copy()
        temp = max(temp * 0.998, 2e-5)

    # ---------- Phase 5: fine random perturbation polish (pair moves prioritized) ----------
    x, y, r = bx.copy(), by.copy(), br.copy()
    cur_sum = r.sum()
    deadline5 = t0 + budget_seconds * 0.97
    scale = 0.004
    while time.process_time() < deadline5:
        if rng.random() < 0.5:
            k = int(rng.integers(n))
            xt = x.copy(); yt = y.copy()
            xt[k] = min(max(xt[k] + rng.normal(0, scale), 0.005), 0.995)
            yt[k] = min(max(yt[k] + rng.normal(0, scale), 0.005), 0.995)
            if rng.random() < 0.5:
                j = int(rng.integers(n))
                if j != k:
                    xt[j] = min(max(xt[j] + rng.normal(0, scale), 0.005), 0.995)
                    yt[j] = min(max(yt[j] + rng.normal(0, scale), 0.005), 0.995)
        else:
            # move two touching/close circles together along their axis
            slack = tightness(x, y, r)
            order = np.argsort(slack)
            k = int(order[rng.integers(min(6, n))])
            j = int(order[rng.integers(min(10, n))])
            if j == k:
                j = int(rng.integers(n))
            xt = x.copy(); yt = y.copy()
            nxs = rng.normal(0, scale, 4)
            xt[k] = min(max(xt[k] + nxs[0], 0.005), 0.995)
            yt[k] = min(max(yt[k] + nxs[1], 0.005), 0.995)
            xt[j] = min(max(xt[j] + nxs[2], 0.005), 0.995)
            yt[j] = min(max(yt[j] + nxs[3], 0.005), 0.995)
        rt = solve_radii(xt, yt)
        s = rt.sum()
        if s > cur_sum + 1e-13:
            x, y, r = xt, yt, rt
            cur_sum = s
            if s > bs:
                bs = s; bx, by, br = xt.copy(), yt.copy(), rt.copy()
            scale = max(scale * 0.995, 3e-5)
        else:
            scale = min(scale * 1.004, 0.008)

    x, y, r = bx, by, br
    r = solve_radii(x, y)

    # ---------- strict safety ----------
    margin = 1e-9
    r = np.minimum(r, np.minimum(x, 1 - x) - margin)
    r = np.minimum(r, np.minimum(y, 1 - y) - margin)
    r = np.maximum(r, 1e-9)
    for _ in range(300):
        dx = x[ii] - x[jj]; dy = y[ii] - y[jj]
        d = np.sqrt(dx * dx + dy * dy)
        over = r[ii] + r[jj] + margin - d
        if over.max() <= 0:
            break
        for k in np.where(over > 0)[0]:
            a = ii[k]; b = jj[k]
            o = over[k]
            r[a] = max(1e-10, r[a] - o * 0.5 - 1e-13)
            r[b] = max(1e-10, r[b] - o * 0.5 - 1e-13)
        r = np.minimum(r, np.minimum(x, 1 - x) - margin)
        r = np.minimum(r, np.minimum(y, 1 - y) - margin)
        r = np.maximum(r, 1e-9)

    return np.column_stack([x, y, r])
