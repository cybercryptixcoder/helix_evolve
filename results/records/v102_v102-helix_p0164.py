# v10.2 seed 1: first above OpenEvolve (0.9449)
# Run: results/v102/v102-helix   program p0164   round 27   written by: wide loop   parent: p0161
# Score R = 0.9456625918821675   steps n = 50000   CPU seconds used: 144.56
# Extracted verbatim from results/v102/v102-helix/programs/ (gzipped parts);
# the model calls of that round: results/v102/v102-helix/trace/part-0003.jsonl.gz
# Its intent, as the agent wrote it: Added a cheap deterministic knot-top refinement step after each Dinkelbach cycle, plus more diverse multi-scale kicks, to squeeze extra R from the plateau.

import numpy as np
import time
from scipy.optimize import minimize


def _knot_R(f):
    n = len(f)
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    F = np.fft.rfft(f, nfft)
    conv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
    L = np.concatenate(([0.0], conv, [0.0]))
    sq = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    l1 = np.sum(f) ** 2
    linf = np.max(L)
    if linf <= 0 or l1 <= 0:
        return 0.0
    return sq / (l1 * linf)


def _phi_and_grad(f, beta, lam):
    n = len(f)
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    F = np.fft.rfft(f, nfft)
    conv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
    L = np.concatenate(([0.0], conv, [0.0]))
    num = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    m = np.max(L)
    e = np.exp(beta * (L - m))
    s = np.sum(e)
    lse = m + np.log(s) / beta
    phi = lam * lse - num
    dnum = np.zeros_like(L)
    dnum[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    dnum[1:] += (2.0 * L[1:] + L[:-1]) / 3.0
    w = lam * (e / s) - dnum
    wi = w[1:-1]
    fr = f[::-1]
    Wf = np.fft.rfft(wi, nfft)
    Fr = np.fft.rfft(fr, nfft)
    corr = np.fft.irfft(Wf * Fr, nfft)
    grad = 2.0 * corr[n - 1:2 * n - 1]
    return phi, grad, L


def _dinkelbach(f0, time_limit, beta_lo, beta_hi, global_best,
                ftol=1e-15, gtol=1e-13, maxiter=400, beta_pin=None,
                pin_frac=0.0, t_off=None):
    n = len(f0)
    f = np.maximum(f0, 0.0)
    s = f.sum()
    f = f / s if s > 0 else np.ones(n) / n
    best_R = _knot_R(f)
    if best_R > global_best[0]:
        global_best = (best_R, f.copy())
    t0 = time.process_time() if t_off is None else t_off
    while True:
        el = time.process_time() - t0
        if el > time_limit:
            break
        frac = min(el / max(time_limit, 1e-9), 1.0)
        if beta_pin is not None and frac >= (1.0 - pin_frac):
            beta = beta_pin
        else:
            eff = frac / max(1.0 - pin_frac, 1e-9) if beta_pin is not None else frac
            eff = min(eff, 1.0)
            beta = beta_lo * (beta_hi / beta_lo) ** eff
        lam = _knot_R(f)

        def obj(x):
            fx = np.maximum(x, 0.0)
            sx = fx.sum()
            if sx <= 0:
                return 1e10, np.zeros(n)
            fx = fx / sx
            phi, g, L = _phi_and_grad(fx, beta, lam)
            gx = (g - np.dot(g, fx)) / sx
            return phi, gx

        try:
            res = minimize(obj, f, jac=True, method='L-BFGS-B',
                           bounds=[(0, None)] * n,
                           options={'maxiter': maxiter, 'ftol': ftol, 'gtol': gtol})
            fnew = np.maximum(res.x, 0.0)
            sx = fnew.sum()
            if sx > 0:
                fnew = fnew / sx
                Rnew = _knot_R(fnew)
                if Rnew > global_best[0]:
                    global_best = (Rnew, fnew.copy())
                f = fnew
        except Exception:
            break
    return global_best


def _refine_knots(h, R, iters=6):
    # Exact local refinement on the active knot-pair formulation:
    # adjust h so the flat top of f*f widens & stays high (smooths the tip).
    # Small, cheap, deterministic polish via reweighting toward the plateau.
    n = len(h)
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    best = h.copy()
    bestR = R
    for _ in range(iters):
        F = np.fft.rfft(best, nfft)
        conv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
        L = np.concatenate(([0.0], conv, [0.0]))
        m = np.max(L)
        # weight indices near the top: push them up, others down slightly
        wgt = np.exp(-((L - m) / (0.02 * m + 1e-12)) ** 2)
        # backprop a mild boost of the top region into h via correlation trick
        wi = wgt[1:-1]
        fr = best[::-1]
        Wf = np.fft.rfft(wi, nfft)
        Fr = np.fft.rfft(fr, nfft)
        corr = np.fft.irfft(Wf * Fr, nfft)
        g = 2.0 * corr[n - 1:2 * n - 1]
        g = g - np.mean(g)
        cand = np.maximum(best + 1e-4 * g * (np.max(best) / (np.max(np.abs(g)) + 1e-12)), 0.0)
        s = cand.sum()
        if s <= 0:
            break
        cand = cand / s
        Rc = _knot_R(cand)
        if Rc > bestR:
            bestR = Rc
            best = cand
        else:
            break
    return best, bestR


def _build_seed(n, P, m, K):
    x = (np.arange(n) + 0.5) / n
    i0 = int(round(0.02 * n))
    i1 = int(round(0.28 * n))
    comb = np.zeros(n)
    idx = np.arange(i0, i1)
    if len(idx) > 0:
        t = ((idx - i0) % P) / float(P)
        val = np.maximum(0.0, np.cos(np.pi * (t - 0.5) / 0.7)) ** 2
        env = np.exp(-((x[idx] - 0.15) / 0.15) ** 2)
        comb[idx] = val * env
    ramp = np.zeros(n)
    if K > 0:
        pos = np.linspace(0.34, 0.98, K)
        hw = np.linspace(0.002, 0.010, K)
        amp = np.linspace(0.5, 0.02, K)
        for p, w, a in zip(pos, hw, amp):
            d = np.abs(x - p)
            mask = d < w
            ramp[mask] += a * (0.5 * (1.0 + np.cos(np.pi * d[mask] / w)))
    csum = comb.sum()
    rsum = ramp.sum()
    if csum > 0 and rsum > 0:
        target_c = (m / (1.0 - m)) * rsum
        comb = comb * (target_c / csum)
    h = comb + ramp
    s = h.sum()
    if s > 0:
        h = h / s
    return h


def construct(budget_seconds, start):
    t_start = time.process_time()
    total = budget_seconds - 4.0
    if total <= 0:
        total = max(budget_seconds * 0.5, 0.1)

    def elapsed():
        return time.process_time() - t_start

    def remaining():
        return total - elapsed()

    start_arr = None
    start_R = -1.0
    if start is not None:
        try:
            a = np.asarray(start, dtype=float).ravel()
            a = np.maximum(a, 0.0)
            s = a.sum()
            if s > 0:
                start_arr = a.copy()
                start_R = _knot_R(a)
        except Exception:
            start_arr = None

    n = 50000

    best_R = -1.0
    best_h = None
    if start_arr is not None and start_R > best_R:
        best_R = start_R
        best_h = start_arr.copy()

    use_seeds = (start_arr is None) or (start_R < 0.90)

    if use_seeds:
        seeds = []
        for P in (100, 140, 200):
            for m in (0.25, 0.32):
                for K in (50, 80):
                    h = _build_seed(n, P, m, K)
                    R = _knot_R(h)
                    seeds.append((R, P, m, K, h))
        seeds.sort(key=lambda t: -t[0])
        top = seeds[:2]
        for rank, (R0, P, m, K, h0) in enumerate(top):
            if remaining() < 10.0:
                break
            slice_t = min(30.0, max(remaining() - 40.0, 5.0))
            gb = (best_R, best_h.copy() if best_h is not None else h0.copy())
            gb = _dinkelbach(h0, slice_t, 1e6, 1e12, gb,
                             ftol=1e-16, gtol=1e-14, maxiter=300,
                             beta_pin=1e12, pin_frac=0.1)
            if gb[0] > best_R:
                best_R, best_h = gb[0], gb[1].copy()
            print(f"seed {rank}: R={gb[0]:.6f}")

    if best_h is not None:
        cur_R, cur_h = best_R, best_h.copy()
        rem = remaining()
        slice_t = max(5.0, rem * 0.30)
        gb = (cur_R, cur_h.copy())
        gb = _dinkelbach(cur_h, slice_t, 1e6, 1e13, gb,
                         ftol=1e-16, gtol=1e-14, maxiter=500)
        cur_R, cur_h = gb
        if cur_R > best_R:
            best_R, best_h = cur_R, cur_h.copy()
        print(f"anneal: R={cur_R:.6f}")

        cyc = 0
        while remaining() > 3.0:
            h = cur_h.copy()
            H = np.fft.rfft(h)
            nmodes = len(H)
            nlow = max(2, int(0.05 * nmodes))
            # vary kick scale & mode count for diversity across cycles
            scale = 1.5e-3 * (1.0 + (cyc % 4)) * np.max(h)
            nlow_c = max(2, nlow + (cyc % 3) * max(1, nlow // 4))
            rng = np.random.default_rng(7919 + cyc)
            kick = rng.standard_normal(nlow_c) * scale
            H[:nlow_c] += kick
            h2 = np.fft.irfft(H, len(h))
            h2 = np.maximum(h2, 0.0)
            s = h2.sum()
            if s > 0:
                h2 = h2 / s
            if _knot_R(h2) < cur_R * 0.995:
                h2 = 0.7 * cur_h + 0.3 * h2
                s = h2.sum()
                if s > 0:
                    h2 = h2 / s
            rep_t = min(max(remaining() * 0.5, 3.0), 25.0)
            gb = (best_R, best_h.copy() if best_h is not None else h2.copy())
            gb = _dinkelbach(h2, rep_t, 1e10, 1e14, gb,
                             ftol=1e-16, gtol=1e-14, maxiter=400,
                             beta_pin=1e14, pin_frac=0.6)
            if gb[0] > cur_R:
                cur_R, cur_h = gb[0], gb[1].copy()
            if cur_R > best_R:
                best_R, best_h = cur_R, cur_h.copy()
            # cheap knot refinement
            if remaining() > 5.0:
                hr, Rr = _refine_knots(cur_h, cur_R)
                if Rr > cur_R:
                    cur_R, cur_h = Rr, hr
                if cur_R > best_R:
                    best_R, best_h = cur_R, cur_h.copy()
            cyc += 1
            print(f"cycle {cyc-1}: R={best_R:.6f}")

    if best_h is None:
        best_h = np.ones(n) / n

    s = best_h.sum()
    if s > 0:
        best_h = best_h / s

    if start_arr is not None and start_R > best_R:
        return {"best": start_arr, "alternative": best_h}
    return best_h
