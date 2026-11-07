import numpy as np
import time
from scipy.signal import fftconvolve
from scipy.optimize import minimize


def _R_and_grad(h, p=-1.0):
    conv = fftconvolve(h, h, mode='full')
    L = np.empty(conv.size + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = conv
    A = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    B = np.sum(h)**2
    C = conv.max()
    R = A / (B * C)

    dA_dL = (np.concatenate(([0.0], L[:-2])) + 4.0*L[:-1] + L[1:]) / 3.0
    dA_dL_int = dA_dL[1:conv.size+1]
    dA_dh = 2.0 * fftconvolve(dA_dL_int, h[::-1], mode='valid')
    sumh = np.sqrt(B)
    dB_dh = 2.0 * sumh * np.ones(h.size)

    if p <= 0.0:
        thresh = (1.0 - 1e-6) * C
        idx = np.flatnonzero(conv >= thresh)
        if idx.size == 0:
            idx = np.array([int(np.argmax(conv))])
        e = np.zeros(conv.size)
        e[idx] = 1.0 / idx.size
        dC_dh = 2.0 * fftconvolve(e, h[::-1], mode='valid')
        Cp = C
    else:
        Lp = np.maximum(conv, 1e-300)
        Cp = np.sum(Lp**p) ** (1.0/p)
        dCp_dL = Lp**(p-1.0) / (Cp**(p-1.0))
        dC_dh = 2.0 * fftconvolve(dCp_dL, h[::-1], mode='valid')
    dR_dh = (dA_dh * B * Cp - A * (dB_dh * Cp + B * dC_dh)) / (B * Cp)**2
    return R, dR_dh


def _exact_R(h):
    conv = np.convolve(h, h)
    L = np.empty(conv.size + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = conv
    A = np.sum(L[:-1]**2 + L[:-1]*L[1:] + L[1:]**2) / 3.0
    B = np.sum(h)**2
    return A / (B * L.max())


def _lbfgs_phase(h, best_h, best_R, deadline, p, maxiter,
                 ftol=0.0, gtol=0.0):
    state = {'best_h': best_h.copy(), 'best_R': best_R}

    def fun(u):
        hh = np.exp(u - u.max())
        s = hh.sum()
        if s > 0:
            hh = hh / s
        R, dR = _R_and_grad(hh, p)
        if R > state['best_R']:
            state['best_R'] = R
            state['best_h'] = hh.copy()
        return -R, -hh * dR

    def cb(xk):
        return time.process_time() > deadline

    u0 = np.log(np.maximum(h, 1e-12))
    try:
        minimize(fun, u0, jac=True, method='L-BFGS-B', callback=cb,
                 options={'maxiter': maxiter, 'maxls': 40,
                          'ftol': ftol, 'gtol': gtol})
    except Exception as e:
        print("L-BFGS-B exception:", e)
    return state['best_h'], state['best_R']


def _resample(h0, N):
    h0 = np.maximum(np.asarray(h0, dtype=float).ravel(), 0.0)
    if h0.size == N:
        return h0.copy()
    return np.interp(np.linspace(0, 1, N), np.linspace(0, 1, h0.size), h0)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90
    N = 16000

    if start is not None:
        h = _resample(start, N)
        if h.max() <= 0:
            h = np.minimum(np.arange(N) + 1.0, np.arange(N, 0, -1))
    else:
        h = np.minimum(np.arange(N) + 1.0, np.arange(N, 0, -1))
    h = h / h.max()
    best_h = h.copy()
    best_R = _exact_R(h)
    print("start R = %.9f" % best_R)

    # Continuation on smooth-max p, then sharp exploitation cycles.
    for p in [1000.0, 300.0, 100.0, 30.0, 10.0, 3.0, 1.0, -1.0]:
        if time.process_time() >= deadline:
            break
        nh, nR = _lbfgs_phase(best_h, best_h, best_R, deadline, p, 2000)
        r = _exact_R(nh)
        if r > nR:
            nR = r
        if nR > best_R:
            best_R = nR
            best_h = nh.copy()
        print("cont p=%.1f best=%.9f" % (p, best_R))

    cycle = [-1.0, 2.0, -1.0, 0.5]
    it = 0
    while time.process_time() < deadline:
        p = cycle[it % len(cycle)]
        it += 1
        nh, nR = _lbfgs_phase(best_h, best_h, best_R, deadline, p, 3000)
        r = _exact_R(nh)
        if r > nR:
            nR = r
        if nR > best_R:
            best_R = nR
            best_h = nh.copy()
        print("cycle %d p=%.1f best=%.9f" % (it, p, best_R))

    r = _exact_R(best_h)
    if r > best_R:
        best_R = r
    print("final R = %.9f" % best_R)
    return best_h
