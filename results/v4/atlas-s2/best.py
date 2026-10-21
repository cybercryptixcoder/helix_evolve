import numpy as np
import time


def _knots(h):
    L = np.convolve(h, h)
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    return Lp


def score(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    Lp = _knots(h)
    a = Lp[:-1]
    b = Lp[1:]
    q = np.sum(a * a + a * b + b * b) / 3.0
    m = Lp.max()
    if m <= 0:
        return 0.0
    return q / (s * s * m)


def _score_and_grad(h):
    h = np.asarray(h, dtype=float)
    n = h.size
    s = h.sum()
    if s <= 0:
        return 0.0, np.zeros(n)
    L = np.convolve(h, h)
    Lp = np.empty(L.size + 2)
    Lp[0] = 0.0
    Lp[-1] = 0.0
    Lp[1:-1] = L
    a = Lp[:-1]
    b = Lp[1:]
    q = np.sum(a * a + a * b + b * b) / 3.0
    m = Lp.max()
    if m <= 0:
        return 0.0, np.zeros(n)
    R = q / (s * s * m)

    dq = np.empty(Lp.size)
    dq[1:-1] = (2.0 * Lp[1:-1] + Lp[2:]) / 3.0 + (Lp[:-2] + 2.0 * Lp[1:-1]) / 3.0
    dq[0] = (2.0 * Lp[0] + Lp[1]) / 3.0
    dq[-1] = (Lp[-2] + 2.0 * Lp[-1]) / 3.0

    imax = int(np.argmax(Lp))

    term2 = np.convolve(dq, h)[:n]
    term1_full = np.convolve(dq, h[::-1])
    term1 = term1_full[n - 1: n - 1 + n]
    dq_dh = term1 + term2

    dm_dh = np.zeros(n)
    k = imax
    lo = max(0, k - n + 1)
    hi = min(n - 1, k)
    for i in range(lo, hi + 1):
        j = k - i
        if 0 <= j < n:
            dm_dh[i] += h[j]
    lo2 = max(0, k)
    hi2 = min(n - 1, k + n - 1)
    for i in range(lo2, hi2 + 1):
        j = i - k
        if 0 <= j < n:
            dm_dh[i] += h[j]

    ds_dh = np.ones(n)
    inv = 1.0 / (s * s * m)
    grad = dq_dh * inv - R * (2.0 * ds_dh / s + dm_dh / m)
    return R, grad


_GR = (np.sqrt(5.0) - 1.0) / 2.0


def _golden(fun, lo, hi, iters):
    a, b = lo, hi
    c = b - _GR * (b - a)
    d = a + _GR * (b - a)
    fc = fun(c); fd = fun(d)
    for _ in range(iters):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - _GR * (b - a)
            fc = fun(c)
        else:
            a, c, fc = c, d, fd
            d = a + _GR * (b - a)
            fd = fun(d)
    return 0.5 * (a + b)


def _coord_sweep(h, cur, deadline, rng):
    n = h.size
    order = rng.permutation(n)
    mean = h.mean() if h.mean() > 0 else 1e-3
    for i in order:
        if time.process_time() >= deadline:
            return h, cur
        base = h[i]
        if base > 0:
            def fun(x):
                hx = h.copy(); hx[i] = base * x
                return score(hx)
            x = _golden(fun, 0.0, 3.0, 22)
            hx = h.copy(); hx[i] = base * x
        else:
            def fun(x):
                hx = h.copy(); hx[i] = x
                return score(hx)
            x = _golden(fun, 0.0, 1e-3 * mean, 22)
            hx = h.copy(); hx[i] = x
        fx = fun(x)
        if fx > cur + 1e-16:
            h = hx
            cur = fx
    return h, cur


def _window_sweep(h, cur, deadline, rng, sizes):
    n = h.size
    for w in sizes:
        if w > n:
            continue
        npos = n - w + 1
        if npos <= 0:
            continue
        # a few random positions per window size
        reps = max(2, min(8, npos))
        for _ in range(reps):
            if time.process_time() >= deadline:
                return h, cur
            i0 = int(rng.integers(0, npos))
            seg = h[i0:i0 + w].copy()
            if seg.sum() <= 0:
                continue
            u = np.linspace(-1.0, 1.0, w)

            def f_tilt(t):
                hx = h.copy()
                hx[i0:i0 + w] = np.clip(seg * (1.0 + t * u), 0.0, None)
                return score(hx)

            t = _golden(f_tilt, -0.9, 0.9, 20)
            ft = f_tilt(t)
            if ft > cur + 1e-16:
                h[i0:i0 + w] = np.clip(seg * (1.0 + t * u), 0.0, None)
                cur = ft

            # scale
            def f_scale(s):
                hx = h.copy()
                hx[i0:i0 + w] = seg * s
                return score(hx)

            s = _golden(f_scale, 0.5, 1.6, 18)
            fs = f_scale(s)
            if fs > cur + 1e-16:
                h[i0:i0 + w] = seg * s
                cur = fs
    return h, cur


def _grad_step(h, cur, deadline):
    R, g = _score_and_grad(h)
    if R > cur:
        cur = R
    g = g.copy()
    g[(h <= 0) & (g < 0)] = 0.0
    nh = np.linalg.norm(h)
    if nh <= 0:
        return h, cur
    best_h = None
    best_R = cur
    for scale in (1e-2, 3e-3, 1e-3, 3e-4):
        if time.process_time() >= deadline:
            break
        trial = np.clip(h + scale * nh * g / (np.linalg.norm(g) + 1e-30), 0.0, None)
        s = trial.sum()
        if s <= 0:
            continue
        trial /= s
        Rt = score(trial)
        if Rt > best_R + 1e-16:
            best_R = Rt
            best_h = trial
    if best_h is not None:
        return best_h, best_R
    return h, cur


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 1.5
    rng = np.random.default_rng(987654321)

    if start is not None and len(start) > 0:
        h0 = np.asarray(start, dtype=float).copy()
    else:
        h0 = np.ones(136)

    h = np.repeat(h0, 4).astype(float)
    s0 = score(h0)
    s1 = score(h)
    assert abs(s0 - s1) < 1e-12, (s0, s1)

    cur = s1
    best_h = h.copy()
    best_R = cur

    sizes = [2, 3, 5, 9, 17, 33, 65, 129]
    sweep = 0
    while time.process_time() < deadline - 3.0:
        sweep += 1
        h, cur = _coord_sweep(h, cur, deadline - 2.0, rng)
        if cur > best_R:
            best_R = cur
            best_h = h.copy()
        h, cur = _window_sweep(h, cur, deadline - 1.5, rng, sizes)
        if cur > best_R:
            best_R = cur
            best_h = h.copy()
        if sweep % 4 == 0:
            h, cur = _grad_step(h, cur, deadline - 1.0)
            if cur > best_R:
                best_R = cur
                best_h = h.copy()
        print(f"sweep {sweep} score {cur:.9f} best {best_R:.9f}")

    # final short coordinate polish on best
    h = best_h.copy()
    cur = best_R
    h, cur = _coord_sweep(h, cur, deadline, rng)
    if cur > best_R:
        best_R = cur
        best_h = h.copy()
    print(f"final {best_R:.9f}")
    return best_h
