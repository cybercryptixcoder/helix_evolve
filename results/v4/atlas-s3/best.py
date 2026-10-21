import time
import numpy as np
from scipy.optimize import minimize
from scipy.signal import fftconvolve


def _R(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return 0.0
    L = fftconvolve(h, h)
    num = (np.dot(L, L) + np.dot(L[:-1], L[1:])) / 3.0
    den = s * s * L.max()
    if den <= 0:
        return 0.0
    return num / den


def _R_grad(h):
    h = np.asarray(h, dtype=float)
    n = len(h)
    s = h.sum()
    if s <= 0:
        return 0.0, np.zeros(n)
    L = fftconvolve(h, h)
    num = (np.dot(L, L) + np.dot(L[:-1], L[1:])) / 3.0
    imax = int(np.argmax(L))
    M = L[imax]
    den = s * s * M
    if den <= 0:
        return 0.0, np.zeros(n)
    R = num / den

    g = (2.0 / 3.0) * L
    g[:-1] += (1.0 / 3.0) * L[1:]
    g[1:] += (1.0 / 3.0) * L[:-1]

    dR_dL = g / den
    dR_dL[imax] -= (num / den) / M

    corr = fftconvolve(dR_dL, h[::-1])
    grad_h = 2.0 * corr[n - 1: n - 1 + n]
    grad_h -= (2.0 * R / s)
    return R, grad_h


def _negR_grad(y):
    h = np.exp(y)
    R, gh = _R_grad(h)
    return -R, -gh * h


def _resample(h, N):
    h = np.asarray(h, dtype=float).ravel()
    n = len(h)
    if n == N:
        return h.copy()
    x_old = (np.arange(n) + 0.5) / n
    x_new = (np.arange(N) + 0.5) / N
    return np.interp(x_new, x_old, h)


def _block_downsample(h, N):
    h = np.asarray(h, dtype=float).ravel()
    n = len(h)
    if n == N:
        return h.copy()
    if n % N != 0:
        return _resample(h, N)
    k = n // N
    return h.reshape(N, k).mean(axis=1)


def _to20(h, N20=20000):
    h = np.asarray(h, dtype=float).ravel()
    n = len(h)
    if n == N20:
        return h.copy()
    if n >= N20 and n % N20 == 0:
        return _block_downsample(h, N20)
    return _resample(h, N20)


def _optimize(y0, deadline, maxiter=5000):
    best_y = y0.copy()
    best_v = -_R(np.exp(best_y))
    if time.process_time() > deadline:
        return best_y, best_v
    try:
        res = minimize(_negR_grad, best_y, jac=True, method="L-BFGS-B",
                       options={"maxiter": maxiter, "ftol": 1e-16,
                                "gtol": 1e-14, "maxcor": 50, "maxls": 50})
        if res.fun < best_v:
            best_v = res.fun
            best_y = np.array(res.x)
    except Exception:
        pass
    return best_y, best_v


def _seed_symmetric_arcsin(N):
    i = np.arange(N + 1)
    u = 2.0 * i / N - 1.0
    u = np.clip(u, -1.0, 1.0)
    a = np.arcsin(u)
    h = N * (a[1:] - a[:-1])
    return np.maximum(h, 0.0)


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.90

    N20 = 20000

    if start is not None:
        hs = np.maximum(np.asarray(start, dtype=float).ravel(), 0.0)
        if hs.sum() <= 0:
            hs = _seed_symmetric_arcsin(N20)
    else:
        hs = _seed_symmetric_arcsin(N20)

    best_h20 = _to20(hs, N20)
    if best_h20.max() > 0:
        best_h20 /= best_h20.max()
    best_R20 = _R(best_h20)
    print("initial R20: %.12f" % best_R20)
    n_accept = 0
    rng = np.random.default_rng(20240919)

    Nhi = 60000

    def consider(hb, tag):
        nonlocal best_h20, best_R20, n_accept
        hb = np.maximum(np.asarray(hb, dtype=float).ravel(), 0.0)
        hb20 = _to20(hb, N20)
        R20 = _R(hb20)
        if R20 > best_R20:
            best_R20 = R20
            best_h20 = hb20.copy()
            n_accept += 1
            print("accept %-10s n=%6d R20=%.12f" % (tag, len(hb), R20))
        return R20

    # Phase 1: lift to 60k and optimise hard.
    dA = t0 + budget_seconds * 0.40
    h_hi = _resample(best_h20, Nhi)
    if h_hi.max() > 0:
        h_hi /= h_hi.max()
    y_hi = np.log(h_hi + 1e-8)
    if time.process_time() < dA:
        y_hi, _ = _optimize(y_hi, dA, maxiter=8000)
        consider(np.exp(y_hi), "opt60")

    # Phase 2: alternate 60k refine and 20k polish, with a stronger
    # multiplicative kick and occasional 40k mid-resolution passes.
    dC = t0 + budget_seconds * 0.60
    Nmid = 40000
    toggle = 0
    while time.process_time() < dC:
        toggle += 1
        h_up = _resample(best_h20, Nhi)
        if h_up.max() > 0:
            h_up /= h_up.max()
        y = np.log(h_up + 1e-8)
        amp = 0.004 if toggle % 2 == 0 else 0.0015
        y = y + amp * rng.standard_normal(len(y))
        y, _ = _optimize(y, dC, maxiter=3000)
        hb = np.exp(y)
        consider(hb, "up60")
        if time.process_time() >= dC:
            break
        h_mid = _block_downsample(hb, N20)
        if h_mid.max() > 0:
            h_mid /= h_mid.max()
        y = np.log(h_mid + 1e-8)
        y, _ = _optimize(y, dC, maxiter=4000)
        consider(np.exp(y), "dn20")
        if time.process_time() >= dC:
            break
        h_mid = _resample(best_h20, Nmid)
        if h_mid.max() > 0:
            h_mid /= h_mid.max()
        y = np.log(h_mid + 1e-8)
        y = y + 0.002 * rng.standard_normal(len(y))
        y, _ = _optimize(y, dC, maxiter=2500)
        consider(np.exp(y), "mid40")

    # Phase 3: block coordinate ascent at N=20000.
    h_fin = np.maximum(best_h20, 0.0)
    if h_fin.max() > 0:
        h_fin /= h_fin.max()
    y = np.log(h_fin + 1e-8)
    R_cur = _R(np.exp(y))
    if R_cur > best_R20:
        best_R20 = R_cur
        best_h20 = np.exp(y).copy()

    BLOCK = 64
    n = len(y)
    nblocks = (n + BLOCK - 1) // BLOCK
    blocks = [np.arange(b * BLOCK, min((b + 1) * BLOCK, n)) for b in range(nblocks)]
    deltas = np.array([-8e-4, -4e-4, -1.5e-4, 1.5e-4, 4e-4, 8e-4])

    def try_block(y, idx, R_cur):
        # (a) uniform multiplicative move
        best_d = 0.0
        best_R = R_cur
        vals = []
        for d in deltas:
            yy = y.copy()
            yy[idx] += d
            Rv = _R(np.exp(yy))
            vals.append(Rv)
            if Rv > best_R:
                best_R = Rv
                best_d = d
        # parabolic refinement around best delta
        if best_d != 0.0:
            j = int(np.where(deltas == best_d)[0][0])
            if 0 < j < len(deltas) - 1:
                x0, x1, x2 = deltas[j - 1], deltas[j], deltas[j + 1]
                f0, f1, f2 = vals[j - 1], vals[j], vals[j + 1]
                denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
                if abs(denom) > 1e-30:
                    A = (x2 * (f1 - f0) + x1 * (f0 - f2) + x0 * (f2 - f1)) / denom
                    B = (x2 * x2 * (f0 - f1) + x1 * x1 * (f2 - f0) + x0 * x0 * (f1 - f2)) / denom
                    if A < 0:
                        xv = -B / (2 * A)
                        if x0 < xv < x2:
                            yy = y.copy()
                            yy[idx] += xv
                            Rv = _R(np.exp(yy))
                            if Rv > best_R:
                                best_R = Rv
                                best_d = xv
        # (b) gradient-direction move
        _, gh = _R_grad(np.exp(y))
        g = gh * np.exp(y)  # dR/dy
        gb = g[idx]
        mx = np.max(np.abs(gb))
        if mx > 1e-30:
            step = 4e-4 / mx
            yy = y.copy()
            yy[idx] += step * gb
            Rv = _R(np.exp(yy))
            if Rv > best_R:
                best_R = Rv
                best_d = None
                best_yy = yy
            else:
                best_yy = None
        else:
            best_yy = None

        if best_d is None and best_yy is not None:
            return best_yy, best_R
        if best_d != 0.0:
            yy = y.copy()
            yy[idx] += best_d
            return yy, best_R
        return y, R_cur

    cycle = 0
    while time.process_time() < deadline:
        cycle += 1
        order = rng.permutation(nblocks)
        improved_any = False
        for b in order:
            if time.process_time() >= deadline:
                break
            idx = blocks[b]
            y_new, R_new = try_block(y, idx, R_cur)
            if R_new > R_cur:
                y = y_new
                R_cur = R_new
                improved_any = True
                if R_cur > best_R20:
                    best_R20 = R_cur
                    best_h20 = np.exp(y).copy()
                    n_accept += 1
                    print("accept %-10s n=%6d R20=%.12f" % ("blk", n, R_cur))
        if time.process_time() >= deadline:
            break
        # one L-BFGS pass after each cycle
        y_l, v_l = _optimize(y, deadline, maxiter=2000)
        R_l = -v_l
        if R_l > R_cur:
            y = y_l
            R_cur = R_l
            if R_cur > best_R20:
                best_R20 = R_cur
                best_h20 = np.exp(y).copy()
                n_accept += 1
                print("accept %-10s n=%6d R20=%.12f" % ("lbfgs", n, R_cur))
        if not improved_any and R_l <= R_cur:
            # no progress; small kick to escape
            y = y + 0.0003 * rng.standard_normal(len(y))
            R_cur = _R(np.exp(y))

    print("final R:", best_R20, "N:", len(best_h20), "accepts:", n_accept)
    return np.asarray(best_h20, dtype=float)
