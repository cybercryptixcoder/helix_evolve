import numpy as np
import time
from scipy.optimize import minimize


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 1.0

    def oot():
        return time.process_time() > deadline

    rng = np.random.default_rng(9133771)
    state = {"best": None, "best_R": -1.0}

    def norm(c):
        c = np.clip(np.asarray(c, dtype=float).ravel(), 0.0, None)
        if c.size == 0:
            return None
        m = c.max()
        if m <= 0 or c.sum() <= 0:
            return None
        return c / m

    def R_from_L(L, s):
        a = L[:-1]; b = L[1:]
        num = np.dot(a, a) + np.dot(a, b) + np.dot(b, b)
        m = L.max()
        if m <= 0 or s <= 0:
            return -1.0
        return (num / 3.0) / (s * s * m)

    def _R(h):
        s = h.sum()
        if s <= 0:
            return -1.0
        return R_from_L(np.convolve(h, h), s)

    def consider(c):
        c = norm(c)
        if c is None:
            return -1.0
        r = _R(c)
        if r > state["best_R"]:
            state["best_R"] = r
            state["best"] = c.copy()
        return r

    if start is not None:
        consider(start)
    if state["best"] is None:
        x = np.linspace(-1, 1, 400)
        consider(np.exp(-0.5 * (x / 0.35) ** 2))
    if state["best"] is None:
        state["best"] = np.ones(200)
        state["best_R"] = _R(state["best"])

    def resample(src, N):
        xs = np.linspace(0, 1, src.size)
        xn = np.linspace(0, 1, N)
        return np.interp(xn, xs, src)

    def grad_R(h, L=None):
        s = h.sum()
        if s <= 0:
            return None, -1.0
        if L is None:
            L = np.convolve(h, h)
        a = L[:-1]; b = L[1:]
        num = np.dot(a, a) + np.dot(a, b) + np.dot(b, b)
        m = L.max()
        if m <= 0:
            return None, -1.0
        denom = 3.0 * s * s * m
        R = num / denom
        dnum = np.zeros_like(L)
        dnum[:-1] += (2.0 * a + b) / 3.0
        dnum[1:] += (a + 2.0 * b) / 3.0
        imax = int(np.argmax(L))
        dR_dL = dnum / denom
        dR_dL[imax] -= num / (3.0 * s * s * m * m)
        dR_ds = -2.0 * num / (3.0 * s * s * s * m)
        g = 2.0 * np.correlate(dR_dL, h, mode='full')[h.size - 1:h.size - 1 + h.size]
        g = g + dR_ds
        return g, R

    def lbfgs_polish(c, end_time, maxiter=800):
        c = norm(c)
        if c is None:
            return None
        c = c.copy()

        def negR_grad(x):
            if oot() or time.process_time() >= end_time:
                raise StopIteration
            h = np.clip(x, 0.0, None)
            L = np.convolve(h, h)
            g, r = grad_R(h, L)
            if g is None:
                return 1e9, np.zeros_like(x)
            return -r, -g

        try:
            res = minimize(negR_grad, c, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * c.size,
                           options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                    'ftol': 1e-16, 'gtol': 1e-13})
            cand = norm(res.x)
            if cand is not None:
                consider(cand)
                return cand
        except StopIteration:
            pass
        except Exception:
            pass
        return c

    def grad_ascent(c, end_time, lr0=0.05, max_iters=5000):
        c = norm(c)
        if c is None:
            return None
        L = np.convolve(c, c)
        r = R_from_L(L, c.sum())
        lr = lr0
        y = c.copy()
        tk = 1.0
        for _ in range(max_iters):
            if time.process_time() >= end_time or oot():
                break
            g, r = grad_R(y, np.convolve(y, y))
            if g is None:
                break
            gn = np.linalg.norm(g)
            if gn < 1e-16:
                break
            improved = False
            for mult in (1.0, 0.5, 0.25, 2.0, 0.1, 0.05, 4.0, 0.02, 0.01, 8.0):
                trial = norm(np.clip(y + (lr * mult / gn) * g, 0.0, None))
                if trial is None:
                    continue
                Lt = np.convolve(trial, trial)
                rt = R_from_L(Lt, trial.sum())
                if rt > r + 1e-16:
                    tk1 = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * tk * tk))
                    y = norm(np.clip(trial + ((tk - 1.0) / tk1) * (trial - c), 0.0, None))
                    c = trial; L = Lt; r = rt
                    tk = tk1
                    lr *= 1.2 * mult
                    improved = True
                    if r > state["best_R"]:
                        state["best_R"] = r
                        state["best"] = c.copy()
                    break
            if not improved:
                lr *= 0.5
                y = c.copy(); tk = 1.0
                if lr < 1e-14:
                    break
        return c

    def refine(c, end_time, step0, use_pairs=True):
        c = norm(c)
        if c is None:
            return None
        L = np.convolve(c, c)
        r = R_from_L(L, c.sum())
        Nc = c.size
        step = step0
        while time.process_time() < end_time and not oot():
            improved = False
            order = rng.permutation(Nc)
            for i in order:
                if time.process_time() >= end_time or oot():
                    break
                old = c[i]
                best_d = 0.0
                best_r = r
                ks = np.arange(i, i + Nc)
                base = L[ks]
                for d in (step, -step, 0.5 * step, -0.5 * step,
                          2.0 * step, -2.0 * step, 0.25 * step, -0.25 * step):
                    v = old + d
                    if v < 0:
                        continue
                    L2 = L.copy()
                    L2[ks] = base + 2.0 * d * c
                    L2[2 * i] += d * d
                    rr = R_from_L(L2, c.sum() + d)
                    if rr > best_r + 1e-16:
                        best_r = rr; best_d = d
                if best_d != 0.0:
                    c[i] = old + best_d
                    L = np.convolve(c, c)
                    r = best_r
                    improved = True
            if use_pairs and not oot() and time.process_time() < end_time:
                for _ in range(max(1, Nc // 2)):
                    if time.process_time() >= end_time or oot():
                        break
                    i, j = rng.integers(0, Nc, 2)
                    if i == j:
                        continue
                    oi, oj = c[i], c[j]
                    best_r = r
                    best_pair = None
                    for amt in (step, -step, 0.5 * step, -0.5 * step):
                        ni = oi - amt; nj = oj + amt
                        if ni < 0 or nj < 0:
                            continue
                        c[i], c[j] = ni, nj
                        rr = _R(c)
                        if rr > best_r + 1e-15:
                            best_r = rr; best_pair = (ni, nj)
                    if best_pair is not None:
                        c[i], c[j] = best_pair
                        r = best_r
                        L = np.convolve(c, c)
                        improved = True
                    else:
                        c[i], c[j] = oi, oj
            if r > state["best_R"]:
                state["best_R"] = r
                state["best"] = c.copy()
            if not improved:
                step *= 0.55
                if step < 1e-13:
                    break
        return c

    def refine_pairs(c, end_time, step0, n_pairs=6000):
        c = norm(c)
        if c is None:
            return None
        L = np.convolve(c, c)
        s = c.sum()
        r = R_from_L(L, s)
        Nc = c.size
        step = step0
        while time.process_time() < end_time and not oot():
            improved = False
            for _ in range(n_pairs):
                if time.process_time() >= end_time or oot():
                    break
                i, j = rng.integers(0, Nc, 2)
                if i == j:
                    continue
                oi, oj = c[i], c[j]
                best_r = r
                best_pair = None
                for amt in (step, -step, 0.5 * step, -0.5 * step,
                            2.0 * step, -2.0 * step):
                    ni = oi + amt; nj = oj - amt
                    if ni < 0 or nj < 0:
                        continue
                    L2 = L.copy()
                    idx_i = np.arange(i, i + Nc)
                    idx_j = np.arange(j, j + Nc)
                    L2[idx_i] += amt * c
                    L2[idx_j] -= amt * c
                    L2[2 * i] += amt * amt
                    L2[2 * j] += amt * amt
                    L2[i + j] -= 2.0 * amt * amt
                    rr = R_from_L(L2, s)
                    if rr > best_r + 1e-16:
                        best_r = rr; best_pair = (ni, nj, L2)
                if best_pair is not None:
                    c[i], c[j] = best_pair[0], best_pair[1]
                    L = best_pair[2]
                    r = best_r
                    improved = True
            if r > state["best_R"]:
                state["best_R"] = r
                state["best"] = c.copy()
            if not improved:
                step *= 0.5
                if step < 1e-14:
                    break
        return c

    def coord_ascent_fd(c, end_time, step0, max_sweeps=30):
        c = norm(c)
        if c is None:
            return None
        r = _R(c)
        Nc = c.size
        step = step0
        for _ in range(max_sweeps):
            if time.process_time() >= end_time or oot():
                break
            improved = False
            order = rng.permutation(Nc)
            for i in order:
                if time.process_time() >= end_time or oot():
                    break
                old = c[i]
                best_v = old
                for d in (step, -step, 0.5 * step, -0.5 * step):
                    v = old + d
                    if v < 0:
                        continue
                    c[i] = v
                    rr = _R(c)
                    if rr > r + 1e-16:
                        r = rr; best_v = v
                c[i] = best_v
                if best_v != old:
                    improved = True
            if r > state["best_R"]:
                state["best_R"] = r
                state["best"] = c.copy()
            if not improved:
                step *= 0.5
                if step < 1e-12:
                    break
        return c

    def merge_tail(c):
        # Try trimming near-zero tails to reduce N; keep if R doesn't drop.
        c = norm(c)
        if c is None:
            return None
        r0 = _R(c)
        N = c.size
        thr = 1e-6
        lo = 0
        hi = N
        while lo < hi and c[lo] < thr:
            lo += 1
        while hi > lo and c[hi - 1] < thr:
            hi -= 1
        if hi - lo >= 2 and (lo > 0 or hi < N):
            cand = norm(c[lo:hi])
            if cand is not None and _R(cand) >= r0 - 1e-12:
                consider(cand)
                return cand
        return c

    total = deadline - t0

    # Stage 1: quick polish of start.
    c = lbfgs_polish(state["best"], t0 + total * 0.08, maxiter=500)
    if c is not None:
        refine(c, t0 + total * 0.14, 0.006, use_pairs=True)
    grad_ascent(state["best"], t0 + total * 0.18, lr0=0.02)
    merge_tail(state["best"])

    # Stage 2: dedicated fine N scan around current best (main new work).
    base_N = state["best"].size
    base = state["best"].copy()
    cand_sizes = set()
    for delta in range(-12, 13):
        cand_sizes.add(base_N + delta)
    for f in (0.94, 0.96, 0.98, 0.99, 1.01, 1.02, 1.04, 1.06, 1.10, 0.90):
        cand_sizes.add(int(round(base_N * f)))
    cand_sizes = sorted(s for s in cand_sizes if 2 <= s <= 50000)
    for Nalt in cand_sizes:
        if oot() or time.process_time() - t0 > total * 0.55:
            break
        cand = resample(base, Nalt)
        consider(cand)
        end = min(deadline, time.process_time() + total * 0.018)
        grad_ascent(cand, end, lr0=0.02)
        refine(cand, end, 0.008, use_pairs=True)

    # Stage 2b: refine_pairs on best after N scan.
    refine_pairs(state["best"], min(deadline, time.process_time() + total * 0.08),
                 0.004, n_pairs=3000)

    # Stage 3: perturb-and-polish around best.
    while not oot() and time.process_time() - t0 < total * 0.85:
        frac = (time.process_time() - t0) / max(1e-9, total)
        c = state["best"].copy()
        nc = c.size
        if rng.random() < 0.5:
            sigma = 0.0005 + 0.006 * (1.0 - frac)
            c = c + rng.normal(0.0, sigma, size=nc)
        else:
            npert = max(1, int(nc * (0.01 + 0.03 * (1.0 - frac))))
            idx = rng.integers(0, nc, npert)
            scale = 0.008 + 0.04 * (1.0 - frac)
            c[idx] *= (1.0 + rng.normal(0.0, scale, npert))
        c = norm(c)
        if c is None:
            continue
        if _R(c) > state["best_R"] - 1.0e-3:
            end = min(deadline, time.process_time() + total * 0.015)
            grad_ascent(c, end, lr0=0.02)
            refine(c, end, 0.008, use_pairs=True)

    # Stage 4: N jitter + coordinate ascent.
    while not oot() and time.process_time() - t0 < total * 0.94:
        base = state["best"]
        nc = base.size
        if rng.random() < 0.5:
            delta = int(rng.integers(-3, 4))
            Nn = max(2, min(50000, nc + delta))
            cand = resample(base, Nn) if Nn != nc else base.copy()
        else:
            cand = base.copy()
        sigma = 0.0005 + 0.0015 * rng.random()
        cand = norm(cand + rng.normal(0.0, sigma, size=cand.size))
        if cand is None:
            continue
        end = min(deadline, time.process_time() + total * 0.015)
        coord_ascent_fd(cand, end, 0.004, max_sweeps=30)

    # Final tight polish.
    lbfgs_polish(state["best"], deadline - 0.4, maxiter=300)
    grad_ascent(state["best"], deadline - 0.15, lr0=0.004)
    refine(state["best"], deadline, 0.0015, use_pairs=True)
    merge_tail(state["best"])

    print("final R ~", state["best_R"], "N =", state["best"].size)
    return state["best"]
