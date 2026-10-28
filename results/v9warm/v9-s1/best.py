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


def _fun_grad_tie(h):
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(h.size)
    num, dq, Lf = _num_and_dq(h)
    mx = Lf.max()
    Lm = mx
    gLf = -dq / num
    idx = np.flatnonzero(Lf >= mx * (1.0 - 1e-10))
    w = 1.0 / idx.size
    gLf[idx] += w / Lm
    grad = _backprop(gLf, h) + 2.0 / s
    val = -np.log(num) + 2.0 * np.log(s) + np.log(Lm)
    return val, grad


def _fun_grad_anchor(h, jstar):
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(h.size)
    num, dq, Lf = _num_and_dq(h)
    Lm = Lf.max()
    if Lm <= 0:
        return 1e18, np.zeros(h.size)
    gLf = -dq / num
    j = int(jstar)
    if j < 0 or j >= gLf.size:
        j = int(np.argmax(Lf))
    gLf[j] += 1.0 / Lm
    grad = _backprop(gLf, h) + 2.0 / s
    val = -np.log(num) + 2.0 * np.log(s) + np.log(Lm)
    return val, grad


def _make_cb(deadline):
    def cb(xk):
        if time.process_time() > deadline:
            raise TimeoutError
    return cb


def _lbfgs_custom(h0, fun_grad, deadline, maxiter=150):
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    pos = np.flatnonzero(h > 0)
    if pos.size == 0:
        return h0
    x0 = h[pos].copy()

    def f(x):
        hh = h.copy()
        hh[pos] = np.clip(x, 0.0, None)
        val, g = fun_grad(hh)
        return val, g[pos]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * pos.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = h.copy()
    h2[pos] = np.clip(res.x, 0.0, None)
    return _rescale(h2)


def _full_lbfgs(h0, deadline, maxiter=150):
    return _lbfgs_custom(h0, _fun_grad_tie, deadline, maxiter=maxiter)


