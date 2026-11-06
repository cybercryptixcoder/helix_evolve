import numpy as np
import time
from scipy.signal import fftconvolve


def _conv(h):
    return fftconvolve(h, h)


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * float(np.max(_conv(h))) / (s * s)


def _resample(h, N):
    n = len(h)
    if n == N:
        return h.copy()
    cum = np.concatenate([[0.0], np.cumsum(h)])
    edges = np.linspace(0, n, N + 1)
    i = np.clip(np.floor(edges).astype(int), 0, n - 1)
    integ = cum[i] + h[i] * (edges - i)
    out = (integ[1:] - integ[:-1]) / (edges[1:] - edges[:-1])
    return np.maximum(out, 0.0)


def _near_set(conv, mx, tol_rel, topk):
    tol = mx * tol_rel
    near = np.where(conv > mx - tol)[0]
    if len(near) == 0:
        return np.array([int(np.argmax(conv))])
    if len(near) > topk:
        near = near[np.argsort(-conv[near])[:topk]]
    return near


def _C_and_grad(h, tol_rel, topk):
    """Return C and dC/dh (analytic, averaged over near-max knots)."""
    N = len(h)
    s = h.sum()
    conv = _conv(h)
    mx = float(conv.max())
    C = 2.0 * N * mx / (s * s)
    near = _near_set(conv, mx, tol_rel, topk)
    g = np.zeros(N)
    msum = 0.0
    for k in near:
        lo = max(0, k - (N - 1))
        hi = min(N - 1, k)
        idx = np.arange(lo, hi + 1)
        g[idx] += 2.0 * h[k - idx]
        msum += conv[k]
    nl = len(near)
    g /= nl
    mavg = msum / nl
    dC = (2.0 * N / (s * s)) * g - (4.0 * N * mavg / (s * s * s))
    return C, dC, conv, mx, near


def _adam(h0, end_time, rng, lr0=0.01, tol_rel=1e-3, topk=60,
          kick_amp=0.003, stall_max=300):
    h = np.maximum(np.asarray(h0, dtype=float).copy(), 1e-12)
    N = len(h)
    h *= N / h.sum()
    best_h = h.copy()
    best_C = _C(h)
    m = np.zeros(N)
    v = np.zeros(N)
    b1, b2, eps = 0.9, 0.999, 1e-12
    lr = lr0
    t = 0
    stall = 0
    while time.process_time() < end_time:
        t += 1
        C, dC, conv, mx, near = _C_and_grad(h, tol_rel, topk)
        gm = dC * np.maximum(h, 1e-9)
        gn = np.linalg.norm(gm)
        if gn < 1e-18:
            break
        gm /= gn
        m = b1 * m + (1 - b1) * gm
        v = b2 * v + (1 - b2) * gm * gm
        mhat = m / (1 - b1 ** t)
        vhat = v / (1 - b2 ** t)
        h_new = h - lr * mhat / (np.sqrt(vhat) + eps) * np.maximum(h, 1e-9)
        h_new = np.maximum(h_new, 0.0)
        s2 = h_new.sum()
        if s2 <= 0:
            h_new = best_h.copy()
            lr *= 0.5
            continue
        h_new *= N / s2
        h = h_new
        if C < best_C - 1e-16:
            best_C = C
            best_h = h.copy()
            stall = 0
        else:
            stall += 1
        if stall > stall_max:
            kick = best_h * (1 + kick_amp * rng.standard_normal(N))
            kick = np.maximum(kick, 0.0)
            if kick.sum() > 0:
                h = kick * (N / kick.sum())
            else:
                h = best_h.copy()
            lr *= 0.85
            m[:] = 0
            v[:] = 0
            t = 1
            stall = 0
    c = _C(h)
    if c < best_C:
        best_h = h.copy()
        best_C = c
    return best_h, best_C


