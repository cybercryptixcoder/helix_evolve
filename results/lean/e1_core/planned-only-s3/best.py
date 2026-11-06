import numpy as np
import time
from scipy.optimize import minimize, linprog


def _unpack(v, n):
    return v[:2 * n].reshape(n, 2), v[2 * n:]


def _constraints(v, n):
    c, r = _unpack(v, n)
    cons = []
    cons.append(c[:, 0] - r)
    cons.append(1.0 - c[:, 0] - r)
    cons.append(c[:, 1] - r)
    cons.append(1.0 - c[:, 1] - r)
    dx = c[:, None, 0] - c[None, :, 0]
    dy = c[:, None, 1] - c[None, :, 1]
    d = np.sqrt(dx * dx + dy * dy)
    rs = r[:, None] + r[None, :]
    iu = np.triu_indices(n, 1)
    cons.append((d - rs)[iu])
    return np.concatenate(cons)


def _repair(out):
    n = out.shape[0]
    out = out.copy()
    out[:, 2] = np.maximum(out[:, 2], 1e-6)
    out[:, 0] = np.clip(out[:, 0], out[:, 2], 1.0 - out[:, 2])
    out[:, 1] = np.clip(out[:, 1], out[:, 2], 1.0 - out[:, 2])
    for _ in range(200):
        c = out[:, :2]
        r = out[:, 2]
        dx = c[:, None, 0] - c[None, :, 0]
        dy = c[:, None, 1] - c[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        iu = np.triu_indices(n, 1)
        viol = (rs - d)[iu]
        if np.max(viol) <= 1e-12:
            break
        for idx in np.where(viol > 0)[0]:
            i, j = iu[0][idx], iu[1][idx]
            excess = (rs[i, j] - d[i, j]) * 0.5 + 1e-12
            out[i, 2] = max(out[i, 2] - excess, 1e-6)
            out[j, 2] = max(out[j, 2] - excess, 1e-6)
        out[:, 0] = np.clip(out[:, 0], out[:, 2], 1.0 - out[:, 2])
        out[:, 1] = np.clip(out[:, 1], out[:, 2], 1.0 - out[:, 2])
    return out


def _lp_reexpand(centers, lower=0.0):
    n = centers.shape[0]
    # Compute distances and wall margins in longdouble for accuracy.
    c_ld = centers.astype(np.longdouble)
    dx = c_ld[:, None, 0] - c_ld[None, :, 0]
    dy = c_ld[:, None, 1] - c_ld[None, :, 1]
    d = np.sqrt(dx * dx + dy * dy)
    iu = np.triu_indices(n, 1)
    A = []
    b = []
    for i, j in zip(iu[0], iu[1]):
        row = np.zeros(n)
        row[i] = 1.0
        row[j] = 1.0
        A.append(row)
        b.append(float(d[i, j]))
    for i in range(n):
        row = np.zeros(n)
        row[i] = 1.0
        A.append(row)
        margin = min(c_ld[i, 0], np.longdouble(1.0) - c_ld[i, 0],
                     c_ld[i, 1], np.longdouble(1.0) - c_ld[i, 1])
        b.append(float(margin))
    A = np.array(A)
    b = np.array(b)
    cvec = -np.ones(n)
    bounds = [(0.0, None)] * n
    try:
        res = linprog(cvec, A_ub=A, b_ub=b, bounds=bounds, method='highs')
        if res.success:
            return res.x
    except Exception:
        pass
    return None


def _lp_radii(centers):
    n = centers.shape[0]
    r = _lp_reexpand(centers, lower=1e-6)
    if r is not None:
        return r
    return np.full(n, 0.05)


def _fix_violations(out):
    n = out.shape[0]
    out = out.copy()
    for _ in range(100):
        c = out[:, :2]
        r = out[:, 2]
        wall_viol = np.stack([
            r - c[:, 0],
            r - (1.0 - c[:, 0]),
            r - c[:, 1],
            r - (1.0 - c[:, 1]),
        ], axis=1)
        maxw = wall_viol.max()
        dx = c[:, None, 0] - c[None, :, 0]
        dy = c[:, None, 1] - c[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        iu = np.triu_indices(n, 1)
        pv = (rs - d)[iu]
        maxp = pv.max() if pv.size else -1.0
        if maxw <= 1e-13 and maxp <= 1e-13:
            break
        for idx in np.where(pv > 1e-13)[0]:
            i, j = iu[0][idx], iu[1][idx]
            excess = (rs[i, j] - d[i, j]) * 0.5 + 1e-13
            out[i, 2] = max(out[i, 2] - excess, 1e-9)
            out[j, 2] = max(out[j, 2] - excess, 1e-9)
        for i in range(n):
            for k in range(4):
                if wall_viol[i, k] > 1e-13:
                    out[i, 2] = max(out[i, 2] - (wall_viol[i, k] + 1e-13), 1e-9)
    return out


def _lp_polish(out):
    centers = out[:, :2]
    r = _lp_reexpand(centers, lower=0.0)
    if r is None:
        return out
    cand = np.column_stack([centers, r])
    cand = _fix_violations(cand)
    return cand


def _slsqp_polish(v0, n, maxiter=1500):
    def obj(v):
        _, r = _unpack(v, n)
        return -np.sum(r)

    def jac(v):
        g = np.zeros_like(v)
        g[2 * n:] = -1.0
        return g

    def cons_fun(v):
        return _constraints(v, n)

    def cons_jac(v):
        c, r = _unpack(v, n)
        J = np.zeros((4 * n, 3 * n))
        for i in range(n):
            J[i, 2 * i] = 1.0
            J[i, 2 * n + i] = -1.0
            J[n + i, 2 * i] = -1.0
            J[n + i, 2 * n + i] = -1.0
            J[2 * n + i, 2 * i + 1] = 1.0
            J[2 * n + i, 2 * n + i] = -1.0
            J[3 * n + i, 2 * i + 1] = -1.0
            J[3 * n + i, 2 * n + i] = -1.0
        iu = np.triu_indices(n, 1)
        npair = len(iu[0])
        Jp = np.zeros((npair, 3 * n))
        dx = c[:, None, 0] - c[None, :, 0]
        dy = c[:, None, 1] - c[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy) + 1e-15
        for k, (i, j) in enumerate(zip(iu[0], iu[1])):
            ux = dx[i, j] / d[i, j]
            uy = dy[i, j] / d[i, j]
            Jp[k, 2 * i] = ux
            Jp[k, 2 * i + 1] = uy
            Jp[k, 2 * j] = -ux
            Jp[k, 2 * j + 1] = -uy
            Jp[k, 2 * n + i] = -1.0
            Jp[k, 2 * n + j] = -1.0
        return np.vstack([J, Jp])

    cons = {'type': 'ineq', 'fun': cons_fun, 'jac': cons_jac}
    bounds = [(0, 1)] * (2 * n) + [(1e-6, 0.5)] * n
    try:
        res = minimize(obj, v0, jac=jac, method='SLSQP',
                       bounds=bounds, constraints=cons,
                       options={'maxiter': maxiter, 'ftol': 1e-14})
        return res.x
    except Exception:
        return v0


def _row_xs(cnt, r, gap_pos, gap):
    if cnt == 1:
        return [0.5]
    xs = [0.0]
    for k in range(cnt - 1):
        step = 2.0 * r + (gap if k == gap_pos else 0.0)
        xs.append(xs[-1] + step)
    span = xs[-1]
    shift = 0.5 - span / 2.0
    return [x + shift for x in xs]


def _alt_row_seed(pattern, rA, ratio, gap_spec=None):
    pts = []
    y = 0.0
    for k, cnt in enumerate(pattern):
        rk = rA if (k % 2 == 0) else rA * ratio
        y += rk
        if gap_spec is not None and k in gap_spec and cnt >= 2:
            gp, gm = gap_spec[k]
            gp = min(gp, cnt - 2)
            xs = _row_xs(cnt, rk, gp, gm * rk)
        else:
            if cnt == 1:
                xs = [0.5]
            else:
                xs = np.linspace(rk, 1.0 - rk, cnt)
        for x in xs:
            pts.append((x, y))
        y += rk
    return np.array(pts)


def _compositions(total, parts, lo, hi):
    if parts == 1:
        if lo <= total <= hi:
            yield (total,)
        return
    for first in range(lo, hi + 1):
        rem = total - first
        if rem < lo * (parts - 1) or rem > hi * (parts - 1):
            continue
        for rest in _compositions(rem, parts - 1, lo, hi):
            yield (first,) + rest


def _cluster_rows(centers, tol=0.06):
    n = centers.shape[0]
    order = np.argsort(centers[:, 1])
    rows = []
    cur = [order[0]]
    for k in order[1:]:
        if abs(centers[k, 1] - centers[cur[-1], 1]) <= tol:
            cur.append(k)
        else:
            rows.append(cur)
            cur = [k]
    rows.append(cur)
    for r in rows:
        r.sort(key=lambda i: centers[i, 0])
    return rows


def _try_swap(centers, rows, ri):
    if ri + 1 >= len(rows):
        return None
    A = rows[ri]
    B = rows[ri + 1]
    if len(A) != len(B):
        return None
    new = centers.copy()
    for a, b in zip(A, B):
        new[a, 0], new[b, 0] = centers[b, 0], centers[a, 0]
    return new


def _highprec_repair(out):
    """Re-expand radii at fixed centers via LP, then minimally repair using
    longdouble arithmetic so no uniform shrink is needed."""
    n = out.shape[0]
    centers = out[:, :2]
    r = _lp_reexpand(centers, lower=0.0)
    if r is None:
        r = out[:, 2].copy()
    r = np.asarray(r, dtype=np.longdouble)
    c = centers.astype(np.longdouble)
    eps = np.longdouble(1e-18)
    iu = np.triu_indices(n, 1)
    for _ in range(2000):
        dx = c[:, None, 0] - c[None, :, 0]
        dy = c[:, None, 1] - c[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        pair_viol = (rs - d)[iu]
        wall_viol = np.stack([
            r - c[:, 0],
            r - (1.0 - c[:, 0]),
            r - c[:, 1],
            r - (1.0 - c[:, 1]),
        ], axis=1)
        maxp = pair_viol.max() if pair_viol.size else np.longdouble(-1)
        maxw = wall_viol.max()
        if maxp <= 0 and maxw <= 0:
            break
        if maxp > 0:
            for idx in np.where(pair_viol > 0)[0]:
                i, j = iu[0][idx], iu[1][idx]
                excess = (rs[i, j] - d[i, j]) * np.longdouble(0.5) + eps
                r[i] = r[i] - excess
                r[j] = r[j] - excess
        if maxw > 0:
            for i in range(n):
                for k in range(4):
                    if wall_viol[i, k] > 0:
                        r[i] = r[i] - (wall_viol[i, k] + eps)
        r = np.maximum(r, np.longdouble(1e-12))
    return np.column_stack([np.asarray(c, dtype=float),
                            np.asarray(r, dtype=float)])


def _longdouble_inflate(out):
    """Final inflation: set each radius to max allowable at fixed centers,
    iterate until no change, then shrink by 1e-15."""
    n = out.shape[0]
    c = out[:, :2].astype(np.longdouble)
    r = out[:, 2].astype(np.longdouble)
    iu = np.triu_indices(n, 1)
    for _ in range(1000):
        dx = c[:, None, 0] - c[None, :, 0]
        dy = c[:, None, 1] - c[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy)
        # max allowable radius from walls
        wall_max = np.minimum(np.minimum(c[:, 0], np.longdouble(1.0) - c[:, 0]),
                              np.minimum(c[:, 1], np.longdouble(1.0) - c[:, 1]))
        # max allowable from pairs: r_i <= d_ij - r_j
        pair_max = np.full(n, np.longdouble(np.inf))
        for k, (i, j) in enumerate(zip(iu[0], iu[1])):
            dij = d[i, j]
            if dij - r[j] < pair_max[i]:
                pair_max[i] = dij - r[j]
            if dij - r[i] < pair_max[j]:
                pair_max[j] = dij - r[i]
        new_r = np.minimum(wall_max, pair_max)
        new_r = np.maximum(new_r, np.longdouble(1e-12))
        # only increase (inflation)
        changed = np.any(new_r > r + np.longdouble(1e-20))
        r = np.maximum(r, new_r)
        if not changed:
            break
    # shrink by 1e-15 for safety
    r = r - np.longdouble(1e-15)
    r = np.maximum(r, np.longdouble(1e-12))
    return np.column_stack([np.asarray(c, dtype=float),
                            np.asarray(r, dtype=float)])


def construct(budget_seconds, start):
    t0 = time.process_time()
    n = 26
    rng = np.random.default_rng(987654321)

    if start is not None and np.asarray(start).shape == (n, 3):
        base = _repair(np.asarray(start, dtype=float))
    else:
        counts = [4, 5, 4, 5, 4, 4]
        r = 1.0 / (2.0 + np.sqrt(3.0) * 5.0)
        pts = []
        for k, cnt in enumerate(counts):
            y = r + k * np.sqrt(3.0) * r
            for j in range(cnt):
                x = 0.5 - (cnt - 1) * r + 2.0 * r * j
                pts.append((x, y, r))
        base = _repair(np.array(pts[:n]))

    base = _lp_polish(base)

    best_out = base.copy()
    best_score = np.sum(base[:, 2])

    def to_v(out):
        return np.concatenate([out[:, :2].ravel(), out[:, 2]])

    def try_candidate(cand):
        nonlocal best_out, best_score
        cand = _lp_polish(cand)
        s = np.sum(cand[:, 2])
        if s > best_score:
            best_score = s
            best_out = cand.copy()
            return True
        return False

    v = _slsqp_polish(to_v(base), n)
    c, r = _unpack(v, n)
    try_candidate(np.column_stack([c, r]))

    deadline = budget_seconds * 0.92

    rA_vals = [0.085, 0.095, 0.105, 0.115]
    ratio_vals = [0.75, 0.85, 0.95, 1.0]
    gap_mults = [0.5, 1.0, 1.5]

    patterns = []
    for nrows in (5, 6, 7):
        for comp in _compositions(n, nrows, 3, 7):
            patterns.append(comp)

    def pat_score(pat):
        best = -1.0
        for rA in rA_vals:
            for ratio in ratio_vals:
                h = sum((rA if k % 2 == 0 else rA * ratio) for k in range(len(pat)))
                if 2 * h <= 1.0:
                    s = 0.0
                    for k, cnt in enumerate(pat):
                        rk = rA if k % 2 == 0 else rA * ratio
                        if cnt * 2 * rk <= 1.0 + 1e-9:
                            s += cnt * rk
                    best = max(best, s)
        return best

    patterns.sort(key=pat_score, reverse=True)

    seeds = []

    for pat in patterns:
        if time.process_time() - t0 >= deadline * 0.4:
            break
        for rA in rA_vals:
            if time.process_time() - t0 >= deadline * 0.4:
                break
            for ratio in ratio_vals:
                if time.process_time() - t0 >= deadline * 0.4:
                    break
                centers = _alt_row_seed(pat, rA, ratio)
                if centers.shape[0] != n:
                    continue
                if np.any(centers < -1e-9) or np.any(centers > 1.0 + 1e-9):
                    continue
                radii = _lp_radii(centers)
                cand = _repair(np.column_stack([centers, radii]))
                v = _slsqp_polish(to_v(cand), n)
                c, r = _unpack(v, n)
                cand = np.column_stack([c, r])
                if try_candidate(cand):
                    seeds.append(best_out.copy())

    for pat in patterns:
        if time.process_time() - t0 >= deadline * 0.85:
            break
        nrows = len(pat)
        for rA in rA_vals:
            if time.process_time() - t0 >= deadline * 0.85:
                break
            for ratio in ratio_vals:
                if time.process_time() - t0 >= deadline * 0.85:
                    break
                gap_rows = [k for k, cnt in enumerate(pat) if cnt >= 3]
                if not gap_rows:
                    continue
                combos = []
                for k in gap_rows:
                    cnt = pat[k]
                    for gp in range(cnt - 1):
                        for gm in gap_mults:
                            combos.append((k, gp, gm))
                rng.shuffle(combos)
                for (k, gp, gm) in combos[:12]:
                    if time.process_time() - t0 >= deadline * 0.85:
                        break
                    gap_spec = {k: (gp, gm)}
                    centers = _alt_row_seed(pat, rA, ratio, gap_spec)
                    if centers.shape[0] != n:
                        continue
                    if np.any(centers < -1e-9) or np.any(centers > 1.0 + 1e-9):
                        continue
                    radii = _lp_radii(centers)
                    cand = _repair(np.column_stack([centers, radii]))
                    v = _slsqp_polish(to_v(cand), n)
                    c, r = _unpack(v, n)
                    cand = np.column_stack([c, r])
                    if try_candidate(cand):
                        seeds.append(best_out.copy())

    swap_deadline = deadline * 0.95
    improved = True
    swap_round = 0
    while improved and time.process_time() - t0 < swap_deadline:
        improved = False
        swap_round += 1
        cur = best_out.copy()
        rows = _cluster_rows(cur[:, :2])
        for ri in range(len(rows) - 1):
            if time.process_time() - t0 >= swap_deadline:
                break
            swapped = _try_swap(cur[:, :2], rows, ri)
            if swapped is None:
                continue
            radii = _lp_radii(swapped)
            cand = _repair(np.column_stack([swapped, radii]))
            v = _slsqp_polish(to_v(cand), n)
            c, r = _unpack(v, n)
            cand = np.column_stack([c, r])
            if try_candidate(cand):
                improved = True
                seeds.append(best_out.copy())
                break
        if swap_round > 30:
            break

    while time.process_time() - t0 < deadline:
        lo, hi = np.log(0.005), np.log(0.06)
        sigma = np.exp(rng.uniform(lo, hi))
        src = best_out if (rng.random() < 0.7 or not seeds) else seeds[rng.integers(len(seeds))]
        pert = src.copy()
        pert[:, 0] += rng.normal(0, sigma, n)
        pert[:, 1] += rng.normal(0, sigma, n)
        scale = rng.uniform(0.97, 1.0, n)
        pert[:, 2] *= scale
        pert = _repair(pert)
        if time.process_time() - t0 >= deadline:
            break
        v = _slsqp_polish(to_v(pert), n)
        c, r = _unpack(v, n)
        try_candidate(np.column_stack([c, r]))

    out = _lp_polish(best_out)
    if np.sum(out[:, 2]) < best_score:
        out = best_out.copy()

    # High-precision minimal repair (no uniform shrink).
    repaired = _highprec_repair(out)
    if np.sum(repaired[:, 2]) >= np.sum(out[:, 2]) - 1e-9:
        out = repaired

    # Final longdouble inflation at fixed centers.
    inflated = _longdouble_inflate(out)
    if np.sum(inflated[:, 2]) >= np.sum(out[:, 2]) - 1e-9:
        out = inflated

    # Final exact verification with longdouble; only shrink if truly needed.
    c = out[:, :2].astype(np.longdouble)
    r = out[:, 2].astype(np.longdouble)
    n = out.shape[0]
    iu = np.triu_indices(n, 1)
    for _ in range(50):
        dx = c[:, None, 0] - c[None, :, 0]
        dy = c[:, None, 1] - c[None, :, 1]
        d = np.sqrt(dx * dx + dy * dy)
        rs = r[:, None] + r[None, :]
        pv = (rs - d)[iu]
        wv = np.stack([r - c[:, 0], r - (1.0 - c[:, 0]),
                       r - c[:, 1], r - (1.0 - c[:, 1])], axis=1)
        if pv.max() <= 0 and wv.max() <= 0:
            break
        for idx in np.where(pv > 0)[0]:
            i, j = iu[0][idx], iu[1][idx]
            ex = (rs[i, j] - d[i, j]) * np.longdouble(0.5) + np.longdouble(1e-18)
            r[i] -= ex
            r[j] -= ex
        for i in range(n):
            for k in range(4):
                if wv[i, k] > 0:
                    r[i] -= (wv[i, k] + np.longdouble(1e-18))
        r = np.maximum(r, np.longdouble(1e-12))
    out = np.column_stack([np.asarray(c, dtype=float),
                           np.asarray(r, dtype=float)])
    return out
