import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _R_of(h):
    h = np.maximum(np.asarray(h, dtype=float).ravel(), 0.0)
    s = h.sum()
    if s <= 0:
        return -1.0
    c = np.convolve(h, h)
    L = np.concatenate(([0.0], c, [0.0]))
    seg = L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]
    l2 = seg.sum() / 3.0
    mx = L.max()
    if mx <= 0:
        return -1.0
    return l2 / (s * s * mx)


def _prep(h):
    h = np.maximum(np.asarray(h, dtype=float).ravel(), 0.0)
    m = h.max()
    if m > 0:
        h = h / m
    return h


def _R_and_grad(h, tau_frac=2e-4):
    h = np.maximum(np.asarray(h, dtype=float).ravel(), 0.0)
    N = h.size
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(N)
    c = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], c, [0.0]))
    seg = L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]
    A = seg.sum() / 3.0
    B = s * s
    mx = L.max()
    if mx <= 0:
        return -1.0, np.zeros(N)
    R = A / (B * mx)

    tau = tau_frac * mx
    z = L / tau
    zmax = z.max()
    e = np.exp(z - zmax)
    Z = e.sum()
    C = tau * (zmax + np.log(Z))
    wL = e / Z

    gA_L = np.zeros(2 * N + 1)
    gA_L[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    gA_L[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
    gA_c = gA_L[1:2 * N]
    conv = fftconvolve(gA_c, h[::-1], mode='full')
    gradA = 2.0 * conv[N - 1:2 * N - 1]

    gradB = 2.0 * s * np.ones(N)
    wc = wL[1:2 * N]
    convC = fftconvolve(wc, h[::-1], mode='full')
    gradC = 2.0 * convC[N - 1:2 * N - 1]

    num = gradA * (B * C) - A * (gradB * C + B * gradC)
    den = (B * C) ** 2
    return R, num / den


def _R_and_grad_hard(h, eps):
    h = np.maximum(np.asarray(h, dtype=float).ravel(), 0.0)
    N = h.size
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(N)
    c = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], c, [0.0]))
    seg = L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]
    A = seg.sum() / 3.0
    B = s * s
    mx = L.max()
    if mx <= 0:
        return -1.0, np.zeros(N)
    R = A / (B * mx)

    active = L >= mx - eps * mx
    na = active.sum()
    if na == 0:
        active = (L == mx)
        na = active.sum()
    wL = active.astype(float) / na
    C = mx

    gA_L = np.zeros(2 * N + 1)
    gA_L[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    gA_L[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
    gA_c = gA_L[1:2 * N]
    conv = fftconvolve(gA_c, h[::-1], mode='full')
    gradA = 2.0 * conv[N - 1:2 * N - 1]

    gradB = 2.0 * s * np.ones(N)
    wc = wL[1:2 * N]
    convC = fftconvolve(wc, h[::-1], mode='full')
    gradC = 2.0 * convC[N - 1:2 * N - 1]

    num = gradA * (B * C) - A * (gradB * C + B * gradC)
    den = (B * C) ** 2
    return R, num / den


def _lbfgsb(h, deadline, grad_fn, maxiter=500):
    h0 = _prep(h)
    if deadline - time.process_time() <= 0.05:
        return h0, _R_of(h0)

    def neg_obj(x):
        r, g = grad_fn(x)
        return -r, -g

    try:
        res = minimize(
            neg_obj, h0, jac=True, method='L-BFGS-B',
            bounds=[(0.0, None)] * h0.size,
            options={'maxiter': maxiter, 'maxfun': maxiter + 300,
                     'ftol': 1e-17, 'gtol': 1e-13},
        )
        x = np.maximum(res.x, 0.0)
        if x.sum() > 0:
            x = _prep(x)
            r = _R_of(x)
            if r >= _R_of(h0):
                return x, r
    except Exception:
        pass
    return h0, _R_of(h0)


def _upsample2(h):
    n = h.size
    x_old = np.linspace(0.0, 1.0, n)
    x_new = np.linspace(0.0, 1.0, 2 * n)
    return np.interp(x_new, x_old, h)


def _pool2(h2):
    n2 = h2.size
    n = n2 // 2
    return 0.5 * (h2[0:2 * n:2] + h2[1:2 * n:2])


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + max(0.0, budget_seconds - 1.2)

    best_h = None
    best_R = -1.0

    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size and s.size <= 50000 and np.isfinite(s).all() and s.sum() > 0:
            s = np.maximum(s, 0.0)
            r = _R_of(s)
            if r > best_R:
                best_R = r
                best_h = s.copy()

    if best_h is None:
        x = np.linspace(-1.0, 1.0, 600)
        best_h = np.exp(-4.0 * x * x)
        best_R = _R_of(best_h)

    def try_update(h, r):
        nonlocal best_h, best_R
        if r > best_R + 1e-15:
            best_R = r
            best_h = _prep(h)
            return True
        return False

    # Phase 1: upsample to 2N, refine with smooth barrier, pool back.
    N0 = best_h.size
    if N0 <= 25000:
        h2 = _prep(_upsample2(_prep(best_h)))
        phase_end = min(deadline, time.process_time() + max(3.0, (deadline - time.process_time()) * 0.45))
        for tau in (1e-5, 3e-6, 1e-6, 3e-7):
            rem = phase_end - time.process_time()
            if rem < 0.3:
                break
            sub = time.process_time() + min(3.0, max(0.4, rem * 0.6))
            h2, _ = _lbfgsb(h2, sub, lambda x, t=tau: _R_and_grad(x, tau_frac=t), maxiter=400)
        if h2.size == 2 * N0:
            hp = _prep(_pool2(h2))
        else:
            xo = np.linspace(0.0, 1.0, h2.size)
            xn = np.linspace(0.0, 1.0, N0)
            hp = _prep(np.interp(xn, xo, h2))
        try_update(hp, _R_of(hp))

    # Phase 2: alternate hard and smooth polishes at native N.
    hard_eps = [1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11]
    smooth_taus = [1e-5, 1e-6, 1e-7, 1e-8, 1e-9, 1e-10]

    round_i = 0
    while time.process_time() < deadline - 0.2 and round_i < 14:
        round_i += 1
        progressed = False

        if time.process_time() < deadline - 0.15:
            eps = hard_eps[min(round_i - 1, len(hard_eps) - 1)]
            rem = deadline - time.process_time()
            sub = time.process_time() + max(0.2, min(2.5, rem * 0.5))
            hH, rH = _lbfgsb(best_h, sub,
                             lambda x, e=eps: _R_and_grad_hard(x, e),
                             maxiter=800)
            if try_update(hH, rH):
                progressed = True

        if time.process_time() < deadline - 0.15:
            tau = smooth_taus[min(round_i - 1, len(smooth_taus) - 1)]
            rem = deadline - time.process_time()
            sub = time.process_time() + max(0.2, min(2.5, rem * 0.5))
            hP, rP = _lbfgsb(best_h, sub,
                             lambda x, t=tau: _R_and_grad(x, tau_frac=t),
                             maxiter=800)
            if try_update(hP, rP):
                progressed = True

        if not progressed and round_i >= len(hard_eps):
            if round_i >= len(smooth_taus) + 1:
                break

    h = np.maximum(best_h, 0.0)
    if h.sum() <= 0:
        h = np.ones(best_h.size)
    return h
