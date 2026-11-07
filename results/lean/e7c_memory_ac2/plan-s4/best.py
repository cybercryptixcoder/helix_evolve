import numpy as np
import time
from scipy.signal import fftconvolve
from scipy.optimize import minimize


def _score(h):
    h = np.asarray(h, dtype=float)
    if h.ndim != 1 or h.size == 0:
        return -1.0
    s = h.sum()
    if s <= 0 or not np.all(np.isfinite(h)):
        return -1.0
    L = fftconvolve(h, h, mode='full')
    M = L.max()
    if M <= 0:
        return -1.0
    Le = np.empty(L.size + 2)
    Le[0] = 0.0
    Le[-1] = 0.0
    Le[1:-1] = L
    l2 = np.sum(Le[:-1] ** 2 + Le[:-1] * Le[1:] + Le[1:] ** 2) / 3.0
    l1 = s * s
    return l2 / (l1 * M)


def _score_and_grad(h):
    h = np.asarray(h, dtype=float)
    n = h.size
    L = fftconvolve(h, h, mode='full')
    M = L.max()
    s = h.sum()
    if M <= 0 or s <= 0:
        return -1.0, np.zeros(n)
    Le = np.empty(L.size + 2)
    Le[0] = 0.0
    Le[-1] = 0.0
    Le[1:-1] = L
    a = Le[:-1]
    b = Le[1:]
    l2 = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2 / (l1 * M)

    gLe = np.zeros(Le.size)
    gLe[:-1] += (2.0 * a + b) / 3.0
    gLe[1:] += (a + 2.0 * b) / 3.0
    gL = gLe[1:-1]

    c = fftconvolve(gL, h[::-1], mode='full')
    dl2_dh = 2.0 * c[n - 1:2 * n - 1]
    dl1_dh = 2.0 * s * np.ones(n)

    k = int(np.argmax(L))
    dM_dh = np.zeros(n)
    j_lo = max(0, k - n + 1)
    j_hi = min(n - 1, k)
    js = np.arange(j_lo, j_hi + 1)
    i_s = k - js
    valid = (i_s >= 0) & (i_s < n)
    np.add.at(dM_dh, i_s[valid], 2.0 * h[js[valid]])

    g = dl2_dh / (l1 * M) - l2 * dl1_dh / (l1 * l1 * M) - l2 * dM_dh / (l1 * M * M)
    return R, g


def _score_and_grad_soft(h, tau):
    h = np.asarray(h, dtype=float)
    n = h.size
    L = fftconvolve(h, h, mode='full')
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(n)
    Lmax = float(L.max())
    if Lmax <= 0:
        return -1.0, np.zeros(n)
    tau = max(float(tau), 1e-12)
    z = (L - Lmax) / tau
    ez = np.exp(z)
    Z = ez.sum()
    if Z <= 0 or not np.isfinite(Z):
        return _score_and_grad(h)
    M = tau * np.log(Z) + Lmax
    if M <= 0 or not np.isfinite(M):
        return _score_and_grad(h)
    w = ez / Z

    Le = np.empty(L.size + 2)
    Le[0] = 0.0
    Le[-1] = 0.0
    Le[1:-1] = L
    a = Le[:-1]
    b = Le[1:]
    l2 = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2 / (l1 * M)

    gLe = np.zeros(Le.size)
    gLe[:-1] += (2.0 * a + b) / 3.0
    gLe[1:] += (a + 2.0 * b) / 3.0
    gL = gLe[1:-1]

    c = fftconvolve(gL, h[::-1], mode='full')
    dl2_dh = 2.0 * c[n - 1:2 * n - 1]
    dl1_dh = 2.0 * s * np.ones(n)

    cw = fftconvolve(w, h[::-1], mode='full')
    dM_dh = 2.0 * cw[n - 1:2 * n - 1]

    g = dl2_dh / (l1 * M) - l2 * dl1_dh / (l1 * l1 * M) - l2 * dM_dh / (l1 * M * M)
    return R, g


