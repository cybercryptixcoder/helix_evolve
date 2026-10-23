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
    e = np.exp(beta * (Lf - mx))
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
    if beta > 0:
        fg = (lambda hh: _fun_grad_beta(hh, beta))
    else:
        fg = _fun_grad

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
    if beta > 0:
        fg = (lambda hh: _fun_grad_beta(hh, beta))
    else:
        fg = _fun_grad

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


def _window_polish_peak(h, deadline, frac, extra, maxiter=400, beta=0.0):
    n = h.size
    lo, hi = _peak_region(h)
    span = hi - lo
    pad = max(extra, int(span * frac))
    lo = max(0, lo - pad)
    hi = min(n - 1, hi + pad)
    free = np.arange(lo, hi + 1)
    return _lbfgs_block(h, free, maxiter=maxiter, deadline=deadline, beta=beta)


def _revive_zeros(h, level, win=256):
    """Set every exact-zero entry to `level` times the local mean of positive
    heights in a `win`-step neighbourhood (fallback to global positive mean)."""
    h = np.clip(np.asarray(h, dtype=float).copy(), 0, None)
    n = h.size
    if n < 4:
        return h
    pos = h > 0
    if not pos.any():
        return h
    k = max(1, min(win, n))
    kernel = np.ones(k) / k
    posf = pos.astype(float)
    num = np.convolve(h, kernel, mode='same')
    den = np.convolve(posf, kernel, mode='same')
    local_mean = np.where(den > 1e-12, num / np.maximum(den, 1e-12), 0.0)
    gmean = h[pos].mean()
    local_mean = np.where(local_mean > 0, local_mean, gmean)
    fill = level * local_mean
    zeros = ~pos
    h[zeros] = fill[zeros]
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

    if start is not None:
        base = np.clip(np.asarray(start, dtype=float).copy(), 0, None)
        if base.size > 0 and base.sum() > 0:
            best = _rescale(base)
            bestR = R_of(best)
        else:
            best, bestR = None, 0.0
    else:
        best, bestR = None, 0.0

    if best is None:
        N = 8192
        i = np.arange(N, dtype=float)
        h = 2.0 * np.sqrt(N) * (np.sqrt(i + 1.0) - np.sqrt(i))
        best = _rescale(h)
        bestR = R_of(h)

    start_best = best.copy()
    start_bestR = bestR
    print("base R=%.7f (N=%d, zeros %.1f%%)" %
          (bestR, best.size, 100.0 * np.mean(best <= 0)))

    # Ladder of revival levels for exact zeros (central + tails).
    levels = (1e-3, 5e-3, 1e-2, 3e-2)
    cur = best.copy()
    found = False
    for L in levels:
        if time.process_time() >= deadline - 8.0:
            break
        cand = _revive_zeros(best, L, win=256)
        cand = _rescale(cand)
        r0 = R_of(cand)
        # sharp log-space polish
        h = _lbfgs_log(cand, 600, deadline)
        r = R_of(h)
        # beta ladder interleaved with peak polishes
        for beta in (1e3, 1e4, 1e5):
            if time.process_time() >= deadline - 6.0:
                break
            hb = _lbfgs_log(h, 250, deadline, beta=beta)
            rb = R_of(hb)
            if rb > r:
                h, r = hb, rb
            for frac in (0.05, 0.10, 0.20):
                if time.process_time() >= deadline - 5.0:
                    break
                hp = _window_polish_peak(h, deadline, frac, 32,
                                         maxiter=200, beta=beta)
                rp = R_of(hp)
                if rp > r:
                    h, r = hp, rp
        print("revive L=%.0e R0=%.7f -> R=%.7f" % (L, r0, r))
        if r > bestR + 1e-12:
            best, bestR = h.copy(), r
            cur = h.copy()
            found = True
            break

    if not found:
        print("no revival level beat base; keeping base")

    # Stage C: alternate full sharp / peak polish to deadline.
    it = 0
    while time.process_time() < deadline - 2.0:
        it += 1
        h = _lbfgs_log(best, 300, deadline)
        r = R_of(h)
        if r > bestR + 1e-13:
            best, bestR = h, r
            print("  alt full #%d R=%.7f" % (it, bestR))
        for frac in (0.05, 0.10, 0.20):
            if time.process_time() >= deadline - 1.5:
                break
            hp = _window_polish_peak(best, deadline, frac, 32, maxiter=200)
            rp = R_of(hp)
            if rp > bestR + 1e-13:
                best, bestR = hp, rp
                print("  alt peak #%d frac=%.2f R=%.7f" % (it, frac, rp))

    print("final R=%.7f (N=%d, zeros %.1f%%)" %
          (bestR, best.size, 100.0 * np.mean(best <= 0)))

    if bestR > start_bestR + 1e-12:
        return best
    return {"best": start_best,
            "alternative": best if bestR > start_bestR - 1e-6 else None}
