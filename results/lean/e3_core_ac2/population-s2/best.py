import numpy as np
import time
from scipy.optimize import minimize


def _parts(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0 or not np.all(np.isfinite(h)):
        return None
    s = h.sum()
    if s <= 0:
        return None
    c = np.convolve(h, h)
    L = np.empty(c.size + 2)
    L[0] = 0.0
    L[-1] = 0.0
    L[1:-1] = c
    a = L[:-1]
    b = L[1:]
    num = np.sum(a * a + a * b + b * b) / 3.0
    mx = L.max()
    if mx <= 0:
        return None
    return num / (s * s * mx), L, s, mx, num


def _R(h):
    p = _parts(h)
    return -1.0 if p is None else p[0]


def _grad(h, L, s, mx, num):
    n = h.size
    a = L[:-1]
    b = L[1:]
    dL = np.zeros_like(L)
    dL[:-1] += (2.0 * a + b) / 3.0
    dL[1:] += (a + 2.0 * b) / 3.0
    gL = dL[1:-1]
    c1 = np.convolve(gL, h[::-1])
    c2 = np.convolve(gL, h)
    dnum = c1[n - 1:2 * n - 1] + c2[n - 1:2 * n - 1]
    argmax = int(np.argmax(L))
    dmx = np.zeros(n)
    if 1 <= argmax <= 2 * n - 1:
        k = argmax - 1
        lo = max(0, k - n + 1)
        hi = min(n, k + 1)
        idx = np.arange(lo, hi)
        dmx[idx] = 2.0 * h[k - idx]
    s2mx = s * s * mx
    return (dnum * s2mx - num * (2.0 * s * mx + s * s * dmx)) / (s2mx * s2mx)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

    def tl():
        return time.process_time() < deadline

    rng = np.random.default_rng(90210 + int(budget_seconds * 977))

    state = {"best": None, "bestR": -1.0}

    def consider(h):
        h = np.asarray(h, dtype=float).ravel()
        if h.size == 0 or h.size > 50000:
            return False
        h = np.maximum(h, 0.0)
        if h.sum() <= 0:
            return False
        r = _R(h)
        if r > state["bestR"]:
            state["bestR"] = r
            state["best"] = h.copy()
            return True
        return False

    if start is not None:
        consider(start)

    def lbfgs_polish(seed, dl, maxfun=300):
        h = np.maximum(np.asarray(seed, dtype=float).copy(), 0.0)
        if h.sum() <= 0:
            return h
        base_scale = h.max()
        if base_scale <= 0:
            return h
        z0 = np.log(np.maximum(h / base_scale, 1e-11))

        def negR_grad(z):
            if time.process_time() >= dl:
                raise TimeoutError
            hh = np.exp(z) * base_scale
            p = _parts(hh)
            if p is None:
                return 1e10, z * 0.0
            r, L, s, mx, num = p
            g = _grad(hh, L, s, mx, num)
            return -r, -g * hh

        try:
            res = minimize(negR_grad, z0, jac=True, method="L-BFGS-B",
                           options={"maxiter": maxfun, "maxfun": maxfun,
                                    "ftol": 1e-20, "gtol": 1e-16})
            cand = np.exp(res.x) * base_scale
            if np.all(np.isfinite(cand)) and cand.sum() > 0:
                if _R(cand) > _R(h):
                    return cand
        except Exception:
            pass
        return h

    def plateau(N, taper, power):
        x = np.linspace(-1, 1, N)
        t = np.clip((1 - np.abs(x)) / max(taper, 1e-6), 0, 1)
        return t ** power

    if state["best"] is None:
        for N in (240, 300, 337, 363, 385):
            for taper in (0.35, 0.5, 0.65):
                for power in (0.6, 1.0, 1.4):
                    consider(plateau(N, taper, power))

    # Phase A: polish start.
    if state["best"] is not None and tl():
        h = lbfgs_polish(state["best"], min(deadline, time.process_time() + budget_seconds * 0.18), maxfun=900)
        consider(h)

    # Phase B: alternating random-restart L-BFGS with size perturbations.
    tried = {}
    stall = 0
    while tl() and state["best"] is not None:
        base = state["best"].copy()
        N0 = base.size
        gained = False

        # Fine size sweep around current N.
        for d in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8,
                  10, -10, 12, -12, 15, -15, 20, -20, 26, -26, 34, -34, 45, -45):
            M = N0 + d
            if M < 20 or M > 50000:
                continue
            if tried.get(M, 0) >= 2:
                continue
            tried[M] = tried.get(M, 0) + 1
            if not tl():
                break
            xi = np.linspace(0, 1, N0)
            xo = np.linspace(0, 1, M)
            cand = np.interp(xo, xi, base)
            # add slight smoothing to avoid exact resample degeneracy
            hc = lbfgs_polish(cand, min(deadline, time.process_time() + 0.55), maxfun=280)
            if consider(hc):
                gained = True

        if not tl():
            break

        if not gained:
            # Random restart with random N near current, small noise.
            for _ in range(3):
                if not tl():
                    break
                M = int(np.clip(N0 + rng.integers(-6, 7), 20, 50000))
                xi = np.linspace(0, 1, N0)
                xo = np.linspace(0, 1, M)
                cand = np.interp(xo, xi, base)
                cand = cand * (1.0 + 0.01 * rng.standard_normal(M))
                cand = np.maximum(cand, 0.0)
                if cand.sum() <= 0:
                    continue
                hc = lbfgs_polish(cand, min(deadline, time.process_time() + 0.55), maxfun=260)
                if consider(hc):
                    gained = True
                    break

        if not gained:
            for sigma in (0.001, 0.002, 0.004, 0.008, 0.016, 0.032):
                if not tl():
                    break
                jit = state["best"] * (1.0 + sigma * rng.standard_normal(state["best"].size))
                jit = np.maximum(jit, 0.0)
                if jit.sum() > 0:
                    hj = lbfgs_polish(jit, min(deadline, time.process_time() + 0.5), maxfun=240)
                    if consider(hj):
                        gained = True
                        break

        if not gained:
            stall += 1
        else:
            stall = 0
        if stall > 4 and len(tried) > 200:
            break

    # Phase C: final long polish.
    if state["best"] is not None and tl():
        hc = lbfgs_polish(state["best"], deadline, maxfun=4000)
        consider(hc)

    best = state["best"]
    if best is None:
        best = np.ones(50)
    return np.asarray(best, dtype=float)