def _score_and_grad_plateau(h, delta):
    h = np.asarray(h, dtype=float)
    n = h.size
    L = fftconvolve(h, h, mode='full')
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(n)
    M = float(L.max())
    if M <= 0:
        return -1.0, np.zeros(n)
    mask = L >= (1.0 - delta) * M
    cnt = int(mask.sum())
    if cnt < 2:
        return _score_and_grad(h)
    Ms = float(L[mask].mean())
    if Ms <= 0:
        return -1.0, np.zeros(n)

    Le = np.empty(L.size + 2)
    Le[0] = 0.0
    Le[-1] = 0.0
    Le[1:-1] = L
    a = Le[:-1]
    b = Le[1:]
    l2 = np.sum(a * a + a * b + b * b) / 3.0
    l1 = s * s
    R = l2 / (l1 * Ms)

    gLe = np.zeros(Le.size)
    gLe[:-1] += (2.0 * a + b) / 3.0
    gLe[1:] += (a + 2.0 * b) / 3.0
    gL = gLe[1:-1]

    c = fftconvolve(gL, h[::-1], mode='full')
    dl2_dh = 2.0 * c[n - 1:2 * n - 1]
    dl1_dh = 2.0 * s * np.ones(n)

    w = np.zeros(L.size)
    w[mask] = 1.0 / cnt
    cw = fftconvolve(w, h[::-1], mode='full')
    dMs_dh = 2.0 * cw[n - 1:2 * n - 1]

    g = dl2_dh / (l1 * Ms) - l2 * dl1_dh / (l1 * l1 * Ms) - l2 * dMs_dh / (l1 * Ms * Ms)
    return R, g


def _resample(h, N):
    h = np.asarray(h, dtype=float)
    n = h.size
    if n == N:
        return h.copy()
    x_old = np.linspace(0, 1, n, endpoint=False) + 0.5 / n
    x_new = np.linspace(0, 1, N, endpoint=False) + 0.5 / N
    return np.interp(x_new, x_old, h)


def _opt(h0, grad_fn, maxiter, deadline):
    h0 = np.maximum(np.asarray(h0, dtype=float), 1e-12)
    h0 = h0 / h0.sum()

    def obj(x):
        h = np.exp(x)
        h = h / h.sum()
        R, g = grad_fn(h)
        dot = np.dot(g, h)
        gx = h * (g - dot)
        return -R, -gx

    x0 = np.log(h0)
    try:
        res = minimize(obj, x0, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxiter * 3,
                                'ftol': 1e-16, 'gtol': 1e-13})
        h = np.exp(res.x)
        h = h / h.sum()
        return h
    except Exception:
        return h0


def _block_polish(h, best_sc, deadline, n_blocks=200, max_sweeps=8):
    h = np.asarray(h, dtype=float).copy()
    n = h.size
    edges = np.linspace(0, n, n_blocks + 1).astype(int)
    phi = (np.sqrt(5.0) - 1.0) / 2.0

    def eval_t(hh, a, b, t):
        trial = hh.copy()
        trial[a:b] *= t
        s = trial.sum()
        if s <= 0:
            return -1.0
        trial /= s
        return _score(trial)

    for sweep in range(max_sweeps):
        improved = False
        for bi in range(n_blocks):
            if time.process_time() >= deadline:
                return h, best_sc
            a, b = edges[bi], edges[bi + 1]
            if b <= a:
                continue
            lo_t, hi_t = 0.5, 2.0
            x1 = hi_t - phi * (hi_t - lo_t)
            x2 = lo_t + phi * (hi_t - lo_t)
            f1 = eval_t(h, a, b, x1)
            f2 = eval_t(h, a, b, x2)
            for _ in range(14):
                if time.process_time() >= deadline:
                    break
                if f1 < f2:
                    lo_t = x1
                    x1 = x2
                    f1 = f2
                    x2 = lo_t + phi * (hi_t - lo_t)
                    f2 = eval_t(h, a, b, x2)
                else:
                    hi_t = x1
                    x2 = x1
                    f2 = f1
                    x1 = hi_t - phi * (hi_t - lo_t)
                    f1 = eval_t(h, a, b, x1)
            t_best = 0.5 * (lo_t + hi_t)
            f_best = eval_t(h, a, b, t_best)
            if f_best > best_sc + 1e-13:
                h[a:b] *= t_best
                s = h.sum()
                if s > 0:
                    h /= s
                best_sc = f_best
                improved = True
        if not improved:
            break
    return h, best_sc


