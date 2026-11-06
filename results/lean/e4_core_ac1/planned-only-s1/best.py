import numpy as np
import time
from scipy.optimize import minimize, minimize_scalar, linprog


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _lp_trust_step(h, bestC, deadline, K=128):
    N = len(h)
    if N < 2:
        return h, bestC
    while time.process_time() < deadline:
        q = np.convolve(h, h)
        if len(q) < 1:
            break
        if len(q) > K:
            idx = np.argpartition(q, -K)[-K:]
        else:
            idx = np.arange(len(q))
        peaks = idx[np.argsort(q[idx])[::-1]]

        rows = []
        rhs = []
        for p in peaks:
            g = np.zeros(N)
            lo = max(0, p - (N - 1))
            hi = min(N - 1, p)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                g[ii] += h[p - ii]
                lo2 = max(0, p)
                hi2 = min(N - 1, p + N - 1)
                if lo2 <= hi2:
                    jj = np.arange(lo2, hi2 + 1)
                    g[jj] += h[jj - p]
            rows.append(g)
            rhs.append(q[p])

        A_ub = np.array(rows)
        b_ub = np.array(rhs)
        nvar = N + 1
        Aub = np.zeros((K, nvar))
        Aub[:, :N] = A_ub
        Aub[:, N] = -1.0
        bub = -b_ub

        Aeq = np.zeros((1, nvar))
        Aeq[0, :N] = 1.0
        beq = np.array([0.0])

        eps = 0.01 * max(h.max(), 1e-12)
        bounds = [(max(-h[i], -eps), eps) for i in range(N)]
        bounds.append((None, None))

        c = np.zeros(nvar)
        c[N] = 1.0

        try:
            res = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq,
                          bounds=bounds, method='highs')
        except Exception:
            break
        if not res.success:
            break
        delta = res.x[:N]
        if not np.all(np.isfinite(delta)):
            break

        improved = False
        best_cand = None
        best_candC = bestC
        for alpha in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
            cand = h + alpha * delta
            cand = np.maximum(cand, 0.0)
            tot = cand.sum()
            if tot <= 0:
                continue
            cand /= tot
            cc = _C(cand)
            if cc < best_candC - 1e-13:
                best_candC = cc
                best_cand = cand
                improved = True
        if improved and best_cand is not None:
            h = best_cand
            bestC = best_candC
        else:
            break
    return h, bestC


def _active_peak_flow(h, bestC, deadline, K=32,
                      etas=(1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125)):
    N = len(h)
    if N < 2:
        return h, bestC
    while time.process_time() < deadline:
        q = np.convolve(h, h)
        if len(q) < 1:
            break
        if len(q) > K:
            idx = np.argpartition(q, -K)[-K:]
        else:
            idx = np.arange(len(q))
        peaks = idx[np.argsort(q[idx])[::-1]]

        G = np.zeros((len(peaks), N))
        for r, p in enumerate(peaks):
            lo = max(0, p - (N - 1))
            hi = min(N - 1, p)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                G[r, ii] += h[p - ii]
            lo2 = max(0, p)
            hi2 = min(N - 1, p + N - 1)
            if lo2 <= hi2:
                jj = np.arange(lo2, hi2 + 1)
                G[r, jj] += h[jj - p]

        qp = q[peaks]
        w = qp / qp.sum()
        g = w @ G

        d = -g
        d -= d.mean()
        improved = False
        best_cand = None
        best_candC = bestC
        scale = max(np.abs(d).max(), 1e-12)
        for eta in etas:
            cand = h + eta * d / scale * (h.max() if h.max() > 0 else 1.0)
            cand = np.maximum(cand, 0.0)
            tot = cand.sum()
            if tot <= 0:
                continue
            cand /= tot
            cc = _C(cand)
            if cc < best_candC - 1e-13:
                best_candC = cc
                best_cand = cand
                improved = True
        if improved and best_cand is not None:
            h = best_cand
            bestC = best_candC
        else:
            break
    return h, bestC