def _peak_window(h, deadline, bestR, half=None):
    n = h.size
    if n < 8:
        return h, bestR
    if half is None:
        half = max(64, n // 8)
    Lf = _knots(h)
    kmax = int(np.argmax(Lf))
    center = kmax - 1
    lo = max(0, center - half)
    hi = min(n, center + half)
    if hi - lo < 4:
        return h, bestR
    pos = np.arange(lo, hi)
    x0 = np.clip(h[pos], 0.0, None)

    def f(x):
        hh = h.copy()
        hh[pos] = np.clip(x, 0.0, None)
        val, g = _fun_grad_tie(hh)
        return val, g[pos]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * pos.size,
                       callback=cb,
                       options={'maxiter': 200, 'maxfun': 400,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h, bestR
    if res is None:
        return h, bestR
    h2 = h.copy()
    h2[pos] = np.clip(res.x, 0.0, None)
    h2 = _rescale(h2)
    r2 = R_of(h2)
    if r2 > bestR + 1e-15:
        return h2, r2
    return h, bestR


# ---------------------------------------------------------------------------
# Plateau-window objective: directly maximise R with the max-anchor forced at
# a *single* central knot. This is the sharpest local model of the active
# ||f*f||_inf constraint when the plateau is nearly flat, and unlike the
# tie-average it does not smear the anchor over a whole plateau.
# ---------------------------------------------------------------------------

def _anchor_window(h, deadline, bestR, jstar, half):
    n = h.size
    lo = max(0, jstar - half)
    hi = min(n, jstar + half)
    if hi - lo < 4:
        return h, bestR
    pos = np.arange(lo, hi)
    x0 = np.clip(h[pos], 0.0, None)

    def f(x):
        hh = h.copy()
        hh[pos] = np.clip(x, 0.0, None)
        val, g = _fun_grad_anchor(hh, jstar + 1)
        return val, g[pos]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * pos.size,
                       callback=cb,
                       options={'maxiter': 200, 'maxfun': 400,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h, bestR
    if res is None:
        return h, bestR
    h2 = h.copy()
    h2[pos] = np.clip(res.x, 0.0, None)
    h2 = _rescale(h2)
    r2 = R_of(h2)
    if r2 > bestR + 1e-15:
        return h2, r2
    return h, bestR


# ---------------------------------------------------------------------------
# Upsample: build a finer grid by linear interpolation, then refine. This
# changes the parametrisation and lets the optimiser escape the current grid
# resolution (the "alternative" construction: genuinely different).
# ---------------------------------------------------------------------------

def _upsample(h, factor):
    if factor <= 1:
        return h
    n = h.size
    m = (n - 1) * factor + 1
    x_old = np.arange(n, dtype=float)
    x_new = np.linspace(0.0, n - 1, m)
    return np.interp(x_new, x_old, h)


def _downsample(h, n_target):
    n = h.size
    if n == n_target:
        return h
    x_old = np.arange(n, dtype=float)
    x_new = np.linspace(0.0, n - 1, n_target)
    return np.interp(x_new, x_old, h)


def _upsample_refine(h, deadline, factor=2, maxiter=80):
    m = (h.size - 1) * factor + 1
    if m > 900000:
        return h
    hu = _upsample(h, factor)
    hu = _rescale(hu)
    hu = _full_lbfgs(hu, deadline, maxiter=maxiter)
    ru = R_of(hu)
    rh = R_of(h)
    if ru > rh + 1e-15:
        return hu
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.93

    if start is not None:
        base = np.clip(np.asarray(start, dtype=float).copy(), 0, None)
        if base.size > 0 and base.sum() > 0:
            h0 = _rescale(base)
        else:
            h0 = None
    else:
        h0 = None

    if h0 is None:
        N = 8192
        i = np.arange(N, dtype=float)
        h0 = _rescale(2.0 * np.sqrt(N) * (np.sqrt(i + 1.0) - np.sqrt(i)))

    startR = R_of(h0)
    best = h0.copy()
    bestR = startR
    print("base R=%.12f (N=%d)" % (bestR, best.size))

    alt_best = None
    alt_bestR = -1.0

    def consider(hn, tag=""):
        nonlocal best, bestR, alt_best, alt_bestR
        r = R_of(hn)
        if r > alt_bestR:
            alt_best = hn.copy(); alt_bestR = r
        if r > bestR + 1e-15:
            best = hn.copy(); bestR = r
            return True
        return False

    # ---- Phase A: single-anchor plateau windows around the current peak ----
    pA_end = t0 + budget_seconds * 0.30
    try:
        while time.process_time() < pA_end - 1.0:
            Lf = _knots(best)
            kmax = int(np.argmax(Lf))
            jstar = kmax - 1
            if jstar < 0:
                jstar = 0
            n = best.size
            gained = False
            for half in (max(64, n // 16), max(64, n // 32), max(32, n // 64)):
                if time.process_time() > pA_end - 0.5:
                    break
                tlim = min(pA_end - 0.3, time.process_time() + 3.0)
                hw, rw = _anchor_window(best, tlim, bestR, jstar, half)
                if rw > bestR + 1e-15:
                    best = hw; bestR = rw; gained = True
            if not gained:
                break
        print("phaseA: R=%.12f" % bestR)
    except Exception as e:
        print("phaseA failed:", e)

    # ---- Phase B: alternate full L-BFGS with anchor windows; escape basins ----
    pB_end = t0 + budget_seconds * 0.65
    try:
        while time.process_time() < pB_end - 1.0:
            gained = False
            tlim = min(pB_end - 0.5, time.process_time() + 3.0)
            hc = _full_lbfgs(best, tlim, maxiter=200)
            if consider(hc):
                gained = True
            Lf = _knots(best)
            kmax = int(np.argmax(Lf))
            jstar = max(0, kmax - 1)
            n = best.size
            tlim = min(pB_end - 0.5, time.process_time() + 3.0)
            hw, rw = _anchor_window(best, tlim, bestR, jstar, max(64, n // 16))
            if rw > bestR + 1e-15:
                best = hw; bestR = rw; gained = True
            tlim = min(pB_end - 0.5, time.process_time() + 3.0)
            hw, rw = _peak_window(best, tlim, bestR, half=max(64, n // 8))
            if rw > bestR + 1e-15:
                best = hw; bestR = rw; gained = True
            if not gained:
                # perturbed restart: upsample+refine pushes out of local min
                tlim = min(pB_end - 0.5, time.process_time() + 4.0)
                hu = _upsample_refine(best, tlim, factor=2, maxiter=80)
                if R_of(hu) > bestR + 1e-15:
                    best = hu; bestR = R_of(hu); gained = True
            if not gained:
                break
        print("phaseB: R=%.12f" % bestR)
    except Exception as e:
        print("phaseB failed:", e)

    # ---- Phase C: upsample to finer grid, keep if better; else keep coarse ----
    pC_end = t0 + budget_seconds * 0.88
    try:
        if time.process_time() < pC_end - 2.0 and best.size < 400000:
            tlim = min(pC_end - 0.5, time.process_time() + 8.0)
            hu = _upsample_refine(best, tlim, factor=2, maxiter=120)
            ru = R_of(hu)
            print("phaseC upsample: R=%.12f (delta %+.3e)" % (ru, ru - bestR))
            if ru > bestR + 1e-15:
                best = hu; bestR = ru
            elif alt_best is None or ru > alt_bestR:
                alt_best = hu.copy(); alt_bestR = ru
    except Exception as e:
        print("phaseC failed:", e)

    # ---- Phase D: final polishing on the current best ----
    try:
        while time.process_time() < deadline - 1.0:
            gained = False
            tlim = min(deadline - 0.5, time.process_time() + 3.0)
            hc = _full_lbfgs(best, tlim, maxiter=250)
            if consider(hc):
                gained = True
            Lf = _knots(best)
            kmax = int(np.argmax(Lf))
            jstar = max(0, kmax - 1)
            n = best.size
            for half in (max(64, n // 16), max(64, n // 32), max(32, n // 64),
                         max(16, n // 128)):
                if time.process_time() > deadline - 0.5:
                    break
                tlim = min(deadline - 0.5, time.process_time() + 2.0)
                hw, rw = _anchor_window(best, tlim, bestR, jstar, half)
                if rw > bestR + 1e-15:
                    best = hw; bestR = rw; gained = True
            if not gained:
                break
        print("phaseD: R=%.12f" % bestR)
    except Exception as e:
        print("phaseD failed:", e)

    print("final R=%.12f (start %.12f, N=%d)" % (bestR, startR, best.size))
    if bestR > startR + 1e-15:
        alt = alt_best if (alt_best is not None and alt_bestR > startR) else h0
        return {"best": best, "alternative": alt}
    if alt_best is not None and alt_bestR > 0:
        return {"best": h0, "alternative": alt_best}
    return {"best": h0, "alternative": best}
