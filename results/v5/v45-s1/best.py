import numpy as np
import time
import math


def _score(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0 or not np.all(np.isfinite(h)) or h.max() <= 0:
        return -1.0
    h = np.maximum(h, 0.0)
    c = np.convolve(h, h)
    L = np.concatenate(([0.0], c, [0.0]))
    num = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    s = h.sum()
    den = s * s * L.max()
    if den <= 0:
        return -1.0
    return num / den


def _upsample_mass(h, N):
    """Resample step function to N steps preserving mass and shape (piecewise constant)."""
    h = np.asarray(h, dtype=float)
    n = h.size
    if n == N:
        return h.copy()
    # cumulative mass at original breakpoints
    xp = np.linspace(0.0, 1.0, n + 1)
    cp = np.concatenate(([0.0], np.cumsum(h)))
    total = cp[-1]
    if total <= 0:
        return np.ones(N) * (total / N)
    xq = np.linspace(0.0, 1.0, N + 1)
    cq = np.interp(xq, xp, cp)
    out = np.diff(cq)
    # scale to preserve total mass
    s = out.sum()
    if s > 0:
        out *= total / s
    return np.maximum(out, 0.0)


def _fft_grad(h):
    """Analytic gradient of R wrt h using FFT-based convolution."""
    n = h.size
    # pad to avoid circular wrap
    m = 1
    while m < 2 * n:
        m *= 2
    H = np.fft.rfft(h, m)
    C = H * H  # autoconvolution spectrum
    c = np.fft.irfft(C, m)[:2 * n - 1]  # length 2n-1
    L = np.concatenate(([0.0], c, [0.0]))  # length 2n+1
    # numerator: sum over j of (L_j^2 + L_j L_{j+1} + L_{j+1}^2)/3
    num = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    s = h.sum()
    Lmax = L.max()
    den = s * s * Lmax
    if den <= 0:
        return -1.0, np.zeros_like(h)
    R = num / den
    # d num / d L_j = (2 L_j + L_{j+1} + L_{j-1})/3 (with boundary handling)
    dL = np.zeros_like(L)
    dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    dL[1:] += (2.0 * L[1:] + L[:-1]) / 3.0
    # dL/dc = shift by 1
    dc = dL[1:-1]  # length 2n-1
    # d num / d h via convolution: num = sum dc_k c_k, c = h*h
    # d/dh_i sum_k dc_k c_k = 2 * sum_t dc_{i+t} h_t (correlation)
    # use FFT: correlation of dc with h
    m2 = 1
    while m2 < 2 * n:
        m2 *= 2
    DC = np.fft.rfft(dc, m2)
    Hh = np.fft.rfft(h, m2)
    # correlation: sum_t dc[i+t] h[t]  -> ifft(DC * conj(Hh))? Let's do direct:
    # c_k = sum_t h_t h_{k-t}. d c_k / d h_i = 2 h_{k-i} (for valid k-i in [0,n-1])
    # d num / d h_i = sum_k dc_k * 2 h_{k-i} = 2 * sum_k dc_k h_{k-i}
    # = 2 * correlation. Use FFT: corr[i] = sum_k dc_k h_{k-i} = ifft(DC * conj(Hh))[i]? 
    # Actually sum_k dc_k h_{k-i}: let j=k-i, = sum_j dc_{i+j} h_j = (dc star h)[i]
    # cross-correlation via FFT: ifft(conj(fft(dc)) * fft(h))
    corr = np.fft.irfft(np.conj(DC) * Hh, m2)[:n]
    dnum_dh = 2.0 * corr
    # den = s^2 * Lmax
    # d den / d h_i = 2 s Lmax + s^2 * dLmax/dh_i
    # dLmax/dh_i = 2 h_{kmax - i} where kmax is argmax of c (L index = kmax+1)
    kmax = int(np.argmax(c))
    # L index kmax+1 corresponds to c[kmax]
    dLmax_dh = np.zeros(n)
    # c[kmax] = sum_t h_t h_{kmax-t}; d/dh_i = 2 h_{kmax-i} if valid
    for i in range(n):
        j = kmax - i
        if 0 <= j < n:
            dLmax_dh[i] = 2.0 * h[j]
    dden_dh = 2.0 * s * Lmax + s * s * dLmax_dh
    grad = (dnum_dh * den - num * dden_dh) / (den * den)
    return R, grad


def _lbfgs(h, budget_s, t_start):
    """Simple L-BFGS with numerical/analytic gradient on R."""
    from scipy.optimize import minimize
    def negR(x):
        return -_score(x)
    def negR_grad(x):
        R, g = _fft_grad(x)
        return -R, -g
    x0 = np.maximum(h, 1e-12)
    try:
        res = minimize(negR_grad, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * x0.size,
                       options={'maxiter': 200, 'maxfun': 5000})
        x = np.maximum(res.x, 0.0)
        if _score(x) > _score(h):
            return x
    except Exception:
        pass
    return h


def _hop_stage(h, budget_s, t_start, rng):
    """Random perturbation hill-climbing."""
    best = h.copy()
    bestR = _score(best)
    n = best.size
    while time.process_time() - t_start < budget_s:
        cand = best.copy()
        # perturb a random block
        k = rng.integers(1, max(2, n // 20))
        start_i = rng.integers(0, n)
        end_i = min(n, start_i + k)
        scale = 1.0 + rng.uniform(-0.1, 0.1)
        cand[start_i:end_i] *= scale
        cand = np.maximum(cand, 0.0)
        R = _score(cand)
        if R > bestR:
            best = cand
            bestR = R
    return best


def construct(budget_seconds, start):
    t0 = time.process_time()
    rng = np.random.default_rng(12345)

    if start is not None:
        best = np.asarray(start, dtype=float).copy()
        bestR = _score(best)
    else:
        best = None
        bestR = -1.0

    # Stage 1: power-law construction
    N0 = 256
    best_pl = None
    best_plR = -1.0
    for alpha in [0.3, 0.4, 0.5, 0.6]:
        for delta in [1e-3, 1e-2, 5e-2]:
            i = np.arange(N0)
            x = (i + 0.5) / N0 + delta
            h = x ** (-alpha)
            R = _score(h)
            if R > best_plR:
                best_plR = R
                best_pl = h
    print(f"stage power_law: -1 -> {best_plR:.6f}, {time.process_time()-t0:.2f} s")

    if best_plR > bestR:
        best = best_pl.copy()
        bestR = best_plR
    keep_best(best)

    # Stage 2: upsample to 1024 and L-BFGS 3s
    if time.process_time() - t0 < budget_seconds * 0.9:
        h = _upsample_mass(best, 1024)
        R0 = _score(h)
        h = _lbfgs(h, 3.0, time.process_time())
        R1 = _score(h)
        print(f"stage lbfgs_1024: {R0:.6f} -> {R1:.6f}, {time.process_time()-t0:.2f} s")
        if R1 > bestR:
            best = h
            bestR = R1
            keep_best(best)

    # Stage 3: upsample to 4096 and L-BFGS 5s
    if time.process_time() - t0 < budget_seconds * 0.85:
        h = _upsample_mass(best, 4096)
        R0 = _score(h)
        h = _lbfgs(h, 5.0, time.process_time())
        R1 = _score(h)
        print(f"stage lbfgs_4096: {R0:.6f} -> {R1:.6f}, {time.process_time()-t0:.2f} s")
        if R1 > bestR:
            best = h
            bestR = R1
            keep_best(best)

    # Stage 4: hop stage 10s
    if time.process_time() - t0 < budget_seconds * 0.8:
        h = best.copy()
        R0 = _score(h)
        h = _hop_stage(h, min(time.process_time() + 10.0, t0 + budget_seconds * 0.9), t0, rng)
        R1 = _score(h)
        print(f"stage hop: {R0:.6f} -> {R1:.6f}, {time.process_time()-t0:.2f} s")
        if R1 > bestR:
            best = h
            bestR = R1
            keep_best(best)

    # Stage 5: final L-BFGS
    if time.process_time() - t0 < budget_seconds * 0.9:
        h = best.copy()
        R0 = _score(h)
        h = _lbfgs(h, budget_seconds * 0.95, time.process_time())
        R1 = _score(h)
        print(f"stage lbfgs_final: {R0:.6f} -> {R1:.6f}, {time.process_time()-t0:.2f} s")
        if R1 > bestR:
            best = h
            bestR = R1
            keep_best(best)

    # diagnostics
    c = np.convolve(best, best)
    L = np.concatenate(([0.0], c, [0.0]))
    kmax = int(np.argmax(L))
    peak_frac = kmax / (len(L) - 1)
    plateau = np.mean(L >= L.max() * 0.999)
    print(f"final R={bestR:.6f}, N={best.size}, peak at {peak_frac:.3f}, plateau={plateau:.3f}")
    print(f"CPU {time.process_time()-t0:.2f} s of {budget_seconds} s budget")

    return np.maximum(best, 0.0)
