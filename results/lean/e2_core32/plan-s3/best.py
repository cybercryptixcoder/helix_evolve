import numpy as np
import math
import time
from scipy.optimize import minimize, linprog


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85
    N = 32
    rng = np.random.default_rng(20240611)

    iu = np.triu_indices(N, 1)
    iu0 = iu[0]; iu1 = iu[1]
    m = len(iu0)

    def lp_radii(centers):
        x = centers[:, 0]; y = centers[:, 1]
        A = np.zeros((m + N, N)); b = np.zeros(m + N)
        A[np.arange(m), iu0] = 1.0
        A[np.arange(m), iu1] = 1.0
        dx = x[iu0] - x[iu1]; dy = y[iu0] - y[iu1]
        b[:m] = np.sqrt(dx * dx + dy * dy)
        w = np.minimum(np.minimum(x, 1.0 - x), np.minimum(y, 1.0 - y))
        A[m + np.arange(N), np.arange(N)] = 1.0
        b[m:] = np.maximum(w, 0.0)
        try:
            res = linprog(-np.ones(N), A_ub=A, b_ub=b,
                          bounds=[(0.0, None)] * N, method='highs')
            if not res.success:
                return None
            return res.x
        except Exception:
            return None

    def shrink(centers, radii):
        r = radii.copy()
        r = np.minimum(r, np.minimum(centers[:, 0], 1.0 - centers[:, 0]))
        r = np.minimum(r, np.minimum(centers[:, 1], 1.0 - centers[:, 1]))
        for _ in range(300):
            d = centers[:, None, :] - centers[None, :, :]
            dist = np.sqrt((d ** 2).sum(-1))
            s = r[:, None] + r[None, :]
            viol = s[iu] - dist[iu]
            if viol.max() <= -1e-12:
                break
            for k in np.where(viol > 0)[0]:
                i, j = iu0[k], iu1[k]
                ex = s[i, j] - dist[i, j]
                tot = r[i] + r[j]
                if tot > 0:
                    r[i] = max(1e-12, r[i] - 0.5 * ex * r[i] / tot - 1e-16)
                    r[j] = max(1e-12, r[j] - 0.5 * ex * r[j] / tot - 1e-16)
        return np.maximum(r, 1e-12)

    def unpack(z):
        return z[:2 * N].reshape(N, 2), z[2 * N:]

    def obj(z):
        return -z[2 * N:].sum()

    def obj_g(z):
        g = np.zeros_like(z); g[2 * N:] = -1.0
        return g

    def cons_f(z):
        c, r = unpack(z)
        d = c[:, None, :] - c[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1) + 1e-30)
        s = r[:, None] + r[None, :]
        out = np.empty(4 * N + m)
        out[:N] = c[:, 0] - r
        out[N:2 * N] = 1.0 - c[:, 0] - r
        out[2 * N:3 * N] = c[:, 1] - r
        out[3 * N:4 * N] = 1.0 - c[:, 1] - r
        out[4 * N:] = dist[iu] - s[iu]
        return out

    def cons_j(z):
        c, r = unpack(z)
        d = c[:, None, :] - c[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1) + 1e-30)
        np.fill_diagonal(dist, 1.0)
        J = np.zeros((4 * N + m, 3 * N))
        idx = np.arange(N)
        J[idx, 2 * idx] = 1.0; J[idx, 2 * N + idx] = -1.0
        J[N + idx, 2 * idx] = -1.0; J[N + idx, 2 * N + idx] = -1.0
        J[2 * N + idx, 2 * idx + 1] = 1.0; J[2 * N + idx, 2 * N + idx] = -1.0
        J[3 * N + idx, 2 * idx + 1] = -1.0; J[3 * N + idx, 2 * N + idx] = -1.0
        dx = c[iu0, 0] - c[iu1, 0]
        dy = c[iu0, 1] - c[iu1, 1]
        dd = dist[iu0, iu1]
        rows = 4 * N + np.arange(m)
        J[rows, 2 * iu0] = dx / dd
        J[rows, 2 * iu0 + 1] = dy / dd
        J[rows, 2 * iu1] = -dx / dd
        J[rows, 2 * iu1 + 1] = -dy / dd
        J[rows, 2 * N + iu0] = -1.0
        J[rows, 2 * N + iu1] = -1.0
        return J

    bounds = [(0.0, 1.0), (0.0, 1.0)] * N + [(1e-9, 0.5)] * N

    def to_z(c, r):
        z = np.empty(3 * N); z[:2 * N] = c.ravel(); z[2 * N:] = r
        return z

    def slsqp_refine(c, r, maxiter=400, ftol=1e-14):
        try:
            z0 = to_z(c, r)
            res = minimize(obj, z0, jac=obj_g, method='SLSQP', bounds=bounds,
                           constraints=[{'type': 'ineq', 'fun': cons_f, 'jac': cons_j}],
                           options={'maxiter': maxiter, 'ftol': ftol})
            c2, r2 = unpack(res.x)
            c2 = np.clip(c2, 0.0, 1.0)
            r2 = shrink(c2, r2)
            return c2, r2
        except Exception:
            return c, r

    def evaluate(c, r):
        r = shrink(c, r)
        rlp = lp_radii(c)
        if rlp is not None and rlp.sum() > r.sum():
            r = shrink(c, rlp)
        return c, r, r.sum()

    best_c = None; best_r = None; best_score = -1.0
    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.shape == (N, 3):
            c, r, sc = evaluate(s[:, :2].copy(), s[:, 2].copy())
            best_c, best_r, best_score = c, r, sc

    if best_c is None:
        rows = [6, 5, 6, 5, 6, 4]
        r0 = 1.0 / 12.0
        dy = math.sqrt(3.0) * r0
        pts = []
        for i, cnt in enumerate(rows):
            y = r0 + i * dy
            x0 = r0 if i % 2 == 0 else 2.0 * r0
            for k in range(cnt):
                pts.append((x0 + k * 2.0 * r0, y))
        c = np.array(pts)
        r = np.full(N, r0)
        c, r, sc = evaluate(c, r)
        best_c, best_r, best_score = c, r, sc

    # ---------- moves ----------
    def contact_pairs(c, r, tol=1e-7):
        d = c[:, None, :] - c[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1))
        s = r[:, None] + r[None, :]
        gap = np.abs(dist - s)
        pairs = []
        for k in range(m):
            i, j = iu0[k], iu1[k]
            if gap[i, j] < tol:
                pairs.append((i, j))
        return pairs

    def wall_contacts(c, r, tol=1e-7):
        out = []
        for k in range(N):
            x, y = c[k]
            if abs(x - r[k]) < tol: out.append((k, 0))
            if abs(1.0 - x - r[k]) < tol: out.append((k, 1))
            if abs(y - r[k]) < tol: out.append((k, 2))
            if abs(1.0 - y - r[k]) < tol: out.append((k, 3))
        return out

    def move_rotate_pair(c, r):
        c2 = c.copy()
        pairs = contact_pairs(c, r)
        if not pairs:
            return None
        i, j = pairs[rng.integers(len(pairs))]
        theta = math.radians(rng.uniform(5.0, 60.0) * (1 if rng.random() < 0.5 else -1))
        mid = 0.5 * (c2[i] + c2[j])
        ct, st = math.cos(theta), math.sin(theta)
        for k in (i, j):
            v = c2[k] - mid
            c2[k] = mid + np.array([ct * v[0] - st * v[1], st * v[0] + ct * v[1]])
        return np.clip(c2, 0.0, 1.0)

    def move_slide_wall(c, r):
        c2 = c.copy()
        wc = wall_contacts(c, r)
        if not wc:
            return None
        k, w = wc[rng.integers(len(wc))]
        delta = rng.uniform(0.01, 0.06) * (1 if rng.random() < 0.5 else -1)
        if w in (0, 1):
            c2[k, 1] += delta
        else:
            c2[k, 0] += delta
        return np.clip(c2, 0.0, 1.0)

    def move_swap(c, r):
        c2 = c.copy()
        i, j = rng.choice(N, 2, replace=False)
        c2[i], c2[j] = c2[j].copy(), c2[i].copy()
        return c2

    def move_jitter_group(c, r):
        c2 = c.copy()
        # jitter a cluster of nearby circles
        k0 = rng.integers(N)
        d = ((c - c[k0]) ** 2).sum(1)
        near = np.argsort(d)[:rng.integers(3, 8)]
        sigma = rng.uniform(0.01, 0.05)
        c2[near] += rng.normal(0.0, sigma, size=(len(near), 2))
        return np.clip(c2, 0.0, 1.0)

    def move_shake(c, r):
        sigma = rng.uniform(0.02, 0.12)
        c2 = c + rng.normal(0.0, sigma, size=(N, 2))
        return np.clip(c2, 0.0, 1.0)

    moves = [move_rotate_pair, move_slide_wall, move_swap, move_jitter_group, move_shake]

    def try_move(c0):
        if c0 is None:
            return
        rlp = lp_radii(c0)
        if rlp is None:
            return
        r0 = shrink(c0, rlp)
        c1, r1 = slsqp_refine(c0, r0, maxiter=300, ftol=1e-13)
        c1, r1, sc1 = evaluate(c1, r1)
        if sc1 > best_score + 1e-12:
            c2, r2 = slsqp_refine(c1, r1, maxiter=600, ftol=1e-15)
            c2, r2, sc2 = evaluate(c2, r2)
            if sc2 > sc1:
                c1, r1, sc1 = c2, r2, sc2
            if sc1 > best_score + 1e-12:
                nonlocal_best[0] = (c1, r1, sc1)
                return True
        return False

    nonlocal_best = [(best_c, best_r, best_score)]

    it = 0
    stall = 0
    while time.process_time() < deadline:
        it += 1
        stall += 1
        # alternate between structured moves and random perturbation
        if stall < 15:
            mv = moves[it % len(moves)]
        else:
            mv = move_shake
        c0 = mv(best_c, best_r)
        if c0 is None:
            continue
        rlp = lp_radii(c0)
        if rlp is None:
            continue
        r0 = shrink(c0, rlp)
        c1, r1 = slsqp_refine(c0, r0, maxiter=300, ftol=1e-13)
        c1, r1, sc1 = evaluate(c1, r1)
        if sc1 > best_score + 1e-12:
            c2, r2 = slsqp_refine(c1, r1, maxiter=600, ftol=1e-15)
            c2, r2, sc2 = evaluate(c2, r2)
            if sc2 > sc1:
                c1, r1, sc1 = c2, r2, sc2
            if sc1 > best_score + 1e-12:
                best_c, best_r, best_score = c1, r1, sc1
                stall = 0

    # final polish
    for _ in range(4):
        c, r = slsqp_refine(best_c, best_r, maxiter=1000, ftol=1e-16)
        c, r, sc = evaluate(c, r)
        if sc > best_score:
            best_c, best_r, best_score = c, r, sc

    c = best_c.copy()
    r = best_r.copy()
    r = shrink(c, r)
    r = np.maximum(r, 1e-9)
    out = np.column_stack([c, r])
    for _ in range(80):
        out[:, 2] *= (1.0 - 1e-11)
        cc = out[:, :2]; rr = out[:, 2]
        ok = True
        if np.any(rr <= 0): ok = False
        if np.any(cc[:, 0] - rr < 0) or np.any(cc[:, 0] + rr > 1): ok = False
        if np.any(cc[:, 1] - rr < 0) or np.any(cc[:, 1] + rr > 1): ok = False
        d = cc[:, None, :] - cc[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1))
        s = rr[:, None] + rr[None, :]
        if np.any(dist[iu] < s[iu]): ok = False
        if ok:
            break
    out[:, 2] = np.maximum(out[:, 2], 1e-9)
    return out
