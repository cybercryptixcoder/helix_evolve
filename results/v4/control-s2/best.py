import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _conv(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size >= 1024 or b.size >= 1024:
        return fftconvolve(a, b, mode='full')
    return np.convolve(a, b)


def _score(h):
    h = np.asarray(h, dtype=float)
    if h.max() <= 0:
        return 0.0
    L = _conv(h, h)
    m = L.max()
    s = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
    l1 = (h.sum()) ** 2
    return s / (l1 * m)


def _convolve_grad(h, dR_dL):
    N = h.size
    c = _conv(dR_dL, h[::-1])
    return 2.0 * c[N - 1: N - 1 + N]


def _make_fun_grad(p):
    def fg(x):
        h = np.exp(x - x.max())
        L = _conv(h, h)
        M = L.size
        Lmax = L.max()
        q = L / Lmax
        qp = np.power(q, p)
        mean_qp = np.mean(qp)
        mp = Lmax * mean_qp ** (1.0 / p)
        s = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
        l1 = (h.sum()) ** 2
        R = s / (l1 * mp)
        ds_dL = np.zeros(M)
        ds_dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
        ds_dL[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
        dmp_dL = (1.0 / M) * (mp / Lmax) ** (1.0 - p) * np.power(q, p - 1.0)
        dR_dL = ds_dL / (l1 * mp) - (s / (l1 * mp * mp)) * dmp_dL
        dR_dh = _convolve_grad(h, dR_dL)
        sh = h.sum()
        dR_dh -= (s / (l1 * l1 * mp)) * 2.0 * sh
        dR_dx = dR_dh * h
        return -R, -dR_dx
    return fg


def _make_fun_grad_logsumexp(alpha):
    def fg(x):
        h = np.exp(x - x.max())
        L = _conv(h, h)
        M = L.size
        Lmax = L.max()
        tau = alpha * Lmax
        e = np.exp((L - Lmax) / tau)
        mean_e = np.mean(e)
        mp = Lmax + tau * np.log(mean_e)
        s = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
        l1 = (h.sum()) ** 2
        R = s / (l1 * mp)
        ds_dL = np.zeros(M)
        ds_dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
        ds_dL[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
        dmp_dL = e / (M * mean_e)
        dR_dL = ds_dL / (l1 * mp) - (s / (l1 * mp * mp)) * dmp_dL
        dR_dh = _convolve_grad(h, dR_dL)
        sh = h.sum()
        dR_dh -= (s / (l1 * l1 * mp)) * 2.0 * sh
        dR_dx = dR_dh * h
        return -R, -dR_dx
    return fg


def _make_fun_grad_lse_direct(alpha):
    def fg(h):
        L = _conv(h, h)
        M = L.size
        Lmax = L.max()
        tau = alpha * Lmax
        e = np.exp((L - Lmax) / tau)
        mean_e = np.mean(e)
        mp = Lmax + tau * np.log(mean_e)
        s = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
        l1 = (h.sum()) ** 2
        R = s / (l1 * mp)
        ds_dL = np.zeros(M)
        ds_dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
        ds_dL[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
        dmp_dL = e / (M * mean_e)
        dR_dL = ds_dL / (l1 * mp) - (s / (l1 * mp * mp)) * dmp_dL
        dR_dh = _convolve_grad(h, dR_dL)
        sh = h.sum()
        dR_dh -= (s / (l1 * l1 * mp)) * 2.0 * sh
        return -R, -dR_dh
    return fg


def _make_fun_grad_exactmax_direct():
    # Averaged subgradient over the near-max plateau (broad max region).
    def fg(h):
        L = _conv(h, h)
        M = L.size
        Lmax = L.max()
        s = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
        l1 = (h.sum()) ** 2
        R = s / (l1 * Lmax)
        ds_dL = np.zeros(M)
        ds_dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
        ds_dL[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
        dR_dL = ds_dL / (l1 * Lmax)
        mask = L >= Lmax * (1.0 - 1e-8)
        w = mask / mask.sum()
        dR_dL -= (s / (l1 * Lmax * Lmax)) * w
        dR_dh = _convolve_grad(h, dR_dL)
        sh = h.sum()
        dR_dh -= (s / (l1 * l1 * Lmax)) * 2.0 * sh
        return -R, -dR_dh
    return fg


def _make_fun_grad_exactmax():
    def fg(x):
        h = np.exp(x - x.max())
        L = _conv(h, h)
        M = L.size
        Lmax = L.max()
        s = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
        l1 = (h.sum()) ** 2
        R = s / (l1 * Lmax)
        ds_dL = np.zeros(M)
        ds_dL[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
        ds_dL[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
        dR_dL = ds_dL / (l1 * Lmax)
        mask = L >= Lmax * (1.0 - 1e-8)
        w = mask / mask.sum()
        dR_dL -= (s / (l1 * Lmax * Lmax)) * w
        dR_dh = _convolve_grad(h, dR_dL)
        sh = h.sum()
        dR_dh -= (s / (l1 * l1 * Lmax)) * 2.0 * sh
        dR_dx = dR_dh * h
        return -R, -dR_dx
    return fg


def _lbfgsb_polish(h, p, deadline, maxiter=300):
    x0 = np.log(np.maximum(h, 1e-12))
    fg = _make_fun_grad(p)

    def fun(x):
        if time.process_time() >= deadline:
            raise StopIteration
        return fg(x)

    try:
        res = minimize(fun, x0, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                'ftol': 1e-15, 'gtol': 1e-12})
        h2 = np.exp(res.x - res.x.max())
        return h2
    except StopIteration:
        return h
    except Exception:
        return h


def _lbfgsb_polish_lse(h, alpha, deadline, maxiter=300):
    x0 = np.log(np.maximum(h, 1e-12))
    fg = _make_fun_grad_logsumexp(alpha)

    def fun(x):
        if time.process_time() >= deadline:
            raise StopIteration
        return fg(x)

    try:
        res = minimize(fun, x0, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                'ftol': 1e-16, 'gtol': 1e-13})
        h2 = np.exp(res.x - res.x.max())
        return h2
    except StopIteration:
        return h
    except Exception:
        return h


def _lbfgsb_polish_lse_direct(h, alpha, deadline, maxiter=150):
    fg = _make_fun_grad_lse_direct(alpha)
    h0 = np.maximum(h, 0.0)

    def fun(x):
        if time.process_time() >= deadline:
            raise StopIteration
        return fg(x)

    try:
        res = minimize(fun, h0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * h0.size,
                       options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                'ftol': 1e-16, 'gtol': 1e-13})
        h2 = np.maximum(res.x, 0.0)
        if h2.max() <= 0:
            return h
        return h2
    except StopIteration:
        return h
    except Exception:
        return h


def _lbfgsb_polish_exactmax_direct(h, deadline, maxiter=80):
    fg = _make_fun_grad_exactmax_direct()
    h0 = np.maximum(h, 0.0)

    def fun(x):
        if time.process_time() >= deadline:
            raise StopIteration
        return fg(x)

    try:
        res = minimize(fun, h0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * h0.size,
                       options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                'ftol': 1e-16, 'gtol': 1e-13})
        h2 = np.maximum(res.x, 0.0)
        if h2.max() <= 0:
            return h
        return h2
    except StopIteration:
        return h
    except Exception:
        return h


def _lbfgsb_polish_exactmax(h, deadline, maxiter=60):
    x0 = np.log(np.maximum(h, 1e-12))
    fg = _make_fun_grad_exactmax()

    def fun(x):
        if time.process_time() >= deadline:
            raise StopIteration
        return fg(x)

    try:
        res = minimize(fun, x0, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                'ftol': 1e-16, 'gtol': 1e-13})
        h2 = np.exp(res.x - res.x.max())
        return h2
    except StopIteration:
        return h
    except Exception:
        return h


def _polish_sequence(best, best_score, deadline, ps, maxiter=200):
    for p in ps:
        if time.process_time() >= deadline:
            break
        cand = _lbfgsb_polish(best, p, deadline, maxiter=maxiter)
        cand = np.maximum(cand, 1e-12)
        cand /= cand.max()
        sc = _score(cand)
        if sc > best_score:
            best = cand
            best_score = sc
    return best, best_score


def _lse_continuation(best, best_score, deadline, alphas, maxiter=200):
    for alpha in alphas:
        if time.process_time() >= deadline:
            break
        cand = _lbfgsb_polish_lse(best, alpha, deadline, maxiter=maxiter)
        cand = np.maximum(cand, 1e-12)
        cand /= cand.max()
        sc = _score(cand)
        if sc > best_score:
            best = cand
            best_score = sc
    return best, best_score


def _lse_direct_continuation(best, best_score, deadline, alphas, maxiter=150):
    for alpha in alphas:
        if time.process_time() >= deadline:
            break
        cand = _lbfgsb_polish_lse_direct(best, alpha, deadline, maxiter=maxiter)
        cand = np.maximum(cand, 0.0)
        if cand.max() <= 0:
            continue
        cand = cand / cand.max()
        sc = _score(cand)
        if sc > best_score:
            best = cand
            best_score = sc
    return best, best_score


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

    if start is not None:
        best = np.asarray(start, dtype=float).copy().ravel()
        best = np.maximum(best, 0.0)
        if best.size == 0 or best.max() <= 0:
            best = np.ones(25600)
    else:
        best = np.ones(25600)

    best = np.maximum(best, 1e-12)
    best /= best.max()
    best_score = _score(best)

    # Phase 1: quick p-norm warm-up
    if time.process_time() < deadline:
        best, best_score = _polish_sequence(
            best, best_score, min(deadline, time.process_time() + 2.0),
            (3000.0, 10000.0, 30000.0, 100000.0), maxiter=100)

    # Phase 2: direct-height LSE continuation
    if time.process_time() < deadline:
        alphas = [3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 3e-6, 1e-6]
        best, best_score = _lse_direct_continuation(
            best, best_score, deadline, alphas, maxiter=150)

    # Phase 3: exact-max direct with averaged plateau subgradient,
    # repeated until deadline (the experiment's main change).
    while time.process_time() < deadline - 0.5:
        cand = _lbfgsb_polish_exactmax_direct(best, deadline, maxiter=200)
        if cand.max() > 0:
            cand = cand / cand.max()
            sc = _score(cand)
            if sc > best_score + 1e-12:
                best = cand
                best_score = sc
            else:
                # no further improvement; try a small LSE nudge then exact-max
                if time.process_time() >= deadline - 0.5:
                    break
                cand2 = _lbfgsb_polish_lse_direct(
                    best, 1e-7, deadline, maxiter=80)
                if cand2.max() > 0:
                    cand2 = cand2 / cand2.max()
                    sc2 = _score(cand2)
                    if sc2 > best_score:
                        best = cand2
                        best_score = sc2
                        continue
                break

    # Phase 4: log-parametrized exact-max polish with averaged subgradient
    if time.process_time() < deadline - 0.3:
        cand = _lbfgsb_polish_exactmax(best, deadline, maxiter=80)
        cand = np.maximum(cand, 1e-12)
        cand /= cand.max()
        sc = _score(cand)
        if sc > best_score:
            best = cand
            best_score = sc

    return best
