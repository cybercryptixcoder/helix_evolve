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


def _lbfgs_custom(h0, fun_grad, deadline, maxiter=150):
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0
    pos = np.flatnonzero(h > 0)
    if pos.size == 0:
        return h0
    hmax = h.max()
    floor = 1e-12 * hmax if hmax > 0 else 1e-12
    u0 = np.log(np.clip(h[pos], floor, None))

    def f(u):
        hh = h.copy()
        hh[pos] = np.exp(u)
        val, g = fun_grad(hh)
        return val, g[pos] * hh[pos]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, u0, jac=True, method='L-BFGS-B',
                       bounds=[(-40.0, 40.0)] * pos.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = h.copy()
    h2[pos] = np.exp(np.clip(res.x, -40.0, 40.0))
    return _rescale(h2)


def _full_lbfgs(h0, deadline, maxiter=150):
    return _lbfgs_custom(h0, _fun_grad_tie, deadline, maxiter=maxiter)


def _window_lbfgs(h0, lo, hi, deadline, maxiter=200):
    """L-BFGS restricted to cells [lo, hi)."""
    n = h0.size
    lo = max(0, lo); hi = min(n, hi)
    if hi - lo < 2:
        return h0
    h = np.clip(h0, 0, None)
    pos = np.arange(lo, hi)[h[lo:hi] > 0]
    if pos.size == 0:
        return h0
    hmax = h.max()
    floor = 1e-12 * hmax if hmax > 0 else 1e-12
    u0 = np.log(np.clip(h[pos], floor, None))

    def f(u):
        hh = h.copy()
        hh[pos] = np.exp(u)
        val, g = _fun_grad_tie(hh)
        return val, g[pos] * hh[pos]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, u0, jac=True, method='L-BFGS-B',
                       bounds=[(-40.0, 40.0)] * pos.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h0
    if res is None:
        return h0
    h2 = h.copy()
    h2[pos] = np.exp(np.clip(res.x, -40.0, 40.0))
    return _rescale(h2)


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
    hmax = h.max()
    floor = 1e-12 * hmax if hmax > 0 else 1e-12
    u0 = np.log(np.clip(h[pos], floor, None))

    def f(u):
        hh = h.copy()
        hh[pos] = np.exp(u)
        val, g = _fun_grad_tie(hh)
        return val, g[pos] * hh[pos]

    cb = _make_cb(deadline - 0.2)
    try:
        res = minimize(f, u0, jac=True, method='L-BFGS-B',
                       bounds=[(-40.0, 40.0)] * pos.size,
                       callback=cb,
                       options={'maxiter': 200, 'maxfun': 400,
                                'ftol': 1e-20, 'gtol': 1e-16})
    except (TimeoutError, Exception):
        return h, bestR
    if res is None:
        return h, bestR
    h2 = h.copy()
    h2[pos] = np.exp(np.clip(res.x, -40.0, 40.0))
    h2 = _rescale(h2)
    r2 = R_of(h2)
    if r2 > bestR + 1e-15:
        return h2, r2
    return h, bestR


def _near_max_fractions(h):
    Lf = _knots(h)
    M = Lf.max()
    if M <= 0:
        return 0.0, 0.0, 0.0
    return (np.mean(Lf >= 0.999 * M),
            np.mean(Lf >= 0.99 * M),
            np.mean(Lf >= 0.95 * M))


# ---------------- Block-scale compound moves ----------------

