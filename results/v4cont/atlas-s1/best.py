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


def _clip_obj_grad(h, c):
    num, dq, Lf = _num_and_dq(h)
    gLf = (Lf - c) * (Lf > c)
    gLf[0] = 0.0
    gLf[-1] = 0.0
    obj = 0.5 * np.sum(gLf * gLf)
    grad = _backprop(gLf, h)
    return obj, grad


def _make_cb(deadline):
    def cb(xk):
        if time.process_time() > deadline:
            raise TimeoutError
    return cb


def run_direct(h0, beta, maxiter, maxfun, deadline):
    if time.process_time() >= deadline - 1.0:
        return h0
    def f(x):
        xc = np.clip(x, 0, None)
        o, g = _direct_obj_grad(xc, beta)
        return o, g * (x > 0)
    cb = _make_cb(deadline - 0.5)
    try:
        res = minimize(f, h0, jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * h0.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': maxfun,
                                'ftol': 1e-17, 'gtol': 1e-13})
        return _rescale_maxL(res.x)
    except TimeoutError:
        try:
            return _rescale_maxL(res.x)
        except Exception:
            return h0
    except Exception:
        return h0


def run_clip(h0, c, maxiter, maxfun, deadline):
    if time.process_time() >= deadline - 1.0:
        return h0
    def f(x):
        xc = np.clip(x, 0, None)
        o, g = _clip_obj_grad(xc, c)
        return o, g * (x > 0)
    cb = _make_cb(deadline - 0.5)
    try:
        res = minimize(f, h0, jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * h0.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': maxfun,
                                'ftol': 1e-17, 'gtol': 1e-13})
        return _rescale_maxL(res.x)
    except TimeoutError:
        try:
            return _rescale_maxL(res.x)
        except Exception:
            return h0
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

    cb = _make_cb(deadline - 0.5)
    try:
        res = minimize(f, u0, jac=True, method='L-BFGS-B',
                       bounds=[(-30.0, 30.0)] * active.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': maxfun,
                                'ftol': 1e-20, 'gtol': 1e-16})
        h2 = np.zeros(n)
        h2[active] = np.exp(np.clip(res.x, -30.0, 30.0))
        return _rescale_maxL(h2)
    except TimeoutError:
        try:
            h2 = np.zeros(n)
            h2[active] = np.exp(np.clip(res.x, -30.0, 30.0))
            return _rescale_maxL(h2)
        except Exception:
            return h0
    except Exception:
        return h0


def _upsample(h, factor):
    n = h.size
    m = (n - 1) * factor + 1
    xo = np.linspace(0.0, n - 1, m)
    return np.interp(xo, np.arange(n), h)


def _prune(h, frac):
    h = np.asarray(h, dtype=float)
    out = h * (h > frac * h.max())
    return _rescale_maxL(out)


def _unzero(h, frac):
    h = np.asarray(h, dtype=float)
    m = h.mean()
    out = h.copy()
    out[h <= 0] += frac * m
    return out


def _window_polish(h, deadline):
    """Exact L-BFGS restricted to indices near the argmax-knot region, then full."""
    if time.process_time() >= deadline - 1.0:
        return h
    n = h.size
    Lf = _knots(h)
    m = int(np.argmax(Lf))
    lo = max(0, m - 1 - (n - 1))
    hi = min(n - 1, m - 1)
    if hi <= lo:
        return h
    pad = max(8, (hi - lo) // 2)
    lo = max(0, lo - pad)
    hi = min(n - 1, hi + pad)
    free = np.arange(lo, hi + 1)
    h2 = _exact_lbfgs(h, 400, 800, deadline, free=free)
    return h2


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.80

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

    # --- NEW: clip (peak-shaving) ladder ---
    for _pass in range(3):
        if time.process_time() >= deadline - 2.0:
            break
        pass_improved = False
        for eps in [3e-2, 1e-2, 3e-3, 1e-3]:
            if time.process_time() >= deadline - 2.0:
                break
            c = (1.0 - eps) * _knots(best).max()
            cand = run_clip(best, c, 300, 600, deadline)
            cand = _exact_lbfgs(cand, 300, 600, deadline)
            r = R_of(cand)
            if r > bestR + 1e-15:
                best, bestR = cand.copy(), r
                pass_improved = True
                print("clip eps=%.0e R=%.7f" % (eps, bestR))
        if not pass_improved:
            break

    if best.size < 120000:
        for factor in (2, 3):
            cand = _rescale_maxL(_upsample(best, factor))
            if cand.size > 200000:
                continue
            r = R_of(cand)
            if r > bestR - 2e-6:
                best, bestR = cand, max(r, bestR)
                print("upsample x%d R=%.7f (N=%d)" % (factor, bestR, best.size))
                break

    betas = [1e5, 1e6, 1e7, 1e8, 3e8, 1e9]
    cycle = 0
    while time.process_time() < deadline - 2.0:
        cycle += 1
        improved = False
        for beta in betas:
            if time.process_time() >= deadline - 2.0:
                break
            h = run_direct(best, beta, 1000, 2000, deadline)
            r = R_of(h)
            if r > bestR + 1e-15:
                best, bestR = h.copy(), r
                improved = True
            if time.process_time() >= deadline - 2.0:
                break
            h2 = _exact_lbfgs(best, 500, 1000, deadline)
            r2 = R_of(h2)
            if r2 > bestR + 1e-15:
                best, bestR = h2.copy(), r2
                improved = True
                print("cycle %d beta %.0e R=%.7f" % (cycle, beta, bestR))
        h3 = _window_polish(best, deadline)
        r3 = R_of(h3)
        if r3 > bestR + 1e-15:
            best, bestR = h3.copy(), r3
            improved = True
            print("window R=%.7f" % bestR)
        if not improved:
            break

    # Shake ladder: 1 round.
    for rnd in range(1):
        if time.process_time() >= deadline - 2.0:
            break
        round_best = best.copy()
        round_bestR = bestR
        improved = False
        for thresh in [1e-4, 1e-3, 1e-2]:
            if time.process_time() >= deadline - 2.0:
                break
            hh = _prune(round_best, thresh)
            hh = _exact_lbfgs(hh, 500, 1000, deadline)
            r = R_of(hh)
            if r > round_bestR + 1e-15:
                round_best, round_bestR = hh.copy(), r
                improved = True
        for frac in [1e-3, 1e-2]:
            if time.process_time() >= deadline - 2.0:
                break
            hh2 = _unzero(round_best, frac)
            hh2 = _exact_lbfgs(hh2, 500, 1000, deadline)
            if time.process_time() < deadline - 2.0:
                hh2 = run_direct(hh2, 1e6, 600, 1200, deadline)
                hh2 = _exact_lbfgs(hh2, 500, 1000, deadline)
            r = R_of(hh2)
            if r > round_bestR + 1e-15:
                round_best, round_bestR = hh2.copy(), r
                improved = True
        if round_bestR > bestR + 1e-15:
            best, bestR = round_best, round_bestR
            print("shake round %d R=%.7f" % (rnd + 1, bestR))
        if not improved:
            break

    hard = t0 + budget_seconds * 0.92
    while time.process_time() < hard - 1.0:
        h2 = _exact_lbfgs(best, 1500, 3000, hard - 0.5)
        r2 = R_of(h2)
        if r2 > bestR + 1e-16:
            best, bestR = h2.copy(), r2
            print("final polish R=%.7f" % bestR)
        else:
            break

    if bestR < R_of(base):
        best = base
        bestR = R_of(base)

    print("final R=%.7f (N=%d)" % (bestR, best.size))
    return best