def _triple_polish(h, bestC, deadline, rng):
    N = len(h)
    if N < 3:
        return h, bestC
    while time.process_time() < deadline:
        i, j, k = rng.integers(0, N, size=3)
        if i == j or j == k or i == k:
            continue

        def obj(x):
            cand = h.copy()
            cand[i] = max(0.0, x[0])
            cand[j] = max(0.0, x[1])
            cand[k] = max(0.0, x[2])
            tot = cand.sum()
            if tot <= 0:
                return 1e9
            cand /= tot
            return _C(cand)

        x0 = np.array([h[i], h[j], h[k]])
        try:
            res = minimize(obj, x0, method='Nelder-Mead',
                           options={'maxiter': 40, 'xatol': 1e-10,
                                    'fatol': 1e-12})
        except Exception:
            continue
        if res.fun < bestC - 1e-13:
            cand = h.copy()
            cand[i] = max(0.0, res.x[0])
            cand[j] = max(0.0, res.x[1])
            cand[k] = max(0.0, res.x[2])
            tot = cand.sum()
            if tot <= 0:
                continue
            cand /= tot
            c = _C(cand)
            if c < bestC - 1e-13:
                h = cand
                bestC = c
    return h, bestC


def _targeted_triple_polish(h, bestC, deadline, rng, K=128, maxiter=60):
    """Targeted triples near high-sensitivity indices."""
    N = len(h)
    if N < 3:
        return h, bestC
    while time.process_time() < deadline:
        q = np.convolve(h, h)
        if len(q) < 1:
            break
        if len(q) > K:
            idx = np.argpartition(q, -K)[-K:]
        else:
            idx = np.arange(len(q))
        peaks = idx[np.argsort(q[idx])[::-1]]

        s = np.zeros(N)
        for p in peaks:
            lo = max(0, p - (N - 1))
            hi = min(N - 1, p)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                s[ii] += h[p - ii]
            lo2 = max(0, p)
            hi2 = min(N - 1, p + N - 1)
            if lo2 <= hi2:
                jj = np.arange(lo2, hi2 + 1)
                s[jj] += h[jj - p]

        abs_s = np.abs(s)
        thresh = np.quantile(abs_s, 0.90)
        cand_idx = np.where(abs_s >= thresh)[0]
        if len(cand_idx) == 0:
            cand_idx = np.arange(N)
        i = int(rng.choice(cand_idx))

        lo = max(0, i - 3)
        hi = min(N - 1, i + 3)
        neigh = np.arange(lo, hi + 1)
        w = abs_s[neigh]
        if w.sum() <= 0:
            w = np.ones(len(neigh))
        w = w / w.sum()
        j = int(rng.choice(neigh, p=w))
        k = int(rng.choice(neigh, p=w))

        if i == j or j == k or i == k:
            continue

        def obj(x):
            cand = h.copy()
            cand[i] = max(0.0, x[0])
            cand[j] = max(0.0, x[1])
            cand[k] = max(0.0, x[2])
            tot = cand.sum()
            if tot <= 0:
                return 1e9
            cand /= tot
            return _C(cand)

        x0 = np.array([h[i], h[j], h[k]])
        try:
            res = minimize(obj, x0, method='Nelder-Mead',
                           options={'maxiter': maxiter, 'xatol': 1e-10,
                                    'fatol': 1e-12})
        except Exception:
            continue
        if res.fun < bestC - 1e-13:
            cand = h.copy()
            cand[i] = max(0.0, res.x[0])
            cand[j] = max(0.0, res.x[1])
            cand[k] = max(0.0, res.x[2])
            tot = cand.sum()
            if tot <= 0:
                continue
            cand /= tot
            c = _C(cand)
            if c < bestC - 1e-13:
                h = cand
                bestC = c
    return h, bestC


