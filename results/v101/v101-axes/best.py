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


def _rescale_sum(h):
    h = np.clip(h, 0, None)
    s = h.sum()
    if s <= 0:
        return h
    return h / s


def _rescale_sum_scaled(h, T):
    h = np.clip(h, 0, None)
    s = h.sum()
    if s <= 0:
        return h
    return h / s * T


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


def _fun_grad_band(h, band):
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(h.size), 0
    num, dq, Lf = _num_and_dq(h)
    mx = Lf.max()
    Lm = mx
    gLf = -dq / num
    idx = np.flatnonzero(Lf >= mx * (1.0 - band))
    if idx.size == 0:
        idx = np.array([int(np.argmax(Lf))])
    w = 1.0 / idx.size
    gLf[idx] += w / Lm
    grad = _backprop(gLf, h) + 2.0 / s
    val = -np.log(num) + 2.0 * np.log(s) + np.log(Lm)
    return val, grad, idx.size


def _make_cb(deadline):
    def cb(xk):
        if time.process_time() > deadline:
            raise TimeoutError
    return cb


def _full_lbfgs(h0, deadline, maxiter=150, mask=None, rescale=_rescale):
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0, 0, 0.0
    if mask is None:
        pos = np.flatnonzero(h > 0)
    else:
        pos = np.flatnonzero(mask)
    if pos.size == 0:
        return h0, 0, 0.0
    x0 = h[pos].copy()

    def f(x):
        hh = h.copy()
        hh[pos] = np.clip(x, 0.0, None)
        val, g = _fun_grad_tie(hh)
        return val, g[pos]

    cb = _make_cb(deadline - 0.2)
    nit = 0
    ginf = 0.0
    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * pos.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
        if res is not None:
            nit = int(getattr(res, 'nit', 0))
            try:
                ginf = float(np.max(np.abs(res.jac)))
            except Exception:
                ginf = 0.0
    except (TimeoutError, Exception):
        return h0, 0, 0.0
    if res is None:
        return h0, 0, 0.0
    h2 = h.copy()
    h2[pos] = np.clip(res.x, 0.0, None)
    return rescale(h2), nit, ginf


def _full_lbfgs_band(h0, band, deadline, maxiter=60, mask=None, rescale=_rescale):
    h = np.clip(h0, 0, None)
    if h.sum() <= 0:
        return h0, 0, 0, 0.0
    if mask is None:
        pos = np.flatnonzero(h > 0)
    else:
        pos = np.flatnonzero(mask)
    if pos.size == 0:
        return h0, 0, 0, 0.0
    x0 = h[pos].copy()
    band_size = [0]

    def f(x):
        hh = h.copy()
        hh[pos] = np.clip(x, 0.0, None)
        val, g, bs = _fun_grad_band(hh, band)
        band_size[0] = bs
        return val, g[pos]

    cb = _make_cb(deadline - 0.2)
    nit = 0
    ginf = 0.0
    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * pos.size,
                       callback=cb,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter,
                                'ftol': 1e-20, 'gtol': 1e-16})
        if res is not None:
            nit = int(getattr(res, 'nit', 0))
            try:
                ginf = float(np.max(np.abs(res.jac)))
            except Exception:
                ginf = 0.0
    except (TimeoutError, Exception):
        return h0, 0, band_size[0], 0.0
    if res is None:
        return h0, 0, band_size[0], 0.0
    h2 = h.copy()
    h2[pos] = np.clip(res.x, 0.0, None)
    return rescale(h2), nit, band_size[0], ginf


def _peak_window_mask(N, h, half):
    L = _knots(h)
    j = int(np.argmax(L))
    c = j - 0.5
    lo = int(max(0, np.floor(c - half)))
    hi = int(min(N, np.ceil(c + half) + 1))
    m = np.zeros(N, dtype=bool)
    m[lo:hi] = True
    return m


