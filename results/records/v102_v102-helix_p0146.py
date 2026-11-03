# v10.2 seed 1: first above best-of-25,600 (0.9344)
# Run: results/v102/v102-helix   program p0146   round 24   written by: wide loop   parent: p0142
# Score R = 0.9379531778678115   steps n = 50000   CPU seconds used: 127.6
# Extracted verbatim from results/v102/v102-helix/programs/ (gzipped parts);
# the model calls of that round: results/v102/v102-helix/trace/part-0003.jsonl.gz
# Its intent, as the agent wrote it: Optimize at coarse resolutions (800→2000→5000→15000) where L-BFGS-B converges far faster, then progressively upsample and polish to 50000; multiplies effective optimization iterations.

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


def _resample_up(f, n):
    """Upsample coarse f to n by linear interpolation."""
    cur = len(f)
    if cur == n:
        return f.copy()
    if cur > n:
        factor = cur // n
        g = f[:n * factor].reshape(n, factor).sum(axis=1)
        s = g.sum()
        return g / s if s > 0 else g
    # linear interp on cell centers
    xc = (np.arange(cur) + 0.5) / cur
    xn = (np.arange(n) + 0.5) / n
    g = np.interp(xn, xc, f)
    g = np.maximum(g, 0.0)
    s = g.sum()
    return g / s if s > 0 else g


def _pool(f, n):
    cur = len(f)
    if cur == n:
        return f.copy()
    if cur % n == 0:
        factor = cur // n
        g = f.reshape(n, factor).sum(axis=1)
    else:
        xc = (np.arange(cur) + 0.5) / cur
        xn = (np.arange(n) + 0.5) / n
        g = np.interp(xn, xc, f)
        g = np.maximum(g, 0.0)
    s = g.sum()
    return g / s if s > 0 else g


def _build_blueprint(n, x, a0, a1, P, c, w, g, K, m):
    h = np.zeros(n)
    i0 = int(round(a0 * n))
    i1 = int(round(a1 * n))
    if i1 > i0:
        idx = np.arange(i0, i1)
        t = ((idx - i0) % P) / float(P)
        duty = 0.7
        val = np.where(t < duty,
                       0.5 * (1.0 + np.cos(np.pi * (t / duty - 0.5) / 0.5)),
                       0.0)
        env = np.exp(-((x[idx] - c) / w) ** 2)
        h[idx] = val * env
    ramp = np.zeros(n)
    if K > 0:
        pos = np.linspace(g, 0.98, K)
        hw = np.linspace(0.001, 0.008, K)
        amp = np.linspace(0.6, 0.02, K)
        for p, ww, a in zip(pos, hw, amp):
            d = np.abs(x - p)
            mask = d < ww
            if np.any(mask):
                ramp[mask] += a * (0.5 * (1.0 + np.cos(np.pi * d[mask] / ww)))
    csum = h.sum()
    rsum = ramp.sum()
    if csum > 0 and rsum > 0:
        target_c = (m / (1.0 - m)) * rsum
        h = h * (target_c / csum)
    h = h + ramp
    s = h.sum()
    if s > 0:
        h = h / s
    return h


