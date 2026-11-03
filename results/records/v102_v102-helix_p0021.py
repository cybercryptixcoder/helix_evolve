# v10.2 seed 1: first above AlphaEvolve May 2025 (0.8962)
# Run: results/v102/v102-helix   program p0021   round 4   written by: deep loop   parent: p0013
# Score R = 0.8976629447098478   steps n = 2048   CPU seconds used: 147.43
# Extracted verbatim from results/v102/v102-helix/programs/ (gzipped parts);
# the model calls of that round: results/v102/v102-helix/trace/part-0001.jsonl.gz
# Its intent, as the agent wrote it: p0013's construction has the right flat two-level f*f (36% of knots within 1% of max, the shape F7 says the optimum has) but is only at n=2048; F3/F23 say a good construction tuned at higher n scores higher, and the Dinkelbach two-term form (lam*LSE - num, F4/F28/F29) polishes it, while FFT-based c…

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


def _num_and_L(f):
    n = len(f)
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    F = np.fft.rfft(f, nfft)
    conv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
    L = np.concatenate(([0.0], conv, [0.0]))
    num = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    return num, L


def _lse(L, beta):
    m = np.max(L)
    return m + np.log(np.sum(np.exp(beta * (L - m)))) / beta


def _phi_and_grad(f, beta, lam):
    """Dinkelbach objective phi = lam*LSE_beta(L) - num, plus grad wrt f."""
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
    # d num / dL_j
    dnum = np.zeros_like(L)
    dnum[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    dnum[1:] += (2.0 * L[1:] + L[:-1]) / 3.0
    # d phi / dL = lam * softmax - dnum
    w = lam * (e / s) - dnum
    wi = w[1:-1]  # length 2n-1
    fr = f[::-1]
    Wf = np.fft.rfft(wi, nfft)
    Fr = np.fft.rfft(fr, nfft)
    corr = np.fft.irfft(Wf * Fr, nfft)
    grad = 2.0 * corr[n - 1:2 * n - 1]
    return phi, grad, L


def _dinkelbach(f0, time_limit, beta_lo, beta_hi, global_best):
    n = len(f0)
    f = np.maximum(f0, 0.0)
    s = f.sum()
    if s <= 0:
        f = np.ones(n) / n
    else:
        f = f / s
    best_R = _knot_R(f)
    if best_R > global_best[0]:
        global_best = (best_R, f.copy())
    t0 = time.process_time()
    round_idx = 0
    while True:
        el = time.process_time() - t0
        if el > time_limit:
            break
        frac = min(el / max(time_limit, 1e-9), 1.0)
        beta = beta_lo * (beta_hi / beta_lo) ** frac
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
                           options={'maxiter': 300, 'ftol': 1e-14, 'gtol': 1e-12})
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
        round_idx += 1
        if round_idx > 20000:
            break
    return global_best


def construct(budget_seconds, start):
    t_start = time.process_time()
    total = budget_seconds - 3.0
    if total <= 0:
        total = max(budget_seconds * 0.5, 0.1)

    rng = np.random.default_rng(20240607)

    # Seed
    if start is not None:
        try:
            f = np.asarray(start, dtype=float).ravel()
            f = np.maximum(f, 0.0)
            s = f.sum()
            if s > 0:
                f = f / s
            else:
                f = None
        except Exception:
            f = None
    else:
        f = None

    if f is None:
        n0 = 2048
        x = (np.arange(n0) + 0.5) / n0
        f = np.zeros(n0)
        for _ in range(8):
            pos = rng.uniform(0.05, 0.95)
            width = rng.uniform(0.01, 0.06)
            f += np.exp(-0.5 * ((x - pos) / width) ** 2)
        f = np.maximum(f, 0.0)
        f = f / f.sum()

    global_best = (_knot_R(f), f.copy())
    print(f"seed: n={len(f)} R={global_best[0]:.6f}")

    stages = [2048, 4096, 8192, 16384]
    shares = [0.15, 0.25, 0.30, 0.30]

    for i, n in enumerate(stages):
        cur_n = len(f)
        if cur_n != n:
            if cur_n < n:
                rep = n // cur_n
                f = np.repeat(f, rep)
                if len(f) < n:
                    f = np.concatenate([f, np.zeros(n - len(f))])
                f = f[:n]
            else:
                # downsample by block-sum (R-preserving-ish)
                factor = cur_n // n
                f = f[:n * factor].reshape(n, factor).sum(axis=1)
            s = f.sum()
            if s > 0:
                f = f / s
        elapsed = time.process_time() - t_start
        remaining = total - elapsed
        if remaining <= 0.02:
            print(f"stage n={n}: skipped, best={global_best[0]:.6f}")
            continue
        slice_time = min(shares[i] * total, remaining * 0.95)
        R_before = global_best[0]
        global_best = _dinkelbach(f, slice_time, 30.0, 1e5, global_best)
        # adopt current best for next stage
        f = global_best[1].copy()
        print(f"stage n={n}: R={global_best[0]:.6f} (gain {global_best[0]-R_before:+.6f})")
        if global_best[0] - R_before < 1e-5 and i < len(stages) - 1:
            # perturb
            amp = 1e-4 * np.max(f)
            f = np.maximum(f + rng.normal(0, amp, len(f)), 0.0)
            s = f.sum()
            if s > 0:
                f = f / s

    # final polish at highest n with remaining time
    elapsed = time.process_time() - t_start
    remaining = total - elapsed
    if remaining > 0.05:
        f = global_best[1].copy()
        global_best = _dinkelbach(f, remaining * 0.97, 1e4, 1e7, global_best)
        print(f"polish done: best={global_best[0]:.6f}")

    result = global_best[1]

    if start is not None:
        sarr = np.asarray(start, dtype=float)
        try:
            Rs = _knot_R(sarr)
        except Exception:
            Rs = 0.0
        if Rs > global_best[0]:
            return {"best": sarr, "alternative": result}
    return result
