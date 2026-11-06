import numpy as np
import time
from scipy.optimize import minimize


def _C(h):
    s = h.sum()
    if s <= 0 or not np.isfinite(s):
        return np.inf
    N = h.size
    m = np.max(np.convolve(h, h))
    return 2.0 * N * m / (s * s)


def _C_fft(h):
    s = h.sum()
    if s <= 0 or not np.isfinite(s):
        return np.inf
    N = h.size
    L = 1
    while L < 2 * N:
        L *= 2
    H = np.fft.rfft(h, L)
    conv = np.fft.irfft(H * H, L)[:2 * N - 1]
    return 2.0 * N * np.max(conv) / (s * s)


def _resample(h, N):
    h = np.asarray(h, dtype=float)
    M = h.size
    if M == N:
        return h.copy()
    xi = np.linspace(0.0, 1.0, M)
    xo = np.linspace(0.0, 1.0, N)
    return np.interp(xo, xi, h)


def _smooth_max(conv, beta):
    m = conv.max()
    z = beta * (conv - m)
    mx = z.max()
    w = np.exp(z - mx)
    S = w.sum()
    return m + (mx + np.log(S)) / beta, w / S


def _make_fg_fft(N, beta):
    L = 1
    while L < 2 * N:
        L *= 2

    def fg(h):
        h = np.maximum(h, 0.0)
        s = h.sum()
        if s <= 0:
            return 1e30, np.zeros_like(h)
        H = np.fft.rfft(h, L)
        conv = np.fft.irfft(H * H, L)[:2 * N - 1]
        lse, w = _smooth_max(conv, beta)
        Lc = 2.0 * N * lse / (s * s)
        wpad = np.zeros(L)
        wpad[:2 * N - 1] = w
        Wf = np.fft.rfft(wpad, L)
        corr = np.fft.irfft(Wf * H, L)
        grad_conv = 2.0 * corr[:N]
        g = 2.0 * N / (s * s) * grad_conv - 2.0 * Lc / s
        return Lc, g
    return fg


def _make_fg(N, beta):
    def fg(h):
        h = np.maximum(h, 0.0)
        s = h.sum()
        if s <= 0:
            return 1e30, np.zeros_like(h)
        conv = np.convolve(h, h)
        lse, w = _smooth_max(conv, beta)
        L = 2.0 * N * lse / (s * s)
        grad_conv = 2.0 * np.convolve(w, h[::-1])[N - 1:2 * N - 1]
        g = 2.0 * N / (s * s) * grad_conv - 2.0 * L / s
        return L, g
    return fg


def _polish_fft(h, best_C, best_h, deadline, betas=(1e3, 1e5, 1e7, 1e9), lb=0.0, maxiter=150):
    h = np.maximum(h, lb)
    if h.sum() <= 0:
        return best_C, best_h
    N = h.size
    h = h / h.sum() * N
    for beta in betas:
        if time.process_time() >= deadline:
            break
        fg = _make_fg_fft(N, beta)
        try:
            res = minimize(fg, h, method='L-BFGS-B', jac=True,
                           bounds=[(lb, None)] * N,
                           options={'maxiter': maxiter, 'ftol': 1e-17, 'gtol': 1e-14})
            h = np.maximum(res.x, lb)
        except Exception:
            pass
        c = _C_fft(h)
        if c < best_C:
            best_C = c
            best_h = h.copy()
    return best_C, best_h


def _polish(h, best_C, best_h, deadline, betas=(1e3, 1e5, 1e7, 1e9), lb=0.0, maxiter=300):
    h = np.maximum(h, lb)
    if h.sum() <= 0:
        return best_C, best_h
    N = h.size
    h = h / h.sum() * N
    for beta in betas:
        if time.process_time() >= deadline:
            break
        fg = _make_fg(N, beta)
        try:
            res = minimize(fg, h, method='L-BFGS-B', jac=True,
                           bounds=[(lb, None)] * N,
                           options={'maxiter': maxiter, 'ftol': 1e-17, 'gtol': 1e-14})
            h = np.maximum(res.x, lb)
        except Exception:
            pass
        c = _C(h)
        if c < best_C:
            best_C = c
            best_h = h.copy()
    return best_C, best_h


def _tilt_step(h, deadline, max_iter=80):
    N = h.size
    h = np.maximum(h, 0.0)
    s = h.sum()
    if s <= 0:
        return h
    h = h / s * N
    best_h = h.copy()
    best_C = _C(h)

    for it in range(max_iter):
        if time.process_time() >= deadline:
            break
        conv = np.convolve(h, h)
        cmax = conv.max()
        band = 1e-6 * max(cmax, 1e-30)
        active = np.where(conv >= cmax - band)[0]
        if active.size < 2:
            M = min(20, conv.size)
            active = np.argpartition(conv, conv.size - M)[conv.size - M:]
            active.sort()
        w = np.zeros_like(conv)
        w[active] = 1.0
        w /= w.sum()
        grad = 2.0 * np.convolve(w, h[::-1])[N - 1:2 * N - 1]
        grad = grad - grad.mean()
        scale = np.max(np.abs(grad)) + 1e-30
        step = 0.05
        improved = False
        for _ in range(25):
            h_try = h - step * (grad / scale) * h
            h_try = np.maximum(h_try, 0.0)
            if h_try.sum() <= 0:
                step *= 0.5
                continue
            c_try = _C(h_try)
            if c_try < best_C - 1e-16:
                h = h_try
                best_C = c_try
                best_h = h.copy()
                improved = True
                break
            step *= 0.5
        if not improved:
            break
    return best_h