def _pair_coord(h, end_time, rng, step0=0.01, floor=2e-4):
    h = np.maximum(h.copy(), 0.0)
    C = _C(h)
    n = len(h)
    step = step0

    def mks(step):
        return [(1 - step, 1 + step), (1 + step, 1 - step),
                (1 - step * 0.5, 1 + step * 0.5), (1 + step * 0.5, 1 - step * 0.5),
                (1 - step * 0.25, 1 + step * 0.25), (1 + step * 0.25, 1 - step * 0.25)]

    mults = mks(step)
    while time.process_time() < end_time:
        improved = False
        idxs = np.arange(n - 1)
        rng.shuffle(idxs)
        for i in idxs:
            if time.process_time() >= end_time:
                return h, C
            o1, o2 = h[i], h[i + 1]
            bC = C
            bm1, bm2 = 1.0, 1.0
            for m1, m2 in mults:
                h[i] = o1 * m1
                h[i + 1] = o2 * m2
                c = _C(h)
                if c < bC - 1e-17:
                    bC = c
                    bm1, bm2 = m1, m2
            h[i] = o1 * bm1
            h[i + 1] = o2 * bm2
            if bm1 != 1.0 or bm2 != 1.0:
                C = bC
                improved = True
        if not improved:
            if step < floor:
                break
            step *= 0.5
            mults = mks(step)
    return h, C


def _grad_descent_projected(h, end_time, rng, tol_rel=3e-4, lr=0.05,
                            topk=80):
    """Plain projected gradient on C using analytic gradient, with momentum."""
    h = np.maximum(h.copy(), 0.0)
    N = len(h)
    h *= N / max(h.sum(), 1e-12)
    best_h = h.copy()
    best_C = _C(h)
    mom = np.zeros(N)
    while time.process_time() < end_time:
        C, dC, _, _, _ = _C_and_grad(h, tol_rel, topk)
        gm = dC * np.maximum(h, 1e-9)
        gn = np.linalg.norm(gm)
        if gn < 1e-18:
            break
        gm /= gn
        mom = 0.8 * mom + gm
        h = h - lr * mom * np.maximum(h, 1e-9)
        h = np.maximum(h, 0.0)
        s = h.sum()
        if s <= 0:
            h = best_h.copy()
            break
        h *= N / s
        c = _C(h)
        if c < best_C - 1e-16:
            best_C = c
            best_h = h.copy()
    return best_h, best_C


def _gauss_newton_ls(h, end_time, rng, tol_rel=3e-4, topk=80, iters_cap=200):
    """Locally minimize max of near-tied knots via iterative least-squares-like
    step: solve for direction reducing the average near-max convolved value,
    subject to preserving sum. Uses small trust region."""
    h = np.maximum(h.copy(), 0.0)
    N = len(h)
    h *= N / max(h.sum(), 1e-12)
    best_h = h.copy()
    best_C = _C(h)
    step = 0.02
    t = 0
    while time.process_time() < end_time and t < iters_cap:
        t += 1
        s = h.sum()
        conv = _conv(h)
        mx = float(conv.max())
        C = 2.0 * N * mx / (s * s)
        near = _near_set(conv, mx, tol_rel, topk)
        # Build target: reduce conv at near knots uniformly.
        # Direction: negative gradient of sum of conv at near knots, projected
        # to preserve sum, then take a step with backtracking.
        g = np.zeros(N)
        for k in near:
            lo = max(0, k - (N - 1))
            hi = min(N - 1, k)
            idx = np.arange(lo, hi + 1)
            g[idx] += 2.0 * h[k - idx]
        g /= len(near)
        # project onto sum-preserving subspace
        g -= g.mean()
        gn = np.linalg.norm(g)
        if gn < 1e-18:
            break
        d = -g / gn
        # backtracking line search on C
        improved = False
        st = step
        for _ in range(6):
            cand = h + st * d * np.maximum(h, 1e-9)
            cand = np.maximum(cand, 0.0)
            sc = cand.sum()
            if sc <= 0:
                st *= 0.5
                continue
            cand *= N / sc
            cc = _C(cand)
            if cc < C - 1e-17:
                h = cand
                if cc < best_C - 1e-16:
                    best_C = cc
                    best_h = cand.copy()
                improved = True
                step = min(step * 1.3, 0.1)
                break
            st *= 0.5
        if not improved:
            step *= 0.6
            if step < 1e-6:
                break
    return best_h, best_C


