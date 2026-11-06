import numpy as np
import time
from scipy.optimize import linprog, minimize


def C_of(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    N = len(h)
    return 2.0 * N * np.max(np.convolve(h, h)) / (s * s)


def _conv_matrix(h):
    N = len(h)
    K = 2 * N - 1
    A = np.zeros((K, N))
    for k in range(K):
        lo = max(0, k - (N - 1))
        hi = min(N - 1, k)
        idx = np.arange(lo, hi + 1)
        A[k, idx] = h[k - idx]
    return A


def slp(h0, out_of_time, max_outer=200):
    h = np.asarray(h0, dtype=float)
    s = h.sum()
    if s <= 0:
        return h, np.inf
    h = h / s
    N = len(h)
    best, best_c = h.copy(), C_of(h)
    K = 2 * N - 1

    for _ in range(max_outer):
        if out_of_time():
            break
        c = np.convolve(h, h)
        Aconv = _conv_matrix(h)
        A_ub = np.zeros((K, N + 1))
        A_ub[:, :N] = 2.0 * Aconv
        A_ub[:, N] = -1.0
        b_ub = -c
        A_eq = np.zeros((1, N + 1))
        A_eq[0, :N] = 1.0
        b_eq = np.array([1.0])
        bounds = [(-h[i], None) for i in range(N)]
        bounds.append((None, None))
        obj = np.zeros(N + 1)
        obj[N] = 1.0
        try:
            res = linprog(obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                          bounds=bounds, method='highs')
        except Exception:
            break
        if not res.success:
            break
        delta = res.x[:N]

        neg = delta < 0
        if np.any(neg):
            amax = np.min(-h[neg] / delta[neg])
        else:
            amax = 1.0
        if not np.isfinite(amax) or amax <= 0:
            break
        amax *= (1.0 - 1e-12)
        alphas = np.exp(np.linspace(np.log(1e-6), np.log(amax), 120))
        best_a, best_trial, best_tc = None, None, np.inf
        for a in alphas:
            t = np.maximum(h + a * delta, 0.0)
            st = t.sum()
            if st <= 0:
                continue
            t /= st
            tc = C_of(t)
            if tc < best_tc:
                best_tc, best_a, best_trial = tc, a, t
        if best_trial is None:
            break
        la = np.log(best_a)
        step = (np.log(amax) - np.log(1e-6)) / 119.0
        a_lo = np.exp(max(np.log(1e-6), la - 2 * step))
        a_hi = np.exp(min(np.log(amax), la + 2 * step))
        gr = (np.sqrt(5.0) - 1.0) / 2.0
        c1 = a_hi - gr * (a_hi - a_lo)
        c2 = a_lo + gr * (a_hi - a_lo)

        def ev(a):
            t = np.maximum(h + a * delta, 0.0)
            st = t.sum()
            if st <= 0:
                return np.inf, None
            t /= st
            return C_of(t), t

        fc1, _ = ev(c1)
        fc2, _ = ev(c2)
        for _ in range(30):
            if fc1 < fc2:
                a_hi, c2, fc2 = c2, c1, fc1
                c1 = a_hi - gr * (a_hi - a_lo)
                fc1, _ = ev(c1)
            else:
                a_lo, c1, fc1 = c1, c2, fc2
                c2 = a_lo + gr * (a_hi - a_lo)
                fc2, _ = ev(c2)
        a_ref = 0.5 * (a_lo + a_hi)
        c_ref, tr_ref = ev(a_ref)
        if c_ref < best_tc:
            best_tc, best_trial = c_ref, tr_ref

        cur_c = C_of(h)
        if best_trial is None or best_tc >= cur_c - 1e-15:
            break
        h = best_trial
        if best_tc < best_c:
            best_c, best = best_tc, h.copy()
    return best, best_c


def smooth_polish(h0, out_of_time, betas=(1e5, 1e6, 1e7, 1e8, 1e9, 1e10), maxiter=400):
    h0 = np.asarray(h0, dtype=float)
    s0 = h0.sum()
    if s0 <= 0:
        return h0, np.inf
    h0 = h0 / s0
    N = len(h0)

    def make_F(beta):
        def F(x):
            s = x.sum()
            if s <= 0:
                return 1e30, np.zeros_like(x)
            c = np.convolve(x, x)
            z = beta * c
            zmax = z.max()
            e = np.exp(z - zmax)
            Z = e.sum()
            lse = zmax + np.log(Z)
            w = e / Z
            g_lse = 2.0 * np.correlate(w, x, mode='valid')
            val = lse - 2.0 * np.log(s)
            g = g_lse - 2.0 / s
            return val, g
        return F

    x = h0.copy()
    best, best_c = h0.copy(), C_of(h0)
    for beta in betas:
        if out_of_time():
            break
        F = make_F(beta)
        try:
            res = minimize(F, x, jac=True, method='L-BFGS-B',
                           bounds=[(0.0, None)] * N,
                           options={'maxiter': maxiter, 'ftol': 1e-16, 'gtol': 1e-13})
            x = np.maximum(res.x, 0.0)
            s = x.sum()
            if s <= 0:
                break
            x = x / s
        except Exception:
            break
        c = C_of(x)
        if c < best_c:
            best_c, best = c, x.copy()
    return best, best_c


def upsample(h, N_new):
    h = np.asarray(h, dtype=float)
    N = len(h)
    if N == N_new:
        return h.copy()
    x_old = (np.arange(N) + 0.5) / N
    x_new = (np.arange(N_new) + 0.5) / N_new
    return np.interp(x_new, x_old, h)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.80

    def oot():
        return time.process_time() > deadline

    if start is not None:
        base = np.asarray(start, dtype=float).copy()
        if base.size == 0 or base.sum() <= 0:
            base = np.ones(400)
    else:
        base = np.ones(400)
    s = base.sum()
    if s > 0:
        base = base / s

    best, best_c = base.copy(), C_of(base)
    print(f"start C={best_c:.9f} N={len(best)}")

    # Refine on current grid
    rnd = 0
    while not oot() and rnd < 3:
        improved = False
        h, c = slp(best, oot, max_outer=120)
        if c < best_c - 1e-14:
            best, best_c = h, c
            improved = True
            print(f"slp#{rnd} C={best_c:.9f}")
        if oot():
            break
        h, c = smooth_polish(best, oot, betas=(1e8, 1e10, 1e12), maxiter=300)
        if c < best_c - 1e-14:
            best, best_c = h, c
            improved = True
            print(f"sm#{rnd} C={best_c:.9f}")
        rnd += 1
        if not improved:
            break

    # Key change: densify the grid in place (more knots -> finer resolution),
    # and always keep the finer representation if it isn't worse.
    for N_fine in (800, 1200, 2000):
        if oot():
            break
        if N_fine <= len(best):
            continue
        h_fine = upsample(best, N_fine)
        c_fine = C_of(h_fine)
        print(f"upsample N={N_fine} C={c_fine:.9f}")
        # Always polish the dense grid; adopt it even if only marginally better,
        # so subsequent iterations work at higher resolution.
        hf, cf = smooth_polish(h_fine, oot, betas=(1e6, 1e8, 1e10), maxiter=200)
        if cf < c_fine:
            h_fine, c_fine = hf, cf
        if not oot():
            hf, cf = slp(h_fine, oot, max_outer=80)
            if cf < c_fine:
                h_fine, c_fine = hf, cf
        if not oot():
            hf, cf = smooth_polish(h_fine, oot, betas=(1e9, 1e11, 1e13), maxiter=300)
            if cf < c_fine:
                h_fine, c_fine = hf, cf
        if c_fine < best_c + 1e-9:
            best, best_c = h_fine, c_fine
            print(f"adopted N={N_fine} C={best_c:.9f}")
        else:
            print(f"fine N={N_fine} rejected C={c_fine:.9f}")

    print(f"final C={best_c:.9f} N={len(best)}")
    return np.asarray(best, dtype=float)
