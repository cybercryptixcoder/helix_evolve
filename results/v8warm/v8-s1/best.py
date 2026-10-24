import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _conv(h):
    if h.size > 1500:
        return fftconvolve(h, h)
    return np.convolve(h, h)


def _conv2(a, b):
    if a.size > 1500 or b.size > 1500:
        return fftconvolve(a, b)
    return np.convolve(a, b)


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


def _peak_ladder(h, deadline, pads=(0.15, 0.10, 0.06, 0.04), iters=400):
    for pad in pads:
        if time.process_time() >= deadline - 0.5:
            break
        win = _peak_window(h, pad_frac=pad, extra=128)
        ht = _lbfgs_block(h, win, iters, deadline - 0.3, beta=1e7)
        if R_of(ht) > R_of(h) + 1e-14:
            h = ht
    return h


def _argmax_frac(h):
    Lf = _knots(h)
    m = int(np.argmax(Lf))
    return m / max(1, Lf.size - 1)


def _zero_frac(h):
    return float(np.mean(h <= 0))


def _nearmax_frac(h, frac=0.95):
    Lf = _knots(h)
    mx = Lf.max()
    if mx <= 0:
        return 0.0
    return float(np.mean(Lf >= frac * mx))


# ---------------- main ----------------

def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

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
    print("base R=%.9f (N=%d)" % (bestR, best.size))

    alt_best = None
    alt_bestR = -1.0

    def offer(cand, tag):
        nonlocal best, bestR, alt_best, alt_bestR
        if cand is None or cand.size == 0 or cand.sum() <= 0:
            return False
        r = R_of(cand)
        if r > bestR + 1e-14:
            best, bestR = cand.copy(), r
            print("NEW BEST R=%.9f (%s)" % (bestR, tag))
            return True
        elif r > alt_bestR and cand.size == best.size:
            alt_best, alt_bestR = cand.copy(), r
        return False

    N = best.size
    amax0 = _argmax_frac(best)

    # ---- Phase A: front-loaded peak-window beta ladder ----
    a_deadline = t0 + budget_seconds * 0.30
    for pad in (0.06, 0.05, 0.04, 0.03, 0.02):
        if time.process_time() >= a_deadline - 0.5:
            break
        win = _peak_window(best, pad_frac=pad, extra=128)
        ht = _lbfgs_block(best, win, 250, a_deadline - 0.3, beta=1e7)
        offer(ht, 'A-beta pad=%.2f' % pad)
        ht2 = _lbfgs_block(best, win, 250, a_deadline - 0.3, beta=0.0)
        offer(ht2, 'A-plain pad=%.2f' % pad)
    print("Phase A done R=%.9f argmax_frac=%.4f" % (bestR, _argmax_frac(best)))

    # ---- Phase B: random-window block L-BFGS rounds ----
    b_deadline = deadline - 6.0
    rng = np.random.default_rng(12345)
    lo_len = max(8, N // 20)
    hi_len = max(lo_len + 1, N // 6)
    rnd = 0
    while time.process_time() < b_deadline:
        rnd += 1
        L = int(rng.integers(lo_len, hi_len + 1))
        c = int(rng.integers(0, N))
        lo = max(0, c - L // 2)
        hi = min(N, lo + L)
        lo = max(0, hi - L)
        win = np.arange(lo, hi)
        cand = best.copy()
        cand = _lbfgs_block(cand, win, 250, b_deadline, beta=1e6)
        cand = _lbfgs_block(cand, win, 250, b_deadline, beta=0.0)
        cand = _peak_ladder(cand, b_deadline, pads=(0.06, 0.04), iters=200)
        r = R_of(cand)
        if r > bestR + 1e-14:
            best, bestR = cand.copy(), r
            print("B round=%d center=%.3f len=%d R=%.9f (NEW BEST)"
                  % (rnd, c / N, L, bestR))
        else:
            print("B round=%d center=%.3f len=%d R=%.9f" % (rnd, c / N, L, r))

    # ---- Final polish ----
    final_deadline = t0 + budget_seconds * 0.98
    ht = _lbfgs_all_pos(best, 400, final_deadline - 0.5, beta=1e8)
    offer(ht, 'final-beta1e8')
    ht = _lbfgs_all_pos(best, 400, final_deadline - 0.3, beta=0.0)
    offer(ht, 'final-plain')
    ht = _peak_ladder(best, final_deadline - 0.2, pads=(0.05, 0.03), iters=300)
    offer(ht, 'final-peak')

    amax1 = _argmax_frac(best)
    print("final R=%.9f (start %.9f, N=%d, zero_frac=%.4f, argmax_frac=%.4f, "
          "d_argmax=%.4f, nearmax5=%.4f)"
          % (bestR, start_bestR, best.size, _zero_frac(best),
             amax1, amax1 - amax0, _nearmax_frac(best)))

    result = {"best": best}
    if alt_best is not None and alt_best.size == best.size and alt_bestR < bestR:
        result["alternative"] = alt_best
    return result
