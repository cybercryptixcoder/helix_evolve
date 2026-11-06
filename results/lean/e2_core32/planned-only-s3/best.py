import numpy as np
import time
from scipy.optimize import minimize


def _feasible_radius(cx, cy, present, n):
    r = min(cx, 1.0 - cx, cy, 1.0 - cy)
    for (px, py, pr) in present:
        d = np.hypot(cx - px, cy - py)
        r = min(r, d - pr)
    return r


def _slsqp_polish(s, n, iters, ftol=1e-14):
    r0 = np.clip(s[:, 2], 1e-6, 0.49)
    denom = 1.0 - 2.0 * r0
    denom = np.where(np.abs(denom) < 1e-9, 1e-9, denom)
    u0 = np.clip((s[:, 0] - r0) / denom, 0.0, 1.0)
    v0 = np.clip((s[:, 1] - r0) / denom, 0.0, 1.0)

    x0 = np.zeros(3 * n)
    x0[0::3] = u0
    x0[1::3] = v0
    x0[2::3] = r0

    def obj(z):
        return -np.sum(z[2::3])

    def obj_grad(z):
        g = np.zeros_like(z)
        g[2::3] = -1.0
        return g

    def xy_from(z):
        u = z[0::3]
        v = z[1::3]
        r = z[2::3]
        x = r + (1.0 - 2.0 * r) * u
        y = r + (1.0 - 2.0 * r) * v
        return x, y, r

    cons = []
    for i in range(n):
        for j in range(i + 1, n):
            def cp(z, i=i, j=j):
                x, y, r = xy_from(z)
                dx = x[i] - x[j]
                dy = y[i] - y[j]
                rs = r[i] + r[j]
                return dx * dx + dy * dy - rs * rs

            def cpg(z, i=i, j=j):
                x, y, r = xy_from(z)
                dx = x[i] - x[j]
                dy = y[i] - y[j]
                rs = r[i] + r[j]
                ax = 1.0 - 2.0 * r[i]
                bx = 1.0 - 2.0 * r[j]
                g = np.zeros_like(z)
                g[3 * i] = 2 * dx * ax
                g[3 * i + 1] = 2 * dy * ax
                g[3 * i + 2] = 2 * dx * (1.0 - 2.0 * z[3 * i]) + 2 * dy * (1.0 - 2.0 * z[3 * i + 1]) - 2 * rs
                g[3 * j] = 2 * dx * (-bx)
                g[3 * j + 1] = 2 * dy * (-bx)
                g[3 * j + 2] = 2 * dx * (-(1.0 - 2.0 * z[3 * j])) + 2 * dy * (-(1.0 - 2.0 * z[3 * j + 1])) - 2 * rs
                return g

            cons.append({'type': 'ineq', 'fun': cp, 'jac': cpg})

    bounds = []
    for i in range(n):
        bounds.append((0.0, 1.0))
        bounds.append((0.0, 1.0))
        bounds.append((1e-6, 0.49))

    try:
        res = minimize(obj, x0, jac=obj_grad, method='SLSQP',
                       constraints=cons, bounds=bounds,
                       options={'maxiter': iters, 'ftol': ftol})
        z = res.x
    except Exception:
        z = x0

    x, y, r = xy_from(z)
    r = np.maximum(r, 1e-9)
    x = np.clip(x, r, 1.0 - r)
    y = np.clip(y, r, 1.0 - r)
    return np.column_stack([x, y, r])


def _repair(out, n, deflate=1e-11):
    out = out.copy()
    for _ in range(200):
        bad = False
        for i in range(n):
            for j in range(i + 1, n):
                d = np.hypot(out[i, 0] - out[j, 0], out[i, 1] - out[j, 1])
                sm = out[i, 2] + out[j, 2]
                if d < sm:
                    bad = True
                    ex = sm - d
                    out[i, 2] -= ex / 2 + 1e-12
                    out[j, 2] -= ex / 2 + 1e-12
        if not bad:
            break
    out[:, 2] = np.maximum(out[:, 2], 1e-12)
    out[:, 2] = out[:, 2] - deflate
    out[:, 2] = np.maximum(out[:, 2], 1e-12)
    out[:, 0] = np.clip(out[:, 0], out[:, 2], 1.0 - out[:, 2])
    out[:, 1] = np.clip(out[:, 1], out[:, 2], 1.0 - out[:, 2])
    return out