def _equalize(h, deadline, iters=200, band_rel=1e-4):
    N = h.size
    h = np.maximum(h, 0.0)
    s = h.sum()
    if s <= 0:
        return h
    h = h / s * N
    best_h = h.copy()
    best_C = _C(h)
    for it in range(iters):
        if time.process_time() >= deadline:
            break
        conv = np.convolve(h, h)
        cmax = conv.max()
        band = band_rel * max(cmax, 1e-30)
        active = np.where(conv >= cmax - band)[0]
        if active.size < 2:
            M = min(15, conv.size)
            active = np.argpartition(conv, conv.size - M)[conv.size - M:]
            active.sort()
        w = np.zeros_like(conv)
        w[active] = 1.0
        w /= w.sum()
        grad = 2.0 * np.convolve(w, h[::-1])[N - 1:2 * N - 1]
        grad = grad - grad.mean()
        scale = np.max(np.abs(grad)) + 1e-30
        step = 0.02
        improved = False
        for _ in range(30):
            h_try = h - step * (grad / scale) * h
            h_try = np.maximum(h_try, 0.0)
            if h_try.sum() <= 0:
                step *= 0.5
                continue
            c_try = _C(h_try)
            if c_try < best_C - 1e-16:
                h = h_try
                best_C = c_try
                best_h = h.copy()
                improved = True
                break
            step *= 0.5
        if not improved:
            break
    return best_h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85

    best_h = None
    best_C = np.inf

    if start is not None:
        hs = np.asarray(start, dtype=float)
        if hs.ndim == 1 and hs.size > 0 and hs.sum() > 0 and np.all(np.isfinite(hs)):
            hs = np.maximum(hs, 0.0)
            c = _C(hs)
            if c < best_C:
                best_C, best_h = c, hs.copy()

    if best_h is None:
        N = 200
        x = -0.25 + (np.arange(N) + 0.5) / (2.0 * N)
        best_h = np.cos(2 * np.pi * x) ** 4 + 1e-3
        best_C = _C(best_h)

    # --- Stage 1: high-res FFT polish at 4096 ---
    high_deadline = min(deadline, t0 + budget_seconds * 0.45)
    N_hi = 4096
    if time.process_time() < high_deadline:
        h_hi = np.maximum(_resample(best_h, N_hi), 0.0)
        if h_hi.sum() > 0:
            c_hi = _C_fft(h_hi)
            c2, h2 = _polish_fft(h_hi.copy(), c_hi, h_hi.copy(),
                                 high_deadline, maxiter=120)
            if c2 < best_C:
                best_C = c2
                best_h = h2.copy()

    # --- Stage 2: multi-resolution L-BFGS polish + equalize ---
    for N in (320, 320, 640, 320, 1280, 320):
        if time.process_time() >= deadline:
            break
        h0 = np.maximum(_resample(best_h, N), 0.0)
        if h0.sum() <= 0:
            continue
        c_p, h_p = _polish(h0.copy(), _C(h0), h0.copy(), deadline,
                           betas=(1e3, 1e5, 1e7, 1e9, 1e11), maxiter=300)
        if c_p < best_C:
            best_C, best_h = c_p, h_p.copy()
        if time.process_time() >= deadline:
            break
        h_e = _equalize(best_h.copy(), deadline, iters=150, band_rel=3e-4)
        if h_e.size == best_h.size:
            c_e = _C(h_e)
            if c_e < best_C:
                best_C, best_h = c_e, h_e.copy()
        if time.process_time() >= deadline:
            break
        h_t = _tilt_step(best_h.copy(), deadline, max_iter=60)
        if h_t.size == best_h.size:
            c_t = _C(h_t)
            if c_t < best_C:
                best_C, best_h = c_t, h_t.copy()

    # --- Stage 3: final high-beta polish at best N ---
    if time.process_time() < deadline:
        best_C, best_h = _polish(best_h.copy(), best_C, best_h.copy(), deadline,
                                 betas=(1e9, 1e11, 1e13), maxiter=300)
    if time.process_time() < deadline:
        best_C, best_h = _polish_fft(best_h.copy(), best_C, best_h.copy(), deadline,
                                     betas=(1e7, 1e9, 1e11), maxiter=200)

    return np.maximum(np.asarray(best_h, dtype=float), 0.0)
