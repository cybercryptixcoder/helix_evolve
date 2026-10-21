import numpy as np
import time
from scipy.optimize import minimize


def _R(h):
    h = np.asarray(h, dtype=float)
    if h.ndim != 1 or h.size == 0 or not np.all(np.isfinite(h)) or np.any(h < 0):
        return -1.0
    s = h.sum()
    if s <= 0:
        return -1.0
    L = np.convolve(h, h)
    if L.size == 0:
        return -1.0
    inf = L.max()
    if inf <= 0:
        return -1.0
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    return l2sq / (s * s * inf)


def _R_and_grad_h(h):
    N = h.size
    s = h.sum()
    L = np.convolve(h, h)
    M = L.size
    inf = L.max()
    Lp = np.empty(M + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2sq / (l1 * inf)

    dA_dLp = np.zeros(Lp.size)
    dA_dLp[:-1] += (2 * Lp[:-1] + Lp[1:]) / 3.0
    dA_dLp[1:] += (Lp[:-1] + 2 * Lp[1:]) / 3.0
    dA_dL = dA_dLp[1:-1]
    corrA = np.correlate(dA_dL, h, 'full')
    dA_dh = 2.0 * corrA[N - 1: N - 1 + N]

    dB_dh = 2.0 * s

    jstar = int(np.argmax(L))
    dC_dh = np.zeros(N)
    lo = max(0, jstar - (N - 1))
    hi = min(N - 1, jstar)
    kk = np.arange(lo, hi + 1)
    jj = jstar - kk
    dC_dh[kk] = 2.0 * h[jj]

    BC = l1 * inf
    dR_dh = (dA_dh * BC - l2sq * (dB_dh * inf + l1 * dC_dh)) / (BC * BC)
    return R, dR_dh


def _negR_and_grad(v):
    h = np.exp(v)
    R, dR_dh = _R_and_grad_h(h)
    return -R, -(h * dR_dh)


def _negR_soft_and_grad(v, tau_frac):
    h = np.exp(v)
    N = h.size
    s = h.sum()
    L = np.convolve(h, h)
    M = L.size
    m = L.max()
    tau = max(m * tau_frac, 1e-300)
    z = (L - m) / tau
    zmax = z.max()
    e = np.exp(z - zmax)
    Z = e.sum()
    w = e / Z
    C = m + tau * (np.log(Z) + zmax)

    Lp = np.empty(M + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2sq / (l1 * C)

    dA_dLp = np.zeros(Lp.size)
    dA_dLp[:-1] += (2 * Lp[:-1] + Lp[1:]) / 3.0
    dA_dLp[1:] += (Lp[:-1] + 2 * Lp[1:]) / 3.0
    dA_dL = dA_dLp[1:-1]
    corrA = np.correlate(dA_dL, h, 'full')
    dA_dh = 2.0 * corrA[N - 1: N - 1 + N]

    dB_dh = 2.0 * s
    dC_dh = 2.0 * np.correlate(w, h, 'valid')

    BC = l1 * C
    dR_dh = (dA_dh * BC - l2sq * (dB_dh * C + l1 * dC_dh)) / (BC * BC)
    return -R, -(h * dR_dh)


def _polish(h, maxiter):
    h = np.maximum(np.asarray(h, dtype=float), 1e-12)
    try:
        res = minimize(_negR_and_grad, np.log(h), jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-15, 'gtol': 1e-13})
        out = np.exp(res.x)
        if np.all(np.isfinite(out)) and np.any(out > 0):
            return out
    except Exception:
        pass
    return h


def _polish_soft(h, tau_frac, maxiter):
    h = np.maximum(np.asarray(h, dtype=float), 1e-12)
    try:
        res = minimize(_negR_soft_and_grad, np.log(h), args=(tau_frac,), jac=True,
                       method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-15, 'gtol': 1e-13})
        out = np.exp(res.x)
        if np.all(np.isfinite(out)) and np.any(out > 0):
            return out
    except Exception:
        pass
    return h


