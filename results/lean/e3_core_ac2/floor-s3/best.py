import numpy as np
import time

def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 3.0
    try:
        from scipy.optimize import minimize
        have_scipy = True
    except Exception:
        have_scipy = False

    def R_of(h):
        h = np.asarray(h, dtype=float)
        s = h.sum()
        if s <= 0:
            return -1.0
        c = np.convolve(h, h)
        L = np.empty(c.size + 2)
        L[0] = 0.0; L[1:-1] = c; L[-1] = 0.0
        a = L[:-1]; b = L[1:]
        num = np.sum(a*a + a*b + b*b) / 3.0
        lmax = L.max()
        den = s*s*lmax
        if den <= 0:
            return -1.0
        return num / den

    best = None
    bestR = -1.0
    if start is not None:
        h = np.asarray(start, dtype=float).ravel()
        if h.size > 0 and h.sum() > 0 and np.all(h >= 0):
            best = h.copy()
            bestR = R_of(best)
    if best is None:
        N = 2000
        x = np.linspace(-1.0, 1.0, N)
        for p in [1.0, 2.0]:
            for w in [0.9, 1.1]:
                h = np.exp(-np.abs(x/w)**p)
                r = R_of(h)
                if r > bestR:
                    bestR = r; best = h.copy()
    if best is None:
        best = np.ones(50); bestR = R_of(best)

    best = best / max(best.max(), 1e-300)
    m = best.size

    def normalize(h):
        s = h.sum()
        if s <= 0:
            return None
        return h / s * m

    def R_soft_and_grad(h, beta):
        h = np.asarray(h, dtype=float)
        s = h.sum()
        if s <= 0:
            return -1.0, None
        c = np.convolve(h, h)
        L = np.empty(c.size + 2)
        L[0] = 0.0; L[1:-1] = c; L[-1] = 0.0
        a = L[:-1]; b = L[1:]
        num = np.sum(a*a + a*b + b*b) / 3.0
        z = beta * L
        zmax = z.max()
        w = np.exp(z - zmax)
        Z = w.sum()
        smax = (w * L).sum() / Z
        den = s*s*smax
        if den <= 0:
            return -1.0, None
        R = num / den
        gL = np.zeros_like(L)
        gL[:-1] += (2*a + b) / 3.0
        gL[1:] += (a + 2*b) / 3.0
        g_inner = gL[1:-1]
        dnum = 2.0 * np.convolve(g_inner, h[::-1], mode='valid')
        p = w / Z
        dsmax = p * (1.0 + beta * (L - smax))
        dsmax_inner = dsmax[1:-1]
        dlmax = 2.0 * np.convolve(dsmax_inner, h[::-1], mode='valid')
        if dlmax.size != h.size:
            tmp = np.zeros(h.size)
            n = min(dlmax.size, h.size)
            tmp[:n] = dlmax[:n]
            dlmax = tmp
        dden = 2.0*s*smax + s*s*dlmax
        grad = (dnum*den - num*dden) / (den*den)
        return R, grad

    cur_beta = [200.0]

    def negR_flat(x):
        h = np.maximum(x, 0.0)
        s = h.sum()
        if s <= 0:
            return 1.0, np.zeros_like(x)
        R, g = R_soft_and_grad(h, beta=cur_beta[0])
        return -R, -g * (x > 0)

    def run_lbfgs(x0, maxiter, ftol=1e-16, beta=200.0):
        if not have_scipy:
            return None, -1.0
        cur_beta[0] = beta
        res = minimize(negR_flat, x0, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'ftol': ftol, 'gtol': 1e-13,
                                'maxcor': 40, 'maxls': 80})
        h = np.maximum(res.x, 0.0)
        if h.sum() <= 0:
            return None, -1.0
        h = normalize(h)
        return h, R_of(h)

    cur = normalize(best.copy())
    curR = R_of(cur) if cur is not None else bestR

    # Aggressive beta ladder: many small steps to reach very high beta smoothly.
    if have_scipy and time.process_time() < deadline:
        x_cur = cur.copy()
        betas = [10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0, 1e4, 3e4, 1e5, 3e5, 1e6, 3e6, 1e7]
        for beta in betas:
            if time.process_time() >= deadline - 2.0:
                break
            hl, rl = run_lbfgs(x_cur, maxiter=600, beta=beta)
            if hl is not None:
                x_cur = hl
                if rl > bestR:
                    bestR = rl; best = hl.copy()
                curR = max(curR, rl)

    rng = np.random.default_rng(24680)
    cur = best.copy()
    curR = R_of(cur)

    stall = 0
    while time.process_time() < deadline - 0.5:
        frac = (time.process_time() - t0) / max(budget_seconds, 1e-9)
        improved = False
        choice = rng.random()
        if choice < 0.5:
            blk = max(2, m // 400)
        elif choice < 0.85:
            blk = max(2, m // 100)
        else:
            blk = max(2, m // 40)
        i0 = int(rng.integers(0, m - blk + 1))
        base = cur[i0:i0+blk].copy()
        best_local = curR
        best_blk = base
        scale = base.max() + 1e-12
        amps = [0.0005, 0.002, 0.008, 0.03, 0.1] if frac < 0.6 else [0.0002, 0.001, 0.004, 0.015]
        for amp in amps:
            for sign in [1.0, -1.0]:
                trial = cur.copy()
                trial[i0:i0+blk] = np.maximum(base + sign*amp*scale, 0.0)
                r = R_of(trial)
                if r > best_local:
                    best_local = r
                    best_blk = trial[i0:i0+blk].copy()
                    improved = True
            fac = 1.0 + amp * rng.standard_normal(blk)
            trial = cur.copy()
            trial[i0:i0+blk] = np.maximum(base * fac, 0.0)
            r = R_of(trial)
            if r > best_local:
                best_local = r
                best_blk = trial[i0:i0+blk].copy()
                improved = True
        if improved:
            cur[i0:i0+blk] = best_blk
            curR = best_local
            if curR > bestR:
                bestR = curR; best = cur.copy()
            stall = 0
        else:
            stall += 1
            if stall > 120:
                if have_scipy:
                    hl, rl = run_lbfgs(cur, maxiter=400, beta=1e5)
                    if hl is not None and rl > curR:
                        cur = hl; curR = rl
                        if rl > bestR:
                            bestR = rl; best = hl.copy()
                stall = 0
                if time.process_time() > deadline - 3.0:
                    break

    # Final polishing: climb to very high beta for near-exact max.
    if have_scipy:
        for beta in [1e7, 3e7, 1e8, 3e8]:
            if time.process_time() > deadline - 0.4:
                break
            hl, rl = run_lbfgs(best.copy(), maxiter=8000, ftol=1e-17, beta=beta)
            if hl is not None and rl > bestR:
                bestR = rl; best = hl.copy()

    best = np.maximum(best, 0.0)
    if best.sum() <= 0:
        best = np.ones(50)
    if best.size > 50000:
        best = best[:50000]
    return best
