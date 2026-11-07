import time
import numpy as np
from scipy.signal import fftconvolve
from scipy.optimize import minimize


def _R(h):
    h = np.asarray(h, dtype=float)
    L = fftconvolve(h, h, mode='full')
    g = np.concatenate(([0.0], L, [0.0]))
    Q = np.sum(g[:-1] ** 2 + g[:-1] * g[1:] + g[1:] ** 2) / 3.0
    S = np.sum(h)
    M = np.max(g)
    if S <= 0 or M <= 0:
        return 0.0
    return Q / (S * S * M)


def _Rg_avg(h, tol=1e-4):
    N = h.size
    L = fftconvolve(h, h, mode='full')
    g = np.concatenate(([0.0], L, [0.0]))
    Q = np.sum(g[:-1] ** 2 + g[:-1] * g[1:] + g[1:] ** 2) / 3.0
    S = np.sum(h)
    M = np.max(g)
    if S <= 0 or M <= 0 or Q <= 0:
        return 0.0, np.zeros(N)
    dQdg = (4.0 * g + np.concatenate(([0.0], g[:-1])) + np.concatenate((g[1:], [0.0]))) / 3.0
    w = dQdg[1:2 * N]
    conv = fftconvolve(w, h[::-1], mode='full')
    dQdh = 2.0 * conv[N - 1:2 * N - 1]
    J = np.where(g >= M * (1.0 - tol))[0]
    if J.size == 0:
        J = np.array([int(np.argmax(g))])
    dMdh = np.zeros(N)
    for j in J:
        k = j - 1
        if 0 <= k <= 2 * N - 2:
            lo = max(0, k - N + 1)
            hi = min(N - 1, k)
            dMdh[lo:hi + 1] += 2.0 * h[k - hi:k - lo + 1][::-1]
    dMdh /= J.size
    grad = dQdh / Q - 2.0 / S - dMdh / M
    return Q / (S * S * M), grad


def _upsample(h, N):
    xp = np.linspace(0.0, 1.0, h.size)
    x = np.linspace(0.0, 1.0, N)
    out = np.interp(x, xp, h)
    out = np.maximum(out, 0.0)
    s = out.sum()
    if s > 0:
        out /= s
    else:
        out = np.ones(N)
        out /= N
    return out


def _lbfgs(h, deadline, maxiter=200, tol=1e-4):
    if time.process_time() > deadline:
        return h, _R(h)
    x0 = np.maximum(h, 0.0).copy()
    if x0.sum() <= 0:
        return h, _R(h)

    def f(x):
        R, g = _Rg_avg(x, tol=tol)
        return -R, -g

    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * x0.size,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter + 10,
                                'ftol': 1e-15, 'gtol': 1e-14})
        xr = np.maximum(res.x, 0.0)
        if xr.sum() > 0:
            Rr = _R(xr)
            if Rr > _R(h):
                return xr, Rr
    except Exception:
        pass
    return h, _R(h)


