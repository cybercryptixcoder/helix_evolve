# v4 atlas-s1: first program above AlphaEvolve May 2025 (0.8962)
# Run: results/v4/atlas-s1   program p0057   round 10   written by: deep loop   parent: p0053
# Score R = 0.907611556938278   steps n = 332   CPU seconds used: 7.26
# Extracted verbatim from results/v4/atlas-s1/programs.jsonl;
# the model calls of that round: results/v4/atlas-s1/trace.jsonl.gz
# Its intent, as the agent wrote it: p0053's mu schedule stops at 1e6 after ~1.2 s/stage and only two stages improved. A longer, denser schedule with exact-R L-BFGS polish after each mu and repeated restarts from the best point will squeeze more flatness out of the same basin.

import numpy as np
import time
from scipy.optimize import minimize, minimize_scalar


def _knots(h):
    L = np.convolve(h, h)
    return np.concatenate(([0.0], L, [0.0]))


def R_of(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    L = _knots(h)
    num = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    den = s * s * L.max()
    if den <= 0:
        return 0.0
    return num / den


def _num_and_dq(h):
    L = np.convolve(h, h)
    Lf = np.concatenate(([0.0], L, [0.0]))
    a = Lf[:-1]; b = Lf[1:]
    num = np.sum(a*a + a*b + b*b) / 3.0
    dq = np.zeros_like(Lf)
    dq[:-1] += (2*a + b)
    dq[1:] += (a + 2*b)
    dq /= 3.0
    return num, dq, h.sum(), Lf


def _backprop(gLf, h):
    gL = gLf[1:-1]
    n = h.size
    return 2.0 * np.correlate(gL, h, mode='valid')[:n]


def _R_and_grad(h):
    n = h.size
    s = h.sum()
    if s <= 0:
        return 0.0, np.zeros(n)
    num, dq, s, Lf = _num_and_dq(h)
    am = int(np.argmax(Lf))
    mx = Lf[am]
    den = s * s * mx
    if den <= 0:
        return 0.0, np.zeros(n)
    R = num / den
    coef = num * s * s / (den * den)
    gLf = dq / den
    gLf[am] -= coef
    grad = _backprop(gLf, h)
    ds = -num * 2.0 * s * mx / (den * den)
    grad += ds
    return R, grad


def _penalty_and_grad(h, mu):
    """P_mu = -num/s^2 + mu * sum relu(Lf-1)^2, gradient wrt h."""
    n = h.size
    s = h.sum()
    if s <= 0:
        return 1e18, np.zeros(n)
    num, dq, s, Lf = _num_and_dq(h)
    s2 = s * s
    P = -num / s2
    gLf = -dq / s2
    grad = _backprop(gLf, h)
    grad += 2.0 * num / (s2 * s)
    r = np.maximum(Lf - 1.0, 0.0)
    if np.any(r > 0):
        P += mu * np.sum(r * r)
        w = 2.0 * mu * r
        grad += _backprop(w, h)
    return P, grad


def _rescale_maxL(h):
    h = np.clip(h, 0, None)
    if h.sum() <= 0:
        return h
    Lf = _knots(h)
    mx = Lf.max()
    if mx <= 0:
        return h
    return h / np.sqrt(mx)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.88
    rng = np.random.default_rng(2024)

    if start is not None:
        base = np.asarray(start, dtype=float).copy()
        base = np.clip(base, 0, None)
        if base.size == 0 or base.sum() <= 0:
            base = np.ones(50)
    else:
        base = np.ones(50)
    base = base / base.max()

    best = base.copy()
    bestR = R_of(best)
    print("start R=%.6f (N=%d)" % (bestR, best.size))

    def exact_obj(x):
        xc = np.clip(x, 0, None)
        R, g = _R_and_grad(xc)
        g = g * (x > 0)
        return -R, -g

    def make_pen(mu):
        def f(x):
            xc = np.clip(x, 0, None)
            P, g = _penalty_and_grad(xc, mu)
            g = g * (x > 0)
            return P, g
        return f

    def coord_sweep(h, cur, n_passes):
        n = h.size
        for _ in range(n_passes):
            if time.process_time() > deadline:
                return h, cur
            improved = False
            order = rng.permutation(n)
            for idx in order:
                if time.process_time() > deadline:
                    return h, cur
                old = h[idx]
                hi = max(4.0 * old, 1.0)

                def neg_r(alpha):
                    h[idx] = alpha
                    return -R_of(h)

                try:
                    res = minimize_scalar(neg_r, bounds=(0.0, hi),
                                          method='bounded',
                                          options={'xatol': 1e-8})
                    cand = res.x
                    cand_r = -res.fun
                except Exception:
                    cand = old
                    cand_r = cur
                if cand_r > cur + 1e-14:
                    h[idx] = cand
                    cur = cand_r
                    improved = True
                else:
                    h[idx] = old
            if not improved:
                break
        return h, cur

    def polish(h, cur):
        """Exact-R L-BFGS-B + one coordinate sweep."""
        if time.process_time() >= deadline:
            return h, cur
        try:
            res = minimize(exact_obj, h, jac=True, method='L-BFGS-B',
                           bounds=[(0, None)] * h.size,
                           options={'maxiter': 2000, 'maxfun': 4000})
            cand = np.clip(res.x, 0, None)
            if cand.sum() > 0:
                cand = cand / cand.max()
                rc = R_of(cand)
                if rc > cur:
                    h, cur = cand, rc
        except Exception:
            pass
        if time.process_time() < deadline:
            h2, c2 = coord_sweep(h.copy(), cur, 1)
            if c2 > cur:
                h, cur = h2, c2
        return h, cur

    def run_schedule(h0, mu_list):
        h = _rescale_maxL(h0.copy())
        cur = R_of(h)
        for mu in mu_list:
            if time.process_time() >= deadline:
                break
            stage_end = min(deadline, time.process_time() + 1.2)
            rem = stage_end - time.process_time()
            if rem <= 0.05:
                break
            try:
                res = minimize(make_pen(mu), h, jac=True, method='L-BFGS-B',
                               bounds=[(0, None)] * h.size,
                               options={'maxiter': 2000, 'maxfun': 4000})
                h = _rescale_maxL(res.x)
            except Exception as e:
                print("  mu=%g failed: %s" % (mu, e))
            r = R_of(h)
            print("  mu=%g R=%.6f" % (mu, r))
            if r > cur:
                cur = r
        return h, cur

    mu_list = [1e0, 3e0, 1e1, 3e1, 1e2, 3e2, 1e3, 3e3, 1e4, 3e4,
               1e5, 3e5, 1e6, 3e6, 1e7]

    # Pass 1: full schedule from the start
    h, cur = run_schedule(best, mu_list)
    h, cur = polish(h, cur)
    if cur > bestR:
        best, bestR = h.copy(), cur
        print("after pass1 R=%.6f (N=%d)" % (bestR, best.size))

    # Pass 2: shifted one decade higher, from best
    mu_shift = [m * 10.0 for m in mu_list]
    while time.process_time() < deadline - 0.5:
        h, cur = run_schedule(best, mu_shift)
        h, cur = polish(h, cur)
        if cur > bestR + 1e-12:
            best, bestR = h.copy(), cur
            print("after pass2 R=%.6f (N=%d)" % (bestR, best.size))
        else:
            break

    print("final R=%.6f (N=%d)" % (bestR, best.size))
    return best