def _targeted_quad_polish(h, bestC, deadline, rng, K=128, maxiter=60):
    """Targeted 4-point polish: two-scale neighborhood (+/-3 or +/-8)."""
    N = len(h)
    if N < 4:
        return h, bestC
    while time.process_time() < deadline:
        q = np.convolve(h, h)
        if len(q) < 1:
            break
        if len(q) > K:
            idx = np.argpartition(q, -K)[-K:]
        else:
            idx = np.arange(len(q))
        peaks = idx[np.argsort(q[idx])[::-1]]

        s = np.zeros(N)
        for p in peaks:
            lo = max(0, p - (N - 1))
            hi = min(N - 1, p)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                s[ii] += h[p - ii]
            lo2 = max(0, p)
            hi2 = min(N - 1, p + N - 1)
            if lo2 <= hi2:
                jj = np.arange(lo2, hi2 + 1)
                s[jj] += h[jj - p]

        abs_s = np.abs(s)
        thresh = np.quantile(abs_s, 0.90)
        cand_idx = np.where(abs_s >= thresh)[0]
        if len(cand_idx) == 0:
            cand_idx = np.arange(N)
        i = int(rng.choice(cand_idx))

        # Two-scale neighborhood: +/-3 with prob 0.5, else +/-8.
        radius = 3 if rng.random() < 0.5 else 8
        lo = max(0, i - radius)
        hi = min(N - 1, i + radius)
        neigh = np.arange(lo, hi + 1)
        w = abs_s[neigh]
        if w.sum() <= 0:
            w = np.ones(len(neigh))
        w = w / w.sum()
        j = int(rng.choice(neigh, p=w))
        k = int(rng.choice(neigh, p=w))
        l = int(rng.choice(neigh, p=w))

        if len({i, j, k, l}) < 4:
            continue

        idx4 = [i, j, k, l]

        def obj(x):
            cand = h.copy()
            for t in range(4):
                cand[idx4[t]] = max(0.0, x[t])
            tot = cand.sum()
            if tot <= 0:
                return 1e9
            cand /= tot
            return _C(cand)

        x0 = np.array([h[t] for t in idx4])
        try:
            res = minimize(obj, x0, method='Nelder-Mead',
                           options={'maxiter': maxiter, 'xatol': 1e-10,
                                    'fatol': 1e-12})
        except Exception:
            continue
        if not np.isfinite(res.fun):
            continue
        if res.fun < bestC - 1e-13:
            cand = h.copy()
            for t in range(4):
                cand[idx4[t]] = max(0.0, res.x[t])
            tot = cand.sum()
            if tot <= 0:
                continue
            cand /= tot
            c = _C(cand)
            if c < bestC - 1e-13:
                h = cand
                bestC = c
    return h, bestC


def _pair_sweep(h, bestC, deadline, rng, ds=(1, 2), maxiter=40):
    """Adjacent-pair sweep (from p0154): optimize (h[i], h[i+d]) pairs."""
    N = len(h)
    if N < 2:
        return h, bestC
    for d in ds:
        if d >= N:
            continue
        order = rng.permutation(N - d)
        for i in order:
            if time.process_time() >= deadline:
                return h, bestC
            j = int(i) + d

            def obj(x):
                cand = h.copy()
                cand[i] = max(0.0, x[0])
                cand[j] = max(0.0, x[1])
                tot = cand.sum()
                if tot <= 0:
                    return 1e9
                cand /= tot
                return _C(cand)

            x0 = np.array([h[i], h[j]])
            try:
                res = minimize(obj, x0, method='Nelder-Mead',
                               options={'maxiter': maxiter, 'xatol': 1e-10,
                                        'fatol': 1e-12})
            except Exception:
                continue
            if not np.isfinite(res.fun):
                continue
            if res.fun < bestC - 1e-13:
                cand = h.copy()
                cand[i] = max(0.0, res.x[0])
                cand[j] = max(0.0, res.x[1])
                tot = cand.sum()
                if tot <= 0:
                    continue
                cand /= tot
                cc = _C(cand)
                if cc < bestC - 1e-13:
                    h = cand
                    bestC = cc
    return h, bestC