def _polish(h, t_end, rescale=_rescale, mi_full=150, mi_peak=120):
    now = time.process_time()
    if now >= t_end - 1.0:
        return h
    t_a = min(t_end, now + 10.0)
    hc, _, _ = _full_lbfgs(h, t_a, maxiter=mi_full, rescale=rescale)
    if R_of(hc) >= R_of(h):
        h = hc
    now = time.process_time()
    if now < t_end - 1.0:
        half = max(8, h.size // 8)
        m = _peak_window_mask(h.size, h, half)
        t_b = min(t_end, now + 6.0)
        hc2, _, _ = _full_lbfgs(h, t_b, maxiter=mi_peak, mask=m, rescale=rescale)
        if R_of(hc2) >= R_of(h):
            h = hc2
    return h


def _run_arm(h_seed, deadline, rescale, label):
    """Run p4488's schedule on one arm. Returns (best_h, bestR, table_rows)."""
    h = h_seed.copy()
    best = h.copy()
    bestR = R_of(h)
    rows = []

    def consider(hn):
        nonlocal best, bestR
        r = R_of(hn)
        if r > bestR + 1e-15:
            best = hn.copy(); bestR = r
            return True
        return False

    # (0) one 20 s full tie L-BFGS + 8 s peak-window polish
    now = time.process_time()
    if now >= deadline - 2.0:
        return best, bestR, rows
    t_a = min(deadline, now + 20.0)
    hc, nit, ginf = _full_lbfgs(h, t_a, maxiter=150, rescale=rescale)
    rc = R_of(hc)
    consider(hc)
    now = time.process_time()
    if now < deadline - 2.0:
        half = max(8, hc.size // 8)
        m = _peak_window_mask(hc.size, hc, half)
        t_b = min(deadline, now + 8.0)
        hc2, nit2, ginf2 = _full_lbfgs(hc, t_b, maxiter=120, mask=m, rescale=rescale)
        consider(hc2)
        rows.append((label, 0, nit, ginf, rc, nit2, ginf2, R_of(hc2)))
    else:
        rows.append((label, 0, nit, ginf, rc, 0, 0.0, rc))

    # (1) 8 rounds of 30 s full + 15 s peak-window polish
    for rnd in range(1, 9):
        now = time.process_time()
        if now >= deadline - 3.0:
            break
        t_a = min(deadline, now + 30.0)
        hf, nit, ginf = _full_lbfgs(best, t_a, maxiter=200, rescale=rescale)
        rf = R_of(hf)
        consider(hf)
        now = time.process_time()
        if now < deadline - 3.0:
            half = max(8, best.size // 8)
            mp = _peak_window_mask(best.size, best, half)
            t_b = min(deadline, now + 15.0)
            hp, nit2, ginf2 = _full_lbfgs(best, t_b, maxiter=120, mask=mp, rescale=rescale)
            rp = R_of(hp)
            consider(hp)
            rows.append((label, rnd, nit, ginf, rf, nit2, ginf2, rp))
        else:
            rows.append((label, rnd, nit, ginf, rf, 0, 0.0, rf))
    return best, bestR, rows


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
    print("base R=%.12f (N=%d, nnz=%d)" % (startR, h0.size, int((h0 > 0).sum())))

    # Three arms, identical seed (h0), identical time-boxed schedule.
    # Total arm budget: split the remaining time 3 ways, leaving a tail for the
    # final polish loop of the winning arm.
    now = time.process_time()
    remaining = deadline - now
    # reserve ~30% for the final polish of the winner
    arm_total = max(0.0, remaining * 0.68)
    per_arm = arm_total / 3.0

    def _rescale_C(h):
        return _rescale_sum_scaled(h, 1e-4)

    arms = [
        ("A", _rescale),
        ("B", _rescale_sum),
        ("C", _rescale_C),
    ]

    results = {}
    all_rows = []
    for label, resc in arms:
        now = time.process_time()
        arm_deadline = min(deadline, now + per_arm)
        if now >= deadline - 3.0:
            results[label] = (h0.copy(), startR)
            continue
        hb, rb, rows = _run_arm(h0, arm_deadline, resc, label)
        results[label] = (hb, rb)
        all_rows.extend(rows)
        print("arm %s done R=%.12f nnz=%d" % (label, rb, int((hb > 0).sum())))

    # Dense arm table
    print("=== arm table (arm round nit1 |g|1 R1 nit2 |g|2 R2) ===")
    for row in all_rows:
        label, rnd, nit, ginf, r1, nit2, ginf2, r2 = row
        print("%s r%d nit=%d g=%.3e R=%.12f | nit=%d g=%.3e R=%.12f" %
              (label, rnd, nit, ginf, r1, nit2, ginf2, r2))

    # Pick the best arm by exact R
    best_label = None
    best_h = h0.copy()
    bestR = startR
    for label, _ in arms:
        if label in results:
            hb, rb = results[label]
            if rb > bestR + 1e-15:
                best_h = hb.copy(); bestR = rb; best_label = label
    if best_label is None:
        best_label = "A"
        if "A" in results:
            best_h, bestR = results["A"]
    print("winning arm %s R=%.12f" % (best_label, bestR))

    # Spend remaining time in p4488's polish loop on the winner.
    try:
        while time.process_time() < deadline - 3.0:
            t_a = min(deadline, time.process_time() + 30.0)
            hf, _, _ = _full_lbfgs(best_h, t_a, maxiter=200, rescale=_rescale)
            if R_of(hf) > bestR + 1e-15:
                best_h = hf; bestR = R_of(hf)
            if time.process_time() > deadline - 3.0:
                break
            half = max(8, best_h.size // 8)
            mp = _peak_window_mask(best_h.size, best_h, half)
            t_b = min(deadline, time.process_time() + 15.0)
            hp, _, _ = _full_lbfgs(best_h, t_b, maxiter=120, mask=mp, rescale=_rescale)
            if R_of(hp) > bestR + 1e-15:
                best_h = hp; bestR = R_of(hp)
            print("polish R=%.12f nnz=%d N=%d" % (bestR, int((best_h > 0).sum()), best_h.size))
    except Exception as e:
        print("final polish failed:", e)

    print("final R=%.12f (start %.12f, N=%d, nnz=%d)" %
          (bestR, startR, best_h.size, int((best_h > 0).sum())))

    # Return: best if it beats start, else best as alternative.
    if bestR > startR + 1e-15:
        return {"best": best_h, "alternative": h0}
    return {"best": h0, "alternative": best_h}