def _fine_polish(h, best_sc, deadline, rng):
    h = np.asarray(h, dtype=float).copy()
    n = h.size
    phi = (np.sqrt(5.0) - 1.0) / 2.0

    def eval_t(hh, a, b, t):
        trial = hh.copy()
        trial[a:b] *= t
        s = trial.sum()
        if s <= 0:
            return -1.0
        trial /= s
        return _score(trial)

    def sweep_blocks(blk, max_sweeps):
        nonlocal h, best_sc
        if blk <= 0:
            return
        stride = max(1, blk)
        starts = list(range(0, max(1, n - blk + 1), stride))
        if not starts or starts[-1] + blk < n:
            starts.append(max(0, n - blk))
        for _ in range(max_sweeps):
            improved = False
            order = rng.permutation(len(starts))
            for oi in order:
                if time.process_time() >= deadline:
                    return
                a = starts[oi]
                b = min(n, a + blk)
                if b <= a:
                    continue
                lo_t, hi_t = 0.5, 2.0
                x1 = hi_t - phi * (hi_t - lo_t)
                x2 = lo_t + phi * (hi_t - lo_t)
                f1 = eval_t(h, a, b, x1)
                f2 = eval_t(h, a, b, x2)
                for _ in range(10):
                    if time.process_time() >= deadline:
                        break
                    if f1 < f2:
                        lo_t = x1
                        x1 = x2
                        f1 = f2
                        x2 = lo_t + phi * (hi_t - lo_t)
                        f2 = eval_t(h, a, b, x2)
                    else:
                        hi_t = x1
                        x2 = x1
                        f2 = f1
                        x1 = hi_t - phi * (hi_t - lo_t)
                        f1 = eval_t(h, a, b, x1)
                t_best = 0.5 * (lo_t + hi_t)
                f_best = eval_t(h, a, b, t_best)
                if f_best > best_sc + 1e-14:
                    h[a:b] *= t_best
                    s = h.sum()
                    if s > 0:
                        h /= s
                    best_sc = f_best
                    improved = True
            if not improved:
                break

    sweep_blocks(1, 2)
    for blk in (2, 4, 8):
        if time.process_time() >= deadline:
            break
        sweep_blocks(blk, 2)
    return h, best_sc


def _pairwise_polish(h, best_sc, deadline, rng, n_pairs=4000, inner=10):
    h = np.asarray(h, dtype=float).copy()
    n = h.size
    if n < 2:
        return h, best_sc
    step = 0.02
    for _ in range(inner):
        if time.process_time() >= deadline:
            break
        improved = False
        idx = rng.integers(0, n - 1, size=n_pairs)
        for i in idx:
            if time.process_time() >= deadline:
                break
            a, b = int(i), int(i) + 1
            cur = h[a:b].copy()
            base = best_sc
            best_local = cur.copy()
            for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (-1, -1), (1, -1), (-1, 1)):
                trial = h.copy()
                trial[a] = cur[0] * np.exp(step * da)
                trial[b] = cur[1] * np.exp(step * db)
                s = trial.sum()
                if s <= 0:
                    continue
                trial /= s
                sc = _score(trial)
                if sc > base + 1e-15:
                    base = sc
                    best_local = trial[a:b].copy()
            if base > best_sc + 1e-15:
                h[a:b] = best_local
                s = h.sum()
                if s > 0:
                    h /= s
                best_sc = base
                improved = True
        if not improved:
            step *= 0.5
            if step < 1e-5:
                break
    return h, best_sc