def _quad_sweep(h, bestC, deadline, rng, maxiter=40):
    """4-point adjacent Nelder-Mead sweep (d=1)."""
    N = len(h)
    if N < 4:
        return h, bestC
    order = rng.permutation(N - 3)
    for i0 in order:
        if time.process_time() >= deadline:
            return h, bestC
        i = int(i0)
        idx = [i, i + 1, i + 2, i + 3]

        def obj(x):
            cand = h.copy()
            for t in range(4):
                cand[idx[t]] = max(0.0, x[t])
            tot = cand.sum()
            if tot <= 0:
                return 1e9
            cand /= tot
            return _C(cand)

        x0 = np.array([h[t] for t in idx])
        try:
            res = minimize(obj, x0, method='Nelder-Mead',
                           options={'maxiter': maxiter, 'xatol': 1e-10,
                                    'fatol': 1e-12})
        except Exception:
            continue
        if not np.isfinite(res.fun):
            continue
        if res.fun < bestC - 1e-13:
            cand = h.copy()
            for t in range(4):
                cand[idx[t]] = max(0.0, res.x[t])
            tot = cand.sum()
            if tot <= 0:
                continue
            cand /= tot
            cc = _C(cand)
            if cc < bestC - 1e-13:
                h = cand
                bestC = cc
    return h, bestC


def _softmax_log_opt(h, bestC, deadline, K=64,
                     betas=(200.0, 1000.0, 5000.0, 20000.0), maxiter=50):
    N = len(h)
    if N < 2:
        return h, bestC
    x = np.log(np.maximum(h, 0.0) + 1e-12)
    x = np.clip(x, -30.0, 5.0)

    def make_obj(beta):
        def obj(xv):
            e = np.exp(np.clip(xv, -30.0, 5.0))
            s = e.sum()
            if s <= 0:
                return 1e9
            q = np.convolve(e, e)
            if len(q) > K:
                idx = np.argpartition(q, -K)[-K:]
                qK = q[idx]
            else:
                qK = q
            m = qK.max()
            lse = m + np.log(np.exp(beta * (qK - m)).sum()) / beta
            return 2.0 * N * lse / (s * s)
        return obj

    bounds = [(-30.0, 5.0)] * N
    for beta in betas:
        if time.process_time() >= deadline:
            break
        obj = make_obj(beta)
        try:
            res = minimize(obj, x, method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': maxiter, 'maxfun': 4 * maxiter,
                                    'ftol': 1e-14, 'gtol': 1e-10})
            if np.all(np.isfinite(res.x)):
                x = np.clip(res.x, -30.0, 5.0)
        except Exception:
            continue
        e = np.exp(np.clip(x, -30.0, 5.0))
        s = e.sum()
        if s > 0:
            cand = e / s
            cc = _C(cand)
            if cc < bestC - 1e-13:
                h = cand
                bestC = cc
    return h, bestC


