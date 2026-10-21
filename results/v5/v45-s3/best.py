import time
import numpy as np


def _score(h):
    s = h.sum()
    if s <= 0:
        return -1.0
    L = np.convolve(h, h)
    Lp = np.concatenate(([0.0], L, [0.0]))
    A = Lp @ Lp
    B = Lp[:-1] @ Lp[1:]
    m = L.max()
    if m <= 0:
        return -1.0
    return (2.0 * A + B) / 3.0 / (s * s * m)


def _score_grad(h, tol):
    """Score and gradient. Uses a *soft* max (log-sum-exp) surrogate when tol>0,
    which smooths the ||f*f||_inf term and yields better-conditioned gradients."""
    n = h.size
    s = h.sum()
    if s <= 0:
        return -1.0, np.zeros(n)
    L = np.convolve(h, h)
    Lmax = L.max()
    if Lmax <= 0:
        return -1.0, np.zeros(n)
    Lp = np.concatenate(([0.0], L, [0.0]))
    A = Lp @ Lp
    B = Lp[:-1] @ Lp[1:]
    num = (2.0 * A + B) / 3.0

    if tol <= 0:
        idx = np.array([int(np.argmax(L))])
        k = 1
        mk = Lmax
    else:
        idx = np.nonzero(L >= (1.0 - tol) * Lmax)[0]
        k = idx.size
        if k < 1:
            idx = np.array([int(np.argmax(L))])
            k = 1
        mk = L[idx].mean()

    den = s * s * mk
    dnum_Lp = (4.0 / 3.0) * Lp
    dnum_Lp[:-1] += Lp[1:] / 3.0
    dnum_Lp[1:] += Lp[:-1] / 3.0
    dq = dnum_Lp[1:-1].copy()

    dR_dL = dq / den
    coef = num / (den * den)
    dR_dL[idx] -= coef * (s * s / k)
    dR_ds = -coef * (2.0 * s * mk)

    grad = np.convolve(dR_dL, h[::-1], mode='valid') * 2.0
    grad += dR_ds
    return _score(h), grad


def _upsample(h, n):
    m = len(h)
    if m == n:
        return h.copy()
    x_old = (np.arange(m) + 0.5) / m
    x_new = (np.arange(n) + 0.5) / n
    return np.interp(x_new, x_old, h)


