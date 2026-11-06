import numpy as np
import time
from scipy.optimize import minimize


def _C_from_heights(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _conv_and_grad(h, N, nfft):
    S = h.sum()
    conv = np.fft.irfft(np.fft.rfft(h, nfft) ** 2, nfft)[:2 * N - 1]
    return S, conv


def _lbfgs_h_exact(h0, t0, budget, maxiter=600, maxfun=1200, m=30,
                   time_frac=0.90, ftol=1e-18, gtol=1e-12):
    h0 = np.maximum(np.asarray(h0, dtype=float), 1e-12)
    N = len(h0)
    nfft = 65536
    while nfft < 2 * N:
        nfft <<= 1
    state = {'best_h': h0.copy(), 'best_C': _C_from_heights(h0),
             'stop': False}

    def fun(h):
        if time.process_time() - t0 > budget * time_frac:
            state['stop'] = True
        h = np.maximum(h, 1e-12)
        S, conv = _conv_and_grad(h, N, nfft)
        k = int(np.argmax(conv))
        C = 2.0 * N * conv[k] / (S * S)
        g = np.zeros(N)
        lo = max(0, k - (N - 1))
        hi = min(N - 1, k)
        idx = np.arange(lo, hi + 1)
        g[idx] = 4.0 * N * h[k - idx] / (S * S)
        g -= 2.0 * C / S
        if C < state['best_C']:
            state['best_C'] = C
            state['best_h'] = h.copy()
        return C, g

    try:
        minimize(fun, h0, jac=True, method='L-BFGS-B',
                 bounds=[(0.0, 1e6)] * N,
                 options={'maxiter': maxiter, 'maxfun': maxfun,
                          'ftol': ftol, 'gtol': gtol, 'm': m},
                 callback=lambda hk: (_ for _ in ()).throw(StopIteration)
                 if state['stop'] else None)
    except StopIteration:
        pass
    except Exception:
        pass

    return state['best_h'], state['best_C']


def _lbfgs_topk_stdpen_h(h0, t0, budget, k=100, lam=1e-2, m=30,
                         maxiter=300, maxfun=600, time_frac=0.85):
    h0 = np.maximum(np.asarray(h0, dtype=float), 1e-12)
    N = len(h0)
    nfft = 65536
    while nfft < 2 * N:
        nfft <<= 1
    state = {'best_h': h0.copy(), 'best_C': _C_from_heights(h0),
             'stop': False}

    def fun(h):
        if time.process_time() - t0 > budget * time_frac:
            state['stop'] = True
        h = np.maximum(h, 1e-12)
        S, conv = _conv_and_grad(h, N, nfft)
        kk = min(k, conv.size)
        idx_top = np.argpartition(conv, -kk)[-kk:]
        vals = conv[idx_top]
        mean_v = float(np.mean(vals))
        var_v = float(np.var(vals))
        if mean_v <= 0:
            mean_v = 1e-30
        std_v = np.sqrt(max(var_v, 0.0))
        Ck = 2.0 * N * mean_v / (S * S)
        pen = lam * std_v / mean_v
        obj = Ck + pen

        g = np.zeros(N)
        for kpos in idx_top:
            lo = max(0, kpos - (N - 1))
            hi = min(N - 1, kpos)
            idx = np.arange(lo, hi + 1)
            g[idx] += (1.0 / kk) * 4.0 * N * h[kpos - idx] / (S * S)
        g -= 2.0 * Ck / S

        inv_m = 1.0 / mean_v
        inv_m2 = inv_m * inv_m
        if std_v > 1e-30:
            inv_s = 1.0 / std_v
        else:
            inv_s = 0.0
        dpen_dv = lam * ((2.0 / kk) * (vals - mean_v) * inv_s * inv_m
                         - std_v * inv_m2 / kk)
        for j, kpos in enumerate(idx_top):
            coef = dpen_dv[j]
            if coef == 0.0:
                continue
            lo = max(0, kpos - (N - 1))
            hi = min(N - 1, kpos)
            idx = np.arange(lo, hi + 1)
            g[idx] += coef * h[kpos - idx]

        Cexact = 2.0 * N * conv.max() / (S * S)
        if Cexact < state['best_C']:
            state['best_C'] = Cexact
            state['best_h'] = h.copy()
        return obj, g

    try:
        minimize(fun, h0, jac=True, method='L-BFGS-B',
                 bounds=[(0.0, 1e6)] * N,
                 options={'maxiter': maxiter, 'maxfun': maxfun,
                          'ftol': 1e-18, 'gtol': 1e-12, 'm': m},
                 callback=lambda hk: (_ for _ in ()).throw(StopIteration)
                 if state['stop'] else None)
    except StopIteration:
        pass
    except Exception:
        pass

    return state['best_h'], state['best_C']


def construct(budget_seconds, start):
    t0 = time.process_time()
    best_h = None
    best_C = np.inf

    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.size > 0 and s.sum() > 0:
            best_h = s.copy()
            best_C = _C_from_heights(s)

    if best_h is None:
        best_h = np.ones(3000)
        best_C = _C_from_heights(best_h)

    time_frac = 0.85

    # --- p0164's two stdpen calls ---
    if time.process_time() - t0 < budget_seconds * time_frac:
        try:
            hv, Cv = _lbfgs_topk_stdpen_h(best_h, t0, budget_seconds, k=100,
                                          lam=1e-2, m=30, maxiter=300,
                                          maxfun=600, time_frac=time_frac)
            if Cv < best_C:
                best_C, best_h = Cv, hv.copy()
        except Exception:
            pass

    if time.process_time() - t0 < budget_seconds * time_frac:
        try:
            hv, Cv = _lbfgs_topk_stdpen_h(best_h, t0, budget_seconds, k=30,
                                          lam=3e-2, m=30, maxiter=300,
                                          maxfun=600, time_frac=time_frac)
            if Cv < best_C:
                best_C, best_h = Cv, hv.copy()
        except Exception:
            pass

    # --- p0172's exact L-BFGS ---
    if time.process_time() - t0 < budget_seconds * 0.95:
        try:
            hf, Cf = _lbfgs_h_exact(best_h, t0, budget_seconds,
                                    maxiter=2000, maxfun=4000, m=50,
                                    time_frac=0.95, ftol=1e-20, gtol=1e-14)
            if Cf < best_C:
                best_C, best_h = Cf, hf
        except Exception:
            pass

    # --- p0172's narrow stdpen polish ---
    if time.process_time() - t0 < budget_seconds * 0.95:
        try:
            hv, Cv = _lbfgs_topk_stdpen_h(best_h, t0, budget_seconds, k=20,
                                          lam=5e-2, m=30, maxiter=500,
                                          maxfun=1000, time_frac=0.95)
            if Cv < best_C:
                best_C, best_h = Cv, hv.copy()
        except Exception:
            pass

    # --- p0172's final exact polish ---
    if time.process_time() - t0 < budget_seconds * 0.97:
        try:
            hf, Cf = _lbfgs_h_exact(best_h, t0, budget_seconds,
                                    maxiter=1000, maxfun=2000, m=30,
                                    time_frac=0.97)
            if Cf < best_C:
                best_C, best_h = Cf, hf
        except Exception:
            pass

    # --- Experiment: extra stdpen/exact alternation with leftover budget ---
    tf = 0.96

    if time.process_time() - t0 < budget_seconds * tf:
        try:
            hv, Cv = _lbfgs_topk_stdpen_h(best_h, t0, budget_seconds, k=20,
                                          lam=5e-2, m=30, maxiter=400,
                                          maxfun=800, time_frac=tf)
            if Cv < best_C:
                best_C, best_h = Cv, hv.copy()
        except Exception:
            pass

    if time.process_time() - t0 < budget_seconds * tf:
        try:
            hf, Cf = _lbfgs_h_exact(best_h, t0, budget_seconds,
                                    maxiter=1000, maxfun=2000, m=50,
                                    time_frac=tf, ftol=1e-22, gtol=1e-14)
            if Cf < best_C:
                best_C, best_h = Cf, hf
        except Exception:
            pass

    if time.process_time() - t0 < budget_seconds * tf:
        try:
            hv, Cv = _lbfgs_topk_stdpen_h(best_h, t0, budget_seconds, k=10,
                                          lam=1e-1, m=30, maxiter=400,
                                          maxfun=800, time_frac=tf)
            if Cv < best_C:
                best_C, best_h = Cv, hv.copy()
        except Exception:
            pass

    if time.process_time() - t0 < budget_seconds * tf:
        try:
            hf, Cf = _lbfgs_h_exact(best_h, t0, budget_seconds,
                                    maxiter=1000, maxfun=2000, m=50,
                                    time_frac=tf)
            if Cf < best_C:
                best_C, best_h = Cf, hf
        except Exception:
            pass

    return np.asarray(best_h, dtype=float)
