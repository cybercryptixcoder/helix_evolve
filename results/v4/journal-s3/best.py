import numpy as np
import time
from scipy.optimize import minimize


def R_of(h):
    h = np.asarray(h, dtype=float)
    if h.ndim != 1 or h.size == 0:
        return -1.0
    s = h.sum()
    if not np.isfinite(s) or s <= 0:
        return -1.0
    L = np.concatenate(([0.0], np.convolve(h, h), [0.0]))
    m = L.max()
    if m <= 0:
        return -1.0
    q = (L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]).sum() / 3.0
    denom = (s * s) * m
    if denom <= 0:
        return -1.0
    return q / denom


def R_of_fft(h):
    """Exact R using FFT convolution (faster for large N)."""
    h = np.asarray(h, dtype=float)
    if h.ndim != 1 or h.size == 0:
        return -1.0
    s = h.sum()
    if not np.isfinite(s) or s <= 0:
        return -1.0
    N = h.size
    nfft = 1
    while nfft < 2 * N:
        nfft *= 2
    H = np.fft.rfft(h, nfft)
    c = np.fft.irfft(H * H, nfft)[:2 * N - 1]
    L = np.empty(2 * N + 1)
    L[0] = 0.0
    L[1:2 * N] = c
    L[2 * N] = 0.0
    m = L.max()
    if m <= 0:
        return -1.0
    q = (L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]).sum() / 3.0
    denom = (s * s) * m
    if denom <= 0:
        return -1.0
    return q / denom


def recurrence_exact(N):
    """h_n = C(2n,n)/4^n, the M=1 recurrence, computed directly."""
    h = np.empty(N)
    h[0] = 1.0
    for n in range(1, N):
        h[n] = h[n - 1] * (2 * n - 1) / (2 * n)
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85

    def time_left():
        return time.process_time() < deadline

    if start is not None:
        h0 = np.asarray(start, dtype=float).copy()
        h0 = np.clip(h0, 0.0, None)
        if h0.sum() <= 0:
            h0 = np.ones(50)
    else:
        n = 50
        x = (np.arange(n) + 0.5) / n
        h0 = np.clip(np.cos(np.pi * (x - 0.5)) ** 2, 0.0, None)

    best = h0.copy()
    bestR = R_of(best)

    # --- Build exact M=1 recurrence at high N (the Abel kernel) ---
    N_rec = 200000
    h_rec = None
    if time_left():
        h_rec = recurrence_exact(N_rec)
        r = R_of_fft(h_rec)
        if r > bestR:
            bestR = r
            best = h_rec.copy()

    # --- Experiment: global smooth multiplicative perturbation ---
    # h2_i = h_i * (1 + a * t_i^p), t_i = (i+0.5)/N
    if h_rec is not None and time_left():
        N = h_rec.size
        t = (np.arange(N) + 0.5) / N
        a_list = [-0.3, -0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2, 0.3, 0.5]
        p_list = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]

        best_a, best_p, best_r_pert = 0.0, 1.0, bestR
        for p in p_list:
            tp = t ** p
            for a in a_list:
                if not time_left():
                    break
                h2 = h_rec * (1.0 + a * tp)
                h2 = np.clip(h2, 0.0, None)
                r = R_of_fft(h2)
                if r > best_r_pert:
                    best_r_pert = r
                    best_a, best_p = a, p
                    if r > bestR:
                        bestR = r
                        best = h2.copy()
            if not time_left():
                break

        # --- Refine best (a, p) with Nelder-Mead ---
        if time_left() and best_r_pert > 0:
            def neg_r_ap(x):
                a, p = x
                p = max(0.05, min(32.0, p))
                h2 = h_rec * (1.0 + a * (t ** p))
                h2 = np.clip(h2, 0.0, None)
                return -R_of_fft(h2)

            x0 = np.array([best_a, best_p])
            try:
                res = minimize(neg_r_ap, x0, method='Nelder-Mead',
                               options={'maxiter': 200, 'xatol': 1e-4,
                                        'fatol': 1e-8})
                a_r, p_r = res.x
                p_r = max(0.05, min(32.0, p_r))
                h2 = h_rec * (1.0 + a_r * (t ** p_r))
                h2 = np.clip(h2, 0.0, None)
                r = R_of_fft(h2)
                if r > bestR:
                    bestR = r
                    best = h2.copy()
                    best_a, best_p = a_r, p_r
            except Exception:
                pass

        # --- Optionally add b * t^2 term with short Nelder-Mead on (a,p,b) ---
        if time_left():
            t2 = t ** 2

            def neg_r_apb(x):
                a, p, b = x
                p = max(0.05, min(32.0, p))
                h2 = h_rec * (1.0 + a * (t ** p) + b * t2)
                h2 = np.clip(h2, 0.0, None)
                return -R_of_fft(h2)

            x0 = np.array([best_a, best_p, 0.0])
            try:
                res = minimize(neg_r_apb, x0, method='Nelder-Mead',
                               options={'maxiter': 300, 'xatol': 1e-4,
                                        'fatol': 1e-8})
                a_r, p_r, b_r = res.x
                p_r = max(0.05, min(32.0, p_r))
                h2 = h_rec * (1.0 + a_r * (t ** p_r) + b_r * t2)
                h2 = np.clip(h2, 0.0, None)
                r = R_of_fft(h2)
                if r > bestR:
                    bestR = r
                    best = h2.copy()
            except Exception:
                pass

    # --- Right-tail multiplier scan on the best candidate (from base) ---
    if time_left() and best.size >= 1000:
        N = best.size
        base_h = best.copy()
        half = N // 2
        idx = np.arange(N)
        tt = np.zeros(N)
        tt[half:] = ((idx[half:] - half) / half) ** 2
        for a in np.linspace(0.0, 0.3, 16):
            if not time_left():
                break
            h2 = base_h * (1.0 + a * tt)
            h2 = np.clip(h2, 0.0, None)
            r = R_of_fft(h2)
            if r > bestR:
                bestR = r
                best = h2.copy()

    return best