def _repair_local(out):
    """Local violation repair: shrink only offending radii, no global deflation."""
    out = out.copy()
    n = out.shape[0]
    for _ in range(100):
        bad = False
        for i in range(n):
            x, y, r = out[i]
            v = max(r - x, x + r - 1.0, r - y, y + r - 1.0)
            if v > 0:
                bad = True
                out[i, 2] = r - v - 1e-13
        for i in range(n):
            for j in range(i + 1, n):
                d = np.hypot(out[i, 0] - out[j, 0], out[i, 1] - out[j, 1])
                sm = out[i, 2] + out[j, 2]
                if d < sm:
                    bad = True
                    ex = sm - d
                    out[i, 2] -= ex / 2 + 1e-13
                    out[j, 2] -= ex / 2 + 1e-13
        if not bad:
            break
    out[:, 2] = np.maximum(out[:, 2], 1e-12)
    return out


def _valid(out, n):
    for i in range(n):
        x, y, r = out[i]
        if r <= 0:
            return False
        if x - r < 0 or x + r > 1 or y - r < 0 or y + r > 1:
            return False
    for i in range(n):
        for j in range(i + 1, n):
            d = np.hypot(out[i, 0] - out[j, 0], out[i, 1] - out[j, 1])
            if d < out[i, 2] + out[j, 2]:
                return False
    return True


def _uniform_scale_up(out, n, rounds=5):
    """Scale all radii up by the maximal uniform factor, keeping centres fixed."""
    out = out.copy()
    for _ in range(rounds):
        r = out[:, 2]
        x = out[:, 0]
        y = out[:, 1]
        lam = 1.0
        for i in range(n):
            if r[i] > 0:
                wd = min(x[i], 1.0 - x[i], y[i], 1.0 - y[i])
                lam = min(lam, wd / r[i])
        for i in range(n):
            for j in range(i + 1, n):
                rs = r[i] + r[j]
                if rs > 0:
                    d = np.hypot(x[i] - x[j], y[i] - y[j])
                    lam = min(lam, d / rs)
        if lam > 1.0 + 1e-15:
            out[:, 2] = r * lam * (1.0 - 1e-14)
        else:
            break
    return out


