import numpy as np
import time
from scipy.optimize import minimize
try:
    from scipy.signal import fftconvolve
except Exception:
    fftconvolve = None


def _conv(h):
    if fftconvolve is not None and len(h) > 400:
        return fftconvolve(h, h)
    return np.convolve(h, h)


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * float(np.max(_conv(h))) / (s * s)


def _interp_to(h, N):
    M = len(h)
    if M == N:
        return h.astype(float).copy()
    xp = np.linspace(0.0, 1.0, M)
    x = np.linspace(0.0, 1.0, N)
    return np.interp(x, xp, h).astype(float)


def _softmax_obj(h, beta):
    N = len(h)
    S = h.sum()
    if S <= 0:
        return 1e18, np.zeros(N)
    conv = _conv(h)
    z = beta * conv
    zmax = z.max()
    e = np.exp(z - zmax)
    Z = e.sum()
    logZ = zmax + np.log(Z)
    J = logZ / (beta * S * S)
    p = e / Z
    corr = np.convolve(p, h[::-1])
    grad_conv = 2.0 * corr[N - 1: 2 * N - 1]
    grad = grad_conv / (S * S) - 2.0 * J / S
    return J, grad


def _active_set_obj(h, tol_rel=1e-6):
    N = len(h)
    S = h.sum()
    if S <= 0:
        return 1e18, np.zeros(N)
    conv = _conv(h)
    M = float(conv.max())
    tol = tol_rel * M
    K = np.where(conv >= M - tol)[0]
    Cval = 2.0 * N * M / (S * S)
    ind = np.zeros(N)
    ind[K] = 1.0
    corr = np.convolve(ind, h[::-1])
    gM = 2.0 * corr[N - 1: 2 * N - 1] / len(K)
    grad = (2.0 * N / (S * S)) * gM - (4.0 * N * M) / (S * S * S)
    return Cval, grad


def _run_lbfgs(fun, x0, deadline, maxiter, callback):
    if time.process_time() >= deadline:
        return x0
    try:
        res = minimize(fun, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0.0, None)] * len(x0), callback=callback,
                       options={'maxiter': maxiter, 'maxfun': maxiter * 10,
                                'ftol': 1e-16, 'gtol': 1e-14})
        return res.x
    except Exception:
        return x0


def _polish(h, deadline, stages):
    best = h.copy()
    bestC = _C(h)
    for kind, param in stages:
        if time.process_time() >= deadline:
            break
        state = {'best': best.copy(), 'bestC': bestC}

        if kind == 'sm':
            def fun(x, _b=param):
                return _softmax_obj(x, _b)
        else:
            def fun(x, _t=param):
                return _active_set_obj(x, _t)

        def cb(xk):
            c = _C(xk)
            if c < state['bestC']:
                state['bestC'] = c
                state['best'] = xk.copy()

        xf = _run_lbfgs(fun, state['best'], deadline, 3000, cb)
        c = _C(xf)
        if c < state['bestC']:
            state['bestC'] = c
            state['best'] = xf.copy()
        best = state['best'].copy()
        bestC = state['bestC']
    return best, bestC


def _build_from_half(x, N, mode):
    if mode == 'centered':
        m = (N + 1) // 2
        h = np.zeros(N)
        h[:m] = x[:m]
        if N % 2 == 0:
            h[m:] = x[:m][::-1]
        else:
            h[m:] = x[:m - 1][::-1]
        return h
    else:
        return 0.5 * (x + x[::-1])


def _mirror_centered(h):
    return 0.5 * (h + h[::-1])


def _mirror_uncentered(h):
    nz = np.where(h > 0)[0]
    if nz.size == 0:
        return h.copy()
    a, b = nz[0], nz[-1]
    seg = h[a:b + 1]
    seg_sym = 0.5 * (seg + seg[::-1])
    out = np.zeros_like(h)
    out[a:b + 1] = seg_sym
    return out


def _sym_grad_chain(gfull, N, mode):
    if mode == 'centered':
        m = (N + 1) // 2
        g = gfull[:m].copy()
        if N % 2 == 0:
            g = g + gfull[m:][::-1]
        else:
            g[:m - 1] += gfull[m:][::-1]
        return g
    else:
        return 0.5 * (gfull + gfull[::-1])


