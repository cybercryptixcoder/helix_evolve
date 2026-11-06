import numpy as np
import time
from scipy.optimize import minimize, linprog


def _R_from_h(h):
    h = np.maximum(h, 0.0)
    m = h.max()
    if m <= 0:
        return 0.0
    h = h / m
    L = np.convolve(h, h)
    Lp = np.concatenate(([0.0], L, [0.0]))
    a = Lp[:-1]
    b = Lp[1:]
    l2sq = np.sum(a * a + a * b + b * b) / 3.0
    l1 = np.sum(h) ** 2
    linf = Lp.max()
    if linf <= 0 or l1 <= 0:
        return 0.0
    return l2sq / (l1 * linf)


def _R_and_grad(h):
    h = np.maximum(h, 0.0)
    N = h.size
    L = np.convolve(h, h)
    Lp = np.concatenate(([0.0], L, [0.0]))
    a = Lp[:-1]
    b = Lp[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    S = np.sum(h)
    B = S * S
    C = Lp.max()
    if C <= 0 or B <= 0:
        return 0.0, np.zeros(N)
    R = A / (B * C)

    gL = (Lp[:-2] + 4.0 * Lp[1:-1] + Lp[2:]) / 3.0
    dA = 2.0 * np.correlate(gL, h, mode='valid')
    dB = 2.0 * S * np.ones(N)
    kstar = int(np.argmax(Lp))
    dC = np.zeros(N)
    m = kstar - 1
    if 0 <= m <= 2 * N - 2:
        for i in range(N):
            j = m - i
            if 0 <= j < N:
                dC[i] = 2.0 * h[j]

    invBC = 1.0 / (B * C)
    g = dA * invBC - (A / (B * B * C)) * dB - (A / (B * C * C)) * dC
    return R, g


def _neg_R_and_grad(x):
    R, g = _R_and_grad(x)
    return -R, -g


def _lbfgsb_polish(h, deadline, maxiter=150):
    h = np.maximum(h, 0.0)
    m = h.max()
    if m <= 0:
        return h, 0.0
    h = h / m
    try:
        res = minimize(_neg_R_and_grad, h, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * h.size,
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-12})
        hh = np.maximum(res.x, 0.0)
        mm = hh.max()
        if mm > 0:
            hh = hh / mm
        val = _R_from_h(hh)
        if val > _R_from_h(h):
            return hh, val
    except Exception:
        pass
    return h, _R_from_h(h)


def _lse_terms(h, tau):
    h = np.maximum(h, 0.0)
    N = h.size
    L = np.convolve(h, h)
    Lp = np.concatenate(([0.0], L, [0.0]))
    a = Lp[:-1]
    b = Lp[1:]
    A = np.sum(a * a + a * b + b * b) / 3.0
    S = np.sum(h)
    B = S * S
    M = Lp.max()
    if M <= 0 or B <= 0:
        return A, B, 0.0, np.zeros(N)
    z = (Lp - M) / tau
    zmax = z.max()
    ez = np.exp(z - zmax)
    se = ez.sum()
    C = M + tau * (zmax + np.log(se))
    w = ez / se

    gL = (Lp[:-2] + 4.0 * Lp[1:-1] + Lp[2:]) / 3.0
    dA = 2.0 * np.correlate(gL, h, mode='valid')
    dB = 2.0 * S * np.ones(N)

    dC = np.zeros(N)
    for i in range(N):
        idx = np.arange(N) + 1 + i
        valid = idx < w.size
        dC[i] = 2.0 * np.sum(w[idx[valid]] * h[np.arange(N)[valid]])

    invBC = 1.0 / (B * C)
    g = dA * invBC - (A / (B * B * C)) * dB - (A / (B * C * C)) * dC
    return A, B, C, g


def _neg_lse(h, tau):
    A, B, C, g = _lse_terms(h, tau)
    if B <= 0 or C <= 0:
        return 0.0, np.zeros_like(h)
    val = A / (B * C)
    return -val, -g


def _lbfgsb_lse(h, tau, deadline, maxiter=200):
    h = np.maximum(h, 0.0)
    m = h.max()
    if m <= 0:
        return h, 0.0
    h = h / m
    try:
        res = minimize(_neg_lse, h, args=(tau,), jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * h.size,
                       options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-12})
        hh = np.maximum(res.x, 0.0)
        mm = hh.max()
        if mm > 0:
            hh = hh / mm
        return hh, _R_from_h(hh)
    except Exception:
        return h, _R_from_h(h)