def _frac_near(h, tol=1e-3):
    L = np.convolve(h, h)
    m = L.max()
    if m <= 0:
        return 0.0
    return float(np.mean(L >= (1.0 - tol) * m))


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.97
    rng = np.random.default_rng(20240517)

    if start is not None:
        best = np.asarray(start, dtype=float).copy()
        best[best < 0] = 0.0
        if best.size == 0 or best.sum() <= 0:
            best = np.ones(50)
    else:
        N = 200
        x = (np.arange(N) + 0.5) / N
        best = np.maximum(np.cos(np.pi * (x - 0.5)) ** 2, 1e-3)

    best_score = _score(best)
    keep_best(best)
    print(f"  start: score={best_score:.6f} N={best.size}")
    print(f"stage init: -> {best_score:.6f}, {time.process_time()-t0:.2f} s")

    def normalize(h):
        m = h.max()
        if m > 0:
            h = h / m
        return np.maximum(h, 0.0)

    def gradient_ascent(h, t_end, tol_schedule, max_iter=1000000, lr0=0.02,
                        lr_decay=0.92, decay_every=500):
        h = normalize(h.copy())
        cur = _score(h)
        n = h.size
        lr = lr0
        m1 = np.zeros(n)
        m2 = np.zeros(n)
        beta1, beta2 = 0.9, 0.999
        eps = 1e-12
        it = 0
        best_h = h.copy()
        best_c = cur
        t_start = time.process_time()
        span = max(1e-9, t_end - t_start)
        while time.process_time() < t_end and it < max_iter:
            it += 1
            frac = min(1.0, (time.process_time() - t_start) / span)
            tol = tol_schedule(frac)
            sc, g = _score_grad(h, tol)
            if sc > best_c:
                best_c = sc
                best_h = h.copy()
            gn = np.linalg.norm(g)
            if gn > 0:
                g = g / (gn + 1e-12)
            m1 = beta1 * m1 + (1 - beta1) * g
            m2 = beta2 * m2 + (1 - beta2) * (g * g)
            mh = m1 / (1 - beta1 ** it)
            vh = m2 / (1 - beta2 ** it)
            h = h + lr * mh / (np.sqrt(vh) + eps)
            h = np.maximum(h, 0.0)
            if it % 50 == 0:
                h = normalize(h)
                if it % decay_every == 0:
                    lr *= lr_decay
        sc = _score(h)
        if sc > best_c:
            best_c = sc
            best_h = h.copy()
        return best_h, best_c

    def tol_sched(frac):
        if frac >= 0.7:
            return 0.0
        u = frac / 0.7
        return 1e-2 * (1e-4 / 1e-2) ** u

    def tol_sched_wide(frac):
        if frac >= 0.7:
            return 0.0
        u = frac / 0.7
        return 1e-1 * (1e-4 / 1e-1) ** u

    def update_global(h, sc, tag):
        nonlocal best, best_score
        if sc > best_score:
            best, best_score = h.copy(), sc
            keep_best(best)
            print(f"  [{tag}] new global best {best_score:.6f} N={best.size}")
        return best_score

    # ---- Stage 1: coarse N=50 ----
    if start is not None and best.size % 50 == 0:
        h50 = best.reshape(50, -1).mean(axis=1)
    else:
        h50 = _upsample(best, 50)
    sc50 = _score(h50)
    print(f"stage coarse: {best_score:.6f} -> {sc50:.6f}, {time.process_time()-t0:.2f} s")

    # ---- Stage 2: short multi-restart at N=50 ----
    t_stage2_end = min(deadline, time.process_time() + 1.5)
    best50 = h50.copy()
    best50_score = sc50
    for run in range(2):
        if time.process_time() >= t_stage2_end:
            break
        if run == 0:
            cand = h50.copy()
        else:
            amp = 0.05
            jitter = 1.0 + amp * rng.standard_normal(50)
            cand = normalize(best50 * np.maximum(jitter, 0.0))
        run_end = min(t_stage2_end, time.process_time() + 0.75)
        h2, sc2 = gradient_ascent(cand, run_end, tol_sched, lr0=0.05)
        if sc2 > best50_score:
            best50, best50_score = h2, sc2
    print(f"stage n=50: {sc50:.6f} -> {best50_score:.6f}, {time.process_time()-t0:.2f} s")

    # ---- Stage 3: ladder 50 -> 100 -> 200 ----
    h100 = np.repeat(best50, 2)
    sc100 = _score(h100)
    update_global(h100, sc100, "h100")
    print(f"stage n=100: {sc100:.6f} -> {sc100:.6f}, {time.process_time()-t0:.2f} s")

    h200 = np.repeat(h100, 2)
    sc200 = _score(h200)
    update_global(h200, sc200, "h200")
    if time.process_time() < deadline - 0.5:
        t_end = min(deadline, time.process_time() + 1.5)
        h2, sc2 = gradient_ascent(h200, t_end, tol_sched, lr0=0.02)
        if sc2 > sc200:
            h200, sc200 = h2, sc2
        update_global(h200, sc200, "n=200")
    print(f"stage n=200: {_score(np.repeat(h100,2)):.6f} -> {sc200:.6f}, {time.process_time()-t0:.2f} s")

    # ---- Stage 4: N=800 (finer than start) to break out of N=400 local optimum ----
    h800 = np.repeat(h200, 4)
    sc800 = _score(h800)
    update_global(h800, sc800, "h800")
    t_800_start = time.process_time()
    if time.process_time() < deadline - 0.5:
        t_end = max(time.process_time() + 0.1, deadline - 4.0)
        h2, sc2 = gradient_ascent(h800, t_end, tol_sched_wide, lr0=0.02)
        if sc2 > sc800:
            h800, sc800 = h2, sc2
        update_global(h800, sc800, "n=800")
    print(f"stage n=800: {_score(np.repeat(h200,4)):.6f} -> {sc800:.6f}, {time.process_time()-t0:.2f} s (elapsed {time.process_time()-t_800_start:.2f} s)")

    # ---- Stage 5: fine refinement at N=800 with tighter tolerance ----
    if time.process_time() < deadline - 0.5:
        h2, sc2 = gradient_ascent(best, deadline - 0.3, tol_sched, lr0=0.01)
        update_global(h2, sc2, "fine")

    # ---- Stage 6: final hard-max polish ----
    if time.process_time() < deadline - 0.15:
        h2, sc2 = gradient_ascent(best, deadline - 0.05, lambda f: 0.0, lr0=0.005)
        update_global(h2, sc2, "final")

    print(f"  frac within 0.1% of max: {_frac_near(best):.4f}")
    print(f"stage final: -> {best_score:.6f}, {time.process_time()-t0:.2f} s, N={best.size}")
    return best
