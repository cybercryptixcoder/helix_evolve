import numpy as np
import time
import random
from scipy.optimize import minimize


def _R(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0 or not np.all(np.isfinite(h)):
        return -1.0
    s = h.sum()
    if s <= 0:
        return -1.0
    conv, _, _ = _conv_fft(h)
    L = np.empty(conv.size + 2, dtype=float)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = conv
    a = L[:-1]
    b = L[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    linf = L.max()
    if linf <= 0:
        return -1.0
    return l2sq / (l1 * linf)


def _conv_fft(h):
    N = h.size
    nfft = 1
    while nfft < 2 * N:
        nfft <<= 1
    H = np.fft.rfft(h, nfft)
    conv = np.fft.irfft(H * H, nfft)[:2 * N - 1]
    return conv, H, nfft


def _Rs_and_grad_exact(h, eps=1e-9, tau=None):
    h = np.asarray(h, dtype=float)
    N = h.size
    s = h.sum()
    if s <= 0:
        return -1e9, np.zeros_like(h)
    conv, H, nfft = _conv_fft(h)
    L = np.empty(conv.size + 2, dtype=float)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = conv
    a = L[:-1]
    b = L[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    B = s * s
    M = L.max()
    if M <= 0:
        return -1e9, np.zeros_like(h)
    R = A / (B * M)

    dA_dL = np.zeros_like(L)
    dA_dL[:-1] += (2.0 * a + b) / 3.0
    dA_dL[1:] += (a + 2.0 * b) / 3.0

    if tau is not None and tau > 0:
        w = np.exp((L - M) / tau)
        sw = w.sum()
        dM_dL = w / sw if sw > 0 else np.zeros_like(L)
        if sw <= 0:
            dM_dL[np.argmax(L)] = 1.0
    else:
        thr = M * (1.0 - eps)
        act = L >= thr
        nact = act.sum()
        if nact == 0:
            act = np.zeros_like(L, dtype=bool)
            act[np.argmax(L)] = True
            nact = 1
        dM_dL = act.astype(float) / nact

    dR_dL = dA_dL / (B * M) - A / (B * M * M) * dM_dL
    dR_dh_direct = -A / (B * B * M) * 2.0 * s

    dR_dconv = dR_dL[1:-1]
    D = np.fft.rfft(dR_dconv, nfft)
    c = np.fft.irfft(D * np.conj(H), nfft)[:N]
    grad = 2.0 * c + dR_dh_direct
    return R, grad


def _logS_lse_and_grad(h, tau_rel):
    h = np.asarray(h, dtype=float)
    N = h.size
    s = h.sum()
    if s <= 0:
        return -1e9, np.zeros_like(h)
    conv, H, nfft = _conv_fft(h)
    L = np.empty(conv.size + 2, dtype=float)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = conv
    a = L[:-1]
    b = L[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    B = s * s
    if A <= 0:
        return -1e9, np.zeros_like(h)
    Lmax = L.max()
    if Lmax <= 0:
        return -1e9, np.zeros_like(h)
    tau = tau_rel * Lmax
    if tau <= 0:
        tau = 1e-300
    z = (L - Lmax) / tau
    w = np.exp(z)
    sw = w.sum()
    if sw <= 0 or not np.isfinite(sw):
        M_tau = Lmax
        dM_dL = np.zeros_like(L)
        dM_dL[np.argmax(L)] = 1.0
    else:
        M_tau = Lmax + tau * np.log(sw)
        dM_dL = w / sw
    if M_tau <= 0:
        return -1e9, np.zeros_like(h)
    logS = np.log(A) - np.log(B) - np.log(M_tau)

    dA_dL = np.zeros_like(L)
    dA_dL[:-1] += (2.0 * a + b) / 3.0
    dA_dL[1:] += (a + 2.0 * b) / 3.0

    dlogS_dL = dA_dL / A - dM_dL / M_tau
    dlogS_dh_direct = -2.0 / s

    dlogS_dconv = dlogS_dL[1:-1]
    D = np.fft.rfft(dlogS_dconv, nfft)
    c = np.fft.irfft(D * np.conj(H), nfft)[:N]
    grad = 2.0 * c + dlogS_dh_direct
    return logS, grad


def _polish_lse(h0, tau_rel, maxiter):
    N = h0.size
    bounds = [(0.0, None)] * N

    def fg(x):
        r, g = _logS_lse_and_grad(x, tau_rel)
        return -r, -g

    try:
        res = minimize(fg, h0, jac=True, method='L-BFGS-B', bounds=bounds,
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-11})
        return np.maximum(res.x, 0.0)
    except Exception:
        return h0


def _polish_exact(h0, maxiter, tau=None, eps=1e-9):
    N = h0.size
    bounds = [(0.0, None)] * N

    def fg(x):
        r, g = _Rs_and_grad_exact(x, eps=eps, tau=tau)
        return -r, -g

    try:
        res = minimize(fg, h0, jac=True, method='L-BFGS-B', bounds=bounds,
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-11})
        return np.maximum(res.x, 0.0)
    except Exception:
        return h0


def _binomial_seq(M):
    h = np.empty(M, dtype=float)
    h[0] = 1.0
    for i in range(M - 1):
        h[i + 1] = h[i] * (2.0 * i + 1.0) / (2.0 * i + 2.0)
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    loop_end = t0 + budget_seconds * 0.85

    # NEW: exact binomial sequence candidates (now including M=50000).
    best_h = None
    best_r = -1.0
    for M in (256, 512, 1024, 2048, 4096, 8192, 16384, 25000, 50000):
        hb = _binomial_seq(M)
        m = hb.max()
        if m > 0:
            hb = hb / m
        r = _R(hb)
        if r > best_r:
            best_r = r
            best_h = hb

    if start is not None:
        hs = np.maximum(np.asarray(start, dtype=float).ravel(), 0.0)
        if hs.sum() > 0:
            rs = _R(hs)
            if rs > best_r:
                best_r = rs
                best_h = hs

    if best_h is None or best_h.sum() <= 0:
        x = np.linspace(-1.0, 1.0, 4001)
        best_h = 1.0 - np.abs(x)
    m = best_h.max()
    if m > 0:
        best_h = best_h / m
    best_h = best_h.copy()
    best_r = _R(best_h)

    def try_h(h_try, thresh=1e-13):
        nonlocal best_h, best_r
        r = _R(h_try)
        if r > best_r + thresh:
            best_r = r
            best_h = h_try
            return True
        return False

    taus = (1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 3e-6, 1e-6)
    h_cur = best_h.copy()
    for tau_rel in taus:
        if time.process_time() >= loop_end:
            break
        h_l = _polish_lse(h_cur, tau_rel, 1000)
        r_l = _R(h_l)
        if r_l > best_r - 1e-6:
            h_cur = h_l
            try_h(h_l)
    if time.process_time() < loop_end:
        h_ex = _polish_exact(h_cur, 3000)
        try_h(h_ex)

    for _ in range(3):
        if time.process_time() >= loop_end:
            break
        h_try = _polish_exact(best_h, 3000)
        try_h(h_try)
        if time.process_time() >= loop_end:
            break
        hmax = best_h.max()
        h_prune = best_h.copy()
        h_prune[h_prune < 1e-9 * hmax] = 0.0
        try_h(_polish_exact(h_prune, 3000))

    return best_h
