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


def _lbfgs_log(h0, maxiter, deadline, beta=0.0):
    if time.process_time() >= deadline - 0.3:
        return h0
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    n = h.size
    thresh = 1e-13 * h.max()
    active = np.flatnonzero(h > thresh)
    if active.size == 0:
        return h0
    u0 = np.log(np.clip(h[active], 1e-300, None))
    fg = (lambda hh: _fun_grad_beta(hh, beta)) if beta > 0 else _fun_grad

    def f(u):
        uu = np.clip(u, -30.0, 30.0)
        hh = np.zeros(n)
        hh[active] = np.exp(uu)
        val, g = fg(hh)
        return val, g[active] * hh[active]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, u0, jac=True, method='L-BFGS-B',
                       bounds=[(-30.0, 30.0)] * active.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = np.zeros(n)
    h2[active] = np.exp(np.clip(res.x, -30.0, 30.0))
    return _rescale(h2)


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


def _peak_region(h, tol=0.999):
    Lf = _knots(h)
    mx = Lf.max()
    if mx <= 0:
        return 0, h.size - 1
    idx = np.flatnonzero(Lf >= tol * mx)
    lo = max(0, idx.min() - 1)
    hi = min(h.size - 1, idx.max())
    return lo, hi


def _window_polish_peak(h, deadline, frac, extra, maxiter=150, beta=0.0):
    n = h.size
    lo, hi = _peak_region(h)
    span = hi - lo
    pad = max(extra, int(span * frac))
    lo = max(0, lo - pad)
    hi = min(n - 1, hi + pad)
    free = np.arange(lo, hi + 1)
    return _lbfgs_block(h, free, maxiter=maxiter, deadline=deadline, beta=beta)


def _prolong2(h, soften=1.0):
    n = h.size
    h = np.asarray(h, dtype=float)
    nxt = np.empty(n)
    nxt[:-1] = h[1:]
    nxt[-1] = h[-1]
    d = (nxt - h) / 4.0 * soften
    a = np.clip(h - d, 0.0, None)
    b = np.clip(h + d, 0.0, None)
    out = np.empty(2 * n)
    out[0::2] = a
    out[1::2] = b
    return out


def _ladder(h, deadline, best, bestR, tag=""):
    cur = h.copy()
    curR = R_of(cur)
    if curR > bestR:
        best, bestR = cur.copy(), curR
        print("  %s init R=%.7f" % (tag, bestR))

    beta_list = (1e4, 1e5, 1e6, 1e7)

    for beta in beta_list:
        if time.process_time() >= deadline - 3.0:
            return best, bestR
        hb = _lbfgs_log(cur, 150, deadline, beta=beta)
        hs = _lbfgs_log(hb, 150, deadline)
        hw = _window_polish_peak(hs, deadline, 0.10, 32, maxiter=150)
        rs = R_of(hs); rw = R_of(hw)
        cand, rc = (hw, rw) if rw > rs else (hs, rs)
        if rc > curR + 1e-13:
            cur, curR = cand, rc
            if curR > bestR + 1e-13:
                best, bestR = cur.copy(), curR
                print("  %s beta=%.0e R=%.7f" % (tag, beta, bestR))

    return best, bestR


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.95

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
    print("base R=%.7f (N=%d)" % (bestR, best.size))

    # Repeated cycling of the beta-softmax window schedule until deadline.
    schedule = [
        (0.05, 64, 0.0),
        (0.05, 64, 1e6),
        (0.10, 64, 1e6),
        (0.10, 64, 1e7),
        (0.15, 128, 1e7),
        (0.25, 128, 1e8),
        (0.40, 256, 1e8),
    ]

    cur = start_best.copy()
    curR = start_bestR
    cycle = 0
    while time.process_time() < deadline - 2.0:
        cycle += 1
        for frac, extra, beta in schedule:
            if time.process_time() >= deadline - 2.0:
                break
            hw = _window_polish_peak(cur, deadline, frac, extra,
                                     maxiter=300, beta=beta)
            rw = R_of(hw)
            if rw > curR + 1e-13:
                cur, curR = hw, rw
                if curR > bestR + 1e-13:
                    best, bestR = cur.copy(), curR
        # After each full cycle: full-array softmax then sharp polish.
        if time.process_time() < deadline - 2.0:
            hb = _lbfgs_log(best, 200, deadline, beta=1e7)
            rb = R_of(hb)
            if rb > bestR + 1e-13:
                best, bestR = hb, rb
                cur, curR = hb.copy(), rb
        if time.process_time() < deadline - 2.0:
            hs = _lbfgs_log(best, 200, deadline)
            rs = R_of(hs)
            if rs > bestR + 1e-13:
                best, bestR = hs, rs
                cur, curR = hs.copy(), rs
        zf = 100.0 * np.mean(best <= 0)
        print("cycle %d R=%.7f zeros=%.1f%%" % (cycle, bestR, zf))

    # Final polish
    if time.process_time() < deadline - 0.5:
        hf = _lbfgs_log(best, 200, deadline)
        rf = R_of(hf)
        if rf > bestR + 1e-13:
            best, bestR = hf, rf

    print("final R=%.7f (N=%d, zeros %.1f%%)" %
          (bestR, best.size, 100.0 * np.mean(best <= 0)))

    if bestR > start_bestR + 1e-12:
        return best
    return {"best": start_best,
            "alternative": best if bestR > start_bestR - 1e-6 else None}