def _lp_pivot(h, deadline, max_pivots=15, active_tol=1e-4, step_frac=0.05):
    """LP active-set pivot on the convex maximization of R over h>=0."""
    h = np.maximum(h, 0.0)
    if h.max() <= 0:
        return h, _R_from_h(h)
    h = h / h.sum()  # normalize sum(h)=1

    best_h = h.copy()
    best_val = _R_from_h(best_h)
    N = h.size

    for pivot in range(max_pivots):
        if time.process_time() > deadline:
            break

        L = np.convolve(h, h)
        Lp = np.concatenate(([0.0], L, [0.0]))
        C = Lp.max()
        if C <= 0:
            break

        # gradient of A (numerator) wrt h
        gL = (Lp[:-2] + 4.0 * Lp[1:-1] + Lp[2:]) / 3.0
        gA = 2.0 * np.correlate(gL, h, mode='valid')

        # active set: knots near max, expanded by +/-2
        act = np.where(Lp >= (1.0 - active_tol) * C)[0]
        if act.size == 0:
            break
        expanded = set()
        for j in act:
            for dj in range(-2, 3):
                jj = j + dj
                if 0 <= jj < Lp.size:
                    expanded.add(jj)
        A_idx = np.array(sorted(expanded), dtype=int)

        # LP: maximize gA·d subject to sum(d)=0, h+d>=0, |d_i|<=step_frac*max(h),
        # and 2*convolve(h,d)_j <= C - Lp[j] for j in A
        dmax = step_frac * h.max()
        n = N
        # variables: d (n), plus we handle abs bound as bounds
        # constraint: sum(d) = 0  -> A_eq
        A_eq = np.ones((1, n))
        b_eq = np.array([0.0])

        # convolution constraints: 2*(h*d)_j <= C - Lp[j] for j in A_idx
        # (h*d)_j = sum_i h[i] d[j-i]  (with valid indices)
        # Build sparse-ish dense matrix for active rows only.
        rows = []
        rhs = []
        for j in A_idx:
            row = np.zeros(n)
            # (h*d)_j = sum_i h[i]*d[j-i], d index k=j-i, i in [0,N-1], k in [0,N-1]
            # k = j - i => i = j - k
            klo = max(0, j - (N - 1))
            khi = min(N - 1, j)
            for k in range(klo, khi + 1):
                i = j - k
                if 0 <= i < N:
                    row[k] += h[i]
            rows.append(2.0 * row)
            rhs.append(C - Lp[j])
        if rows:
            A_ub = np.array(rows)
            b_ub = np.array(rhs)
        else:
            A_ub = None
            b_ub = None

        bounds = [(-dmax, dmax)] * n
        # also h+d >= 0 -> d >= -h
        bounds = [(max(-dmax, -h[i]), dmax) for i in range(n)]

        try:
            res = linprog(c=-gA, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                          bounds=bounds, method='highs')
        except Exception:
            break
        if not res.success or res.x is None:
            break
        d = res.x
        if np.max(np.abs(d)) < 1e-12:
            break

        # line search t in [0,1] maximizing exact R with h+t*d>=0
        # find max feasible t
        tmax = 1.0
        neg = d < 0
        if np.any(neg):
            tmax = min(tmax, np.min(-h[neg] / d[neg]))
        if tmax <= 0:
            break

        ts = np.linspace(0.0, tmax, 21)
        best_t = 0.0
        best_tv = best_val
        for t in ts:
            if t <= 0:
                continue
            hh = h + t * d
            if hh.min() < -1e-12:
                continue
            hh = np.maximum(hh, 0.0)
            s = hh.sum()
            if s <= 0:
                continue
            hh = hh / s
            v = _R_from_h(hh)
            if v > best_tv:
                best_tv = v
                best_t = t

        if best_t <= 0:
            # no improvement from this pivot direction; try next pivot
            # (perturb direction slightly by shrinking step)
            break

        h = h + best_t * d
        h = np.maximum(h, 0.0)
        s = h.sum()
        if s <= 0:
            break
        h = h / s

        # polish
        h, v = _lbfgsb_polish(h, deadline, maxiter=40)
        if v > best_val:
            best_val = v
            best_h = h.copy()
        else:
            h = best_h.copy()
            break

    return best_h, best_val


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.75

    if start is None:
        N = 401
        centers = np.arange(N)
        s = np.exp(-0.5 * ((centers - (N - 1) / 2.0) / 50.0) ** 2)
    else:
        s = np.asarray(start, dtype=float).ravel()

    s = np.maximum(s, 0.0)
    if s.max() <= 0:
        s = np.ones_like(s)
    s = s / s.max()

    best_h = s.copy()
    best_val = _R_from_h(best_h)

    # First: LP active-set pivots
    h_lp, v_lp = _lp_pivot(best_h, deadline)
    print("lp pivot score", v_lp)
    if v_lp > best_val:
        best_val = v_lp
        best_h = h_lp.copy()

    # Then: LSE smoothing polish
    for tau_rel in (3e-11, 1e-11, 3e-12):
        if time.process_time() > deadline:
            break
        h0 = best_h.copy()
        m0 = h0.max()
        if m0 > 0:
            h0 = h0 / m0
        L0 = np.convolve(h0, h0)
        Lp0 = np.concatenate(([0.0], L0, [0.0]))
        C0 = Lp0.max()
        tau = tau_rel * C0
        hh, vv = _lbfgsb_lse(best_h, tau, deadline, maxiter=150)
        print("lse tau_rel", tau_rel, "score", vv)
        if time.process_time() > deadline:
            break
        hh, vv = _lbfgsb_polish(hh, deadline, maxiter=100)
        print("exact after lse", tau_rel, "score", vv)
        if vv > best_val:
            best_val = vv
            best_h = hh.copy()

    print("score approx", best_val)
    return best_h
