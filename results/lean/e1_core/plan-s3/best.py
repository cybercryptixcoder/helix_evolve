import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 26
    rng = np.random.default_rng(12345)

    # ---- setup ----
    if start is not None:
        z_start = np.asarray(start, dtype=float).flatten().copy()
    else:
        k = int(np.ceil(np.sqrt(n)))
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        z_start = np.array([[x, y, 0.02] for x, y in pts]).flatten()

    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    npairs = len(pairs)
    pi = np.array([p[0] for p in pairs])
    pj = np.array([p[1] for p in pairs])
    ar = np.arange(npairs)

    bounds = []
    for i in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-6, 1.0))

    def obj(z):
        return -np.sum(z[2::3])

    def obj_grad(z):
        g = np.zeros_like(z)
        g[2::3] = -1.0
        return g

    def all_constraints(z):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        wall = np.concatenate([x - r, 1.0 - x - r, y - r, 1.0 - y - r])
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]; sr = r[pi] + r[pj]
        pair = dx*dx + dy*dy - sr*sr
        return np.concatenate([wall, pair])

    def all_jac(z):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        Jw = np.zeros((4 * n, 3 * n))
        for i in range(n):
            Jw[i, 3*i] = 1.0; Jw[i, 3*i+2] = -1.0
            Jw[n+i, 3*i] = -1.0; Jw[n+i, 3*i+2] = -1.0
            Jw[2*n+i, 3*i+1] = 1.0; Jw[2*n+i, 3*i+2] = -1.0
            Jw[3*n+i, 3*i+1] = -1.0; Jw[3*n+i, 3*i+2] = -1.0
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]; sr = r[pi] + r[pj]
        Jp = np.zeros((npairs, 3 * n))
        np.add.at(Jp, (ar, 3*pi), 2*dx)
        np.add.at(Jp, (ar, 3*pj), -2*dx)
        np.add.at(Jp, (ar, 3*pi+1), 2*dy)
        np.add.at(Jp, (ar, 3*pj+1), -2*dy)
        np.add.at(Jp, (ar, 3*pi+2), -2*sr)
        np.add.at(Jp, (ar, 3*pj+2), -2*sr)
        return np.vstack([Jw, Jp])

    constraints = [{'type': 'ineq', 'fun': all_constraints, 'jac': all_jac}]

    def max_violation(z):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        v = 0.0
        v = max(v, float(np.max(r - x)))
        v = max(v, float(np.max(x + r - 1.0)))
        v = max(v, float(np.max(r - y)))
        v = max(v, float(np.max(y + r - 1.0)))
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]; sr = r[pi] + r[pj]
        d = np.sqrt(dx*dx + dy*dy)
        v = max(v, float(np.max(sr - d)))
        return v

    def score(z):
        return float(np.sum(z[2::3]))

    def run_slsqp(z_init, deadline, maxiter=500, ftol=1e-14):
        def cb(zz):
            return time.process_time() > deadline
        try:
            res = minimize(obj, z_init, jac=obj_grad, method='SLSQP',
                           bounds=bounds, constraints=constraints,
                           options={'ftol': ftol, 'maxiter': maxiter, 'disp': False},
                           callback=cb)
            return res.x if res.x is not None else z_init
        except Exception:
            return z_init

    def cd_inflate(z, rounds=8):
        z = z.copy()
        x = z[0::3].copy(); y = z[1::3].copy(); r = z[2::3].copy()
        for _ in range(rounds):
            improved = False
            for i in rng.permutation(n):
                wall_lim = min(x[i], 1.0 - x[i], y[i], 1.0 - y[i])
                dx = x[i] - x
                dy = y[i] - y
                d = np.sqrt(dx*dx + dy*dy)
                d[i] = np.inf
                pair_lim = np.min(d - r)
                lim = min(wall_lim, pair_lim) - 1e-11
                if lim > r[i] + 1e-12:
                    r[i] = lim
                    improved = True
            if not improved:
                break
        z[2::3] = r
        return z

    # ---- initial polish ----
    deadline0 = t0 + budget_seconds * 0.08
    best = np.asarray(run_slsqp(z_start, deadline0, 800), dtype=float)
    c = cd_inflate(best, 8)
    c = run_slsqp(c, deadline0, 500)
    if max_violation(c) <= 1e-9 and score(c) > score(best):
        best = c
    best_score = score(best)
    if max_violation(best) > 1e-7:
        best = z_start.copy()
        best_score = score(best)

    def consider(z):
        nonlocal best, best_score
        if max_violation(z) <= 1e-9:
            s = score(z)
            if s > best_score + 1e-12:
                best = z.copy()
                best_score = s
                return True
        return False

    # ---- soft penalty relaxation for exploration ----
    def soft_fg(z, lam):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]; sr = r[pi] + r[pj]
        d = np.sqrt(dx*dx + dy*dy)
        ov = sr - d
        mask = ov > 0
        pair_pen = np.sum(ov[mask] ** 2)
        wx0 = r - x; wx1 = x + r - 1.0
        wy0 = r - y; wy1 = y + r - 1.0
        wall_pen = (np.sum(np.maximum(wx0, 0.0)**2) + np.sum(np.maximum(wx1, 0.0)**2)
                    + np.sum(np.maximum(wy0, 0.0)**2) + np.sum(np.maximum(wy1, 0.0)**2))
        f = -np.sum(r) + lam * (pair_pen + wall_pen)
        g = np.zeros_like(z)
        g[2::3] = -1.0
        if np.any(mask):
            idx = np.where(mask)[0]
            ii = pi[idx]; jj = pj[idx]
            ovm = ov[idx]
            ds = np.maximum(d[idx], 1e-12)
            coef = 2.0 * ovm * lam
            gx = -coef * dx[idx] / ds
            gy = -coef * dy[idx] / ds
            gr = coef
            np.add.at(g, 3*ii, gx)
            np.add.at(g, 3*jj, -gx)
            np.add.at(g, 3*ii+1, gy)
            np.add.at(g, 3*jj+1, -gy)
            np.add.at(g, 3*ii+2, gr)
            np.add.at(g, 3*jj+2, gr)
        for arr, sx, sr_, off in [(wx0, 1.0, -1.0, 0), (wx1, -1.0, 1.0, 0),
                                   (wy0, 1.0, -1.0, 1), (wy1, -1.0, 1.0, 1)]:
            m = arr > 0
            if np.any(m):
                idx = np.where(m)[0]
                cc = 2.0 * arr[idx] * lam
                g[3*idx+off] += cc * sx
                g[3*idx+2] += cc * sr_
        return f, g

    def soft_opt(z, lam, maxiter):
        try:
            res = minimize(lambda zz: soft_fg(zz, lam), z, jac=True,
                           method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': maxiter, 'ftol': 1e-12, 'gtol': 1e-10})
            return res.x if res.x is not None else z
        except Exception:
            return z

    # ---- exploration loop: basin hopping + soft relaxation ----
    explore_deadline = t0 + budget_seconds * 0.90
    it = 0
    while time.process_time() < explore_deadline:
        it += 1
        frac = (time.process_time() - t0) / max(1e-6, budget_seconds * 0.90)
        scale = 0.05 * (1.0 - 0.6 * frac) + 0.003

        z = best.copy()
        if rng.random() < 0.6:
            order = np.argsort(z[2::3])
            pool = order[:max(8, n // 2)]
            nmove = int(rng.integers(2, 7))
            idx = rng.choice(pool, size=min(nmove, len(pool)), replace=False)
        else:
            nmove = int(rng.integers(2, 7))
            idx = rng.choice(n, size=nmove, replace=False)

        z[0::3][idx] += rng.normal(0.0, scale, len(idx))
        z[1::3][idx] += rng.normal(0.0, scale, len(idx))
        z[2::3][idx] += rng.normal(0.0, scale * 0.3, len(idx))

        if rng.random() < 0.4:
            i = int(rng.integers(0, n))
            side = int(rng.integers(0, 4))
            r_i = z[3*i+2]
            if side == 0:
                z[3*i] = r_i
            elif side == 1:
                z[3*i] = 1.0 - r_i
            elif side == 2:
                z[3*i+1] = r_i
            else:
                z[3*i+1] = 1.0 - r_i

        z[0::3] = np.clip(z[0::3], 0.0, 1.0)
        z[1::3] = np.clip(z[1::3], 0.0, 1.0)
        z[2::3] = np.clip(z[2::3], 1e-4, 0.4)

        zz = z.copy()
        for lam in (1e2, 1e4, 1e6):
            if time.process_time() > explore_deadline:
                break
            zz = soft_opt(zz, lam, 40)
            zz[0::3] = np.clip(zz[0::3], 0.0, 1.0)
            zz[1::3] = np.clip(zz[1::3], 0.0, 1.0)
            zz[2::3] = np.clip(zz[2::3], 1e-4, 0.4)

        if time.process_time() > explore_deadline:
            break

        sub_dl = min(explore_deadline, time.process_time() +
                     max(0.05, (explore_deadline - time.process_time()) * 0.4))
        cand = run_slsqp(zz, sub_dl, 400)
        if time.process_time() < sub_dl:
            c2 = cd_inflate(cand, 6)
            c2 = run_slsqp(c2, sub_dl, 300)
            if max_violation(c2) <= 1e-9 and score(c2) > score(cand):
                cand = c2
        consider(cand)

    # ---- NEW: exact KKT/nullspace step on near-active constraints ----
    def build_active_eq(z, tol=1e-6):
        x = z[0::3]; y = z[1::3]; r = z[2::3]
        dx = x[pi] - x[pj]; dy = y[pi] - y[pj]; sr = r[pi] + r[pj]
        dist = np.sqrt(dx*dx + dy*dy)
        gap = dist - sr
        ap = np.where(gap < tol)[0]
        wm = np.concatenate([x - r, 1.0 - x - r, y - r, 1.0 - y - r])
        aw = np.where(wm < tol)[0]
        return ap, aw

    def eq_fun(zc, ap, aw):
        xx = zc[0::3]; yy = zc[1::3]; rr = zc[2::3]
        out = []
        if len(ap):
            ddx = xx[pi[ap]] - xx[pj[ap]]
            ddy = yy[pi[ap]] - yy[pj[ap]]
            ssr = rr[pi[ap]] + rr[pj[ap]]
            out.append(ddx*ddx + ddy*ddy - ssr*ssr)
        if len(aw):
            wmm = np.concatenate([xx - rr, 1.0 - xx - rr, yy - rr, 1.0 - yy - rr])
            out.append(wmm[aw])
        return np.concatenate(out) if out else np.zeros(0)

    def eq_jac(zc, ap, aw):
        xx = zc[0::3]; yy = zc[1::3]; rr = zc[2::3]
        rows = []
        if len(ap):
            ddx = xx[pi[ap]] - xx[pj[ap]]
            ddy = yy[pi[ap]] - yy[pj[ap]]
            ssr = rr[pi[ap]] + rr[pj[ap]]
            Jp = np.zeros((len(ap), 3*n))
            rws = np.arange(len(ap))
            np.add.at(Jp, (rws, 3*pi[ap]), 2*ddx)
            np.add.at(Jp, (rws, 3*pj[ap]), -2*ddx)
            np.add.at(Jp, (rws, 3*pi[ap]+1), 2*ddy)
            np.add.at(Jp, (rws, 3*pj[ap]+1), -2*ddy)
            np.add.at(Jp, (rws, 3*pi[ap]+2), -2*ssr)
            np.add.at(Jp, (rws, 3*pj[ap]+2), -2*ssr)
            rows.append(Jp)
        if len(aw):
            Jw = np.zeros((len(aw), 3*n))
            for k, wi in enumerate(aw):
                if wi < n:
                    i = wi; Jw[k, 3*i] = 1.0; Jw[k, 3*i+2] = -1.0
                elif wi < 2*n:
                    i = wi - n; Jw[k, 3*i] = -1.0; Jw[k, 3*i+2] = -1.0
                elif wi < 3*n:
                    i = wi - 2*n; Jw[k, 3*i+1] = 1.0; Jw[k, 3*i+2] = -1.0
                else:
                    i = wi - 3*n; Jw[k, 3*i+1] = -1.0; Jw[k, 3*i+2] = -1.0
            rows.append(Jw)
        return np.vstack(rows) if rows else np.zeros((0, 3*n))

    def nullspace_step(z, deadline):
        z = z.copy()
        for _ in range(50):
            if time.process_time() > deadline:
                break
            ap, aw = build_active_eq(z, 1e-6)
            if len(ap) + len(aw) == 0:
                break
            J = eq_jac(z, ap, aw)
            g = obj_grad(z)
            try:
                U, S, Vt = np.linalg.svd(J, full_matrices=True)
            except Exception:
                break
            # nullspace of J: rows of Vt beyond rank
            rank = int(np.sum(S > 1e-10 * max(1.0, S[0] if len(S) else 1.0)))
            N = Vt[rank:].T  # (3n, k)
            if N.shape[1] == 0:
                break
            # projected step: descend objective (-sum r) => minimize obj => step = -N N^T g
            dz = -N @ (N.T @ g)
            # normalize
            nrm = np.linalg.norm(dz)
            if nrm < 1e-16:
                break
            dz = dz / nrm
            # line search
            alpha = 1e-3
            accepted = False
            for _ls in range(40):
                zc = z + alpha * dz
                # bounds
                xc = zc[0::3]; yc = zc[1::3]; rc = zc[2::3]
                if np.any(rc <= 1e-9) or np.any(xc - rc < -1e-12) or \
                   np.any(xc + rc > 1.0 + 1e-12) or np.any(yc - rc < -1e-12) or \
                   np.any(yc + rc > 1.0 + 1e-12):
                    alpha *= 0.5
                    continue
                # restore equalities via least squares
                e = eq_fun(zc, ap, aw)
                if len(e):
                    try:
                        Jc = eq_jac(zc, ap, aw)
                        corr, *_ = np.linalg.lstsq(Jc, -e, rcond=None)
                        zc = zc + corr
                    except Exception:
                        alpha *= 0.5
                        continue
                # check all constraints strictly feasible
                if max_violation(zc) <= -1e-12:
                    if score(zc) > score(z) + 1e-15:
                        z = zc
                        accepted = True
                        break
                alpha *= 0.5
            if not accepted:
                break
        return z

    # ---- final polish: nullspace step + SLSQP on active equalities ----
    fin_deadline = t0 + budget_seconds * 0.97
    cand = nullspace_step(best.copy(), fin_deadline)
    if max_violation(cand) <= 1e-10 and score(cand) > best_score:
        best = cand
        best_score = score(cand)

    # SLSQP with only near-active equalities, tight ftol
    if time.process_time() < fin_deadline:
        ap, aw = build_active_eq(best, 1e-6)
        if len(ap) + len(aw) > 0:
            cons_eq = [{'type': 'eq',
                        'fun': lambda zc, ap=ap, aw=aw: eq_fun(zc, ap, aw),
                        'jac': lambda zc, ap=ap, aw=aw: eq_jac(zc, ap, aw)}]
            try:
                res = minimize(obj, best, jac=obj_grad, method='SLSQP',
                               bounds=bounds, constraints=cons_eq,
                               options={'ftol': 1e-16, 'maxiter': 2000, 'disp': False})
                cand = res.x if res.x is not None else best
                if max_violation(cand) <= 1e-10 and score(cand) > best_score:
                    best = cand
                    best_score = score(cand)
            except Exception:
                pass

    # also do a couple of active_polish-like SLSQP runs as fallback
    for _ in range(3):
        if time.process_time() > fin_deadline:
            break
        cand = nullspace_step(best.copy(), fin_deadline)
        if max_violation(cand) <= 1e-10 and score(cand) > best_score:
            best = cand
            best_score = score(cand)

    # ---- SAFE final shrink ----
    z = best
    x = z[0::3].copy(); y = z[1::3].copy(); r = z[2::3].copy()
    for _ in range(80):
        v = max_violation(np.column_stack([x, y, r]).flatten())
        if v <= 1e-12:
            break
        r = np.maximum(r - (v + 1e-10), 1e-9)
        x = np.clip(x, r, 1.0 - r)
        y = np.clip(y, r, 1.0 - r)
    r = np.maximum(r - 1e-12, 1e-9)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    return np.column_stack([x, y, r])