def _smooth(h, w):
    """Local averaging with a small window to escape grid-scale noise."""
    if w <= 1:
        return h
    k = np.ones(w) / w
    hp = np.pad(h, w // 2, mode='edge')
    return np.convolve(hp, k, mode='valid')[:h.size]


def construct(budget_seconds, start):
    t0 = time.process_time()
    limit = t0 + budget_seconds * 0.90

    base_h = None
    base_sc = -1.0
    if start is not None:
        try:
            s = np.asarray(start, dtype=float).ravel()
            if s.size > 0 and s.size <= 50000 and np.all(np.isfinite(s)) and s.sum() > 0:
                base_h = np.maximum(s, 0.0)
                base_h = base_h / base_h.sum()
                base_sc = _score(base_h)
        except Exception:
            pass

    if base_h is None:
        for N in (50, 100, 200, 400, 800):
            x = np.linspace(-1, 1, N)
            c = (1.0 - np.abs(x)) + 1e-6
            c = c / c.sum()
            sc = _score(c)
            if sc > base_sc:
                base_sc = sc
                base_h = c

    best_h = base_h.copy()
    best_sc = base_sc
    print(f"start score {base_sc:.9f}, N={base_h.size}")

    if best_h.size != 50000:
        best_h = _resample(best_h, 50000)
        best_h = best_h / best_h.sum()
        sc = _score(best_h)
        if sc > best_sc:
            best_sc = sc
            print(f"  resampled to 50000: {sc:.9f}")

    # Phase 1: exact-gradient L-BFGS refinement.
    grad_deadline = t0 + budget_seconds * 0.90 * 0.20
    for it in range(4):
        if time.process_time() >= grad_deadline:
            break
        h = _opt(best_h, _score_and_grad, 400, grad_deadline)
        h = np.maximum(h, 0.0)
        ssum = h.sum()
        if ssum > 0:
            h = h / ssum
        sc = _score(h)
        if sc > best_sc:
            best_sc = sc
            best_h = h.copy()
        print(f"  grad {it}: {sc:.9f} (best {best_sc:.9f})")

    # Phase 2: plateau surrogate.
    now = time.process_time()
    plateau_deadline = now + max(0.0, limit - now) * 0.15
    deltas = (2e-4, 1e-4, 5e-5)
    for i, delta in enumerate(deltas):
        now = time.process_time()
        if now >= plateau_deadline:
            break
        n_left = len(deltas) - i
        share = (plateau_deadline - now) / max(1, n_left)
        h = _opt(best_h, lambda hh, d=delta: _score_and_grad_plateau(hh, d),
                 120, min(now + share, plateau_deadline))
        h = np.maximum(h, 0.0)
        ssum = h.sum()
        if ssum > 0:
            h = h / ssum
        sc = _score(h)
        if sc > best_sc:
            best_sc = sc
            best_h = h.copy()
        print(f"  plateau delta={delta:g}: {sc:.9f} (best {best_sc:.9f})")

    # Phase 3: exact gradient re-polish.
    polish_deadline = t0 + budget_seconds * 0.90 * 0.40
    for it in range(2):
        if time.process_time() >= polish_deadline:
            break
        h = _opt(best_h, _score_and_grad, 400, polish_deadline)
        h = np.maximum(h, 0.0)
        ssum = h.sum()
        if ssum > 0:
            h = h / ssum
        sc = _score(h)
        if sc > best_sc:
            best_sc = sc
            best_h = h.copy()
        print(f"  polish {it}: {sc:.9f} (best {best_sc:.9f})")

    # Phase 4: block-coordinate multiplicative polish.
    block_deadline = t0 + budget_seconds * 0.90 * 0.48
    if time.process_time() < block_deadline:
        try:
            h, sc = _block_polish(best_h, best_sc, block_deadline,
                                  n_blocks=250, max_sweeps=4)
            if sc > best_sc:
                best_sc = sc
                best_h = h.copy()
            print(f"  block polish: {sc:.9f} (best {best_sc:.9f})")
        except Exception:
            pass

    # Phase 5: pairwise coordinate descent.
    pair_deadline = t0 + budget_seconds * 0.90 * 0.58
    if time.process_time() < pair_deadline:
        try:
            rng = np.random.default_rng(987654321)
            h, sc = _pairwise_polish(best_h, best_sc, pair_deadline, rng,
                                     n_pairs=4000, inner=8)
            if sc > best_sc:
                best_sc = sc
                best_h = h.copy()
            print(f"  pairwise polish: {sc:.9f} (best {best_sc:.9f})")
        except Exception:
            pass

    # Phase 6: softmax (log-sum-exp) annealed surrogate.
    soft_start = time.process_time()
    soft_deadline = t0 + budget_seconds * 0.90 * 0.94
    if soft_start < soft_deadline:
        taus = (1e-2, 3e-3, 1e-3, 3e-4, 1e-4)
        for i, tfrac in enumerate(taus):
            now = time.process_time()
            if now >= soft_deadline:
                break
            n_left = len(taus) - i
            share = (soft_deadline - now) / max(1, n_left)
            Lmax = float(fftconvolve(best_h, best_h, mode='full').max())
            tau = tfrac * Lmax
            h = _opt(best_h, lambda hh, tt=tau: _score_and_grad_soft(hh, tt),
                     120, min(now + share, soft_deadline))
            h = np.maximum(h, 0.0)
            ssum = h.sum()
            if ssum > 0:
                h = h / ssum
            sc = _score(h)
            if sc > best_sc:
                best_sc = sc
                best_h = h.copy()
            print(f"  soft tau={tfrac:g}: {sc:.9f} (best {best_sc:.9f})")

    # Phase 7: short exact fine polish.
    fine_deadline = t0 + budget_seconds * 0.90 * 0.995
    if time.process_time() < fine_deadline:
        try:
            h = _opt(best_h, _score_and_grad, 200, fine_deadline)
            h = np.maximum(h, 0.0)
            ssum = h.sum()
            if ssum > 0:
                h = h / ssum
            sc = _score(h)
            if sc > best_sc:
                best_sc = sc
                best_h = h.copy()
            print(f"  exact fine: {sc:.9f} (best {best_sc:.9f})")
        except Exception:
            pass
        try:
            rng = np.random.default_rng(12345)
            h, sc = _fine_polish(best_h, best_sc, fine_deadline, rng)
            if sc > best_sc:
                best_sc = sc
                best_h = h.copy()
            print(f"  fine polish: {sc:.9f} (best {best_sc:.9f})")
        except Exception:
            pass

    # Phase 8: smoothing / re-optimisation escape attempt.
    # The optimum likely has a flat top in f*f; tiny grid-scale noise in h
    # is unhelpful, so we try light smoothing followed by re-optimisation.
    escape_deadline = t0 + budget_seconds * 0.90 * 0.9995
    for w in (3, 5):
        if time.process_time() >= escape_deadline:
            break
        try:
            hs = _smooth(best_h, w)
            hs = np.maximum(hs, 0.0)
            ssum = hs.sum()
            if ssum <= 0:
                continue
            hs = hs / ssum
            sc = _score(hs)
            if sc > best_sc + 1e-9:
                best_sc = sc
                best_h = hs.copy()
                print(f"  smooth w={w}: {sc:.9f} (best {best_sc:.9f})")
        except Exception:
            pass

    print(f"final score {best_sc:.9f}, N={best_h.size}")
    return np.maximum(np.asarray(best_h, dtype=float), 0.0)