def _sym_polish(h, deadline, mode):
    N = len(h)
    if mode == 'centered':
        m = (N + 1) // 2
        x0 = h[:m].copy()
    else:
        x0 = h.copy()
    best_x = x0.copy()
    bestC = _C(_build_from_half(best_x, N, mode))

    stages = [('as', 1e-6),
              ('sm', 12000.0),
              ('sm', 50000.0), ('sm', 200000.0)]
    for kind, param in stages:
        if time.process_time() >= deadline:
            break
        state = {'best': best_x.copy(), 'bestC': bestC}

        if kind == 'as':
            def fun(x, _t=param):
                hh = _build_from_half(x, N, mode)
                cv, gfull = _active_set_obj(hh, _t)
                return cv, _sym_grad_chain(gfull, N, mode)
        else:
            def fun(x, _b=param):
                hh = _build_from_half(x, N, mode)
                J, gfull = _softmax_obj(hh, _b)
                return J, _sym_grad_chain(gfull, N, mode)

        def cb(xk):
            c = _C(_build_from_half(xk, N, mode))
            if c < state['bestC']:
                state['bestC'] = c
                state['best'] = xk.copy()

        xf = _run_lbfgs(fun, state['best'], deadline, 2000, cb)
        c = _C(_build_from_half(xf, N, mode))
        if c < state['bestC']:
            state['bestC'] = c
            state['best'] = xf.copy()
        best_x = state['best'].copy()
        bestC = state['bestC']

    return _build_from_half(best_x, N, mode), bestC


def _half_vars(h, mode):
    N = len(h)
    if mode == 'centered':
        m = (N + 1) // 2
        return h[:m].copy()
    return h.copy()