def _triple_coord(h, end_time, rng, step0=0.004, floor=1e-4):
    h = np.maximum(h.copy(), 0.0)
    C = _C(h)
    n = len(h)
    step = step0
    while time.process_time() < end_time:
        improved = False
        idxs = np.arange(n - 2)
        rng.shuffle(idxs)
        for i in idxs:
            if time.process_time() >= end_time:
                return h, C
            a, b, c0 = h[i], h[i + 1], h[i + 2]
            tot = a + b + c0
            if tot <= 0:
                continue
            bC = C
            bd = 0.0
            for d in (step, step * 0.5, step * 0.25,
                      -step * 0.25, -step * 0.5, -step):
                nb = b + d * tot
                rem = tot - nb
                if rem < 0 or nb < 0:
                    continue
                sa = a + c0
                if sa <= 0:
                    continue
                h[i] = rem * (a / sa)
                h[i + 1] = nb
                h[i + 2] = rem * (c0 / sa)
                cv = _C(h)
                if cv < bC - 1e-17:
                    bC = cv
                    bd = d
            if bd != 0.0:
                nb = b + bd * tot
                rem = tot - nb
                sa = a + c0
                h[i] = rem * (a / sa)
                h[i + 1] = nb
                h[i + 2] = rem * (c0 / sa)
                C = bC
                improved = True
            else:
                h[i] = a
                h[i + 1] = b
                h[i + 2] = c0
        if not improved:
            if step < floor:
                break
            step *= 0.5
    return h, C


def _block_smooth(h, end_time, rng, block=8, step0=0.003, floor=5e-5):
    h = np.maximum(h.copy(), 0.0)
    C = _C(h)
    n = len(h)
    step = step0
    while time.process_time() < end_time:
        improved = False
        starts = np.arange(0, n - block + 1)
        rng.shuffle(starts)
        for s0 in starts:
            if time.process_time() >= end_time:
                return h, C
            seg = h[s0:s0 + block]
            tot = seg.sum()
            if tot <= 0:
                continue
            bC = C
            bd = 0.0
            k = np.arange(block)
            bump = np.cos(np.pi * (k + 0.5) / block - np.pi / 2)
            bump -= bump.mean()
            for d in (step, step * 0.5, -step * 0.5, -step):
                cand = seg + d * tot * bump
                if cand.min() < 0:
                    continue
                h[s0:s0 + block] = cand
                cv = _C(h)
                if cv < bC - 1e-17:
                    bC = cv
                    bd = d
            if bd != 0.0:
                h[s0:s0 + block] = seg + bd * tot * bump
                C = bC
                improved = True
            else:
                h[s0:s0 + block] = seg
        if not improved:
            if step < floor:
                break
            step *= 0.5
    return h, C


