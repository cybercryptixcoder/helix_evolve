import numpy as np
import time
from scipy.optimize import minimize, linprog
from scipy.sparse import csr_matrix


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * np.max(np.convolve(h, h)) / (s * s)


def _conv_fft(h):
    N = len(h)
    L = 2 * N
    H = np.fft.rfft(h, L)
    return np.fft.irfft(H * H, L)[:L - 1]


def _refine(h, deadline, thresh=1e-4, dmax=0.05):
    """LP-based active-set polish: minimise M subject to conv(h)[k] <= M on active knots
    and sum(h)=1, with a trust-region dmax. Uses FFT conv for speed."""
    N = len(h)
    h = h / h.sum()
    best = h.copy()
    best_C = _C(h)
    thresh = thresh
    it = 0
    while time.process_time() < deadline and it < 400:
        it += 1
        conv = _conv_fft(h)
        M = conv.max()
        idx = np.where(conv >= M * (1.0 - thresh))[0]
        if len(idx) == 0:
            break
        nvar = N + 1
        c_obj = np.zeros(nvar)
        c_obj[N] = 1.0
        nA = len(idx)
        rows = []
        cols = []
        vals = []
        b_ub = np.zeros(nA)
        for r, k in enumerate(idx):
            lo = max(0, k - (N - 1))
            hi = min(N - 1, k)
            js = np.arange(lo, hi + 1)
            rows.extend([r] * len(js))
            cols.extend(js.tolist())
            vals.extend((2.0 * h[k - js]).tolist())
            rows.append(r)
            cols.append(N)
            vals.append(-1.0)
            b_ub[r] = -conv[k]
        A_ub = csr_matrix((vals, (rows, cols)), shape=(nA, nvar))
        A_eq = csr_matrix((np.ones(N), (np.zeros(N, dtype=int), np.arange(N))),
                          shape=(1, nvar))
        b_eq = np.array([0.0])
        bounds = [(-h[i], dmax) for i in range(N)] + [(None, None)]
        try:
            res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                          bounds=bounds, method='highs')
        except Exception:
            break
        if not res.success or res.x is None:
            break
        d = res.x[:N]
        if np.linalg.norm(d) < 1e-15:
            break
        accepted = False
        alpha = 1.0
        for _ in range(25):
            if time.process_time() >= deadline:
                break
            h2 = h + alpha * d
            h2 = np.maximum(h2, 0.0)
            s2 = h2.sum()
            if s2 <= 0:
                alpha *= 0.5
                continue
            h2 /= s2
            c2 = _C(h2)
            if c2 < best_C - 1e-16:
                h = h2
                best_C = c2
                best = h2.copy()
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            if thresh > 1e-8:
                thresh *= 0.3
                dmax *= 0.5
                continue
            break
    return best, best_C


def _newton_kkt(h, deadline, max_iter=40, thresh=1e-5, tol=1e-13):
    """Newton on the KKT system of min M s.t. conv(h)[k]=M on active set, sum h=1."""
    N = len(h)
    h = h / h.sum()
    best = h.copy()
    best_C = _C(h)
    stall = 0
    for it in range(max_iter):
        if time.process_time() >= deadline:
            break
        conv = _conv_fft(h)
        M = conv.max()
        idx = np.where(conv >= M * (1.0 - thresh))[0]
        if len(idx) == 0:
            break
        nA = len(idx)
        J = np.zeros((nA + 1, N + 1))
        r = np.zeros(nA + 1)
        for row, k in enumerate(idx):
            lo = max(0, k - (N - 1))
            hi = min(N - 1, k)
            J[row, lo:hi + 1] = 2.0 * h[k - np.arange(lo, hi + 1)]
            J[row, N] = -1.0
            r[row] = conv[k] - M
        J[nA, :N] = 1.0
        r[nA] = h.sum() - 1.0
        if np.max(np.abs(r)) < tol:
            break
        try:
            step, _, _, _ = np.linalg.lstsq(J, -r, rcond=None)
        except Exception:
            break
        dh = step[:N]
        if not np.all(np.isfinite(dh)):
            break
        accepted = False
        alpha = 1.0
        for _ in range(30):
            if time.process_time() >= deadline:
                break
            h2 = np.maximum(h + alpha * dh, 0.0)
            s2 = h2.sum()
            if s2 <= 0:
                alpha *= 0.5
                continue
            h2 /= s2
            c2 = _C(h2)
            if c2 < best_C - 1e-16:
                h = h2
                best_C = c2
                best = h2.copy()
                accepted = True
                stall = 0
                break
            alpha *= 0.5
        if not accepted:
            stall += 1
            if stall >= 3:
                break
    return best, best_C


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.88

    if start is not None:
        base = np.maximum(np.asarray(start, dtype=float).ravel(), 0.0)
        if base.sum() <= 0:
            base = np.ones(200)
    else:
        base = np.ones(200)
    base_C = _C(base)
    print("start C = %.6f, N = %d" % (base_C, len(base)))

    N = 8192
    N0 = len(base)
    x0 = (np.arange(N0) + 0.5) / N0
    x1 = (np.arange(N) + 0.5) / N
    h0 = np.interp(x1, x0, base)
    h0 = np.maximum(h0, 0.0)
    s = h0.sum()
    if s <= 0:
        h0 = np.ones(N)
        s = N
    h0 = h0 / s
    best = h0.copy()
    best_C = _C(best)
    print("upsampled C = %.6f, N = %d" % (best_C, N))

    # Alternate LP (active-set exchange) and Newton KKT until deadline
    round_i = 0
    while time.process_time() < deadline - 0.5:
        round_i += 1
        t_start = time.process_time()
        slice_end = min(deadline - 0.5, t_start + 4.0)
        best, best_C = _refine(best, slice_end, thresh=1e-4, dmax=0.05)
        print("r%d LP C=%.9f (t=%.1f)" % (round_i, best_C, time.process_time() - t0))
        if time.process_time() >= deadline - 0.5:
            break
        slice_end = min(deadline - 0.5, time.process_time() + 3.0)
        best, best_C = _newton_kkt(best, slice_end, max_iter=40, thresh=1e-5)
        print("r%d NK C=%.9f (t=%.1f)" % (round_i, best_C, time.process_time() - t0))
        # shrink thresholds for finer polish
        if round_i >= 2 and best_C < base_C:
            # try aggressive fine
            slice_end = min(deadline - 0.5, time.process_time() + 2.0)
            best, best_C = _refine(best, slice_end, thresh=1e-6, dmax=0.005)
            print("r%d fine C=%.9f" % (round_i, best_C))

    print("final C = %.6f, N = %d" % (best_C, len(best)))
    return best
