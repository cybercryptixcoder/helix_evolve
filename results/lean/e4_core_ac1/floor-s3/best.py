import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.8

    if start is not None:
        h0 = np.asarray(start, dtype=float).copy()
        if h0.ndim != 1 or h0.size == 0 or not np.all(np.isfinite(h0)) or h0.sum() <= 0:
            h0 = np.ones(50)
    else:
        h0 = np.ones(50)
    h0 = np.maximum(h0, 0.0)
    if h0.sum() <= 0:
        h0 = np.ones(50)

    def C_of(h):
        s = h.sum()
        N = len(h)
        if s <= 0 or N == 0:
            return np.inf
        return 2.0 * N * np.max(np.convolve(h, h)) / (s * s)

    def resample(h, newN):
        N = len(h)
        if N == newN:
            return h.copy()
        cum = np.concatenate([[0.0], np.cumsum(h)])
        edges = np.linspace(0.0, N, newN + 1)
        out = np.empty(newN)
        for j in range(newN):
            a, b = edges[j], edges[j + 1]
            ia, ib = int(np.floor(a)), int(np.floor(b))
            if ia == ib:
                out[j] = h[ia] * (b - a)
            else:
                val = h[ia] * (ia + 1 - a)
                if ib > ia + 1:
                    val += (cum[ib] - cum[ia + 1])
                if ib < N:
                    val += h[ib] * (b - ib)
                out[j] = val
        out = np.maximum(out, 0.0)
        if out.sum() > 0:
            out *= h.sum() / out.sum()
        return out

    def exact_descent(h, end_time, rounds=400):
        """Subgradient descent on the exact max with momentum + adaptive step."""
        h = np.maximum(np.asarray(h, dtype=float), 0.0)
        s = h.sum()
        if s <= 0:
            return np.ones(len(h)), np.inf
        h = h / s
        N = len(h)
        conv = np.convolve(h, h)
        bestC = 2.0 * N * conv.max()
        best = h.copy()
        step = 0.01
        vel = np.zeros(N)
        mom = 0.6
        for it in range(rounds):
            if time.process_time() >= end_time:
                break
            M = conv.max()
            band = 1e-6 * max(M, 1e-30)
            active = np.where(conv >= M - band)[0]
            g = np.zeros(N)
            for k in active:
                lo = max(0, k - (N - 1))
                hi = min(N - 1, k)
                idx = np.arange(lo, hi + 1)
                g[idx] += 2.0 * h[k - idx]
            g /= len(active)
            g -= g.mean()
            gn = np.linalg.norm(g)
            if gn < 1e-15:
                break
            g /= gn
            vel = mom * vel - step * g
            improved = False
            for _ls in range(50):
                hn = h + vel
                hn = np.maximum(hn, 0.0)
                sn = hn.sum()
                if sn <= 0:
                    vel *= 0.5
                    step *= 0.5
                    continue
                hn /= sn
                cn = np.convolve(hn, hn)
                Cc = 2.0 * N * cn.max()
                if Cc < bestC - 1e-16:
                    h = hn
                    conv = cn
                    bestC = Cc
                    best = h.copy()
                    improved = True
                    step *= 1.3
                    break
                else:
                    vel *= 0.5
                    step *= 0.5
            if not improved:
                step *= 0.7
                vel *= 0.5
                if step < 1e-14:
                    break
        return best, bestC

    def optimize_smooth(h, end_time, beta_scale=300.0):
        h = np.maximum(np.asarray(h, dtype=float), 0.0)
        s = h.sum()
        if s <= 0:
            return np.ones(len(h)), np.inf
        h = h / s
        N = len(h)

        def unpack(x):
            z = x - x.max()
            e = np.exp(z)
            return e / e.sum()

        def Cval(x):
            hh = unpack(x)
            c = np.convolve(hh, hh)
            return 2.0 * N * c.max()

        def Cval_smooth(x, beta):
            hh = unpack(x)
            c = np.convolve(hh, hh)
            m = c.max()
            w = np.exp(beta * (c - m))
            sm = (c * w).sum() / w.sum()
            return 2.0 * N * sm

        best = h.copy()
        bestC = Cval(np.log(h + 1e-12))
        x = np.log(h + 1e-12)

        betas = [beta_scale, beta_scale * 4, beta_scale * 16, beta_scale * 64, beta_scale * 256]
        for beta in betas:
            if time.process_time() >= end_time:
                break
            def f(xx):
                return Cval_smooth(xx, beta)
            try:
                res = minimize(f, x, method='L-BFGS-B',
                               options={'maxiter': 300, 'ftol': 1e-15, 'gtol': 1e-13})
                x = res.x
            except Exception:
                break
            cand = unpack(x)
            cc = Cval(x)
            if cc < bestC:
                bestC = cc
                best = cand.copy()
        return best, bestC

    def polish(h, end_time):
        h = np.maximum(np.asarray(h, dtype=float), 0.0)
        s = h.sum()
        if s <= 0:
            return np.ones(len(h)), np.inf
        h = h / s
        N = len(h)
        conv = np.convolve(h, h)
        bestC = 2.0 * N * conv.max()
        best = h.copy()

        def try_update(h, conv, s, i, nv):
            old = h[i]
            d = nv - old
            if d == 0.0 or nv < 0:
                return None
            sc = s + d
            if sc <= 0:
                return None
            c = conv.copy()
            a = 2.0 * d
            end = min(i + N, 2 * N - 1)
            c[i:end] += a * h[0:end - i]
            c[2 * i] += d * d
            M = c.max()
            return (2.0 * N * M / (sc * sc), c, sc, nv)

        for scale in (0.03, 0.01, 0.005, 0.002, 0.001, 5e-4, 2e-4, 1e-4,
                      5e-5, 2e-5, 1e-5, 5e-6, 2e-6, 1e-6, 5e-7, 2e-7, 1e-7, 5e-8):
            if time.process_time() >= end_time:
                break
            improved = True
            while improved and time.process_time() < end_time:
                improved = False
                M = conv.max()
                active = np.where(conv >= M * (1.0 - 1e-5))[0]
                cand = np.zeros(N, dtype=bool)
                for k in active:
                    lo = max(0, k - (N - 1))
                    hi = min(N - 1, k)
                    cand[lo:hi + 1] = True
                order = np.where(cand)[0]
                for i in order:
                    if time.process_time() >= end_time:
                        break
                    old = h[i]
                    best_res = None
                    for f in (1.0 + scale, 1.0 - scale, 1.0 + 0.5 * scale, 1.0 - 0.5 * scale):
                        nv = old * f
                        r = try_update(h, conv, s, i, nv)
                        if r is not None and r[0] < bestC - 1e-17:
                            if best_res is None or r[0] < best_res[0]:
                                best_res = r
                    for d in (scale * 0.01, -scale * 0.01):
                        nv = max(0.0, old + d)
                        r = try_update(h, conv, s, i, nv)
                        if r is not None and r[0] < bestC - 1e-17:
                            if best_res is None or r[0] < best_res[0]:
                                best_res = r
                    if best_res is not None:
                        bestC, conv, s, nv = best_res
                        h[i] = nv
                        best = h.copy()
                        improved = True
        return best, bestC

    N0 = len(h0)
    # Broad N search around current best
    candidates = set([N0])
    for dN in (-4, -3, -2, -1, 1, 2, 3, 4, 6, -6, 8, -8):
        n = N0 + dN
        if 4 <= n <= 30000:
            candidates.add(n)
    for n in (40, 45, 50, 55, 60, 65, 70, 80, 90):
        candidates.add(n)
    candidates = sorted(candidates)

    scored = []
    for n in candidates:
        hc = resample(h0, n) if n != N0 else h0.copy()
        if hc.sum() <= 0:
            continue
        hc = hc / hc.sum()
        c = C_of(hc)
        scored.append((c, n, hc))
    scored.sort(key=lambda x: x[0])

    if not scored:
        return np.asarray(h0, dtype=float)

    best_overall = None
    best_overall_C = np.inf

    # Give more weight to top few candidates
    top = scored[:3]
    weights = [1.0, 0.55, 0.3]

    for k, (c0, n, hc) in enumerate(top):
        now = time.process_time()
        if now >= deadline - 0.05:
            break
        frac = weights[k] / sum(weights[:len(top)])
        end_t = now + max(deadline - now, 0.0) * frac
        end_t = min(end_t, deadline)
        h_opt, c_opt = exact_descent(hc, min(end_t, now + 0.35 * (end_t - now)))
        h_opt, c_opt = optimize_smooth(h_opt, min(end_t, now + 0.70 * (end_t - now)))
        h_opt, c_opt = exact_descent(h_opt, min(end_t, now + 0.85 * (end_t - now)), rounds=200)
        h_opt, c_opt = polish(h_opt, end_t)
        c_opt = C_of(h_opt)
        if c_opt < best_overall_C:
            best_overall_C = c_opt
            best_overall = h_opt.copy()

    if best_overall is None:
        best_overall = h0
        best_overall_C = C_of(h0)

    now = time.process_time()
    if now < deadline - 0.05:
        h_fin, c_fin = exact_descent(best_overall, (now + deadline) / 2, rounds=300)
        h_fin, c_fin = polish(h_fin, deadline)
        c_fin = C_of(h_fin)
        if c_fin < best_overall_C:
            best_overall = h_fin
            best_overall_C = c_fin

    return np.asarray(best_overall, dtype=float)
