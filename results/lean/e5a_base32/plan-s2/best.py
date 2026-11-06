import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    limit = budget_seconds * 0.80
    rng = np.random.default_rng(2024)

    # ---- helpers ----
    def unpack(v):
        v = np.asarray(v, dtype=float).reshape(-1)
        return v[:2 * n].reshape(n, 2).copy(), v[2 * n:3 * n].copy()

    def pack(xy, r):
        return np.concatenate([xy.reshape(-1), r])

    def pair_dist(xy):
        d = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)
        np.fill_diagonal(d, np.inf)
        return d

    def repair(xy, r):
        """Shrink radii to strict feasibility; clamp centers."""
        xy = xy.copy(); r = r.copy()
        for _ in range(300):
            changed = False
            wall = np.minimum(np.minimum(xy[:, 0], 1 - xy[:, 0]),
                              np.minimum(xy[:, 1], 1 - xy[:, 1]))
            over_wall = r - (wall - 1e-12)
            if np.any(over_wall > 0):
                r = np.minimum(r, np.maximum(wall - 1e-12, 1e-9))
                changed = True
            d = pair_dist(xy)
            over = (r[:, None] + r[None, :]) - d
            np.fill_diagonal(over, -np.inf)
            if np.any(over > 0):
                for i in range(n):
                    for j in range(i + 1, n):
                        if over[i, j] > 0:
                            s = over[i, j] * 0.5 + 1e-12
                            r[i] = max(r[i] - s, 1e-9)
                            r[j] = max(r[j] - s, 1e-9)
                            changed = True
            if not changed:
                break
        xy[:, 0] = np.clip(xy[:, 0], r, 1 - r)
        xy[:, 1] = np.clip(xy[:, 1], r, 1 - r)
        return xy, r

    def slsqp_opt(xy0, r0, maxiter=200):
        v0 = pack(xy0, r0)

        def obj(v):
            return -np.sum(v[2 * n:3 * n])

        def cons(v):
            x = v[0:2 * n:2]; y = v[1:2 * n:2]; r = v[2 * n:3 * n]
            c = [x - r, 1 - x - r, y - r, 1 - y - r]
            d2 = ((x[:, None] - x[None, :]) ** 2 +
                  (y[:, None] - y[None, :]) ** 2)
            np.fill_diagonal(d2, 1.0)
            rs = r[:, None] + r[None, :]
            iu = np.triu_indices(n, 1)
            c.append(d2[iu] - rs[iu] ** 2)
            return np.concatenate(c)

        try:
            res = minimize(obj, v0, method='SLSQP', constraints=[{'type': 'ineq', 'fun': cons}],
                           options={'maxiter': maxiter, 'ftol': 1e-14})
            xy, r = unpack(res.x)
            xy, r = repair(xy, r)
            return xy, r, r.sum()
        except Exception:
            return xy0, r0, r0.sum()

    def destroy_repair(xy, r, k=4):
        """Remove k low-contact circles, reinsert into largest gaps."""
        d = pair_dist(xy)
        rs = r[:, None] + r[None, :]
        contacts = (d <= rs + 1e-6).sum(axis=1)
        wall = np.minimum(np.minimum(xy[:, 0], 1 - xy[:, 0]),
                          np.minimum(xy[:, 1], 1 - xy[:, 1]))
        contacts += (wall <= r + 1e-6).astype(int)
        order = np.argsort(contacts)
        removed = list(order[:k])
        keep = [i for i in range(n) if i not in removed]

        g = np.linspace(0.01, 0.99, 50)
        gx, gy = np.meshgrid(g, g)
        cand = np.stack([gx.ravel(), gy.ravel()], axis=1)
        kxy = xy[keep]; kr = r[keep]
        dd = np.linalg.norm(cand[:, None, :] - kxy[None, :, :], axis=2) - kr[None, :]
        clear_c = dd.min(axis=1) if len(keep) > 0 else np.full(len(cand), 1.0)
        clear_w = np.minimum(np.minimum(cand[:, 0], 1 - cand[:, 0]),
                             np.minimum(cand[:, 1], 1 - cand[:, 1]))
        clear = np.minimum(clear_c, clear_w)
        idx = np.argsort(-clear)
        chosen = []
        for ii in idx:
            if clear[ii] <= 0:
                break
            p = cand[ii]
            if all(np.linalg.norm(p - cand[c]) > 0.08 for c in chosen):
                chosen.append(ii)
            if len(chosen) >= max(20, len(removed)):
                break
        if len(chosen) < len(removed):
            return None

        xy2 = xy.copy(); r2 = r.copy()
        for m, ri in enumerate(removed):
            ci = chosen[m]
            xy2[ri] = cand[ci]
            r2[ri] = max(0.45 * clear[ci], 1e-3)
        xy2, r2 = repair(xy2, r2)
        return xy2, r2

    def inflate_relax(xy0, r0, alpha):
        """Inflate radii, relax centers only via L-BFGS-B penalty, then reoptimize."""
        r2 = r0 * alpha
        x0 = xy0.reshape(-1).copy()

        def pen(x):
            xy = x.reshape(n, 2)
            xc = xy[:, 0]; yc = xy[:, 1]
            # pair overlaps
            dx = xc[:, None] - xc[None, :]
            dy = yc[:, None] - yc[None, :]
            d = np.sqrt(dx * dx + dy * dy)
            rs = r2[:, None] + r2[None, :]
            ov = np.maximum(0.0, rs - d)
            np.fill_diagonal(ov, 0.0)
            # walls
            wx = np.maximum(0.0, r2 - xc) + np.maximum(0.0, xc + r2 - 1.0)
            wy = np.maximum(0.0, r2 - yc) + np.maximum(0.0, yc + r2 - 1.0)
            return np.sum(ov * ov) + np.sum(wx * wx) + np.sum(wy * wy)

        try:
            res = minimize(pen, x0, method='L-BFGS-B',
                           bounds=[(0.0, 1.0)] * (2 * n),
                           options={'maxiter': 300})
            xy_new = res.x.reshape(n, 2).copy()
        except Exception:
            return None
        xy_new, r_new = repair(xy_new, r2)
        xy_new, r_new, sc = slsqp_opt(xy_new, r_new, maxiter=250)
        return xy_new, r_new, sc

    # ---- initial ----
    if start is not None:
        s = np.asarray(start, dtype=float)
        xy = s[:, :2].copy(); r = s[:, 2].copy()
        xy, r = repair(xy, r)
    else:
        k = 6
        pts = []
        for j in range(k):
            for i in range(k):
                x = (i + 0.5 + (0.5 if j % 2 else 0)) / k
                y = (j + 0.5) / k
                pts.append((x, y))
        pts = pts[:n]
        xy = np.array(pts)
        r = np.full(n, 0.03)
        xy, r = repair(xy, r)

    best_xy, best_r, best_score = slsqp_opt(xy, r, maxiter=300)

    # ---- restarts: jitter, destroy-repair, and inflation-relaxation ----
    tries = 0
    while time.process_time() - t0 < limit and tries < 200:
        tries += 1
        mode = tries % 3
        if mode == 0:
            dr = destroy_repair(best_xy, best_r, k=4)
            if dr is None:
                continue
            xy2, r2 = dr
            xy2, r2, sc = slsqp_opt(xy2, r2, maxiter=200)
            if sc > best_score:
                best_score, best_xy, best_r = sc, xy2, r2
        elif mode == 1:
            scale = 0.02 if tries < 20 else 0.04
            xy2 = best_xy + rng.normal(scale=scale, size=best_xy.shape)
            xy2[:, 0] = np.clip(xy2[:, 0], 0.001, 0.999)
            xy2[:, 1] = np.clip(xy2[:, 1], 0.001, 0.999)
            r2 = best_r * (0.95 + 0.1 * rng.random(n))
            xy2, r2 = repair(xy2, r2)
            xy2, r2, sc = slsqp_opt(xy2, r2, maxiter=150)
            if sc > best_score:
                best_score, best_xy, best_r = sc, xy2, r2
        else:
            alpha = rng.uniform(1.02, 1.10)
            out = inflate_relax(best_xy, best_r, alpha)
            if out is None:
                continue
            xy2, r2, sc = out
            if sc > best_score:
                best_score, best_xy, best_r = sc, xy2, r2

    # ---- final strict safety shrink ----
    xy = best_xy.copy(); r = best_r.copy()
    r = r - 1e-10
    r = np.maximum(r, 1e-9)
    xy[:, 0] = np.clip(xy[:, 0], r, 1 - r)
    xy[:, 1] = np.clip(xy[:, 1], r, 1 - r)
    for _ in range(50):
        d = pair_dist(xy)
        area = (r[:, None] + r[None, :]) - d
        np.fill_diagonal(area, -np.inf)
        mx = area.max()
        if mx <= 0:
            break
        r = r * (1 - 2e-10)
        r = np.maximum(r, 1e-9)

    out = np.empty((n, 3))
    out[:, :2] = xy
    out[:, 2] = r
    return out