def construct(budget_seconds, start):
    t_start = time.process_time()
    total = budget_seconds - 3.0
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

    NF = 50000
    xf = (np.arange(NF) + 0.5) / NF

    best_R = -1.0
    best_h = None
    if start_arr is not None and start_R > best_R:
        best_R = start_R
        best_h = start_arr.copy()

    # ---- Multi-resolution strategy ----
    # Coarse resolutions to optimize at (fast L-BFGS-B).
    levels = [800, 2000, 5000, 15000]

    # Build seeds at coarse resolution 800
    n0 = levels[0]
    x0 = (np.arange(n0) + 0.5) / n0
    bands = [(0.02, 0.26), (0.02, 0.30), (0.05, 0.30)]
    Ps = [60, 100, 140, 200]
    cws = [(0.14, 0.14), (0.16, 0.18)]
    ms = [0.25, 0.29, 0.34]
    Ks = [50, 80, 120]
    combos = []
    for (a0, a1) in bands:
        for P in Ps:
            for (c, w) in cws:
                for goff in (0.04, 0.08):
                    g = a1 + goff
                    for K in Ks:
                        for m in ms:
                            combos.append((a0, a1, P, c, w, g, K, m))

    seeds = []
    for combo in combos:
        a0, a1, P, c, w, g, K, m = combo
        h = _build_blueprint(n0, x0, a0, a1, P, c, w, g, K, m)
        R = _knot_R(h)
        seeds.append((R, combo, h))
    seeds.sort(key=lambda t: -t[0])
    print(f"coarse grid best R={seeds[0][0]:.6f}")

    # Also include a downsampled start as a seed (very valuable!)
    if start_arr is not None:
        hs = _pool(start_arr, n0)
        seeds.insert(0, (_knot_R(hs), None, hs))

    # Phase A: coarse optimization of top seeds at n0, then refine up levels
    n_seed = 6
    top = seeds[:n_seed]
    # allocate time: coarse phase ~40% of budget
    coarse_deadline = t_start + 0.45 * total

    refined = []  # list of (R, coarse_h)
    for rank, (R0, combo, h0) in enumerate(top):
        if elapsed() > coarse_deadline - 2.0:
            break
        # time slice for this seed's coarse optimization
        n_left = max(1, n_seed - rank)
        slice_t = max(2.0, (coarse_deadline - time.process_time()) / n_left)
        t_slice0 = time.process_time()
        gb = (best_R, best_h.copy() if best_h is not None else h0.copy())
        gb = _dinkelbach(h0, slice_t * 0.7, 1e4, 1e10, gb,
                         ftol=1e-16, gtol=1e-13, maxiter=400,
                         beta_pin=1e10, pin_frac=0.5, t_off=t_slice0)
        cur_R, cur_h = gb
        # a couple of kicks
        cyc = 0
        while time.process_time() - t_slice0 < slice_t - 1.5:
            if elapsed() > coarse_deadline - 1.5:
                break
            h = cur_h.copy()
            rng = np.random.default_rng(700 + cyc + 17 * rank)
            nlow = max(1, int(0.05 * len(h)))
            amp = 3e-3 * np.max(h)
            H = np.fft.rfft(h)
            H[:nlow] += rng.standard_normal(nlow) * amp
            h2 = np.maximum(np.fft.irfft(H, len(h)), 0.0)
            s = h2.sum()
            if s > 0:
                h2 = h2 / s
            gb2 = (cur_R, cur_h.copy())
            rep_t = min(slice_t - (time.process_time() - t_slice0), 4.0)
            if rep_t < 1.0:
                break
            gb2 = _dinkelbach(h2, rep_t, 1e8, 1e10, gb2,
                              ftol=1e-16, gtol=1e-13, maxiter=300,
                              beta_pin=1e10, pin_frac=0.6)
            if gb2[0] > cur_R:
                cur_R, cur_h = gb2
            cyc += 1
        refined.append((cur_R, cur_h))
        print(f"  seed {rank} coarse R={cur_R:.6f}")

    refined.sort(key=lambda t: -t[0])

    # Phase B: progressive upsampling + refinement of best refined seeds
    # Take top 2-3 coarse results and upsample through levels
    n_refine = min(3, len(refined))
    if n_refine == 0:
        refined = [(seeds[0][0], seeds[0][2])]
        n_refine = 1

    # We'll refine the single best to full resolution with most time,
    # and keep others as backups.
    refine_deadline = t_start + 0.88 * total

    def refine_through_levels(h_coarse, deadline):
        """Upsample h_coarse through levels, refining at each."""
        cur_h = h_coarse
        cur_n = len(cur_h)
        cur_R = _knot_R(cur_h)
        nonlocal_best = (cur_R, cur_h.copy())
        for lv in levels:
            if lv <= cur_n:
                continue
            if time.process_time() > deadline:
                break
            h = _resample_up(cur_h, lv)
            R = _knot_R(h)
            if R > nonlocal_best[0]:
                nonlocal_best = (R, h.copy())
            # refine at this level
            rem = deadline - time.process_time()
            if rem < 1.0:
                break
            # proportional time to level
            sl = min(rem * 0.6, 8.0)
            gb = (nonlocal_best[0], nonlocal_best[1].copy())
            gb = _dinkelbach(h, sl, 1e6, 1e12, gb,
                             ftol=1e-16, gtol=1e-13, maxiter=300,
                             beta_pin=1e12, pin_frac=0.6)
            cur_h = gb[1]
            cur_n = len(cur_h)
            cur_R = gb[0]
        # finally upsample to full resolution
        if len(cur_h) < NF:
            hf = _resample_up(cur_h, NF)
            Rf = _knot_R(hf)
            if Rf > nonlocal_best[0]:
                nonlocal_best = (Rf, hf.copy())
            cur_h = hf
        return nonlocal_best

    all_candidates = []
    for i in range(n_refine):
        if remaining() < 8.0:
            break
        R0, h0 = refined[i]
        # split remaining across candidates, giving more to the best
        rem = refine_deadline - time.process_time()
        if rem < 2.0:
            break
        share = rem / (n_refine - i)
        dl = time.process_time() + share
        cand = refine_through_levels(h0, dl)
        all_candidates.append(cand)
        if cand[0] > best_R:
            best_R, best_h = cand[0], cand[1].copy()
        print(f"  refined candidate {i}: R={cand[0]:.6f}")

    # Phase C: final full-resolution polish + kicks
    if best_h is not None and remaining() > 2.0:
        t_final0 = time.process_time()
        final_slice = max(2.0, remaining() - 1.0)
        gb = (best_R, best_h.copy())
        gb = _dinkelbach(best_h, final_slice * 0.55, 1e10, 1e14, gb,
                         ftol=1e-16, gtol=1e-14, maxiter=300,
                         beta_pin=1e14, pin_frac=0.85, t_off=t_final0)
        if gb[0] > best_R:
            best_R, best_h = gb[0], gb[1].copy()
        print(f"final polish: R={best_R:.6f}")

        for k in range(4):
            if remaining() < 2.0:
                break
            el = time.process_time() - t_final0
            if el > final_slice - 1.5:
                break
            h = best_h.copy()
            H = np.fft.rfft(h)
            nlow = max(1, int(0.02 * len(H)))
            amp = 1e-3 * np.max(h)
            rng = np.random.default_rng(9000 + k)
            H[:nlow] += rng.standard_normal(nlow) * amp
            h2 = np.maximum(np.fft.irfft(H, len(h)), 0.0)
            s = h2.sum()
            if s > 0:
                h2 = h2 / s
            gb = (best_R, best_h.copy())
            rep_t = min(4.0, max(final_slice - el - 0.5, 1.0))
            gb = _dinkelbach(h2, rep_t, 1e10, 1e14, gb,
                             ftol=1e-16, gtol=1e-14, maxiter=250,
                             beta_pin=1e14, pin_frac=0.85)
            if gb[0] > best_R:
                best_R, best_h = gb[0], gb[1].copy()
            print(f"final kick {k}: R={best_R:.6f}")

    if best_h is None:
        best_h = _resample_up(seeds[0][2], NF)

    # ensure full resolution
    if len(best_h) < NF:
        best_h = _resample_up(best_h, NF)
    elif len(best_h) > NF:
        best_h = _pool(best_h, NF)

    s = best_h.sum()
    if s > 0:
        best_h = best_h / s

    if start_arr is not None and start_R > best_R:
        return {"best": start_arr, "alternative": best_h}
    return best_h