def _anchor_motif(cur, n, anchor, kind, rng):
    ax, ay = anchor
    dists = np.hypot(cur[:, 0] - ax, cur[:, 1] - ay)
    near = np.where(dists < 0.30)[0].tolist()
    order = np.argsort(dists)
    if len(near) < 12:
        for idx in order:
            if int(idx) not in near:
                near.append(int(idx))
            if len(near) >= 12:
                break
    elif len(near) > 20:
        near.sort(key=lambda i: dists[i])
        near = near[:20]
    del_set = set(near)
    keep_idx = [i for i in range(n) if i not in del_set]

    trial = cur.copy()
    present = [(cur[i, 0], cur[i, 1], cur[i, 2]) for i in keep_idx]

    ts = (0.12, 0.30, 0.50)
    if kind == 'corner':
        sx = 1.0 if ax < 0.5 else -1.0
        sy = 1.0 if ay < 0.5 else -1.0
        motif_pts = [(ax, ay)]
        for t in (0.15, 0.35, 0.55):
            motif_pts.append((ax + sx * t, ay))
            motif_pts.append((ax, ay + sy * t))
    else:
        if abs(ay) < 1e-9 or abs(ay - 1.0) < 1e-9:
            ny = 1.0 if ay < 0.5 else -1.0
            motif_pts = [(ax, ay)]
            for t in ts:
                motif_pts.append((ax - t, ay))
                motif_pts.append((ax + t, ay))
            for t in ts:
                motif_pts.append((ax, ay + ny * t))
        else:
            nx = 1.0 if ax < 0.5 else -1.0
            motif_pts = [(ax, ay)]
            for t in ts:
                motif_pts.append((ax, ay - t))
                motif_pts.append((ax, ay + t))
            for t in ts:
                motif_pts.append((ax + nx * t, ay))

    ins_order = list(near)
    rng.shuffle(ins_order)
    mi = 0
    for i in ins_order:
        if mi < len(motif_pts):
            px, py = motif_pts[mi]
            mi += 1
            if px <= 0.0:
                px = 0.0
            if px >= 1.0:
                px = 1.0
            if py <= 0.0:
                py = 0.0
            if py >= 1.0:
                py = 1.0
            rr = _feasible_radius(px, py, present, n)
            if rr <= 0:
                rr = 1e-6
            trial[i, 0] = px
            trial[i, 1] = py
            trial[i, 2] = rr
            present.append((px, py, rr))
        else:
            ox, oy, orad = cur[i]
            cap = 1.2 * orad
            best_r = -1.0
            best_c = (ox, oy)
            for kk in range(2000):
                if kk < 1000:
                    px = ox + rng.normal(0, 0.05)
                    py = oy + rng.normal(0, 0.05)
                else:
                    px = rng.uniform(0.02, 0.98)
                    py = rng.uniform(0.02, 0.98)
                if px <= 0 or px >= 1 or py <= 0 or py >= 1:
                    continue
                rr = _feasible_radius(px, py, present, n)
                if rr > cap:
                    rr = cap
                if rr > best_r:
                    best_r = rr
                    best_c = (px, py)
            if best_r <= 0:
                best_r = 1e-6
            trial[i, 0] = best_c[0]
            trial[i, 1] = best_c[1]
            trial[i, 2] = best_r
            present.append((best_c[0], best_c[1], best_r))

    return trial


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 32
    deadline = t0 + budget_seconds - 1.0

    if start is not None and np.asarray(start).shape == (n, 3):
        cur = np.array(start, dtype=float)
    else:
        k = 6
        pts = [((i + 0.5) / k, (j + 0.5) / k) for j in range(k) for i in range(k)][:n]
        cur = np.array([[x, y, 0.08] for (x, y) in pts])

    cur = _repair(cur, n)
    best = cur.copy()
    best_score = np.sum(best[:, 2])

    rng = np.random.default_rng(12345)
    anchors = [
        ((0.0, 0.0), 'corner'),
        ((1.0, 0.0), 'corner'),
        ((0.0, 1.0), 'corner'),
        ((1.0, 1.0), 'corner'),
        ((0.5, 0.0), 'edge'),
        ((0.5, 1.0), 'edge'),
        ((0.0, 0.5), 'edge'),
        ((1.0, 0.5), 'edge'),
    ]
    ai = 0

    while time.process_time() < deadline:
        anchor, kind = anchors[ai % len(anchors)]
        ai += 1

        trial = _anchor_motif(cur, n, anchor, kind, rng)
        trial = _repair(trial, n)
        if time.process_time() < deadline:
            try:
                polished = _slsqp_polish(trial, n, 350)
                polished = _repair(polished, n)
            except Exception:
                polished = trial
        else:
            polished = trial

        if _valid(polished, n):
            sc = np.sum(polished[:, 2])
            if sc > best_score + 1e-12:
                best = polished.copy()
                best_score = sc
                cur = polished.copy()
            else:
                cur = best.copy()
        else:
            cur = best.copy()

    fallback = _repair(best, n)
    final = fallback

    try:
        polished = _slsqp_polish(best, n, 5000, ftol=1e-18)
        if _valid(polished, n):
            candidate = polished
        else:
            candidate = _repair_local(polished)
        if _valid(candidate, n) and np.sum(candidate[:, 2]) >= np.sum(fallback[:, 2]):
            final = candidate
    except Exception:
        final = fallback

    # Experiment: uniform scale-up of radii at fixed centres.
    try:
        scaled = _uniform_scale_up(final, n, rounds=5)
        if _valid(scaled, n) and np.sum(scaled[:, 2]) >= np.sum(final[:, 2]):
            final = scaled
    except Exception:
        pass

    return final