def _lp_norm_log_opt(h, bestC, deadline, ps=(8, 16, 32, 64, 128),
                     maxiter=60, flow_time=0.5, rng=None,
                     targeted_time=0.7, coord_time=0.5, pair_time=0.3,
                     quad_time=0.3, tquad_time=0.8):
    N = len(h)
    if N < 2:
        return h, bestC
    x = np.log(np.maximum(h, 0.0) + 1e-12)
    x = np.clip(x, -30.0, 5.0)
    bounds = [(-30.0, 5.0)] * N

    for p in ps:
        if time.process_time() >= deadline:
            break

        def obj(xv, p=p):
            e = np.exp(np.clip(xv, -30.0, 5.0))
            s = e.sum()
            if s <= 0:
                return 1e9
            q = np.convolve(e, e)
            m = q.max()
            if m <= 0:
                return 1e9
            lp = m * (np.sum((q / m) ** p)) ** (1.0 / p)
            return 2.0 * N * lp / (s * s)

        try:
            res = minimize(obj, x, method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': maxiter, 'maxfun': 4 * maxiter,
                                    'ftol': 1e-14, 'gtol': 1e-10})
            if np.all(np.isfinite(res.x)):
                x = np.clip(res.x, -30.0, 5.0)
        except Exception:
            continue

        e = np.exp(np.clip(x, -30.0, 5.0))
        s = e.sum()
        if s <= 0:
            continue
        cand = e / s
        cc = _C(cand)
        if cc < bestC - 1e-13:
            h = cand
            bestC = cc

        if time.process_time() < deadline:
            t_flow = min(time.process_time() + flow_time, deadline)
            h, bestC = _active_peak_flow(h, bestC, t_flow, K=32)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)

        if rng is not None and time.process_time() < deadline:
            t_coord = min(time.process_time() + coord_time, deadline)
            h, bestC = _coord_sweep(h, bestC, t_coord, rng)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)

        if rng is not None and time.process_time() < deadline:
            t_pair = min(time.process_time() + pair_time, deadline)
            h, bestC = _pair_sweep(h, bestC, t_pair, rng)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)

        if rng is not None and time.process_time() < deadline:
            t_quad = min(time.process_time() + quad_time, deadline)
            h, bestC = _quad_sweep(h, bestC, t_quad, rng)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)

        # Targeted 4-point polish (two-scale neighborhood) after each Lp stage
        if rng is not None and time.process_time() < deadline:
            t_tq = min(time.process_time() + tquad_time, deadline)
            h, bestC = _targeted_quad_polish(h, bestC, t_tq, rng,
                                             K=128, maxiter=60)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)

        if rng is not None and time.process_time() < deadline:
            t_tri = min(time.process_time() + targeted_time, deadline)
            h, bestC = _targeted_triple_polish(h, bestC, t_tri, rng,
                                               K=128, maxiter=60)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)

        if rng is not None and time.process_time() < deadline:
            t_pair = min(time.process_time() + pair_time, deadline)
            h, bestC = _pair_sweep(h, bestC, t_pair, rng)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)

        if rng is not None and time.process_time() < deadline:
            t_quad = min(time.process_time() + quad_time, deadline)
            h, bestC = _quad_sweep(h, bestC, t_quad, rng)
            x = np.log(np.maximum(h, 0.0) + 1e-12)
            x = np.clip(x, -30.0, 5.0)
    return h, bestC


def _threshold_sparsify(h, bestC, deadline, taus=(1e-5, 3e-5, 1e-4, 3e-4)):
    if h.max() <= 0:
        return h, bestC
    best_h = h
    best_c = bestC
    for tau_rel in taus:
        if time.process_time() >= deadline:
            break
        tau = tau_rel * h.max()
        cand = h.copy()
        cand[cand < tau] = 0.0
        tot = cand.sum()
        if tot <= 0:
            continue
        cand /= tot
        cc = _C(cand)
        t_flow = min(time.process_time() + 0.3, deadline)
        cand2, cc2 = _active_peak_flow(cand, cc, t_flow, K=32)
        if cc2 < best_c - 1e-13:
            best_c = cc2
            best_h = cand2
    return best_h, best_c


def _coord_sweep(h, bestC, deadline, rng):
    N = len(h)
    if N < 1:
        return h, bestC
    order = rng.permutation(N)
    for i in order:
        if time.process_time() >= deadline:
            break
        hi_bound = max(3.0 * h[i], 1e-6)
        if hi_bound <= 0:
            continue

        def obj(x):
            cand = h.copy()
            cand[i] = max(0.0, x)
            tot = cand.sum()
            if tot <= 0:
                return 1e9
            cand /= tot
            return _C(cand)

        try:
            res = minimize_scalar(obj, bounds=(0.0, hi_bound),
                                  method='bounded',
                                  options={'xatol': 1e-12, 'maxiter': 30})
        except Exception:
            continue
        if not np.isfinite(res.fun):
            continue
        if res.fun < bestC - 1e-13:
            x = max(0.0, res.x)
            cand = h.copy()
            cand[i] = x
            tot = cand.sum()
            if tot <= 0:
                continue
            cand /= tot
            cc = _C(cand)
            if cc < bestC - 1e-13:
                h = cand
                bestC = cc
    return h, bestC


