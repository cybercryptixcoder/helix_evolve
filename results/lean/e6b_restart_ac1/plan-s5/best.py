import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve
from scipy.sparse.linalg import LinearOperator, cg


def _C(h):
    s = h.sum()
    if s <= 0:
        return 1e9
    return 2.0 * len(h) * float(np.max(np.convolve(h, h))) / (s * s)


def _C_fft(h):
    s = h.sum()
    if s <= 0:
        return 1e9
    return 2.0 * len(h) * float(np.max(fftconvolve(h, h, 'full'))) / (s * s)


def _softmax_C_and_grad(z, beta):
    N = len(z)
    h = np.exp(np.clip(z, -20, 20))
    S = h.sum()
    if S <= 0:
        return 1e9, np.zeros(N)
    conv = fftconvolve(h, h, 'full')
    b = beta * conv
    bmax = b.max()
    e = np.exp(b - bmax)
    Z = e.sum()
    lse = bmax + np.log(Z)
    M = lse / beta
    C = 2.0 * N * M / (S * S)
    w = e / Z
    g_M = 2.0 * fftconvolve(w, h[::-1], 'full')[N - 1:2 * N - 1]
    g_h = (2.0 * N / (S * S)) * g_M - 2.0 * C / S
    g_z = h * g_h
    return C, g_z


def _polish_soft(z0, beta, maxiter, deadline, t0):
    def fun(z):
        return _softmax_C_and_grad(z, beta)

    def cb(xk):
        return time.process_time() - t0 > deadline
    try:
        res = minimize(fun, z0, jac=True, method='L-BFGS-B',
                       bounds=[(-20.0, 20.0)] * len(z0),
                       callback=cb,
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-13,
                                'maxcor': 30})
        return res.x
    except Exception:
        return z0


def _hard_polish(z0, maxiter, deadline, t0):
    def hard_fun(z):
        N = len(z)
        h = np.exp(np.clip(z, -20, 20))
        S = h.sum()
        if S <= 0:
            return 1e9, np.zeros(N)
        conv = fftconvolve(h, h, 'full')
        m = conv.max()
        C = 2.0 * N * m / (S * S)
        active = np.where(conv >= m - 1e-9 * max(1.0, abs(m)))[0]
        mask = np.zeros(N + N - 1)
        mask[active] = 1.0
        na = max(1, len(active))
        corr = fftconvolve(mask, h[::-1], 'full')[N - 1:2 * N - 1]
        g_h = -2.0 * C / S + (4.0 * N / (S * S)) * (1.0 / na) * corr
        return C, h * g_h

    def cb(xk):
        return time.process_time() - t0 > deadline
    try:
        res = minimize(hard_fun, z0, jac=True, method='L-BFGS-B',
                       bounds=[(-20.0, 20.0)] * len(z0),
                       callback=cb,
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-13,
                                'maxcor': 30})
        return res.x
    except Exception:
        return z0


def _upsample(h, N_target):
    N_cur = len(h)
    if N_cur == N_target:
        return h.copy()
    if N_target % N_cur == 0:
        return np.repeat(h, N_target // N_cur)
    if N_cur % N_target == 0:
        f = N_cur // N_target
        return h[:f * N_target].reshape(N_target, f).mean(axis=1)
    x_old = np.linspace(0, 1, N_cur, endpoint=False)
    x_new = np.linspace(0, 1, N_target, endpoint=False)
    return np.interp(x_new, x_old, h)


def _exact_downsample_check(h):
    best_h = h.copy()
    best_C = _C(h)
    n = len(h)
    f = 2
    while f <= 8 and n % f == 0:
        hd = h.reshape(n // f, f).mean(axis=1)
        Cd = _C(hd)
        if Cd < best_C:
            best_C = Cd
            best_h = hd
        f *= 2
    return best_h, best_C


def _active_set_solve(h, thresh=1e-9, eps=1e-12, maxiter=3000, rtol=1e-14):
    """Solve min ||B h - 1||^2 + eps||h||^2 on the active set via CG."""
    N = len(h)
    conv = fftconvolve(h, h, 'full')
    m = conv.max()
    if m <= 0:
        return h
    active = np.where(conv >= m - thresh * m)[0]
    if len(active) == 0:
        return h
    mask = np.zeros(2 * N - 1)
    mask[active] = 1.0

    def B(x):
        return fftconvolve(mask, x[::-1], 'full')[N - 1:2 * N - 1]

    def BT(y):
        return fftconvolve(mask, y[::-1], 'full')[N - 1:2 * N - 1]

    def matvec(x):
        return BT(B(x)) + eps * x

    A = LinearOperator((N, N), matvec=matvec, dtype=float)
    rhs = BT(np.ones(2 * N - 1))
    try:
        x, _ = cg(A, rhs, maxiter=maxiter, rtol=rtol, atol=0.0)
    except Exception:
        return h
    x = np.maximum(x, 0.0)
    s = x.sum()
    if s <= 0:
        return h
    return x / s


def construct(budget_seconds, start):
    t0 = time.process_time()
    margin = 1.0
    deadline = budget_seconds - margin

    if start is not None:
        h_start = np.asarray(start, dtype=float)
        if h_start.sum() <= 0 or not np.all(np.isfinite(h_start)):
            h_start = None
    else:
        h_start = None

    if h_start is None:
        N = 400
        x = np.linspace(-0.25, 0.25, N, endpoint=False) + 0.25 / N
        h_start = np.exp(-2.6 * (x - x.min()))

    h_start = np.maximum(h_start, 1e-12)

    best_h, best_C = _exact_downsample_check(h_start)

    # Upsample start to 30000 and run a sustained softmax schedule.
    h_cur = np.maximum(_upsample(h_start, 30000), 1e-12)
    z = np.log(h_cur)
    betas = [1500, 5000, 20000, 80000, 300000]
    for beta in betas:
        if time.process_time() > deadline - 2.5:
            break
        z = _polish_soft(z, beta, 400, deadline - 2.0, t0)
        h = np.exp(np.clip(z, -20, 20))
        C = _C_fft(h)
        if C < best_C:
            best_C = C
            best_h = h

    # Final hard polish at full resolution.
    if time.process_time() < deadline - 1.0:
        z = _hard_polish(z, 2000, deadline - 0.5, t0)
        h = np.exp(np.clip(z, -20, 20))
        hd, Cd = _exact_downsample_check(h)
        if Cd < best_C:
            best_C = Cd
            best_h = hd

    # Iterated active-set reidentification with tight least-squares solve.
    for it in range(6):
        if time.process_time() > deadline - 1.5:
            break
        h_as = _active_set_solve(best_h, thresh=1e-9, eps=1e-12,
                                 maxiter=3000, rtol=1e-14)
        C_as = _C_fft(h_as)
        improved = False
        if C_as < best_C:
            best_C = C_as
            best_h = h_as
            improved = True
        # short hard polish from the active-set solution
        if time.process_time() < deadline - 1.0:
            z_as = np.log(np.maximum(best_h, 1e-12))
            z_as = _hard_polish(z_as, 150, deadline - 0.5, t0)
            h2 = np.exp(np.clip(z_as, -20, 20))
            hd2, Cd2 = _exact_downsample_check(h2)
            if Cd2 < best_C:
                gain = best_C - Cd2
                best_C = Cd2
                best_h = hd2
                improved = True
            else:
                gain = 0.0
        else:
            gain = 0.0
        if not improved or gain < 1e-10:
            break

    print("final C = %.9f  N=%d  t=%.2f" % (best_C, len(best_h),
                                            time.process_time() - t0))
    return best_h
