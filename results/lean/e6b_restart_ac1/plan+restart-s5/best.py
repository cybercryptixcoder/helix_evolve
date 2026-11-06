import numpy as np
import time
from scipy.optimize import minimize


def C_of(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _C_and_grad(h):
    h = np.asarray(h, dtype=float)
    N = len(h)
    S = h.sum()
    if S <= 0:
        return np.inf, np.zeros(N)
    conv = np.convolve(h, h)
    m = int(np.argmax(conv))
    M = conv[m]
    C = 2.0 * N * M / (S * S)
    grad = np.zeros(N)
    lo = max(0, m - N + 1)
    hi = min(N - 1, m)
    idx = np.arange(lo, hi + 1)
    grad[idx] = 4.0 * N * h[m - idx] / (S * S) - 2.0 * C / S
    return C, grad


def _Cp_and_grad(h, p):
    h = np.asarray(h, dtype=float)
    N = len(h)
    S = h.sum()
    if S <= 0:
        return np.inf, np.zeros(N)
    conv = np.maximum(np.convolve(h, h), 0.0)
    mx = conv.max()
    if mx <= 0:
        return np.inf, np.zeros(N)
    w = (conv / mx) ** p
    sw = w.sum()
    if sw <= 0:
        return np.inf, np.zeros(N)
    sump = (mx ** p) * sw
    Cp = 2.0 * N * (sump ** (1.0 / p)) / (S * S)
    pref = (sump ** (1.0 / p)) / sump
    dconv = pref * (conv ** (p - 1))
    full = np.convolve(dconv, h[::-1])
    grad_conv = 2.0 * full[N - 1: 2 * N - 1]
    grad = 2.0 * N * grad_conv / (S * S) - 2.0 * Cp / S
    return Cp, grad


def _Clse_and_grad(h, tau):
    h = np.asarray(h, dtype=float)
    N = len(h)
    S = h.sum()
    if S <= 0:
        return np.inf, np.zeros(N)
    conv = np.maximum(np.convolve(h, h), 0.0)
    mx = conv.max()
    if mx <= 0:
        return np.inf, np.zeros(N)
    tau = max(tau, 1e-12 * max(mx, 1e-30))
    z = (conv - mx) / tau
    e = np.exp(z)
    se = e.sum()
    lse = mx + tau * np.log(se)
    Cl = 2.0 * N * lse / (S * S)
    dconv = e / se
    full = np.convolve(dconv, h[::-1])
    grad_conv = 2.0 * full[N - 1: 2 * N - 1]
    grad = 2.0 * N * grad_conv / (S * S) - 2.0 * Cl / S
    return Cl, grad


def _resample(h, Nnew):
    xs = np.linspace(0.0, 1.0, len(h))
    xi = (np.arange(Nnew) + 0.5) / Nnew
    return np.maximum(np.interp(xi, xs, h), 0.0)


def _lbfgs(h0, maxiter=200, p=None, tau=None):
    h = np.maximum(np.asarray(h0, dtype=float), 0.0)
    best, bestC = h.copy(), C_of(h)
    if p is not None:
        fun = lambda x: _Cp_and_grad(x, p)
    elif tau is not None:
        fun = lambda x: _Clse_and_grad(x, tau)
    else:
        fun = _C_and_grad
    try:
        res = minimize(fun, h, method='L-BFGS-B',
                       bounds=[(0.0, None)] * len(h), jac=True,
                       options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                'ftol': 1e-15, 'gtol': 1e-13})
        xh = np.maximum(res.x, 0.0)
        c = C_of(xh)
        if c < bestC:
            best, bestC = xh, c
    except Exception:
        pass
    return best, bestC


def _polish(h, remaining, maxiter=60):
    if remaining() < 0.3:
        return h, C_of(h)
    for p in (16, 64):
        if remaining() < 0.25:
            break
        hp, cp = _lbfgs(h, maxiter=maxiter, p=p)
        if cp < C_of(h):
            h = hp
    for frac in (3e-3, 1e-3, 3e-4, 1e-4):
        if remaining() < 0.2:
            break
        conv = np.convolve(h, h)
        mx = conv.max()
        hl, cl = _lbfgs(h, maxiter=maxiter, tau=frac * mx)
        if cl < C_of(h):
            h = hl
    if remaining() > 0.15:
        h, c = _lbfgs(h, maxiter=maxiter)
    else:
        c = C_of(h)
    return h, c


def _coord_descent(h, remaining, rng, deltas, max_rounds=40, deadline_margin=0.3):
    """True-C coordinate descent with exact 1-D line search per coordinate."""
    N = h.size
    c = C_of(h)
    improved_any = True
    rounds = 0
    while improved_any and remaining() > deadline_margin and rounds < max_rounds:
        improved_any = False
        rounds += 1
        order = rng.permutation(N)
        for i in order:
            if remaining() < deadline_margin:
                break
            base_val = h[i]
            bval = base_val
            bC = c
            hmax = h.max() if h.max() > 0 else 1.0
            for d in deltas:
                for sign in (1.0, -1.0):
                    nv = base_val + sign * d * hmax
                    if nv < 0:
                        continue
                    h[i] = nv
                    cc = C_of(h)
                    if cc < bC - 1e-13:
                        bC = cc
                        bval = nv
            h[i] = bval
            if bC < c - 1e-13:
                c = bC
                improved_any = True
    return h, c


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + 0.88 * budget_seconds

    def remaining():
        return deadline - time.process_time()

    best = None
    bestC = np.inf
    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size > 0 and s.size <= 30000 and np.all(np.isfinite(s)) and s.sum() > 0:
            best, bestC = s.copy(), C_of(s)

    if best is None:
        N = 200
        x = (np.arange(N) + 0.5) / N
        u = 2.0 * x - 1.0
        best = np.maximum(0.0, (1.0 - u * u))
        bestC = C_of(best)

    # Quick baseline polish preserving start resolution
    if remaining() > 0.5:
        work, Cw = _polish(best.copy(), remaining, maxiter=50)
        if Cw < bestC:
            bestC, best = Cw, work.copy()

    rng = np.random.default_rng(1234567)
    deltas = [0.05, 0.02, 0.01, 0.005, 0.002, 0.001]

    # Independent coordinate searches at several resolutions.
    resolutions = [250, 300, 350, 400, 500]
    # Allocate remaining time roughly equally across resolutions.
    for Np in resolutions:
        if remaining() < 0.6:
            break
        h = _resample(best, Np)
        c = C_of(h)
        # Per-resolution time slice: share of what's left.
        slice_deadline = time.process_time() + max(0.0, (remaining()) / max(1, len(resolutions)))
        def rem_slice():
            return min(remaining(), slice_deadline - time.process_time())
        h, c = _coord_descent(h, rem_slice, rng, deltas, max_rounds=25)
        if c < bestC:
            bestC, best = c, h.copy()
            print("res-improved", bestC, "N", Np)

    # Finish with _polish at winning N
    if remaining() > 0.3:
        h, c = _polish(best.copy(), remaining, maxiter=100)
        if c < bestC:
            bestC, best = c, h.copy()
            print("final-polish", bestC, "N", best.size)

    return np.maximum(np.asarray(best, dtype=float), 0.0)
