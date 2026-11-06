import numpy as np
import time
from scipy.optimize import minimize


def _C(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    n = h.size
    return 2.0 * n * np.max(np.convolve(h, h)) / (s * s)


def _fft_conv(h):
    n = h.size
    L = 2 * n - 1
    m = 1
    while m < L:
        m <<= 1
    F = np.fft.rfft(h, m)
    return np.fft.irfft(F * F, m)[:L]


def _Cfft(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    n = h.size
    return 2.0 * n * np.max(_fft_conv(h)) / (s * s)


def _conv(h):
    if h.size > 2000:
        return _fft_conv(h)
    return np.convolve(h, h)


def _area_resample(s, N):
    s = np.asarray(s, dtype=float)
    if s.size == N:
        return s.copy()
    if s.sum() <= 0:
        return np.ones(N)
    x_old = np.linspace(0.0, 1.0, s.size + 1)
    cum = np.concatenate(([0.0], np.cumsum(s)))
    total = cum[-1]
    x_new = np.linspace(0.0, 1.0, N + 1)
    target = x_new * total
    edges = np.interp(target, cum, x_old)
    mass_new = np.diff(np.interp(edges, x_old, cum))
    w = 1.0 / N
    return np.maximum(mass_new / w, 0.0)


def _sweep_incremental(h, deadline, rng, step0=0.05, min_step=1e-4, max_sweeps=25):
    n = h.size
    h = h.copy()
    conv = np.convolve(h, h)
    s = h.sum()
    if s <= 0:
        return h, np.inf
    C = 2.0 * n * conv.max() / (s * s)
    step = step0
    sweeps = 0
    while step > min_step and sweeps < max_sweeps:
        if time.process_time() > deadline:
            break
        sweeps += 1
        improved = False
        idxs = rng.permutation(n)
        for i in idxs:
            if time.process_time() > deadline:
                break
            old = h[i]
            if old <= 0:
                continue
            best_v = old
            best_C = C
            best_conv = None
            best_s = s
            for mult in (1.0 + step, 1.0 - step):
                nv = old * mult
                if nv < 0:
                    nv = 0.0
                if nv == old:
                    continue
                delta = nv - old
                seg = conv[i:i + n] + delta * h
                ns = s + delta
                if ns <= 0:
                    continue
                m1 = seg.max()
                m0 = conv[:i].max() if i > 0 else -np.inf
                m2 = conv[i + n:].max() if i + n < conv.size else -np.inf
                newmax = max(m0, m1, m2)
                nC = 2.0 * n * newmax / (ns * ns)
                if nC < best_C - 1e-13:
                    best_C = nC
                    best_v = nv
                    best_conv = seg
                    best_s = ns
            if best_v != old:
                h[i] = best_v
                conv[i:i + n] = best_conv
                s = best_s
                C = best_C
                improved = True
        if not improved:
            step *= 0.5
    return h, C


def _active_set_step(h, deadline, max_steps=400, thresh=0.9999, reg=1e-12):
    h = h.copy()
    n = h.size
    c = _Cfft(h)
    for step_idx in range(max_steps):
        if time.process_time() > deadline:
            break
        conv = _conv(h)
        M = conv.max()
        thr = min(0.9999, thresh + 1e-5 * step_idx)
        A = np.where(conv > thr * M)[0]
        if A.size < 2:
            break
        k = A.size
        J = np.zeros((k + 1, n))
        for r, kk in enumerate(A):
            lo = max(0, kk - n + 1)
            hi = min(n - 1, kk)
            idx = np.arange(lo, hi + 1)
            J[r, idx] = 2.0 * h[kk - idx]
        J[k, :] = 1.0
        target = np.empty(k + 1)
        target[:k] = conv[A].mean() - conv[A]
        target[k] = 0.0
        JJt = J @ J.T
        JJt[np.diag_indices_from(JJt)] += reg
        try:
            y = np.linalg.solve(JJt, target)
        except np.linalg.LinAlgError:
            break
        d = J.T @ y
        improved = False
        for alpha in (2.0, 1.5, 1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125,
                      0.015625, 0.0078125, 0.00390625, 0.001953125,
                      0.0009765625, 0.00048828125, 0.000244140625):
            hn = h + alpha * d
            if np.all(hn >= 0):
                cn = _Cfft(hn)
                if cn < c - 1e-14:
                    h = hn
                    c = cn
                    improved = True
                    break
        if not improved:
            if thr >= 0.9999:
                break
    return h, c


def _minimax_polish(h, deadline, iters=300, beta_schedule=None):
    h = h.copy()
    n = h.size
    s0 = h.sum()
    if s0 <= 0:
        return h, np.inf
    h = h / s0
    best_h = h.copy()
    best_C = _C(h)

    def softmax_obj(x, beta):
        n = x.size
        L = 2 * n - 1
        m = 1
        while m < L:
            m <<= 1
        F = np.fft.rfft(x, m)
        conv = np.fft.irfft(F * F, m)[:L]
        s = x.sum()
        if s <= 0:
            return np.inf, np.zeros(n)
        cmax = conv.max()
        e = np.exp(beta * (conv - cmax))
        Z = e.sum()
        lse = cmax + np.log(Z) / beta
        Fval = 2.0 * n * lse / (s * s)
        p = e / Z
        corr = np.convolve(p, x[::-1])[n - 1:2 * n - 1]
        grad_lse = 2.0 * corr
        grad = 2.0 * n / (s * s) * grad_lse - 2.0 * Fval / s
        return Fval, grad

    conv0 = _fft_conv(h)
    sd = conv0.std()
    if sd <= 0:
        sd = 1.0
    if beta_schedule is None:
        beta_schedule = [4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0]
    for tb in beta_schedule:
        if time.process_time() > deadline:
            break
        beta = tb / sd
        try:
            res = minimize(lambda x: softmax_obj(x, beta), h, jac=True,
                           method='L-BFGS-B', bounds=[(0, None)] * n,
                           options={'maxiter': iters, 'ftol': 1e-15,
                                    'gtol': 1e-13})
            h = np.maximum(res.x, 0.0)
            s = h.sum()
            if s > 0:
                h = h / s
        except Exception:
            pass
        c = _Cfft(h)
        if c < best_C:
            best_C = c
            best_h = h.copy()
    return best_h, best_C


def _refine(h, deadline, rng, t0, iters=250, tag=""):
    beta_sched = [4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0, 1024.0, 2048.0]
    if time.process_time() < deadline - 0.5:
        h, _ = _minimax_polish(h, deadline, iters=iters, beta_schedule=beta_sched)
        h = np.maximum(h, 0.0)
        if h.sum() > 0:
            h /= h.sum()
    for _r in range(20):
        if time.process_time() > deadline - 0.3:
            break
        h, _ = _active_set_step(h, deadline)
        h = np.maximum(h, 0.0)
        if h.sum() > 0:
            h /= h.sum()
    if time.process_time() < deadline - 0.3:
        h, _ = _sweep_incremental(h, deadline, rng, step0=0.02,
                                   min_step=3e-5, max_sweeps=8)
        h = np.maximum(h, 0.0)
        if h.sum() > 0:
            h /= h.sum()
    return h


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.82
    rng = np.random.default_rng(88172645463325252)

    if start is not None:
        s = np.asarray(start, dtype=float)
        base = np.maximum(s, 0.0) if (s.size > 0 and s.sum() > 0) else \
            np.exp(-3.0 * np.linspace(-1, 1, 512) ** 2)
    else:
        base = np.exp(-3.0 * np.linspace(-1, 1, 512) ** 2)
    base = base / base.sum()
    best = base.copy()
    bestC = _C(best)
    print("start C = %.6f, N = %d" % (bestC, best.size))

    Ns = [best.size, 1600, 2400, 3000]
    Ns = [N for N in Ns if 64 <= N <= 30000]
    seen = set()
    for N in Ns:
        if N in seen:
            continue
        seen.add(N)
        if time.process_time() > deadline - 1.0:
            break
        h = _area_resample(best, N)
        h = np.maximum(h, 0.0)
        if h.sum() <= 0:
            h = np.ones(N)
        h = h / h.sum()
        c_in = _C(h)
        h = _refine(h, deadline, rng, t0, iters=250, tag="N=%d" % N)
        c_out = _C(h)
        print("N=%d: %.6f -> %.6f cpu=%.1f" % (N, c_in, c_out,
                                               time.process_time() - t0))
        if c_out < bestC - 1e-12:
            bestC, best = c_out, h.copy()

    if time.process_time() < deadline - 0.5:
        h = _refine(best.copy(), deadline, rng, t0, iters=400, tag="final")
        c = _C(h)
        print("final polish C=%.6f cpu=%.1f" % (c, time.process_time() - t0))
        if c < bestC - 1e-12:
            bestC, best = c, h.copy()

    print("final C = %.6f, N = %d, cpu %.2f s"
          % (bestC, best.size, time.process_time() - t0))
    return np.maximum(best, 0.0)