def _runs(h):
    nz = h > 0
    runs = []
    n = h.size
    i = 0
    while i < n:
        if nz[i]:
            j = i
            while j + 1 < n and nz[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def _zero_gaps(h):
    z = h <= 0
    gaps = []
    n = h.size
    i = 0
    while i < n:
        if z[i]:
            j = i
            while j + 1 < n and z[j + 1]:
                j += 1
            gaps.append((i, j))
            i = j + 1
        else:
            i += 1
    return gaps


def _translate_block(h, a, b, k):
    """Shift block [a,b] by k cells (k can be negative). Returns new array or None."""
    n = h.size
    L = b - a + 1
    na = a + k
    nb = na + L - 1
    if na < 0 or nb >= n:
        return None
    h2 = h.copy()
    block = h[a:b + 1].copy()
    h2[a:b + 1] = 0.0
    h2[na:nb + 1] = block
    return h2


def _split_block(h, a, b, ratio):
    """Split block [a,b] at midpoint, scaling halves by ratio."""
    L = b - a + 1
    if L < 4:
        return None
    mid = a + L // 2
    h2 = h.copy()
    h2[a:mid] *= ratio
    h2[mid:b + 1] /= ratio
    return h2


def _fill_gap(h, ga, gb):
    """Fill zero gap [ga,gb] with linear interpolation between neighbours."""
    n = h.size
    hl = h[ga - 1] if ga - 1 >= 0 else 0.0
    hr = h[gb + 1] if gb + 1 < n else 0.0
    if hl <= 0 and hr <= 0:
        return None
    h2 = h.copy()
    L = gb - ga + 2
    for i in range(ga, gb + 1):
        t = (i - ga + 1) / L
        h2[i] = (1 - t) * hl + t * hr
    return h2


def _widen_gap(h, ga, gb):
    """Zero one more cell adjacent to the gap."""
    n = h.size
    h2 = h.copy()
    if ga - 1 >= 0 and h[ga - 1] > 0:
        h2[ga - 1] = 0.0
    elif gb + 1 < n and h[gb + 1] > 0:
        h2[gb + 1] = 0.0
    else:
        return None
    return h2


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
    f01, f1, f5 = _near_max_fractions(best)
    print("base R=%.12f (N=%d) fracs 0.1%%=%.4f 1%%=%.4f 5%%=%.4f"
          % (bestR, best.size, f01, f1, f5))

    total_tried = 0
    accepted_any = False

    # ---------- Compound block-move sweep ----------
    sweep_end = deadline - 2.0
    sweep = 0
    while time.process_time() < sweep_end - 3.0:
        sweep += 1
        runs = _runs(best)
        gaps = _zero_gaps(best)
        # rank blocks by total mass
        block_order = sorted(range(len(runs)),
                             key=lambda i: -best[runs[i][0]:runs[i][1] + 1].sum())
        # rank gaps by length (short first) then position
        gap_order = sorted(range(len(gaps)),
                           key=lambda i: (gaps[i][1] - gaps[i][0], gaps[i][0]))

        best_cand = None
        best_cand_R = bestR
        best_info = None
        sweep_improved = False

        def try_candidate(h2, kind, k, raw_R):
            nonlocal best_cand, best_cand_R, best_info, total_tried
            if h2 is None or h2.sum() <= 0:
                return
            total_tried += 1
            if time.process_time() > sweep_end - 1.5:
                return
            # re-relax affected window
            a, b = kind[1], kind[2]
            lo = max(0, a - 3000)
            hi = min(h2.size, b + 3000)
            tlim = min(sweep_end - 1.0, time.process_time() + 2.5)
            hp = _window_lbfgs(h2, lo, hi, tlim, maxiter=200)
            tlim = min(sweep_end - 0.5, time.process_time() + 1.0)
            hw, rw = _peak_window(hp, tlim, R_of(hp), half=max(64, (hi - lo) // 2))
            rp = R_of(hw)
            if rp > best_cand_R + 1e-12:
                best_cand = hw
                best_cand_R = rp
                best_info = (kind[0], k, raw_R, rp)

        # iterate blocks
        for bi in block_order:
            if time.process_time() > sweep_end - 2.0:
                break
            a, b = runs[bi]
            # translations
            for k in (-3, -2, -1, 1, 2, 3):
                if time.process_time() > sweep_end - 2.0:
                    break
                h2 = _translate_block(best, a, b, k)
                if h2 is None:
                    continue
                raw_R = R_of(h2)
                try_candidate(h2, ('translate', a, b), k, raw_R)
            # splits
            for ratio in (0.5, 1.0, 2.0):
                if time.process_time() > sweep_end - 2.0:
                    break
                if ratio == 1.0:
                    continue  # no-op
                h2 = _split_block(best, a, b, ratio)
                if h2 is None:
                    continue
                raw_R = R_of(h2)
                try_candidate(h2, ('split', a, b), ratio, raw_R)

        # iterate gaps
        for gi in gap_order:
            if time.process_time() > sweep_end - 2.0:
                break
            ga, gb = gaps[gi]
            L = gb - ga + 1
            if L < 1 or L > 3:
                continue
            h2 = _fill_gap(best, ga, gb)
            if h2 is not None:
                raw_R = R_of(h2)
                try_candidate(h2, ('fill', max(0, ga - 1), min(best.size - 1, gb + 1)), 0, raw_R)
            h2 = _widen_gap(best, ga, gb)
            if h2 is not None:
                raw_R = R_of(h2)
                try_candidate(h2, ('widen', max(0, ga - 1), min(best.size - 1, gb + 1)), 0, raw_R)

        if best_cand is not None and best_cand_R > bestR + 1e-9:
            dR = best_cand_R - bestR
            kind, k, raw_R, rp = best_info
            print("sweep %d ACCEPT %s k=%s dR_raw=%.3e dR_pol=%.3e R=%.12f"
                  % (sweep, kind, k, raw_R - bestR, dR, best_cand_R))
            best = best_cand
            bestR = best_cand_R
            accepted_any = True
            sweep_improved = True
            f01, f1, f5 = _near_max_fractions(best)
            print("  fracs 0.1%%=%.4f 1%%=%.4f 5%%=%.4f tried=%d"
                  % (f01, f1, f5, total_tried))
        else:
            print("sweep %d: no acceptance (best polished %.12f, tried=%d)"
                  % (sweep, best_cand_R if best_cand is not None else bestR, total_tried))
            if not sweep_improved:
                break

    # ---------- Final polish: alternate full L-BFGS and peak window ----------
    while time.process_time() < deadline - 1.0:
        tlim = min(deadline - 0.5, time.process_time() + 3.0)
        hc = _full_lbfgs(best, tlim, maxiter=200)
        rc = R_of(hc)
        gained = False
        if rc > bestR + 1e-15:
            best = hc; bestR = rc
            print("full R=%.12f" % bestR)
            gained = True
        tlim = min(deadline - 0.5, time.process_time() + 3.0)
        hw, rw = _peak_window(best, tlim, bestR)
        if rw > bestR + 1e-15:
            best = hw; bestR = rw
            print("peakwin R=%.12f" % bestR)
            gained = True
        if not gained:
            break

    if bestR < startR:
        best = h0.copy()
        bestR = startR

    f01, f1, f5 = _near_max_fractions(best)
    print("final R=%.12f (start %.12f, N=%d) fracs 0.1%%=%.4f 1%%=%.4f 5%%=%.4f tried=%d"
          % (bestR, startR, best.size, f01, f1, f5, total_tried))

    if bestR > startR + 1e-15:
        return {"best": best, "alternative": h0}
    return {"best": h0, "alternative": best}