def _window_coord(h, end_time, rng, win=5, step0=0.002, floor=4e-5):
    h = np.maximum(h.copy(), 0.0)
    C = _C(h)
    n = len(h)
    step = step0
    k = np.arange(win)
    ramp = (k - (win - 1) / 2.0)
    ramp -= ramp.mean()
    rn = np.linalg.norm(ramp)
    if rn > 0:
        ramp /= rn
    while time.process_time() < end_time:
        improved = False
        starts = np.arange(0, n - win + 1)
        rng.shuffle(starts)
        for s0 in starts:
            if time.process_time() >= end_time:
                return h, C
            seg = h[s0:s0 + win]
            tot = seg.sum()
            if tot <= 0:
                continue
            bC = C
            bd = 0.0
            for d in (step, step * 0.5, -step * 0.5, -step):
                cand = seg + d * tot * ramp
                if cand.min() < 0:
                    continue
                h[s0:s0 + win] = cand
                cv = _C(h)
                if cv < bC - 1e-17:
                    bC = cv
                    bd = d
            if bd != 0.0:
                h[s0:s0 + win] = seg + bd * tot * ramp
                C = bC
                improved = True
            else:
                h[s0:s0 + win] = seg
        if not improved:
            if step < floor:
                break
            step *= 0.5
    return h, C


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.6
    rng = np.random.default_rng(20240113)

    def remaining():
        return deadline - time.process_time()

    pool = []
    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size > 0 and s.sum() > 0:
            pool.append(np.maximum(s.copy(), 0.0))
    for N in [200, 400]:
        x = (np.arange(N) + 0.5) / N * 2 - 1
        pool.append(np.maximum(1 - x * x, 0.0) + 1e-6)

    scored = [(_C(c), c) for c in pool if c.sum() > 0]
    scored.sort(key=lambda t: t[0])
    best_C, best_h = scored[0]

    # Quick initial polish of the start with projected gradient
    if remaining() > 0.5:
        end = time.process_time() + min(remaining() * 0.06, 1.2)
        rh, rc = _grad_descent_projected(best_h, end, rng, tol_rel=3e-4,
                                         lr=0.03, topk=80)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.5:
        end = time.process_time() + remaining() * 0.05
        rh, rc = _adam(best_h, end, rng, lr0=0.008, tol_rel=3e-4)
        if rc < best_C:
            best_C, best_h = rc, rh

    for N_target in [1600, 2400, 3200, 4000]:
        if remaining() < 0.4:
            break
        hu = _resample(best_h, N_target)
        if hu.sum() <= 0:
            continue
        end = min(deadline - 0.3, time.process_time() + 0.4)
        rh, rc = _adam(hu, end, rng, lr0=0.01, tol_rel=5e-4)
        if rc < best_C - 1e-13:
            best_C, best_h = rc, rh

    for N_target in [5000, 6000]:
        if remaining() < 1.5:
            break
        hu = _resample(best_h, N_target)
        if hu.sum() <= 0:
            continue
        end = min(deadline - 0.8, time.process_time() + 0.5)
        rh, rc = _adam(hu, end, rng, lr0=0.008, tol_rel=3e-4)
        if rc < best_C - 1e-13:
            best_C, best_h = rc, rh

    if remaining() > 0.5:
        end = time.process_time() + remaining() * 0.08
        rh, rc = _gauss_newton_ls(best_h, end, rng, tol_rel=3e-4, topk=80,
                                  iters_cap=300)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = time.process_time() + remaining() * 0.07
        rh, rc = _adam(best_h, end, rng, lr0=0.002, tol_rel=2e-4, topk=80,
                       kick_amp=0.0015, stall_max=400)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = min(deadline - 0.4, time.process_time() + remaining() * 0.12)
        rh, rc = _triple_coord(best_h, end, rng, step0=0.004, floor=1e-4)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = min(deadline - 0.3, time.process_time() + remaining() * 0.14)
        rh, rc = _block_smooth(best_h, end, rng, block=8, step0=0.003,
                               floor=5e-5)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = min(deadline - 0.25, time.process_time() + remaining() * 0.14)
        rh, rc = _window_coord(best_h, end, rng, win=5, step0=0.002,
                               floor=4e-5)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = min(deadline - 0.2, time.process_time() + remaining() * 0.14)
        rh, rc = _pair_coord(best_h, end, rng, step0=0.004, floor=1e-4)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = min(deadline - 0.2, time.process_time() + remaining() * 0.12)
        rh, rc = _gauss_newton_ls(best_h, end, rng, tol_rel=2e-4, topk=120,
                                  iters_cap=200)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = min(deadline - 0.15, time.process_time() + remaining() * 0.12)
        rh, rc = _block_smooth(best_h, end, rng, block=12, step0=0.0015,
                               floor=2e-5)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.3:
        end = min(deadline - 0.12, time.process_time() + remaining() * 0.12)
        rh, rc = _window_coord(best_h, end, rng, win=9, step0=0.001,
                               floor=2e-5)
        if rc < best_C:
            best_C, best_h = rc, rh

    if remaining() > 0.15:
        end = deadline - 0.03
        rh, rc = _adam(best_h, end, rng, lr0=0.0005, tol_rel=1.5e-4,
                       topk=120, kick_amp=0.0006, stall_max=800)
        if rc < best_C:
            best_C, best_h = rc, rh

    best_h = np.maximum(best_h, 0.0)
    if best_h.sum() <= 0:
        best_h = np.ones(50)
    if best_h.size > 30000:
        best_h = best_h[:30000]
    return best_h
