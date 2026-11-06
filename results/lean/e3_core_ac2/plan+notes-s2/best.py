import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def compute_R(h):
    h = np.asarray(h, dtype=float)
    if h.ndim != 1 or h.size == 0:
        return -1.0
    if not np.all(np.isfinite(h)) or np.any(h < 0):
        return -1.0
    s = h.sum()
    if s <= 0:
        return -1.0
    c = np.convolve(h, h)
    L = np.concatenate(([0.0], c, [0.0]))
    num = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    den = s * s * np.max(L)
    if den <= 0:
        return -1.0
    return num / den


def _R_from_c(c, s):
    L = np.concatenate(([0.0], c, [0.0]))
    num = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    M = np.max(L)
    den = s * s * M
    if den <= 0:
        return -1.0
    return num / den


def _corr(a, h):
    n = h.size
    full = fftconvolve(a, h[::-1], mode='full')
    return full[n-1:n-1+n]


def _grad_common(h, weight_fn):
    n = h.size
    s = h.sum()
    c = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], c, [0.0]))
    dA_dL = (np.concatenate(([0.0], L[:-1])) + 4.0*L
             + np.concatenate((L[1:], [0.0]))) / 3.0
    dA_dc = dA_dL[1:1+c.size]
    dA_dh = 2.0 * _corr(dA_dc, h)
    A = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    Ms, dMs_dL = weight_fn(L, c)
    dMs_dc = dMs_dL[1:1+c.size]
    dMs_dh = 2.0 * _corr(dMs_dc, h)
    B = s * s
    R = A / (B * Ms)
    dB_dh = 2.0 * s
    dR_dh = (dA_dh/(B*Ms) - A/(B*B*Ms)*dB_dh - A/(B*Ms*Ms)*dMs_dh)
    return R, dR_dh


def _R_grad(h):
    def wf(L, c):
        M = np.max(L)
        tol = 1e-12 * max(M, 1e-300)
        mask = (L >= M - tol).astype(float)
        s = mask.sum()
        if s > 0:
            mask = mask / s
        return M, mask
    return _grad_common(h, wf)


def _smooth_R_grad(h, tau):
    def wf(L, c):
        Lmax = np.max(L)
        w = np.exp((L - Lmax) / tau)
        w /= w.sum()
        Ms = np.sum(w * L)
        dMs_dL = w * (L - Ms) / tau + w
        return Ms, dMs_dL
    return _grad_common(h, wf)