# --- symmetric-subspace helpers (from p0101) ---

def _R_sym(v):
    e = np.exp(np.clip(v, -700, 700))
    h = np.concatenate([e, e[::-1]])
    return _R(h)


def _negR_sym_and_grad(v):
    m = v.size
    e = np.exp(v)
    h = np.concatenate([e, e[::-1]])
    N = h.size
    s = h.sum()
    L = np.convolve(h, h)
    M = L.size
    inf = L.max()
    Lp = np.empty(M + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2sq / (l1 * inf)

    dA_dLp = np.zeros(Lp.size)
    dA_dLp[:-1] += (2 * Lp[:-1] + Lp[1:]) / 3.0
    dA_dLp[1:] += (Lp[:-1] + 2 * Lp[1:]) / 3.0
    dA_dL = dA_dLp[1:-1]
    corrA = np.correlate(dA_dL, h, 'full')
    dA_dh = 2.0 * corrA[N - 1: N - 1 + N]

    dB_dh = 2.0 * s

    jstar = int(np.argmax(L))
    dC_dh = np.zeros(N)
    lo = max(0, jstar - (N - 1))
    hi = min(N - 1, jstar)
    kk = np.arange(lo, hi + 1)
    jj = jstar - kk
    dC_dh[kk] = 2.0 * h[jj]

    BC = l1 * inf
    dR_dh = (dA_dh * BC - l2sq * (dB_dh * inf + l1 * dC_dh)) / (BC * BC)

    g = h * dR_dh
    gv = g[:m] + g[N - 1:N - 1 - m:-1]
    return -R, -gv


def _negR_soft_sym_and_grad(v, tau_frac):
    m = v.size
    e = np.exp(v)
    h = np.concatenate([e, e[::-1]])
    N = h.size
    s = h.sum()
    L = np.convolve(h, h)
    M = L.size
    mx = L.max()
    tau = max(mx * tau_frac, 1e-300)
    z = (L - mx) / tau
    zmax = z.max()
    ee = np.exp(z - zmax)
    Z = ee.sum()
    w = ee / Z
    C = mx + tau * (np.log(Z) + zmax)

    Lp = np.empty(M + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2sq / (l1 * C)

    dA_dLp = np.zeros(Lp.size)
    dA_dLp[:-1] += (2 * Lp[:-1] + Lp[1:]) / 3.0
    dA_dLp[1:] += (Lp[:-1] + 2 * Lp[1:]) / 3.0
    dA_dL = dA_dLp[1:-1]
    corrA = np.correlate(dA_dL, h, 'full')
    dA_dh = 2.0 * corrA[N - 1: N - 1 + N]

    dB_dh = 2.0 * s
    dC_dh = 2.0 * np.correlate(w, h, 'valid')

    BC = l1 * C
    dR_dh = (dA_dh * BC - l2sq * (dB_dh * C + l1 * dC_dh)) / (BC * BC)

    g = h * dR_dh
    gv = g[:m] + g[N - 1:N - 1 - m:-1]
    return -R, -gv


def _polish_sym(v, maxiter):
    v = np.asarray(v, dtype=float)
    try:
        res = minimize(_negR_sym_and_grad, v, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-15, 'gtol': 1e-13})
        out = res.x
        if np.all(np.isfinite(out)):
            return out
    except Exception:
        pass
    return v


def _polish_soft_sym(v, tau_frac, maxiter):
    v = np.asarray(v, dtype=float)
    try:
        res = minimize(_negR_soft_sym_and_grad, v, args=(tau_frac,), jac=True,
                       method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-15, 'gtol': 1e-13})
        out = res.x
        if np.all(np.isfinite(out)):
            return out
    except Exception:
        pass
    return v


def _resample(h, N):
    h = np.asarray(h, dtype=float)
    if h.size == N:
        return h.copy()
    xs = np.linspace(0, 1, h.size)
    xn = np.linspace(0, 1, N)
    return np.interp(xn, xs, h)