def _newton_active(h, deadline, mode, tol_rel=1e-11, max_iter=200):
    N = len(h)
    if mode == 'centered':
        m = (N + 1) // 2
    else:
        m = N

    def build(x):
        return _build_from_half(x, N, mode)

    x = _half_vars(h, mode)
    hh = build(x)
    Cval = _C(hh)
    best_x = x.copy()
    best_C = Cval

    for it in range(max_iter):
        if time.process_time() >= deadline:
            break
        hh = build(x)
        S = hh.sum()
        if S <= 0:
            break
        conv = _conv(hh)
        M = float(conv.max())
        tol = tol_rel * M
        K = np.where(conv >= M - tol)[0]
        if K.size == 0:
            break
        ind = np.zeros(N)
        ind[K] = 1.0
        corr = np.convolve(ind, hh[::-1])
        gM = 2.0 * corr[N - 1: 2 * N - 1] / K.size
        gfull = (2.0 * N / (S * S)) * gM - (4.0 * N * M) / (S * S * S)
        g = _sym_grad_chain(gfull, N, mode)

        nz = x > 1e-14
        gscale = np.max(np.abs(g)) + 1e-30
        resid = np.where(nz, g, np.minimum(g, 0.0))
        if np.max(np.abs(resid)) / gscale < 1e-13:
            break

        if mode == 'centered':
            idxA = []
            wA = []
            for a in range(m):
                idxA.append(a); wA.append(1.0)
                if N % 2 == 0:
                    idxA.append(N - 1 - a); wA.append(1.0)
                elif a < m - 1:
                    idxA.append(N - 1 - a); wA.append(1.0)
        else:
            idxA = []
            wA = []
            for a in range(m):
                idxA.append(a); wA.append(0.5)
                b = N - 1 - a
                if b != a:
                    idxA.append(b); wA.append(0.5)
        idxA = np.array(idxA, dtype=np.int64)
        wA = np.array(wA, dtype=float)
        counts = np.array([1 + (1 if (N % 2 == 0 or (mode == 'centered' and a < m - 1)) else 0)
                           if mode == 'centered' else (1 if a == N - 1 - a else 2)
                           for a in range(m)])
        offs = np.zeros(m + 1, dtype=np.int64)
        offs[1:] = np.cumsum(counts)

        Kset = np.zeros(2 * N - 1, dtype=bool)
        Kset[K] = True

        coef_M = 2.0 * N / (S * S) * (2.0 / K.size)
        coef_g = -4.0 * N / (S * S * S)
        coef_S = 12.0 * N * M / (S * S * S * S)

        Hr = np.empty((m, m))
        gsum = g[:, None] + g[None, :]
        for a in range(m):
            ia = idxA[offs[a]:offs[a + 1]]
            wa = wA[offs[a]:offs[a + 1]]
            acc = np.zeros(m)
            for ii, wi in zip(ia, wa):
                jj = ii + idxA
                contrib = Kset[jj] * wA
                csum = np.zeros(m)
                for b in range(m):
                    csum[b] = contrib[offs[b]:offs[b + 1]].sum()
                acc += wi * csum
            Hr[a, :] = coef_M * acc + coef_g * gsum[a, :] + coef_S
        Hr = 0.5 * (Hr + Hr.T)

        fixed = (x <= 1e-14) & (g > 0)
        free = ~fixed
        dx = np.zeros(m)
        if np.any(free):
            Hf = Hr[np.ix_(free, free)]
            gf = g[free]
            tr = np.trace(Hf) / max(1, Hf.shape[0])
            reg = 1e-13 * max(abs(tr), 1e-30)
            try:
                df = np.linalg.solve(Hf + reg * np.eye(Hf.shape[0]), -gf)
            except np.linalg.LinAlgError:
                df = -gf / (np.abs(np.diag(Hf)) + 1e-12)
            dx[free] = df
        slope = float(np.dot(g, dx))
        if slope >= 0:
            dx = -g / (np.abs(np.diag(Hr)) + 1e-12)
            slope = float(np.dot(g, dx))
        if slope >= 0:
            break

        step = 1.0
        improved = False
        for _ in range(50):
            xn = np.maximum(x + step * dx, 0.0)
            cn = _C(build(xn))
            if cn < Cval - 1e-16:
                x = xn
                Cval = cn
                improved = True
                if cn < best_C:
                    best_C = cn
                    best_x = xn.copy()
                break
            step *= 0.5
        if not improved:
            break

    return build(best_x), best_C


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.92

    seed = None
    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size > 0 and s.size <= 30000 and np.all(np.isfinite(s)) and s.sum() > 0:
            seed = s.copy()
    if seed is None:
        N0 = 60
        x = np.linspace(-1, 1, N0)
        seed = np.maximum(0.0, 1.0 - np.abs(x)) + 0.05

    best = seed.copy()
    bestC = _C(best)
    print("start C=%.12f (N=%d)" % (bestC, len(best)))

    newton_end = t0 + budget_seconds * 0.55
    for mode in ('centered', 'uncentered'):
        if time.process_time() >= newton_end:
            break
        if mode == 'centered':
            hs = _mirror_centered(best)
        else:
            hs = _mirror_uncentered(best)
        hn, cn = _newton_active(hs, newton_end, mode, tol_rel=1e-13, max_iter=400)
        if cn < bestC - 1e-15:
            bestC = cn
            best = hn.copy()
            print("newton %s: C=%.12f" % (mode, cn))

    polish_end = t0 + budget_seconds * 0.70
    if time.process_time() < polish_end:
        hb, cb = _polish(best, polish_end,
                         [('as', 1e-9), ('sm', 1e6), ('as', 1e-10)])
        if cb < bestC:
            bestC = cb
            best = hb.copy()
    print("after polish: C=%.12f (N=%d)" % (bestC, len(best)))

    sym_end = t0 + budget_seconds * 0.85
    if time.process_time() < sym_end:
        for mode in ('centered', 'uncentered'):
            if time.process_time() >= sym_end:
                break
            if mode == 'centered':
                hs = _mirror_centered(best)
            else:
                hs = _mirror_uncentered(best)
            hopt, copt = _sym_polish(hs, sym_end, mode)
            if copt < bestC - 1e-15:
                bestC = copt
                best = hopt.copy()
                print("sym %s: C=%.12f" % (mode, copt))
    print("after symmetry: C=%.12f" % bestC)

    final_end = deadline
    if time.process_time() < final_end:
        for mode in ('centered', 'uncentered'):
            if time.process_time() >= final_end:
                break
            if mode == 'centered':
                hs = _mirror_centered(best)
            else:
                hs = _mirror_uncentered(best)
            hn, cn = _newton_active(hs, final_end, mode, tol_rel=1e-13, max_iter=400)
            if cn < bestC - 1e-15:
                bestC = cn
                best = hn.copy()
                print("final newton %s: C=%.12f" % (mode, cn))

    print("final C=%.12f (N=%d)" % (bestC, len(best)))
    return np.asarray(best, dtype=float)