def _smooth_field(N, rng, kind):
    if kind == 0:
        w = rng.standard_normal(N)
        f = np.cumsum(w)
        x = np.linspace(0.0, 1.0, N)
        A = np.vstack([np.ones(N), x]).T
        coef, *_ = np.linalg.lstsq(A, f, rcond=None)
        f = f - A @ coef
    elif kind == 1:
        m = max(4, N // 64)
        low = rng.standard_normal(m)
        f = np.interp(np.linspace(0.0, 1.0, N), np.linspace(0.0, 1.0, m), low)
    else:
        m = max(4, N // 8)
        low = rng.standard_normal(m)
        f = np.interp(np.linspace(0.0, 1.0, N), np.linspace(0.0, 1.0, m), low)
    s = np.sqrt(np.mean(f * f))
    if s <= 0 or not np.isfinite(s):
        f = rng.standard_normal(N)
        s = np.sqrt(np.mean(f * f))
    return f / s


def _rescale_N(h, N):
    if h.size == N:
        return h.copy()
    return _upsample(h, N)


# --- symmetric wrappers -------------------------------------------------
def _sym_to_full(u):
    m = u.size
    N = 2 * m
    h = np.empty(N)
    h[:m] = u
    h[m:] = u[::-1]
    return h


def _full_to_sym(h):
    N = h.size
    m = (N + 1) // 2
    u = h[:m].copy()
    if N % 2 == 0:
        # even: pair (i, N-1-i) for i<m
        u = 0.5 * (h[:m] + h[N - m:][::-1])
    else:
        u = h[:m].copy()
        u[:-1] = 0.5 * (h[:m - 1] + h[N - m + 1:][::-1])
    return u


def _R_sym(u):
    return _R(_sym_to_full(u))


def _Rg_sym(u, tol=1e-4):
    h = _sym_to_full(u)
    N = h.size
    m = u.size
    R, gh = _Rg_avg(h, tol=tol)
    if N % 2 == 0:
        gu = gh[:m] + gh[m:][::-1]
    else:
        gu = gh[:m].copy()
        gu[:-1] += gh[N - m + 1:][::-1]
    return R, gu


def _lbfgs_sym(u, deadline, maxiter=200, tol=1e-4):
    if time.process_time() > deadline:
        return u, _R_sym(u)
    x0 = np.maximum(u, 0.0).copy()
    if x0.sum() <= 0:
        return u, _R_sym(u)

    def f(x):
        R, g = _Rg_sym(x, tol=tol)
        return -R, -g

    try:
        res = minimize(f, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * x0.size,
                       options={'maxiter': maxiter, 'maxfun': 2 * maxiter + 10,
                                'ftol': 1e-15, 'gtol': 1e-14})
        xr = np.maximum(res.x, 0.0)
        if xr.sum() > 0:
            Rr = _R_sym(xr)
            if Rr > _R_sym(u):
                return xr, Rr
    except Exception:
        pass
    return u, _R_sym(u)


def construct(budget_seconds, start):
    t0 = time.process_time()
    hard_deadline = t0 + budget_seconds * 0.95

    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size > 0 and np.all(np.isfinite(s)) and s.sum() > 0:
            s = np.maximum(s, 0.0)
            s = s / s.sum()
            best_h = s.copy()
            best_R = _R(s)
        else:
            best_h = None
    else:
        best_h = None

    if best_h is None:
        h = np.ones(1000)
        return h / h.sum()

    N0 = best_h.size

    # Phase 1: annealed active-set L-BFGS.
    tols = [1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8]
    p1_deadline = min(t0 + 10.0, hard_deadline)
    for tol in tols:
        if time.process_time() >= p1_deadline:
            break
        h_try, R_try = _lbfgs(best_h, p1_deadline, maxiter=150, tol=tol)
        if R_try > best_R:
            best_h, best_R = h_try, R_try

    # Phase 2: resolution exploration.
    p2_deadline = min(t0 + 18.0, hard_deadline)
    candidate_Ns = [N0, min(50000, int(N0 * 1.5)), min(50000, N0 * 2),
                    min(50000, int(N0 * 0.7)), min(50000, int(N0 * 1.25))]
    for Nc in candidate_Ns:
        if time.process_time() >= p2_deadline:
            break
        hc = best_h if Nc == N0 else _rescale_N(best_h, Nc)
        remaining = p2_deadline - time.process_time()
        if remaining <= 0:
            break
        trial_deadline = time.process_time() + max(1.0, remaining * 0.5)
        h_new, R_new = _lbfgs(hc, trial_deadline, maxiter=200, tol=1e-6)
        if R_new > best_R + 1e-9:
            best_h, best_R = h_new, R_new
            N0 = best_h.size

    # Phase 3: perturbation loop with 3 field types.
    rng = np.random.default_rng(987654321)
    N = best_h.size
    perturb_deadline = min(t0 + 29.0, hard_deadline)
    log_lo, log_hi = np.log(1e-5), np.log(1e-2)
    trial = 0
    while time.process_time() < perturb_deadline:
        trial += 1
        sigma = float(np.exp(rng.uniform(log_lo, log_hi)))
        kind = trial % 3
        field = _smooth_field(N, rng, kind)
        cand = best_h * np.exp(sigma * field)
        cand = np.maximum(cand, 0.0)
        ssum = cand.sum()
        if ssum <= 0 or not np.isfinite(ssum):
            continue
        cand /= ssum
        remaining = perturb_deadline - time.process_time()
        if remaining <= 0:
            break
        trial_deadline = time.process_time() + max(0.3, remaining * 0.5)
        hc, Rc = _lbfgs(cand, trial_deadline, maxiter=200, tol=1e-7)
        if Rc > best_R:
            best_h, best_R = hc, Rc

    best_h = np.maximum(best_h, 0.0)
    if best_h.sum() <= 0:
        best_h = np.ones(best_h.size)
    if best_h.size > 50000:
        best_h = _upsample(best_h, 50000)

    # --- Symmetric refinement phase -------------------------------------
    sym_deadline = min(t0 + 29.5, hard_deadline)
    if time.process_time() < sym_deadline:
        u = _full_to_sym(best_h)
        u = np.maximum(u, 0.0)
        if u.sum() > 0:
            u = u / u.sum()
            # annealed tolerances
            for tol in [1e-4, 1e-6, 1e-8]:
                if time.process_time() >= sym_deadline:
                    break
                u2, R2 = _lbfgs_sym(u, sym_deadline, maxiter=300, tol=tol)
                if R2 >= _R_sym(u):
                    u = u2
            h_sym = _sym_to_full(u)
            h_sym = np.maximum(h_sym, 0.0)
            if h_sym.sum() > 0:
                h_sym = h_sym / h_sym.sum()
                R_sym = _R(h_sym)
                if R_sym > best_R:
                    best_h, best_R = h_sym, R_sym

    return best_h
