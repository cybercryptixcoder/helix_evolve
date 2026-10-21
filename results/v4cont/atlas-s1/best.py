import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _knots(h):
    if h.size > 1500:
        L = fftconvolve(h, h)
    else:
        L = np.convolve(h, h)
    return np.concatenate(([0.0], L, [0.0]))


def R_of(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    L = _knots(h)
    a = L[:-1]; b = L[1:]
    num = np.sum(a*a + a*b + b*b) / 3.0
    den = s * s * L.max()
    if den <= 0:
        return 0.0
    return num / den


def _num_and_dq(h):
    if h.size > 1500:
        L = fftconvolve(h, h)
    else:
        L = np.convolve(h, h)
    Lf = np.concatenate(([0.0], L, [0.0]))
    a = Lf[:-1]; b = Lf[1:]
    num = np.sum(a*a + a*b + b*b) / 3.0
    dq = np.zeros_like(Lf)
    dq[:-1] += (2*a + b)
    dq[1:] += (a + 2*b)
    dq /= 3.0
    return num, dq, Lf


def _backprop(gLf, h):
    gL = gLf[1:-1]
    n = h.size
    if n > 1500:
        return 2.0 * fftconvolve(gL, h[::-1], mode='valid')[:n]
    return 2.0 * np.correlate(gL, h, mode='valid')[:n]


def _rescale_maxL(h):
    h = np.clip(h, 0, None)
    if h.sum() <= 0:
        return h
    mx = _knots(h).max()
    if mx <= 0:
        return h
    return h / np.sqrt(mx)


def _direct_obj_grad(h, beta):
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(h.size)
    num, dq, Lf = _num_and_dq(h)
    mx = Lf.max()
    e = np.exp(np.clip(beta * (Lf - mx), -50, 0))
    Z = e.sum()
    logM = mx + np.log(Z) / beta
    w = e / Z
    obj = -np.log(num) + 2.0 * np.log(s) + logM
    gLf = -dq / num + w
    grad = _backprop(gLf, h)
    grad += 2.0 / s
    return obj, grad


def run_direct(h0, beta, maxiter, maxfun, deadline):
    if time.process_time() >= deadline - 1.0:
        return h0
    def f(x):
        xc = np.clip(x, 0, None)
        o, g = _direct_obj_grad(xc, beta)
        return o, g * (x > 0)
    try:
        res = minimize(f, h0, jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * h0.size,
                       options={'maxiter': maxiter, 'maxfun': maxfun,
                                'ftol': 1e-17, 'gtol': 1e-13})
        return _rescale_maxL(res.x)
    except Exception:
        return h0


def _norm_eq_grad(h):
    s = h.sum()
    num, dq, Lf = _num_and_dq(h)
    m = int(np.argmax(Lf))
    Lm = Lf[m]
    gLf = -dq / num
    gLf[m] += 1.0 / Lm
    grad = _backprop(gLf, h) + 2.0 / s
    return grad


def _norm_eq_fun(h):
    s = h.sum()
    if s <= 0:
        return 1e18
    num, dq, Lf = _num_and_dq(h)
    return -np.log(num) + 2.0 * np.log(s) + np.log(Lf.max())


def _exact_lbfgs(h0, maxiter, maxfun, deadline, free=None):
    if time.process_time() >= deadline - 1.0:
        return h0
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    n = h.size
    if free is None:
        thresh = 1e-13 * h.max()
        active = np.flatnonzero(h > thresh)
    else:
        active = np.asarray(free, dtype=int)
    if active.size == 0:
        return h0
    u0 = np.log(np.clip(h[active], 1e-300, None))

    def f(u):
        uu = np.clip(u, -30.0, 30.0)
        hh = np.zeros(n)
        hh[active] = np.exp(uu)
        val = _norm_eq_fun(hh)
        g = _norm_eq_grad(hh)[active] * hh[active]
        return val, g

    try:
        res = minimize(f, u0, jac=True, method='L-BFGS-B',
                       bounds=[(-30.0, 30.0)] * active.size,
                       options={'maxiter': maxiter, 'maxfun': maxfun,
                                'ftol': 1e-20, 'gtol': 1e-16})
        h2 = np.zeros(n)
        h2[active] = np.exp(np.clip(res.x, -30.0, 30.0))
        return _rescale_maxL(h2)
    except Exception:
        return h0


def _zoh_double(h):
    return np.repeat(h, 2)


def _block_avg(h, k):
    n = h.size
    m = n // k
    if m * k != n:
        h = h[:m * k]
    return h.reshape(m, k).mean(axis=1)


def _refine_subcell(h, deadline, rounds=1):
    """For each cell, allow splitting into 2 subcells with a linear split of mass,
    optimise the split fraction locally. This is a cheap local refinement that
    can improve R without doubling the whole grid."""
    if time.process_time() >= deadline - 1.0:
        return h
    n = h.size
    # build doubled grid with split fraction 0.5 initially
    h2 = np.repeat(h, 2) * 0.5
    # free indices are all (both children), but we tie them: mass conserving
    # We parametrise by fraction t_i in (0,1) with children = h_i*(t_i, 1-t_i).
    # Optimise t via a coarse grid search using exact objective on the doubled grid.
    # Cheap: just try a few common fractions and pick best.
    best = h2.copy()
    bestR = R_of(best)
    for frac in [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65]:
        cand = np.empty(2 * n)
        cand[0::2] = h * frac
        cand[1::2] = h * (1.0 - frac)
        r = R_of(cand)
        if r > bestR + 1e-15:
            best = cand
            bestR = r
    if bestR > R_of(h) + 1e-15:
        # polish with exact LBFGS on doubled grid
        h3 = _exact_lbfgs(best, 300, 600, deadline)
        if R_of(h3) > bestR:
            return h3
        return best
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85

    if start is not None:
        base = np.clip(np.asarray(start, dtype=float).copy(), 0, None)
        if base.size == 0 or base.sum() <= 0:
            base = np.ones(50)
    else:
        base = np.ones(50)
    base = _rescale_maxL(base)

    best = base.copy()
    bestR = R_of(best)
    print("start R=%.6f (N=%d)" % (bestR, best.size))

    N0 = base.size
    low = None
    if N0 % 4 == 0 and N0 >= 8:
        low = _rescale_maxL(_block_avg(base, 4))
        print("downsampled to N=%d R=%.7f" % (low.size, R_of(low)))
    else:
        low = base.copy()

    low_best = low.copy()
    low_bestR = R_of(low_best)

    for beta in [200, 1000, 5000, 20000]:
        if time.process_time() >= deadline - 2.0:
            break
        h = run_direct(low_best, beta, 400, 800, deadline)
        r = R_of(h)
        if r > low_bestR + 1e-15:
            low_best, low_bestR = h.copy(), r
            print("low beta=%d R=%.7f" % (beta, low_bestR))

    # NEW: subcell refinement at low res (split each cell into 2)
    for rnd in range(2):
        if time.process_time() >= deadline - 2.0:
            break
        h = _refine_subcell(low_best, deadline)
        r = R_of(h)
        if r > low_bestR + 1e-15:
            low_best, low_bestR = h.copy(), r
            print("low refine rnd=%d R=%.7f (N=%d)" % (rnd, low_bestR, low_best.size))
        else:
            break

    cand = low_best
    while cand.size < N0:
        cand = _zoh_double(cand)
    if cand.size > N0:
        cand = cand[:N0]
    cand = _rescale_maxL(cand)
    r = R_of(cand)
    print("redoubled R=%.7f (N=%d)" % (r, cand.size))
    if r > bestR + 1e-15:
        best, bestR = cand.copy(), r

    if time.process_time() < deadline - 1.0:
        h = _exact_lbfgs(best, 800, 1600, deadline)
        r = R_of(h)
        if r > bestR + 1e-15:
            best, bestR = h.copy(), r
            print("full exact R=%.7f" % bestR)

    for beta in [2000, 5000, 20000, 100000]:
        if time.process_time() >= deadline - 0.5:
            break
        h = run_direct(best, beta, 300, 600, deadline)
        r = R_of(h)
        if r > bestR + 1e-15:
            best, bestR = h.copy(), r
            print("full lse beta=%d R=%.7f" % (beta, bestR))

    if time.process_time() < deadline - 0.5:
        h = _exact_lbfgs(best, 400, 800, deadline)
        r = R_of(h)
        if r > bestR + 1e-15:
            best, bestR = h.copy(), r
            print("final exact R=%.7f" % bestR)

    if bestR < R_of(base):
        best = base
        bestR = R_of(base)

    print("final R=%.7f (N=%d)" % (bestR, best.size))
    return best
