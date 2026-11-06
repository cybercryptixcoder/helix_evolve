import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    deadline = t0 + budget_seconds - 0.7
    rng = np.random.default_rng(77003)
    I, J = np.triu_indices(n, 1)

    def repair(c, iters=800):
        c = c.copy()
        c[:, 2] = np.maximum(c[:, 2], 1e-12)
        for _ in range(iters):
            rmax = np.minimum(np.minimum(c[:, 0], 1 - c[:, 0]),
                              np.minimum(c[:, 1], 1 - c[:, 1]))
            c[:, 2] = np.minimum(c[:, 2], np.maximum(rmax, 1e-12))
            dx = c[I, 0] - c[J, 0]
            dy = c[I, 1] - c[J, 1]
            d = np.hypot(dx, dy)
            viol = (c[I, 2] + c[J, 2]) - d
            if viol.max() <= 1e-14:
                break
            amt = np.maximum(viol, 0.0) * 0.5
            np.add.at(c[:, 2], I, -amt)
            np.add.at(c[:, 2], J, -amt)
            c[:, 2] = np.maximum(c[:, 2], 1e-12)
        return c

    # ---- SLSQP on exact problem ----
    def make_slsqp(c):
        x0 = c.ravel().copy()

        def obj(x):
            return -x[2::3].sum()

        def obj_grad(x):
            g = np.zeros(3 * n)
            g[2::3] = -1.0
            return g

        def cons(x):
            cc = x.reshape(n, 3)
            r = cc[:, 2]
            dx = cc[I, 0] - cc[J, 0]
            dy = cc[I, 1] - cc[J, 1]
            dd = np.hypot(dx, dy)
            return np.concatenate([
                cc[:, 0] - r, 1.0 - cc[:, 0] - r,
                cc[:, 1] - r, 1.0 - cc[:, 1] - r,
                dd - (r[I] + r[J])])

        def cons_jac(x):
            cc = x.reshape(n, 3)
            m = 4 * n + len(I)
            Jm = np.zeros((m, 3 * n))
            idx = np.arange(n)
            Jm[idx, 3 * idx] = 1.0
            Jm[idx, 3 * idx + 2] = -1.0
            Jm[n + idx, 3 * idx] = -1.0
            Jm[n + idx, 3 * idx + 2] = -1.0
            Jm[2 * n + idx, 3 * idx + 1] = 1.0
            Jm[2 * n + idx, 3 * idx + 2] = -1.0
            Jm[3 * n + idx, 3 * idx + 1] = -1.0
            Jm[3 * n + idx, 3 * idx + 2] = -1.0
            dx = cc[I, 0] - cc[J, 0]
            dy = cc[I, 1] - cc[J, 1]
            dd = np.hypot(dx, dy)
            ds = np.where(dd > 1e-12, dd, 1.0)
            ux = dx / ds; uy = dy / ds
            rows = 4 * n + np.arange(len(I))
            Jm[rows, 3 * I] = ux
            Jm[rows, 3 * J] = -ux
            Jm[rows, 3 * I + 1] = uy
            Jm[rows, 3 * J + 1] = -uy
            Jm[rows, 3 * I + 2] = -1.0
            Jm[rows, 3 * J + 2] = -1.0
            return Jm

        return x0, obj, obj_grad, cons, cons_jac

    def slsqp_polish(c, time_cap, maxiter=800):
        c = repair(c)
        if time.process_time() > time_cap:
            return c
        x0, obj, og, cons, cj = make_slsqp(c)
        try:
            res = minimize(obj, x0, jac=og, method='SLSQP',
                           constraints={'type': 'ineq', 'fun': cons, 'jac': cj},
                           options={'maxiter': maxiter, 'ftol': 1e-16})
            c2 = res.x.reshape(n, 3)
            c2 = repair(c2)
            if c2[:, 2].sum() >= c[:, 2].sum() - 1e-9:
                return c2
        except Exception:
            pass
        return c

    # ---- L-BFGS penalty polish ----
    def make_energy(PEN):
        def energy(x):
            c = x.reshape(n, 3); cs = c[:, 2]
            e = -cs.sum()
            a = np.maximum(0, cs - c[:, 0]); e += PEN * (a * a).sum()
            b = np.maximum(0, c[:, 0] + cs - 1); e += PEN * (b * b).sum()
            d1 = np.maximum(0, cs - c[:, 1]); e += PEN * (d1 * d1).sum()
            d2 = np.maximum(0, c[:, 1] + cs - 1); e += PEN * (d2 * d2).sum()
            dx = c[I, 0] - c[J, 0]; dy = c[I, 1] - c[J, 1]
            dd = np.hypot(dx, dy)
            ov = np.maximum(0, (c[I, 2] + c[J, 2]) - dd)
            e += PEN * (ov * ov).sum()
            return e

        def grad(x):
            c = x.reshape(n, 3); g = np.zeros_like(c); cs = c[:, 2]
            g[:, 2] -= 1.0
            a = np.maximum(0, cs - c[:, 0]); g[:, 2] += 2 * PEN * a; g[:, 0] -= 2 * PEN * a
            b = np.maximum(0, c[:, 0] + cs - 1); g[:, 2] += 2 * PEN * b; g[:, 0] += 2 * PEN * b
            d1 = np.maximum(0, cs - c[:, 1]); g[:, 2] += 2 * PEN * d1; g[:, 1] -= 2 * PEN * d1
            d2 = np.maximum(0, c[:, 1] + cs - 1); g[:, 2] += 2 * PEN * d2; g[:, 1] += 2 * PEN * d2
            dx = c[I, 0] - c[J, 0]; dy = c[I, 1] - c[J, 1]
            dd = np.hypot(dx, dy)
            ov = (c[I, 2] + c[J, 2]) - dd
            mask = ov > 0
            if mask.any():
                ds = np.where(dd > 1e-12, dd, 1.0)
                f = 2 * PEN * ov * mask
                ux = dx / ds; uy = dy / ds
                np.add.at(g[:, 0], I, f * ux); np.add.at(g[:, 0], J, -f * ux)
                np.add.at(g[:, 1], I, f * uy); np.add.at(g[:, 1], J, -f * uy)
                np.add.at(g[:, 2], I, f); np.add.at(g[:, 2], J, f)
            return g.ravel()
        return energy, grad

    PENS = (1e5, 1e7, 1e9)
    energies = {p: make_energy(p) for p in PENS}

    def hex_init():
        c = np.zeros((n, 3))
        idx = 0
        for row in range(6):
            for col in range(6):
                if idx >= n: break
                x = (col + 0.5) / 6.0 + (0.5 / 6.0 if row % 2 else 0.0)
                y = (row + 0.5) / 6.0
                c[idx] = [min(max(x, 0.06), 0.94), min(max(y, 0.06), 0.94), 0.06]
                idx += 1
            if idx >= n: break
        return c

    # ---- "Voronoi-ish" reinit: perturb one circle to a random spot, redistribute
    def perturb(c, mode, rng):
        cand = c.copy()
        if mode == 0:
            base = hex_init()
            base[:, 0] += rng.normal(0, 0.05, n)
            base[:, 1] += rng.normal(0, 0.05, n)
            base[:, 2] = rng.uniform(0.04, 0.10, n)
            return base
        if mode <= 3:
            k = rng.integers(2, 12)
            idxs = rng.choice(n, size=k, replace=False)
            sc = (0.03, 0.015, 0.006)[mode - 1]
            cand[idxs, 0] += rng.normal(0, sc, k)
            cand[idxs, 1] += rng.normal(0, sc, k)
            cand[:, 2] *= rng.uniform(0.97, 1.03, n)
        elif mode == 4:
            a, b = rng.choice(n, size=2, replace=False)
            cand[[a, b], :2] = cand[[b, a], :2]
        elif mode == 5:
            a = rng.integers(0, n)
            d = np.hypot(cand[:, 0] - cand[a, 0], cand[:, 1] - cand[a, 1])
            mask = d < 0.16
            cand[mask, 2] *= rng.uniform(0.97, 1.03, mask.sum())
        elif mode == 6:
            cx, cy = rng.uniform(0.25, 0.75, 2)
            d = np.hypot(cand[:, 0] - cx, cand[:, 1] - cy)
            w = np.exp(-(d / 0.18) ** 2)
            ang = rng.uniform(0, 2 * np.pi)
            cand[:, 0] += w * 0.025 * np.cos(ang)
            cand[:, 1] += w * 0.025 * np.sin(ang)
        elif mode == 7:
            # swap radii between two circles (preserve positions)
            a, b = rng.choice(n, size=2, replace=False)
            cand[[a, b], 2] = cand[[b, a], 2]
        elif mode == 8:
            # move one circle to a random free spot
            a = rng.integers(0, n)
            cand[a, 0] = rng.uniform(0.1, 0.9)
            cand[a, 1] = rng.uniform(0.1, 0.9)
        else:
            cand[:, 0] += rng.normal(0, 0.002, n)
            cand[:, 1] += rng.normal(0, 0.002, n)
            cand[:, 2] *= rng.uniform(1.0, 1.006, n)
        return cand

    if start is not None:
        try:
            c0 = np.array(start, dtype=float).reshape(n, 3)
        except Exception:
            c0 = hex_init()
    else:
        c0 = hex_init()

    best = repair(c0)
    best_s = best[:, 2].sum()

    # Initial SLSQP polish of start
    if time.process_time() < deadline:
        cap = min(deadline, time.process_time() + (deadline - time.process_time()) * 0.20)
        pol = slsqp_polish(best, cap, 1500)
        if pol[:, 2].sum() > best_s:
            best = pol; best_s = pol[:, 2].sum()

    # Iterated local search
    attempt = 0
    stale = 0
    while time.process_time() < deadline - 0.05:
        attempt += 1
        cand = perturb(best, attempt % 10, rng)
        cand[:, 2] = np.maximum(cand[:, 2], 1e-6)
        cand = repair(cand)
        cand[:, 2] *= 1.003
        cand = repair(cand)

        remaining = deadline - time.process_time()
        if remaining <= 0.1:
            break
        cap = min(deadline, time.process_time() + max(0.15, remaining * 0.7))
        c2 = slsqp_polish(cand, cap, 600)
        s2 = c2[:, 2].sum()
        if s2 > best_s + 1e-14:
            best_s = s2
            best = c2.copy()
            stale = 0
        else:
            stale += 1
            # occasionally restart from hex when stuck
            if stale > 40:
                h = hex_init()
                h[:, 0] += rng.normal(0, 0.04, n)
                h[:, 1] += rng.normal(0, 0.04, n)
                h[:, 2] = rng.uniform(0.05, 0.09, n)
                h = repair(h)
                if h[:, 2].sum() > best_s - 0.01:
                    best = h
                    best_s = h[:, 2].sum()
                stale = 0

    if time.process_time() < deadline - 0.3:
        cand = slsqp_polish(best, deadline - 0.1, 2500)
        if cand[:, 2].sum() > best_s:
            best = cand
            best_s = best[:, 2].sum()

    out = repair(best)
    out[:, 2] *= (1.0 - 1e-9)
    out[:, 2] = np.maximum(out[:, 2], 1e-9)
    out[:, 0] = np.clip(out[:, 0], out[:, 2], 1 - out[:, 2])
    out[:, 1] = np.clip(out[:, 1], out[:, 2], 1 - out[:, 2])
    return out
