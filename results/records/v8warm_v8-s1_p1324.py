# v4->v8 line, second stage: first program above Jaech & Joseph (0.941362)
# Run: results/v8warm/v8-s1   program p1324   round 352   written by: wide loop   parent: p1318
# Score R = 0.9413645409275625   steps n = 104992   CPU seconds used: 55.95
# Extracted verbatim from results/v8warm/v8-s1/programs.jsonl;
# the model calls of that round: results/v8warm/v8-s1/trace.jsonl.gz
# Its intent, as the agent wrote it: Replaced long half-res phase with a Gaussian-smoothing perturbation search (new neighbourhood) feeding L-BFGS, keeping the half-res and peak polish as fallbacks.

import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _conv(h):
    if h.size > 1500:
        return fftconvolve(h, h)
    return np.convolve(h, h)


def _knots(h):
    return np.concatenate(([0.0], _conv(h), [0.0]))


def R_of(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    L = _knots(h)
    a = L[:-1]; b = L[1:]
    num = np.sum(a * a + a * b + b * b) / 3.0
    den = s * s * L.max()
    if den <= 0:
        return 0.0
    return num / den


def _num_and_dq(h):
    Lf = _knots(h)
    a = Lf[:-1]; b = Lf[1:]
    num = np.sum(a * a + a * b + b * b) / 3.0
    dq = np.zeros_like(Lf)
    dq[:-1] += (2 * a + b)
    dq[1:] += (a + 2 * b)
    dq /= 3.0
    return num, dq, Lf


def _backprop(gLf, h):
    gL = gLf[1:-1]
    n = h.size
    if n > 1500:
        return 2.0 * fftconvolve(gL, h[::-1], mode='valid')[:n]
    return 2.0 * np.correlate(gL, h, mode='valid')[:n]


def _rescale(h):
    h = np.clip(h, 0, None)
    if h.sum() <= 0:
        return h
    mx = _knots(h).max()
    if mx <= 0:
        return h
    return h / np.sqrt(mx)


def _fun_grad(h):
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(h.size)
    num, dq, Lf = _num_and_dq(h)
    m = int(np.argmax(Lf))
    Lm = Lf[m]
    gLf = -dq / num
    gLf[m] += 1.0 / Lm
    grad = _backprop(gLf, h) + 2.0 / s
    val = -np.log(num) + 2.0 * np.log(s) + np.log(Lm)
    return val, grad


def _fun_grad_beta(h, beta):
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(h.size)
    num, dq, Lf = _num_and_dq(h)
    mx = Lf.max()
    if mx <= 0:
        return _fun_grad(h)
    e = np.exp(np.clip(beta * (Lf - mx), -60.0, 60.0))
    Z = e.sum()
    if Z <= 0:
        return _fun_grad(h)
    w = e / Z
    sm = mx + np.log(Z) / beta
    gLf = -dq / num + w / sm
    grad = _backprop(gLf, h) + 2.0 / s
    val = -np.log(num) + 2.0 * np.log(s) + np.log(sm)
    return val, grad


def _make_cb(deadline):
    def cb(xk):
        if time.process_time() > deadline:
            raise TimeoutError
    return cb


def _lbfgs_all_pos(h0, maxiter, deadline, beta=0.0):
    if time.process_time() >= deadline - 0.3:
        return h0
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    n = h.size
    fg = (lambda hh: _fun_grad_beta(hh, beta)) if beta > 0 else _fun_grad

    def f(x):
        hh = np.clip(x, 0.0, None)
        val, g = fg(hh)
        return val, g

    cb = _make_cb(deadline - 0.2)
    opts = {'maxiter': maxiter, 'maxfun': 2 * maxiter,
            'ftol': 1e-20, 'gtol': 1e-16}
    try:
        res = minimize(f, h, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * n,
                       callback=cb, options=opts)
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    return _rescale(np.clip(res.x, 0.0, None))


def _lbfgs_block(h0, free, maxiter, deadline, beta=0.0):
    if time.process_time() >= deadline - 0.3:
        return h0
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    active = np.asarray(free, dtype=int)
    if active.size == 0:
        return h0
    x0 = h[active].copy()
    fg = (lambda hh: _fun_grad_beta(hh, beta)) if beta > 0 else _fun_grad

    def f(x):
        hh = h.copy()
        hh[active] = np.clip(x, 0.0, None)
        val, g = fg(hh)
        return val, g[active]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * active.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = h.copy()
    h2[active] = np.clip(res.x, 0.0, None)
    return _rescale(h2)


def _peak_window(h, tol=0.9995, pad_frac=0.4, extra=256):
    Lf = _knots(h)
    mx = Lf.max()
    if mx <= 0:
        return np.arange(h.size)
    idx = np.flatnonzero(Lf >= tol * mx)
    lo = max(0, idx.min() - 1)
    hi = min(h.size - 1, idx.max())
    span = hi - lo
    pad = max(extra, int(span * pad_frac))
    lo = max(0, lo - pad)
    hi = min(h.size - 1, hi + pad)
    return np.arange(lo, hi + 1)


def _zero_frac(h):
    return float(np.mean(h == 0))


def _half_cycle(c, bestR, deadline, tag="", pads=None):
    best = c.copy()
    work = c.copy()
    origin = tag
    for beta in [1e5, 1e6, 1e7]:
        if time.process_time() >= deadline - 0.5:
            break
        ht = _lbfgs_all_pos(work, 300, deadline - 0.3, beta=beta)
        r = R_of(ht)
        if r > bestR + 1e-14:
            work, best, bestR = ht, ht.copy(), r
            origin = "%sbeta%g" % (tag, beta)
    if pads is None:
        pads = [0.30, 0.20, 0.15, 0.10, 0.08]
    for it, pad in enumerate(pads):
        if time.process_time() >= deadline - 0.5:
            break
        win = _peak_window(work, pad_frac=pad, extra=128)
        ht = _lbfgs_block(work, win, 400, deadline - 0.3, beta=1e7)
        r = R_of(ht)
        if r > bestR + 1e-14:
            work, best, bestR = ht, ht.copy(), r
            origin = "%spk%d" % (tag, it)
        if time.process_time() < deadline - 0.6:
            ht2 = _lbfgs_all_pos(work, 300, deadline - 0.3, beta=0.0)
            r2 = R_of(ht2)
            if r2 > bestR + 1e-14:
                work, best, bestR = ht2, ht2.copy(), r2
                origin = "%spk%d+all0" % (tag, it)
    return work, best, bestR, origin


def _gauss_smooth(h, sigma):
    """Gaussian smoothing of the heights (keeps mass roughly, non-negative)."""
    if sigma <= 0:
        return h
    rad = int(3 * sigma) + 1
    x = np.arange(-rad, rad + 1)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    pad = np.concatenate((np.zeros(rad), h, np.zeros(rad)))
    out = np.convolve(pad, k, mode='valid')
    return out


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.93

    if start is not None:
        base = np.clip(np.asarray(start, dtype=float).copy(), 0, None)
        if base.size > 0 and base.sum() > 0:
            start_best = _rescale(base)
            start_bestR = R_of(start_best)
        else:
            start_best, start_bestR = None, 0.0
    else:
        start_best, start_bestR = None, 0.0

    if start_best is None:
        N = 8192
        i = np.arange(N, dtype=float)
        h = 2.0 * np.sqrt(N) * (np.sqrt(i + 1.0) - np.sqrt(i))
        start_best = _rescale(h)
        start_bestR = R_of(start_best)

    best = start_best.copy()
    bestR = start_bestR
    origin = 'start'
    print("base R=%.9f (N=%d)" % (bestR, best.size))

    alt_best = None
    alt_bestR = -1.0

    # ---- Phase 1: half-resolution polish (0-35%) ----
    N = best.size
    best_c = None
    best_cR = -1.0
    if N % 2 == 0 and N >= 4 and time.process_time() < deadline - 2.0:
        c = best[0::2].copy()
        cR = R_of(c)
        print("half-res R(c)=%.9f (full %.9f)" % (cR, bestR))
        half_deadline = t0 + budget_seconds * 0.35
        work_c = c.copy()
        best_c = c.copy()
        best_cR = cR
        rounds = 0
        while time.process_time() < half_deadline - 1.0:
            work_c, best_c, best_cR, org = _half_cycle(
                work_c, best_cR, half_deadline, tag='h%d' % rounds)
            rounds += 1
        print("half-res rounds=%d R(c)=%.9f" % (rounds, best_cR))
        h_lift = _rescale(np.repeat(best_c, 2))
        r_lift = R_of(h_lift)
        ht = h_lift
        for beta in [1e6, 1e7]:
            if time.process_time() >= deadline - 1.0:
                break
            ht = _lbfgs_all_pos(ht, 300, deadline - 0.5, beta=beta)
        r = R_of(ht)
        if r > bestR + 1e-14:
            best, bestR, origin = ht.copy(), r, 'lift+ladder'
            print("lift+ladder NEW BEST R=%.9f" % bestR)
        elif r > alt_bestR:
            alt_best, alt_bestR = ht.copy(), r

    # ---- Phase 2 (NEW): smoothing perturbations + gentle re-optimisation ----
    # Try convolving the current best with a small Gaussian, then re-polish.
    # This explores a genuinely different neighbourhood than multiplicative noise.
    if time.process_time() < deadline - 6.0:
        sigmas = [0.6, 1.2, 2.0, 3.0, 1.8, 0.9]
        si = 0
        while time.process_time() < deadline - 5.0:
            sigma = sigmas[si % len(sigmas)]
            si += 1
            hs = _gauss_smooth(best, sigma)
            hs = _rescale(hs)
            r0 = R_of(hs)
            slice_deadline = min(deadline - 2.0,
                                 time.process_time() + 0.05 * budget_seconds)
            ht = hs
            for beta in [1e6, 1e7]:
                if time.process_time() >= slice_deadline - 0.5:
                    break
                ht = _lbfgs_all_pos(ht, 250, slice_deadline - 0.3, beta=beta)
            if time.process_time() < slice_deadline - 0.5:
                win = _peak_window(ht, pad_frac=0.12, extra=128)
                ht2 = _lbfgs_block(ht, win, 400, slice_deadline - 0.3, beta=1e7)
                if R_of(ht2) > R_of(ht):
                    ht = ht2
            if time.process_time() < slice_deadline - 0.5:
                ht = _lbfgs_all_pos(ht, 250, slice_deadline - 0.3, beta=0.0)
            r = R_of(ht)
            if r > bestR + 1e-14:
                best, bestR, origin = ht.copy(), r, 'smooth%d' % si
                print("smooth sigma=%.2f NEW BEST R=%.9f" % (sigma, bestR))
            else:
                if r > alt_bestR:
                    alt_best, alt_bestR = ht.copy(), r
                print("smooth sigma=%.2f R=%.9f (no gain)" % (sigma, r))

    # ---- Phase 3: perturb-then-polish restarts on half-res quotient ----
    restarts_done = 0
    if best_c is not None and time.process_time() < deadline - 4.0:
        rng = np.random.default_rng(7)
        amps = [0.008, 0.015, 0.03, 0.05]
        ri = 0
        while time.process_time() < deadline - 4.0:
            amp = amps[ri % len(amps)]
            ri += 1
            cc2 = best_c.copy()
            nz = cc2 > 0
            if nz.sum() == 0:
                break
            cc2[nz] *= np.exp(amp * rng.standard_normal(int(nz.sum())))
            cc2 = _rescale(cc2)
            r0 = R_of(cc2)
            slice_deadline = min(deadline - 2.0,
                                 time.process_time() + 0.04 * budget_seconds)
            work_c2, cand_c, cand_cR, org = _half_cycle(
                cc2, r0, slice_deadline, tag='rs%d' % ri,
                pads=[0.30, 0.15])
            restarts_done += 1
            if cand_cR > best_cR + 1e-12:
                best_c = cand_c.copy()
                best_cR = cand_cR
                print("restart %d amp=%.3f ACCEPT R(c)=%.9f" %
                      (ri, amp, best_cR))
            if time.process_time() >= deadline - 4.0:
                break

    # ---- Phase 4: lift best_c and full-N polish ----
    if best_c is not None:
        h_lift = _rescale(np.repeat(best_c, 2))
        r_lift = R_of(h_lift)
        if r_lift > bestR + 1e-14:
            best, bestR, origin = h_lift.copy(), r_lift, 'restart_lift'
            print("restart lift NEW BEST R=%.9f" % bestR)
        elif r_lift > alt_bestR:
            alt_best, alt_bestR = h_lift, r_lift
        ht = h_lift
        for beta in [1e6, 1e7, 0.0]:
            if time.process_time() >= deadline - 1.0:
                break
            ht = _lbfgs_all_pos(ht, 300, deadline - 0.5, beta=beta)
        r = R_of(ht)
        if r > bestR + 1e-14:
            best, bestR, origin = ht.copy(), r, origin + '+full'
            print("full polish NEW BEST R=%.9f" % bestR)
        elif r > alt_bestR:
            alt_best, alt_bestR = ht.copy(), r

    # ---- Phase 5: fine peak polish on best ----
    if time.process_time() < deadline - 1.0:
        for pad in [0.10, 0.06]:
            if time.process_time() >= deadline - 0.8:
                break
            win = _peak_window(best, pad_frac=pad, extra=128)
            ht2 = _lbfgs_block(best, win, 400, deadline - 0.3, beta=1e7)
            r2 = R_of(ht2)
            if r2 > bestR + 1e-14:
                best, bestR, origin = ht2.copy(), r2, origin + '+pk'
                print("peak polish NEW BEST R=%.9f" % bestR)
            elif r2 > alt_bestR:
                alt_best, alt_bestR = ht2.copy(), r2

    print("restarts=%d best_c=%.9f best_full=%.9f" %
          (restarts_done, best_cR, bestR))
    print("final R=%.9f origin=%s (start %.9f, N=%d, zero_frac=%.3f)" %
          (bestR, origin, start_bestR, best.size, _zero_frac(best)))

    result = {"best": best}
    if alt_best is not None and alt_best.size == best.size and alt_bestR < bestR:
        result["alternative"] = alt_best
    return result