def _resample(h, N):
    if h.size == N:
        return h.copy()
    if N > h.size:
        x_old = np.linspace(0.0, 1.0, h.size)
        x_new = np.linspace(0.0, 1.0, N)
        return np.maximum(0.0, np.interp(x_new, x_old, h))
    out = np.empty(N)
    edges = np.linspace(0, h.size, N + 1)
    for i in range(N):
        a = int(np.floor(edges[i]))
        b = int(np.ceil(edges[i + 1]))
        b = max(b, a + 1)
        out[i] = h[a:b].mean()
    return np.maximum(0.0, out)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + max(0.0, budget_seconds - 4.0)

    if start is not None:
        base = np.asarray(start, dtype=float).ravel().copy()
        if base.size == 0 or not np.all(np.isfinite(base)) or np.any(base < 0) \
                or base.sum() <= 0:
            base = np.ones(50)
    else:
        base = np.ones(50)

    state = {'best': base.copy(), 'best_R': compute_R(base)}

    def try_candidate(h):
        h = np.asarray(h, dtype=float)
        if h.size == 0 or h.size > 50000:
            return False
        if not np.all(np.isfinite(h)) or np.any(h < 0) or h.sum() <= 0:
            return False
        r = compute_R(h)
        if r > state['best_R']:
            state['best_R'] = r
            state['best'] = h.copy()
            return True
        return False

    def optimize_at(h_start, maxiter, use_smooth, tau):
        def fun(u):
            h = u * u
            if h.sum() <= 0:
                return 1.0, np.zeros_like(u)
            if use_smooth:
                R, g = _smooth_R_grad(h, tau)
            else:
                R, g = _R_grad(h)
            if not np.isfinite(R):
                return 1.0, np.zeros_like(u)
            return -R, -g * (2.0 * u)

        def cb(u):
            r = compute_R(u * u)
            if r > state['best_R']:
                state['best_R'] = r
                state['best'] = (u * u).copy()
            if time.process_time() >= deadline:
                raise StopIteration

        h0 = h_start / max(h_start.max(), 1e-300)
        u0 = np.sqrt(np.maximum(h0, 0.0))
        try:
            res = minimize(fun, u0, jac=True, method='L-BFGS-B', callback=cb,
                           options={'maxiter': maxiter, 'ftol': 1e-16,
                                    'gtol': 1e-14})
            try_candidate(res.x * res.x)
        except StopIteration:
            pass
        except Exception:
            pass

    def optimize_symmetric(h_start, maxiter, use_smooth=False, tau=0.0):
        N = h_start.size
        m = (N + 1) // 2
        h0 = h_start / max(h_start.max(), 1e-300)
        v0 = np.sqrt(np.maximum(h0[:m], 0.0))

        def expand(v):
            if N % 2 == 0:
                return np.concatenate((v, v[::-1]))
            return np.concatenate((v, v[-2::-1]))

        def fun(u):
            v = u * u
            h = expand(v)
            if h.sum() <= 0:
                return 1.0, np.zeros_like(u)
            if use_smooth:
                R, g = _smooth_R_grad(h, tau)
            else:
                R, g = _R_grad(h)
            if not np.isfinite(R):
                return 1.0, np.zeros_like(u)
            gv = g[:m].copy()
            if N % 2 == 0:
                gv += g[m:][::-1]
            else:
                gv[1:] += g[m:][::-1]
            return -R, -gv * (2.0 * u)

        def cb(u):
            h = expand(u * u)
            r = compute_R(h)
            if r > state['best_R']:
                state['best_R'] = r
                state['best'] = h.copy()
            if time.process_time() >= deadline:
                raise StopIteration

        try:
            res = minimize(fun, v0, jac=True, method='L-BFGS-B', callback=cb,
                           options={'maxiter': maxiter, 'ftol': 1e-16,
                                    'gtol': 1e-14})
            try_candidate(expand(res.x * res.x))
        except StopIteration:
            pass
        except Exception:
            pass

    # Phase 1: sharpen native best.
    optimize_at(state['best'], 4000, False, 0.0)
    print("phase1 R =", state['best_R'], "N =", state['best'].size)

    # Phase 1b: enforce symmetry then symmetric polish.
    if time.process_time() < deadline:
        hsym = 0.5 * (state['best'] + state['best'][::-1])
        try_candidate(hsym)
        if time.process_time() < deadline:
            optimize_symmetric(state['best'], 2000)
        print("phase1b sym R =", state['best_R'])

    # Phase 2: size variations, using resampling + symmetric optimize.
    baseN = state['best'].size
    cand_Ns = []
    for d in [1, -1, 2, -2, 3, -3, 5, -5, 8, -8, 13, -13, 21, -21]:
        n = baseN + d
        if 50 <= n <= 50000 and n not in cand_Ns:
            cand_Ns.append(n)

    for N in cand_Ns:
        if time.process_time() >= deadline:
            break
        h_up = _resample(state['best'], N)
        if try_candidate(h_up):
            optimize_symmetric(state['best'], 2000)
            if time.process_time() >= deadline:
                break
            optimize_at(state['best'], 1500, False, 0.0)
    print("phase2 R =", state['best_R'])

    # Phase 3: softmax polishes + symmetric.
    taus = [1e-3, 3e-4, 1e-4, 5e-5, 2e-5, 1e-5, 5e-6, 1e-6, 3e-7]
    for tf in taus:
        if time.process_time() >= deadline:
            break
        cc = np.convolve(state['best'], state['best'])
        peak = cc.max()
        optimize_at(state['best'], 800, True, peak * tf)
        if time.process_time() >= deadline:
            break
        optimize_at(state['best'], 1500, False, 0.0)
    print("phase3 R =", state['best_R'])

    # Phase 4: alternating symmetric + full polish.
    for _ in range(4):
        if time.process_time() >= deadline:
            break
        optimize_symmetric(state['best'], 3000)
        if time.process_time() >= deadline:
            break
        optimize_at(state['best'], 3000, False, 0.0)
    print("phase4 R =", state['best_R'])

    # Phase 6 (improved): coordinate-wise local refinement with incremental
    # autoconvolution updates, plus a vectorised "shift whole tail" move.
    if time.process_time() < deadline:
        h = state['best'].copy()
        N = h.size
        c = np.convolve(h, h)
        s = h.sum()
        cur_R = _R_from_c(c, s)
        eps_list = [1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 3e-6, 1e-6, 3e-7]
        for eps in eps_list:
            if time.process_time() >= deadline:
                break
            improved = True
            sweeps = 0
            while improved and sweeps < 8 and time.process_time() < deadline:
                improved = False
                sweeps += 1
                for i in range(N):
                    if time.process_time() >= deadline:
                        break
                    hi = h[i]
                    for fac in (1.0 - eps, 1.0 + eps):
                        new_hi = max(0.0, hi * fac)
                        delta = new_hi - hi
                        if delta == 0.0:
                            continue
                        c_trial = c.copy()
                        c_trial[i:i+N] += 2.0 * delta * h
                        c_trial[2*i] += delta * delta
                        s_trial = s + delta
                        r = _R_from_c(c_trial, s_trial)
                        if r > cur_R:
                            h[i] = new_hi
                            c = c_trial
                            s = s_trial
                            cur_R = r
                            hi = new_hi
                            improved = True
        if try_candidate(h):
            optimize_at(state['best'], 2000, False, 0.0)
        print("phase6 coord R =", state['best_R'])

    # NEW Phase 7: plateau-shaping via shifting the flat-top region's
    # shoulder entries and re-polishing; exploits the fact that f*f has a
    # wide plateau. Perturb boundary shoulders of the near-max set.
    if time.process_time() < deadline:
        for _ in range(3):
            if time.process_time() >= deadline:
                break
            h = state['best'].copy()
            N = h.size
            c = np.convolve(h, h)
            L = np.concatenate(([0.0], c, [0.0]))
            M = L.max()
            # indices where f*f is close to max
            near = np.where(L >= 0.999 * M)[0]
            if near.size < 2:
                break
            lo, hi = near[0], near[-1]
            # approximate support of h from plateau edges
            a = max(0, (lo) // 2 - 2)
            b = min(N, (hi) // 2 + 3)
            changed = False
            for i in range(a, min(a + 4, N)):
                for fac in (1.0 - 2e-4, 1.0 + 2e-4, 1.0 - 5e-5, 1.0 + 5e-5):
                    ht = state['best'].copy()
                    ht[i] = max(0.0, ht[i] * fac)
                    if try_candidate(ht):
                        changed = True
                        break
                if changed:
                    break
            if changed:
                optimize_at(state['best'], 2000, False, 0.0)
        print("phase7 R =", state['best_R'])

    if time.process_time() < deadline:
        optimize_at(state['best'], 20000, False, 0.0)
    print("final R =", state['best_R'], "N =", state['best'].size)
    return state['best']