def _anneal(h_init, tau_fracs, it_s, it_e, deadline, best):
    h_cur = h_init.copy()
    for tf in tau_fracs:
        if time.process_time() >= deadline:
            break
        h_soft = _polish_soft(h_cur, tf, it_s)
        h_ex = _polish(h_soft, it_e)
        Re = _R(h_ex)
        if Re > best[0] + 1e-12:
            best[0] = Re
            best[1] = h_ex.copy()
            h_cur = h_ex.copy()
        else:
            if _R(h_soft) > _R(h_cur):
                h_cur = h_soft.copy()
    return best


def _symmetric_stage(best, deadline):
    h = best[1]
    N = h.size
    hs = 0.5 * (h + h[::-1])
    m = N // 2
    v = np.log(np.maximum(hs[:m], 1e-12))
    v = _polish_sym(v, 400)
    e = np.exp(v)
    h_sym = np.concatenate([e, e[::-1]])
    Rs = _R(h_sym)
    if Rs > best[0] + 1e-12:
        best[0] = Rs
        best[1] = h_sym.copy()
    taus = [1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 3e-6, 1e-6, 3e-7, 1e-7]
    for tf in taus:
        if time.process_time() >= deadline:
            break
        v = _polish_soft_sym(v, tf, 400)
        v = _polish_sym(v, 400)
        e = np.exp(v)
        h_sym = np.concatenate([e, e[::-1]])
        Rs = _R(h_sym)
        if Rs > best[0] + 1e-12:
            best[0] = Rs
            best[1] = h_sym.copy()
    return best


# --- clipped-target refit machinery (from p0111) ---

def _refit_to_target(T, N, maxiter=300):
    """Find non-negative h with conv(h,h) ~= T (least squares on knots)."""
    T = np.asarray(T, dtype=float)
    M = T.size
    # h has length N, conv has length 2N-1; require M == 2N-1
    if M != 2 * N - 1:
        # resample T to correct length
        xs = np.linspace(0, 1, M)
        xn = np.linspace(0, 1, 2 * N - 1)
        T = np.interp(xn, xs, T)
    Tn = T / max(T.max(), 1e-300)

    def f(v):
        h = np.exp(v)
        L = np.convolve(h, h)
        d = L - Tn
        val = np.sum(d * d)
        # gradient wrt h: 2 * correlate(d, h) at center
        corr = np.correlate(d, h, 'full')
        g_h = 2.0 * corr[N - 1: N - 1 + N]
        return val, h * g_h

    h0 = np.ones(N)
    # initial guess: sqrt-ish of T center
    try:
        h0 = np.sqrt(np.maximum(Tn[N - 1: 2 * N - 1], 1e-12))
        h0 = np.maximum(h0, 1e-6)
    except Exception:
        pass
    try:
        res = minimize(f, np.log(h0), jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 2,
                                'ftol': 1e-15, 'gtol': 1e-13})
        out = np.exp(res.x)
        if np.all(np.isfinite(out)) and np.any(out > 0):
            return out
    except Exception:
        pass
    return h0


