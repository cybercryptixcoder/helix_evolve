import numpy as np
import time
from scipy.optimize import minimize, minimize_scalar
from scipy.fft import next_fast_len


def _knots(h):
    c = np.convolve(h, h)
    return np.concatenate(([0.0], c, [0.0]))


def _knots_fft(h):
    N = len(h)
    n = next_fast_len(2 * N - 1)
    H = np.fft.rfft(h, n)
    c = np.fft.irfft(H * H, n)[:2 * N - 1]
    return np.concatenate(([0.0], c, [0.0]))


def _knots_of(h):
    return _knots_fft(h) if len(h) > 4000 else _knots(h)


def R_of(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return -1.0
    L = _knots_of(h)
    sq = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    inf = L.max()
    if inf <= 0:
        return -1.0
    return sq / (s * s * inf)


def _A_and_dA(h):
    N = len(h)
    use_fft = N > 4000
    L = _knots_fft(h) if use_fft else _knots(h)
    dA_dL = (2.0 * L + np.concatenate(([0.0], L[:-1])) + np.concatenate((L[1:], [0.0]))) / 3.0
    dA_dc = dA_dL[1:len(L)-1]
    if use_fft:
        n = next_fast_len(2 * N - 1)
        C = np.fft.rfft(dA_dc, n)
        Hh = np.fft.rfft(h, n)
        dA_dh = 2.0 * np.fft.irfft(C * np.conj(Hh), n)[:N]
    else:
        dA_dh = 2.0 * np.correlate(dA_dc, h, mode='valid')
    A = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    return A, dA_dh, L


def R_and_grad(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros_like(h)
    N = len(h)
    A, dA_dh, L = _A_and_dA(h)
    B = s * s
    dB_dh = 2.0 * s
    m = L.max()
    dC_dh = np.zeros(N)
    idx = np.where(L >= m - 1e-15)[0]
    for kL in idx:
        k = kL - 1
        if 0 <= k <= 2 * N - 2:
            lo = max(0, k - N + 1)
            hi = min(N - 1, k)
            if lo <= hi:
                ii = np.arange(lo, hi + 1)
                dC_dh[ii] += 2.0 * h[k - ii] / len(idx)
    C = m
    dR_dh = (dA_dh * B - A * dB_dh) / (B * B * C) - A * dC_dh / (B * C * C)
    return A / (B * C), dR_dh


def R_beta_of(h, beta):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return -1.0
    L = _knots_of(h)
    sq = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    m = L.max()
    z = beta * (L - m)
    lse = m + np.log(np.sum(np.exp(z))) / beta
    if lse <= 0:
        return -1.0
    return sq / (s * s * lse)


def grad_R_beta(h, beta):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.zeros_like(h)
    N = len(h)
    A, dA_dh, L = _A_and_dA(h)
    B = s * s
    dB_dh = 2.0 * s
    m = L.max()
    z = beta * (L - m)
    ez = np.exp(z)
    sez = ez.sum()
    w = ez / sez
    lse = m + np.log(sez) / beta
    wshift = w[1:]
    if N > 4000:
        n = next_fast_len(2 * N - 1)
        W = np.fft.rfft(wshift, n)
        Hh = np.fft.rfft(h, n)
        conv = np.fft.irfft(W * Hh, n)
        dC_dh = 2.0 * conv[N-1:2*N-1]
    else:
        conv = np.convolve(wshift, h, mode='full')
        dC_dh = 2.0 * conv[N-1:2*N-1]
    C = lse
    dR_dh = (dA_dh * B - A * dB_dh) / (B * B * C) - A * dC_dh / (B * C * C)
    return dR_dh


def polish_exact(h, deadline, maxiter=500):
    h = np.asarray(h, dtype=float).copy()
    if time.process_time() >= deadline:
        return h
    try:
        res = minimize(
            fun=lambda x: -R_and_grad(x)[0],
            jac=lambda x: -R_and_grad(x)[1],
            x0=h, method='L-BFGS-B',
            bounds=[(0.0, None)] * len(h),
            options={'maxiter': maxiter, 'ftol': 1e-16, 'gtol': 1e-14, 'maxls': 40},
        )
        return np.maximum(0.0, res.x)
    except Exception:
        return h


def polish_beta(h, beta, deadline, maxiter=3000):
    h = np.asarray(h, dtype=float).copy()
    if time.process_time() >= deadline:
        return h
    try:
        res = minimize(
            fun=lambda x: -R_beta_of(x, beta),
            jac=lambda x: -grad_R_beta(x, beta),
            x0=h, method='L-BFGS-B',
            bounds=[(0.0, None)] * len(h),
            options={'maxiter': maxiter, 'ftol': 1e-16, 'gtol': 1e-13, 'maxls': 60},
        )
        return np.maximum(0.0, res.x)
    except Exception:
        return h


def resample_mass(h, M):
    """Mass-preserving upsampling via cumulative-mass interpolation."""
    h = np.asarray(h, dtype=float)
    N = len(h)
    S = np.concatenate(([0.0], np.cumsum(h)))
    x_new = np.arange(M + 1, dtype=float) * (N / M)
    S_new = np.interp(x_new, np.arange(N + 1, dtype=float), S)
    h_new = np.diff(S_new) * (M / N)
    return np.maximum(0.0, h_new)


def tail_modulated(h, gamma):
    h = np.asarray(h, dtype=float).copy()
    N = len(h)
    i = np.arange(N, dtype=float)
    mod = np.maximum(1.0 + gamma * (i / N), 0.0)
    return h * mod


def construct(budget_seconds, start):
    t0 = time.process_time()
    hard_deadline = t0 + budget_seconds * 0.88

    if start is not None:
        best = np.asarray(start, dtype=float).copy()
        best_r = R_of(best)
    else:
        best = np.ones(64)
        best_r = R_of(best)
    print("start R =", best_r, "N =", len(best))

    # Higher-N reconstruction to push resolution further than the start.
    M = 30000
    if len(best) != M:
        h_up = resample_mass(best, M)
    else:
        h_up = best.copy()
    r_up = R_of(h_up)
    print(f"upsampled R={r_up:.10f} N={len(h_up)}")

    if r_up >= best_r:
        work, work_r = h_up, r_up
    else:
        work, work_r = best.copy(), best_r

    # Gamma scan on tail modulation (fine grid).
    gammas = [-0.08, -0.04, -0.02, 0.0, 0.02, 0.04, 0.08]
    best_g = 0.0
    best_gr = work_r
    best_gh = work.copy()
    for g in gammas:
        if time.process_time() >= hard_deadline:
            break
        hg = tail_modulated(work, g)
        rg = R_of(hg)
        if rg > best_gr:
            best_gr, best_g, best_gh = rg, g, hg

    if time.process_time() < hard_deadline and best_gr >= work_r:
        try:
            def neg_R(g):
                return -R_of(tail_modulated(work, g))
            res = minimize_scalar(neg_R, bounds=(best_g - 0.04, best_g + 0.04),
                                  method='bounded', options={'xatol': 1e-5})
            g_fine = res.x
            hg = tail_modulated(work, g_fine)
            rg = R_of(hg)
            print(f"gamma_fine={g_fine:+.5f} R={rg:.10f}")
            if rg > best_gr:
                best_gr, best_gh = rg, hg
        except Exception:
            pass

    if best_gr > work_r:
        work, work_r = best_gh, best_gr
        print(f"gamma modulation gain -> R={work_r:.10f}")

    # Polish exact
    if time.process_time() < hard_deadline:
        rem = hard_deadline - time.process_time()
        sub = time.process_time() + rem * 0.30
        h_pol = polish_exact(work, sub, maxiter=3000)
        r_pol = R_of(h_pol)
        print(f"polished R={r_pol:.10f}")
        if r_pol > work_r:
            work, work_r = h_pol, r_pol

    # Beta ladder, continuing upward from the start's known range.
    for beta in (1e5, 1e6, 1e7, 1e8, 1e9):
        if time.process_time() >= hard_deadline:
            break
        rem = hard_deadline - time.process_time()
        sub = time.process_time() + rem * 0.35
        h = polish_beta(work, beta, sub, maxiter=1500)
        h2 = polish_exact(h, sub, maxiter=400)
        r2 = R_of(h2)
        if r2 > work_r:
            work, work_r = h2.copy(), r2
            print(f"beta={beta:.0e} R={work_r:.10f}")
        else:
            print(f"beta={beta:.0e} no gain (R={r2:.10f})")

    # Final exact polish with remaining time.
    if time.process_time() < hard_deadline:
        h_final = polish_exact(work, hard_deadline, maxiter=2000)
        r_final = R_of(h_final)
        if r_final > work_r:
            work, work_r = h_final, r_final

    if work_r > best_r:
        best, best_r = work, work_r

    best = np.maximum(0.0, best)
    print("final R =", best_r, "N =", len(best))
    return best