def _fourier_perturb(h, rng):
    """Multiply h by exp(0.005 * sum of low-frequency Fourier terms)."""
    N = len(h)
    u = (np.arange(N) + 0.5) / N - 0.5
    a1, b1, a2, b2, a3, b3 = rng.standard_normal(6)
    pert = (a1 * np.sin(2 * np.pi * u) + b1 * np.cos(2 * np.pi * u)
            + a2 * np.sin(4 * np.pi * u) + b2 * np.cos(4 * np.pi * u)
            + a3 * np.sin(6 * np.pi * u) + b3 * np.cos(6 * np.pi * u))
    cand = h * np.exp(0.005 * pert)
    cand = np.maximum(cand, 0.0)
    tot = cand.sum()
    if tot <= 0:
        return h.copy()
    return cand / tot


def construct(budget_seconds, start):
    deadline = min(budget_seconds - 1.0, 19.0)

    if start is not None:
        h = np.asarray(start, dtype=float).copy()
        h = np.maximum(h, 0.0)
    else:
        N0 = 800
        u = (np.arange(N0) + 0.5) / N0 - 0.5
        h = np.maximum(0.01, 1.0 + 0.85 * np.sin(2 * np.pi * u))

    s = h.sum()
    if s <= 0:
        h = np.ones(len(h))
        s = h.sum()
    h = h / s

    bestC = _C(h)
    rng = np.random.default_rng(98765)

    # Phase 0: softmax-smoothed log-height optimization (barrier escape)
    t_sm = min(time.process_time() + 3.0, deadline)
    h, bestC = _softmax_log_opt(h, bestC, t_sm, K=64)

    # Phase 0b: L^p-norm smoothing path
    if time.process_time() < deadline:
        t_lp = min(time.process_time() + 4.0, deadline)
        h, bestC = _lp_norm_log_opt(h, bestC, t_lp, rng=rng,
                                    targeted_time=0.7, coord_time=0.5,
                                    pair_time=0.3, quad_time=0.3,
                                    tquad_time=0.8)

    # Phase 2: alternate LP trust-region, active-peak flow, triple polish.
    while time.process_time() < deadline:
        t_lp = min(time.process_time() + 3.0, deadline)
        h, bestC = _lp_trust_step(h, bestC, t_lp, K=128)
        if time.process_time() >= deadline:
            break
        t_flow = min(time.process_time() + 1.0, deadline)
        h, bestC = _active_peak_flow(h, bestC, t_flow, K=32)
        if time.process_time() >= deadline:
            break
        t_tri = min(time.process_time() + 1.0, deadline)
        h, bestC = _triple_polish(h, bestC, t_tri, rng)
        if time.process_time() >= deadline:
            break
        t_thr = min(time.process_time() + 1.3, deadline)
        h, bestC = _threshold_sparsify(h, bestC, t_thr)

        if time.process_time() >= deadline:
            break
        t_coord = min(time.process_time() + 1.5, deadline)
        while time.process_time() < t_coord:
            h, bestC = _coord_sweep(h, bestC, t_coord, rng)
            if time.process_time() >= t_coord:
                break
            t_pair = min(time.process_time() + 0.3, t_coord)
            h, bestC = _pair_sweep(h, bestC, t_pair, rng)
            if time.process_time() >= t_coord:
                break
            t_quad = min(time.process_time() + 0.3, t_coord)
            h, bestC = _quad_sweep(h, bestC, t_quad, rng)
            if time.process_time() >= t_coord:
                break
            t_f = min(time.process_time() + 0.3, t_coord)
            h, bestC = _active_peak_flow(h, bestC, t_f, K=32)

    # Phase 3: Fourier perturbation + short L^p smoothing.
    while time.process_time() < deadline:
        cand = _fourier_perturb(h, rng)
        cc = _C(cand)
        t_lp = min(time.process_time() + 1.5, deadline)
        cand2, cc2 = _lp_norm_log_opt(
            cand, cc, t_lp,
            ps=(16, 32, 64, 128), maxiter=40, flow_time=0.4,
            rng=rng, targeted_time=0.7, coord_time=0.5, pair_time=0.3,
            quad_time=0.3, tquad_time=0.8)
        if cc2 < bestC - 1e-13:
            h = cand2
            bestC = cc2

    return h
