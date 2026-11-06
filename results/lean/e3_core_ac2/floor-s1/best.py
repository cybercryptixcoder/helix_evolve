import numpy as np
import time
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _parts(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0, 0.0, None
    Lc = fftconvolve(h, h)
    L = np.concatenate(([0.0], Lc, [0.0]))
    sq = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
    return sq, s, Lc


def _R(h):
    sq, s, Lc = _parts(h)
    if Lc is None:
        return 0.0
    mx = Lc.max()
    if mx <= 0 or s <= 0:
        return 0.0
    return sq / (s * s * mx)


def _grad_sq(h, L):
    c = np.zeros_like(L)
    c[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    c[1:] += (L[:-1] + 2.0 * L[1:]) / 3.0
    c = c[1:-1]
    return 2.0 * np.correlate(c, h, mode='valid')


def _obj_exact(x):
    h = np.maximum(x, 0.0)
    s = h.sum()
    if s <= 0:
        return 0.0, np.zeros_like(x)
    Lc = fftconvolve(h, h)
    L = np.concatenate(([0.0], Lc, [0.0]))
    sq = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
    grad_sq = _grad_sq(h, L)
    n = h.size
    l1 = s * s
    linf = Lc.max()
    ties = np.where(Lc >= linf - 1e-12 * max(1.0, linf))[0]
    grad_linf = np.zeros(n)
    for k in ties:
        lo = max(0, k - (n - 1))
        hi = min(n - 1, k)
        idx = np.arange(lo, hi + 1)
        grad_linf[idx] += 2.0 * h[k - idx]
    grad_linf /= len(ties)
    denom = l1 * linf
    g = (grad_sq * denom - sq * (2.0 * s * linf + l1 * grad_linf)) / (denom * denom)
    gx = -g
    gx[x <= 0] = 0.0
    return -sq / denom, gx


def _obj_smooth(x, p):
    h = np.maximum(x, 0.0)
    s = h.sum()
    if s <= 0:
        return 0.0, np.zeros_like(x)
    Lc = fftconvolve(h, h)
    L = np.concatenate(([0.0], Lc, [0.0]))
    sq = np.sum(L[:-1] * L[:-1] + L[:-1] * L[1:] + L[1:] * L[1:]) / 3.0
    grad_sq = _grad_sq(h, L)
    Lpos = np.maximum(Lc, 1e-300)
    logLp = np.log(Lpos)
    mx = logLp.max()
    w = np.exp(p * (logLp - mx))
    sw = w.sum()
    Lp = np.exp(mx + np.log(sw) / p)
    dLp_dLc = (w / sw) * (Lp / Lpos)
    grad_Lp = 2.0 * np.correlate(dLp_dLc, h, mode='valid')
    l1 = s * s
    denom = l1 * Lp
    g = (grad_sq * denom - sq * (2.0 * s * Lp + l1 * grad_Lp)) / (denom * denom)
    gx = -g
    gx[x <= 0] = 0.0
    return -sq / denom, gx


def _refine(h, until, obj, maxiter):
    h = np.maximum(np.asarray(h, dtype=float), 0.0)
    if h.sum() <= 0:
        h = np.ones(max(1, h.size))
    h = h / h.mean()
    state = {'h': h.copy(), 'r': _R(h)}

    def cb(xk):
        if time.process_time() > until:
            raise StopIteration
        r = _R(np.maximum(xk, 0.0))
        if r > state['r']:
            state['r'] = r
            state['h'] = np.maximum(xk, 0.0).copy()

    try:
        minimize(obj, h, jac=True, method='L-BFGS-B',
                 bounds=[(0.0, None)] * h.size,
                 options={'maxiter': maxiter, 'ftol': 1e-20, 'gtol': 1e-15},
                 callback=cb)
    except (StopIteration, Exception):
        pass
    return state['h'], state['r']


def _resample(h, n_new):
    n = h.size
    x = np.linspace(0.0, n, n_new + 1)
    xs = np.arange(n + 1)
    edges = np.interp(x, xs, np.concatenate(([0.0], np.cumsum(h))))
    out = np.diff(edges) * (n / n_new)
    return np.maximum(out, 0.0)


def _smooth(h, width):
    h = np.asarray(h, dtype=float)
    if width < 1:
        return h
    k = np.ones(width) / width
    pad = width // 2
    if pad > 0:
        hp = np.concatenate((h[:pad][::-1], h, h[-pad:][::-1]))
    else:
        hp = h
    sm = np.convolve(hp, k, mode='same')
    return sm[pad:pad + h.size]


def _downsample_pool(h, factor):
    n = h.size
    nb = n // factor
    if nb < 1:
        return h.copy()
    trimmed = h[:nb * factor].reshape(nb, factor)
    k = max(1, factor // 2)
    part = np.partition(trimmed, -k, axis=1)[:, -k:]
    return part.mean(axis=1)


def _trim_zeros(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0:
        return h
    thr = 1e-9 * max(h.max(), 1e-30)
    nz = np.where(h > thr)[0]
    if nz.size == 0:
        return h
    return h[nz[0]:nz[-1] + 1]


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90
    rng = np.random.default_rng(424242 + int(time.process_time() * 1000) % 1000)

    best = None
    best_r = -1.0
    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.ndim == 1 and s.size > 0 and np.all(np.isfinite(s)) and s.sum() > 0:
            best = np.maximum(s, 0.0)
            best_r = _R(best)
    if best is None:
        best = np.ones(50)
        best_r = _R(best)

    # Phase 1: exact polish of start
    if time.process_time() < deadline:
        seg = min(deadline, time.process_time() + budget_seconds * 0.15)
        h, r = _refine(best.copy(), seg, _obj_exact, 8000)
        if r > best_r:
            best, best_r = h, r

    # Phase 2: multiscale - upsample to finer grid and refine (often helps)
    for scale in [1.5, 2.0, 1.25, 3.0]:
        if time.process_time() >= deadline:
            break
        n_new = min(50000, max(20, int(best.size * scale)))
        if n_new <= best.size:
            continue
        cand = _resample(best, n_new)
        seg = min(deadline, time.process_time() + budget_seconds * 0.06)
        h, r = _refine(cand, seg, _obj_exact, 4000)
        if r > best_r:
            best, best_r = h, r

    # Phase 3: downsample search
    for factor in [2, 3, 4, 5]:
        if time.process_time() >= deadline:
            break
        cand = _downsample_pool(best, factor)
        if cand.size < 20:
            continue
        seg = min(deadline, time.process_time() + budget_seconds * 0.03)
        h, r = _refine(cand, seg, _obj_exact, 3000)
        if r > best_r:
            best, best_r = h, r

    # Phase 4: p-norm anneal to sharpen the plateau
    for p in [8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0, 1024.0, 2048.0, 4096.0]:
        if time.process_time() >= deadline:
            break
        seg = min(deadline, time.process_time() + budget_seconds * 0.015)
        h, r = _refine(best.copy(), seg, lambda x, pp=p: _obj_smooth(x, pp), 2500)
        if r > best_r:
            best, best_r = h, r

    # Phase 5: perturb + refine loop
    it = 0
    while time.process_time() < deadline:
        it += 1
        mode = it % 10
        if mode == 0:
            trial = best * (1.0 + 0.001 * rng.standard_normal(best.size))
        elif mode == 1:
            w = int(rng.integers(2, max(3, best.size // 10)))
            trial = _smooth(best, w)
        elif mode == 2:
            trial = best + 0.0006 * best.mean() * rng.standard_normal(best.size)
        elif mode == 3:
            n_new = max(10, int(best.size * (0.7 + 0.6 * rng.random())))
            small = _resample(best, n_new)
            small = _smooth(small, max(1, n_new // 14))
            trial = _resample(small, best.size)
        elif mode == 4:
            trial = best.copy()
            lo = int(rng.integers(0, best.size))
            length = int(rng.integers(2, max(3, best.size // 5)))
            hi = min(best.size, lo + length)
            trial[lo:hi] *= (1.0 + 0.004 * rng.standard_normal(hi - lo))
        elif mode == 5:
            trial = best + 0.0015 * best.std() * rng.standard_normal(best.size)
        elif mode == 6:
            f = int(rng.integers(2, 5))
            trial = _downsample_pool(best, f)
            trial = _resample(trial, best.size)
        elif mode == 7:
            n_new = max(4, int(best.size * 0.75))
            trial = _resample(_resample(best, n_new), best.size)
        elif mode == 8:
            trial = best.copy()
            c = int(rng.integers(0, best.size))
            w = int(rng.integers(2, max(3, best.size // 8)))
            lo = max(0, c - w); hi = min(best.size, c + w)
            trial[lo:hi] += 0.008 * best.mean() * rng.random(hi - lo)
        else:
            f = int(rng.integers(2, 4))
            cand = _downsample_pool(best, f)
            if cand.size < 20:
                continue
            trial = cand

        trial = np.maximum(trial, 0.0)
        if trial.sum() <= 0:
            continue
        seg = min(deadline, time.process_time() + 0.4)
        h, r = _refine(trial, seg, lambda x: _obj_smooth(x, 200.0), 500)
        if r > best_r:
            if time.process_time() < deadline:
                seg2 = min(deadline, time.process_time() + 0.3)
                h2, r2 = _refine(h.copy(), seg2, _obj_exact, 600)
                if r2 > r:
                    h, r = h2, r2
            if h.size > 100:
                for f in [2, 3]:
                    cand = _downsample_pool(h, f)
                    if cand.size < 20:
                        continue
                    rc = _R(cand)
                    if rc >= r - 5e-4:
                        seg3 = min(deadline, time.process_time() + 0.3)
                        h3, r3 = _refine(cand, seg3, _obj_exact, 500)
                        if r3 > r:
                            h, r = h3, r3
                        break
            best, best_r = h, r

    trimmed = _trim_zeros(best)
    if trimmed.size >= 4 and trimmed.size != best.size:
        rt = _R(trimmed)
        if rt >= best_r - 1e-12:
            best = trimmed
            best_r = rt
    if time.process_time() < deadline:
        h, r = _refine(best.copy(), deadline, _obj_exact, 8000)
        if r > best_r:
            best, best_r = h, r

    best = np.maximum(best, 0.0)
    if best.sum() <= 0:
        best = np.ones(50)
    return best
