import numpy as np
import time
from scipy.optimize import minimize


def _conv(h):
    n = h.size
    m = 1
    while m < 2 * n - 1:
        m *= 2
    H = np.fft.rfft(h, m)
    conv = np.fft.irfft(H * H, m)[:2 * n - 1]
    return np.maximum(conv, 0.0)


def _R_from_h(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0 or not np.all(np.isfinite(h)) or np.max(h) <= 0:
        return -1.0, None
    conv = _conv(h)
    L = np.concatenate(([0.0], conv, [0.0]))
    a = L[:-1]
    b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = float(np.sum(h)) ** 2
    linf = float(np.max(L))
    if linf <= 0 or l1 <= 0:
        return -1.0, None
    return l2sq / (l1 * linf), L


def _eval_grad(h):
    n = h.size
    conv = _conv(h)
    L = np.concatenate(([0.0], conv, [0.0]))
    a = L[:-1]
    b = L[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    S = float(np.sum(h))
    B = S * S
    m_idx = int(np.argmax(L))
    C = float(L[m_idx])
    if C <= 0 or B <= 0:
        return -1.0, None
    R = A / (B * C)

    g = 4.0 * L
    g[1:] += L[:-1]
    g[:-1] += L[1:]
    g /= 3.0

    Mg = 1
    while Mg < (2 * n + 1) + n:
        Mg *= 2
    G = np.fft.rfft(g, Mg)
    Hh = np.fft.rfft(h, Mg)
    corr = np.fft.irfft(np.conj(Hh) * G, Mg)
    dA = 2.0 * corr[:n]

    dB = 2.0 * S * np.ones(n)

    thresh = C * (1.0 - 1e-4)
    cand = np.flatnonzero(L >= thresh)
    if cand.size > 2000:
        order = np.argsort(L[cand])[::-1][:2000]
        cand = cand[order]
    w = np.exp((L[cand] - C) / (1e-3 * C))
    wsum = float(np.sum(w))
    dC = np.zeros(n)
    if wsum > 0:
        for idx, wi in zip(cand, w):
            lo = max(0, idx - (n - 1))
            hi = min(n - 1, idx)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                dC[ii] += (wi / wsum) * 2.0 * h[idx - ii]

    BC = B * C
    dR = (dA * BC - A * (dB * C + B * dC)) / (BC * BC)
    return R, dR


def _resample(h_old, N_new):
    n_old = h_old.size
    x_new = (np.arange(N_new) + 0.5) / N_new
    x_old = (np.arange(n_old) + 0.5) / n_old
    return np.interp(x_new, x_old, h_old)


def _lbfgsb_polish(h0, deadline, t0, maxiter=1000):
    h0 = np.asarray(h0, dtype=float)
    s = np.mean(h0)
    if s <= 0:
        return h0, -1.0
    h0 = h0 / s
    x0 = np.log(np.maximum(h0, 1e-12))
    n = x0.size
    bounds = [(-30.0, 10.0)] * n

    state = {'best_h': h0.copy(), 'best_R': -1.0}

    class _Timeout(Exception):
        pass

    def fun(x):
        if time.process_time() - t0 > deadline:
            raise _Timeout()
        h = np.exp(np.clip(x, -30.0, 10.0))
        sn = np.mean(h)
        if sn <= 0 or not np.isfinite(sn):
            return 1.0, np.zeros(n)
        h = h / sn
        R, dR = _eval_grad(h)
        if dR is None or not np.isfinite(R):
            return 1.0, np.zeros(n)
        if R > state['best_R']:
            state['best_R'] = R
            state['best_h'] = h.copy()
        gx = -(h * dR)
        gx = gx - np.mean(gx)
        return -R, gx

    try:
        res = minimize(fun, x0, method='L-BFGS-B', jac=True, bounds=bounds,
                       options={'ftol': 1e-15, 'gtol': 1e-11,
                                'maxiter': maxiter, 'maxfun': 100000,
                                'maxls': 50})
        if res is not None and res.x is not None:
            x = np.clip(res.x, -30.0, 10.0)
            h = np.exp(x)
            sn = np.mean(h)
            if sn > 0:
                h = h / sn
                R, _ = _R_from_h(h)
                if R > state['best_R']:
                    state['best_R'] = R
                    state['best_h'] = h.copy()
    except _Timeout:
        pass
    except Exception:
        pass
    return state['best_h'], state['best_R']


def _cand_perturb(h, frac, rng):
    """Smooth multiplicative perturbation on a low-frequency basis."""
    n = h.size
    k = max(8, int(frac * n))
    # smooth random bump
    t = np.linspace(0, 1, n)
    pert = np.zeros(n)
    for _ in range(6):
        freq = rng.uniform(0.5, 6.0)
        phase = rng.uniform(0, 2 * np.pi)
        amp = rng.uniform(0.2, 1.0)
        pert += amp * np.sin(2 * np.pi * freq * t + phase)
    pert /= (np.max(np.abs(pert)) + 1e-12)
    scale = 0.02 * frac
    return h * np.exp(scale * pert)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

    if start is None:
        h = np.ones(1000)
    else:
        h = np.maximum(np.asarray(start, dtype=float).copy(), 0.0)

    if h.size == 0 or np.max(h) <= 0:
        h = np.ones(1000)

    R0, _ = _R_from_h(h)
    best_h = h.copy()
    best_R = R0
    print(f"start R={R0:.6f}, N={h.size}")

    # Stage 1: resample to N=160000 and L-BFGS-B polish (the incumbent)
    N1 = 160000
    h1 = _resample(h, N1) if h.size != N1 else h.copy()
    s = np.mean(h1)
    if s > 0:
        h1 = h1 / s
    R1, _ = _R_from_h(h1)
    if R1 > best_R:
        best_R = R1
        best_h = h1.copy()
    print(f"after resample R={R1:.6f}, N={N1}, cpu={time.process_time()-t0:.2f}")

    if time.process_time() < deadline:
        h1p, R1p = _lbfgsb_polish(h1, deadline, t0, maxiter=1000)
        if R1p > best_R:
            best_R = R1p
            best_h = h1p.copy()
        print(f"L-BFGS-B stage1 R={R1p:.6f}, cpu={time.process_time()-t0:.2f}")

    # Stage 2: try multiple perturbations from current best at moderate N,
    # polish each briefly, keep the best. This escapes the incumbent basin.
    N2 = 80000
    rng = np.random.default_rng(12345)
    n_trials = 6
    for trial in range(n_trials):
        if time.process_time() > deadline - 2.0:
            break
        base = _resample(best_h, N2)
        s = np.mean(base)
        if s > 0:
            base = base / s
        frac = 0.5 if trial % 2 == 0 else 0.9
        cand = _cand_perturb(base, frac, rng)
        sn = np.mean(cand)
        if sn > 0:
            cand = cand / sn
        Rc, _ = _R_from_h(cand)
        # per-trial deadline: divide remaining time
        rem = deadline - time.process_time()
        trials_left = n_trials - trial
        sub_deadline = time.process_time() + max(0.5, rem / trials_left * 0.9)
        hc, Rcp = _lbfgsb_polish(cand, sub_deadline, t0, maxiter=200)
        if Rcp > Rc:
            Rc = Rcp
        if Rc > best_R:
            # resample to full resolution and polish
            hfull = _resample(hc, N1)
            sf = np.mean(hfull)
            if sf > 0:
                hfull = hfull / sf
            Rf, _ = _R_from_h(hfull)
            if Rf > best_R:
                best_R = Rf
                best_h = hfull.copy()
            # quick full-res polish if time
            if time.process_time() < deadline - 1.0:
                sub2 = min(deadline, time.process_time() + (deadline - time.process_time()) * 0.5)
                hfp, Rfp = _lbfgsb_polish(hfull, sub2, t0, maxiter=300)
                if Rfp > best_R:
                    best_R = Rfp
                    best_h = hfp.copy()
            print(f"trial {trial} improved R={best_R:.6f}, cpu={time.process_time()-t0:.2f}")

    # Final: if time remains, one more full-res polish of best
    if time.process_time() < deadline - 0.5:
        hf, Rf = _lbfgsb_polish(best_h, deadline, t0, maxiter=500)
        if Rf > best_R:
            best_R = Rf
            best_h = hf.copy()

    if start is not None:
        Rorig, _ = _R_from_h(np.maximum(np.asarray(start, dtype=float), 0.0))
        if Rorig > best_R:
            best_h = np.maximum(np.asarray(start, dtype=float), 0.0)
            best_R = Rorig

    best_h = np.maximum(best_h, 0.0)
    if best_h.size > 200000:
        best_h = _resample(best_h, 200000)
    if np.max(best_h) <= 0:
        best_h = np.ones(1000)
    print(f"best R={best_R:.6f}, N={best_h.size}, cpu={time.process_time()-t0:.2f}")
    return best_h