def _clip_refit_stage(best, deadline):
    N = best[1].size
    T = np.convolve(best[1], best[1])
    qs = [0.99, 0.995, 0.998, 0.999, 0.9995]
    alphas = [0.2, 0.1, 0.05, 0.02]
    soft_taus = [1e-4, 3e-5, 1e-5, 3e-6]
    for q in qs:
        for alpha in alphas:
            if time.process_time() >= deadline:
                return best
            Tmax = T.max()
            Tclip = np.minimum(T, q * Tmax)
            Tblend = (1.0 - alpha) * T + alpha * Tclip
            h_new = _refit_to_target(Tblend, N, maxiter=300)
            h_new = _polish(h_new, 300)
            Rh = _R(h_new)
            accepted = False
            if Rh > best[0] + 1e-13:
                best[0] = Rh
                best[1] = h_new.copy()
                T = np.convolve(best[1], best[1])
                accepted = True
            # short soft anneal from h_new
            h_cur = h_new
            for tf in soft_taus:
                if time.process_time() >= deadline:
                    return best
                hs = _polish_soft(h_cur, tf, 300)
                he = _polish(hs, 300)
                Re = _R(he)
                if Re > best[0] + 1e-13:
                    best[0] = Re
                    best[1] = he.copy()
                    T = np.convolve(best[1], best[1])
                    accepted = True
                    h_cur = he
                else:
                    if _R(hs) > _R(h_cur):
                        h_cur = hs
            if accepted:
                # reset T already done; continue with next q
                pass
    return best


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.88

    N = 4000
    best = [-1.0, None]

    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size > 0 and np.all(np.isfinite(s)) and np.any(s > 0):
            s = np.maximum(s, 0)
            if s.sum() > 0:
                base = _resample(s, N)
                best[1] = base.copy()
                best[0] = _R(base)

    if best[1] is None:
        best[1] = np.ones(N)
        best[0] = _R(best[1])

    # Stage 1: fine soft->exact anneal from start.
    tau_fracs = [3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 3e-6, 1e-6,
                 3e-7, 1e-7, 3e-8, 1e-8]
    _anneal(best[1], tau_fracs, 400, 400, deadline, best)

    # Stage 1b: symmetric-subspace anneal (p0101 driver) from current best.
    if time.process_time() < deadline:
        _symmetric_stage(best, deadline)

    # Stage 1c: clipped-target refit stage (p0111 machinery).
    if time.process_time() < deadline:
        _clip_refit_stage(best, deadline)

    # Stage 2: multi-scale polish.
    for N2 in [8000, 6000, 4000]:
        if time.process_time() >= deadline:
            break
        h2 = _resample(best[1], N2)
        b2 = [_R(h2), h2.copy()]
        _anneal(h2, [1e-4, 3e-5, 1e-5, 3e-6, 1e-6, 3e-7, 1e-7], 300, 300,
                deadline, b2)
        if b2[0] > best[0] + 1e-12:
            best[0] = b2[0]
            best[1] = _resample(b2[1], N)

    # Stage 3: alternating exact polish / larger-grid polish until deadline.
    rng = np.random.default_rng(12345)
    flip = 0
    while time.process_time() < deadline:
        if flip % 2 == 0:
            h = _polish(best[1], 1000)
            Rh = _R(h)
            if Rh > best[0] + 1e-13:
                best[0] = Rh
                best[1] = h.copy()
                flip += 1
                continue
        N2 = 8000 if flip % 4 < 2 else 6000
        if time.process_time() >= deadline:
            break
        h2 = _resample(best[1], N2)
        h2 = _polish(h2, 800)
        R2 = _R(h2)
        if R2 > best[0] + 1e-13:
            best[0] = R2
            best[1] = _resample(h2, N)
            flip += 1
            continue
        hs = _polish_soft(best[1], 1e-5, 400)
        h3 = _polish(hs, 700)
        R3 = _R(h3)
        if R3 > best[0] + 1e-13:
            best[0] = R3
            best[1] = h3.copy()
            flip += 1
        else:
            if time.process_time() >= deadline:
                break
            h4 = best[1] * (1.0 + 0.002 * rng.standard_normal(N))
            h4 = np.maximum(h4, 1e-12)
            h4 = _polish(h4, 400)
            R4 = _R(h4)
            if R4 > best[0] + 1e-13:
                best[0] = R4
                best[1] = h4.copy()
            flip += 1
            if R4 <= best[0] + 1e-13 and R2 <= best[0] + 1e-13 and R3 <= best[0] + 1e-13:
                if flip > 6:
                    break

    out = best[1]
    if out is None or not np.all(np.isfinite(out)) or not np.any(out > 0):
        out = np.ones(N)
    print("final R=%.6f" % _R(out))
    return np.asarray(out, dtype=float)
