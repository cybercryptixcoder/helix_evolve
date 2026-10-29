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


def _make_cb(deadline):
    def cb(xk):
        if time.process_time() > deadline:
            raise TimeoutError
    return cb


def _full_lbfgs(h0, deadline, maxiter=150, mask=None):
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    if mask is None:
        pos = np.flatnonzero(h > 0)
    else:
        pos = np.flatnonzero(mask)
    if pos.size == 0:
        return h0
    x0 = h[pos].copy()

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
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = h.copy()
    h2[pos] = np.clip(res.x, 0.0, None)
    return _rescale(h2)


def _upsample(h, newN):
    oldN = h.size
    if oldN == newN:
        return h.copy()
    xc_old = (np.arange(oldN) + 0.5) / oldN
    xc_new = (np.arange(newN) + 0.5) / newN
    h2 = np.interp(xc_new, xc_old, h, left=0.0, right=0.0)
    h2 = np.clip(h2, 0, None)
    s_old = h.sum() / oldN
    s_new = h2.sum() / newN
    if s_new > 0:
        h2 = h2 * (s_old / s_new)
    return _rescale(h2)


def _peak_window_mask(N, h, half):
    L = _knots(h)
    j = int(np.argmax(L))
    c = j - 0.5
    lo = int(max(0, np.floor(c - half)))
    hi = int(min(N, np.ceil(c + half) + 1))
    m = np.zeros(N, dtype=bool)
    m[lo:hi] = True
    return m


def _perturb(h, eps, k, phi):
    N = h.size
    x = np.arange(N) / N
    fac = np.exp(eps * np.cos(2 * np.pi * k * x + phi))
    return _rescale(h * fac)


def _is_repeat(h, period=32, tol=1e-9):
    n = h.size
    if n < period or n % period != 0:
        return False
    blocks = h.reshape(-1, period)
    m = blocks.mean(axis=0)
    if np.max(np.abs(m)) <= 0:
        return False
    dev = np.max(np.abs(blocks - m[None, :])) / np.max(np.abs(m))
    return dev < tol


def _block_patterns(period=32):
    i = np.arange(period, dtype=float)
    pats = []
    # linear ramp -1..1
    p = (i - (period - 1) / 2.0)
    p = p / (np.max(np.abs(p)) + 1e-30)
    pats.append(p)
    # cosine
    pats.append(np.cos(2 * np.pi * i / period))
    # alternating odd/even
    p = np.where(i % 2 == 0, 1.0, -1.0)
    pats.append(p)
    # fixed pseudo-random zero-mean
    rng = np.random.RandomState(12345)
    p = rng.randn(period)
    p = p - p.mean()
    p = p / (np.max(np.abs(p)) + 1e-30)
    pats.append(p)
    return pats


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

    def consider(hn):
        nonlocal best, bestR, alt_best, alt_bestR
        r = R_of(hn)
        if r > alt_bestR:
            alt_best = hn.copy(); alt_bestR = r
        if r > bestR + 1e-15:
            best = hn.copy(); bestR = r
            return True
        return False

    N0 = h0.size

    def polish_level(h, level_deadline, tag):
        nonlocal best, bestR
        h = h.copy()
        hc = _full_lbfgs(h, min(level_deadline, time.process_time() + 30.0), maxiter=200)
        if R_of(hc) >= R_of(h):
            h = hc
        consider(h)
        print("%s full polish R=%.12f (N=%d)" % (tag, R_of(h), h.size))
        half = max(8, h.size // 8)
        cyc = 0
        while time.process_time() < level_deadline - 0.5:
            cyc += 1
            m = _peak_window_mask(h.size, h, half)
            tlim = min(level_deadline - 0.3, time.process_time() + 12.0)
            hc = _full_lbfgs(h, tlim, maxiter=200, mask=m)
            if R_of(hc) > R_of(h) + 1e-15:
                h = hc
                consider(h)
            else:
                h = hc if R_of(hc) > R_of(h) else h
            if cyc % 2 == 0:
                eps = 1e-3
                k = (cyc // 2) % 3 + 1
                phi = (cyc * 0.7) % (2 * np.pi)
                hp = _perturb(h, eps, k, phi)
                tlim = min(level_deadline - 0.3, time.process_time() + 10.0)
                hp = _full_lbfgs(hp, tlim, maxiter=150)
                if R_of(hp) > R_of(h) + 1e-15:
                    h = hp
                    consider(h)
            if cyc % 3 == 0:
                print("%s cyc=%d R=%.12f" % (tag, cyc, R_of(h)))
            if time.process_time() > level_deadline - 0.5:
                break
        return h

    try:
        N1 = min(2 * N0, 2000000)
        t1_end = t0 + budget_seconds * 0.20
        if time.process_time() < t1_end - 1.0:
            h1 = _upsample(h0, N1)
            consider(h1)
            h1 = polish_level(h1, t1_end, "L1(2x)")
            consider(h1)
            print("L1 done R=%.12f" % R_of(h1))
        else:
            h1 = h0

        N2 = min(4 * N0, 2000000)
        t2_end = t0 + budget_seconds * 0.60
        if time.process_time() < t2_end - 1.0:
            h2 = _upsample(h1, N2)
            consider(h2)
            h2 = polish_level(h2, t2_end, "L2(4x)")
            consider(h2)
            print("L2 done R=%.12f" % R_of(h2))
        else:
            h2 = h1

        # ---- Block-pattern injection phase ----
        t3_end = t0 + budget_seconds * 0.90
        period = 32
        pats = _block_patterns(period)
        amps = [1e-5, 3e-5, 1e-4, 3e-4]
        rep = _is_repeat(best, period)
        print("repeat32 check: %s (N=%d)" % (rep, best.size))

        trial = 0
        while time.process_time() < t3_end - 1.0:
            trial += 1
            h = best.copy()
            N = h.size
            # build pattern over full array
            idx = np.arange(N) % period
            pi = (trial - 1) % len(pats)
            ai = ((trial - 1) // len(pats)) % len(amps)
            s = pats[pi][idx]
            a = amps[ai]
            fac = 1.0 + a * s
            fac = np.clip(fac, 1e-6, None)
            hp = _rescale(h * fac)
            # full-array tie-averaged L-BFGS on positive cells for 3-6 s
            tlim = min(t3_end - 0.5, time.process_time() + 4.5)
            hp = _full_lbfgs(hp, tlim, maxiter=120)
            # peak-window polish
            half = max(8, N // 8)
            m = _peak_window_mask(N, hp, half)
            tlim = min(t3_end - 0.3, time.process_time() + 3.0)
            hq = _full_lbfgs(hp, tlim, maxiter=120, mask=m)
            if R_of(hq) > R_of(hp):
                hp = hq
            r = R_of(hp)
            improved = consider(hp)
            if trial % 5 == 0 or improved:
                print("blk trial=%d pat=%d amp=%.0e R=%.12f%s" %
                      (trial, pi, a, r, " *" if improved else ""))

        # ---- Final polish of best ----
        t4_end = deadline
        if time.process_time() < t4_end - 1.0:
            hf = polish_level(best, t4_end, "final")
            consider(hf)
    except Exception as e:
        print("ladder failed:", e)

    print("final R=%.12f (start %.12f, N=%d)" % (bestR, startR, best.size))
    if bestR > startR + 1e-15:
        alt = alt_best if (alt_best is not None and alt_bestR > startR) else h0
        return {"best": best, "alternative": alt}
    if alt_best is not None and alt_bestR > 0:
        return {"best": h0, "alternative": alt_best}
    return {"best": h0, "alternative": best}
