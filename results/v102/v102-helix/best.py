import numpy as np
import time
import math
from scipy.optimize import minimize


def _nfft_for(n, factor=2):
    nfft = 1
    need = factor * n
    while nfft < need:
        nfft *= 2
    return nfft


def _conv_of(h):
    n = len(h)
    nfft = _nfft_for(n)
    F = np.fft.rfft(h, nfft)
    return np.fft.irfft(F * F, nfft)[:2 * n - 1]


def _R_from_L(L, l1):
    sq = np.sum(L[:-1] ** 2 + L[:-1] * L[1:] + L[1:] ** 2) / 3.0
    linf = np.max(L)
    if linf <= 0 or l1 <= 0:
        return 0.0
    return sq / (l1 * linf)


def _knot_R(f):
    conv = _conv_of(f)
    L = np.concatenate(([0.0], conv, [0.0]))
    return _R_from_L(L, np.sum(f) ** 2)


def _corr_with_weights(h, w):
    n = len(h)
    nfft = _nfft_for(n, 3)
    Wf = np.fft.rfft(w, nfft)
    Hr = np.fft.rfft(h[::-1], nfft)
    corr = np.fft.irfft(Wf * Hr, nfft)
    return 2.0 * corr[n - 1:2 * n - 1]


def _dnum_of(L):
    d = np.zeros_like(L)
    d[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    d[1:] += (2.0 * L[1:] + L[:-1]) / 3.0
    return d


def _shares(h):
    try:
        cv = _conv_of(h)
        L = np.concatenate(([0.0], cv, [0.0]))
        m = np.max(L)
        if m <= 0:
            return (0.0, 0.0, 0.0)
        return (float(np.mean(L >= 0.999 * m)),
                float(np.mean(L >= 0.99 * m)),
                float(np.mean(L >= 0.95 * m)))
    except Exception:
        return (0.0, 0.0, 0.0)


def _beta_for_target_m(L, M, m):
    d = L - M
    if m <= 1.0:
        return 1e16

    def S(beta):
        return float(np.sum(np.exp(np.clip(beta * d, -700.0, 0.0))))

    lo, hi = 0.0, 1.0
    for _ in range(200):
        if S(hi) <= m:
            break
        hi *= 2.0
        if hi > 1e18:
            return hi
    la, lb = math.log(max(lo, 1e-300)), math.log(max(hi, 1e-300))
    for _ in range(60):
        mid = 0.5 * (la + lb)
        beta = math.exp(mid)
        if S(beta) > m:
            la = mid
        else:
            lb = mid
    return math.exp(0.5 * (la + lb))


def _lbfgs_target_m(f, deadline, m, maxiter=400, free_mask=None):
    n = len(f)
    nfft = _nfft_for(n)
    fw = np.maximum(f, 0.0).copy()
    if free_mask is not None:
        fw[~free_mask] = 0.0
    s = fw.sum()
    if s <= 0:
        return fw, _knot_R(fw), False
    fw /= s
    F = np.fft.rfft(fw, nfft)
    conv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
    L0 = np.concatenate(([0.0], conv, [0.0]))
    num0 = np.sum(L0[:-1] ** 2 + L0[:-1] * L0[1:] + L0[1:] ** 2) / 3.0
    m0 = float(np.max(L0))
    if m0 <= 0:
        return fw, 0.0, False
    beta = _beta_for_target_m(L0, m0, m)
    e0 = np.exp(np.clip(beta * (L0 - m0), -700.0, 0.0))
    s0 = e0.sum()
    lse0 = m0 + math.log(s0) / beta if beta > 0 else m0
    lam = num0 / lse0 if lse0 > 0 else 1.0
    R_before = _knot_R(fw)

    if free_mask is None:
        idx = np.arange(n)
    else:
        idx = np.where(free_mask)[0]
    if len(idx) == 0:
        return fw, R_before, False
    x0 = fw[idx].copy()

    def obj(x, _beta=beta, _lam=lam):
        if time.process_time() >= deadline:
            raise TimeoutError
        fx = np.zeros(n)
        fx[idx] = np.maximum(x, 0.0)
        sx = fx.sum()
        if sx <= 0:
            return 1e10, np.zeros(len(idx))
        fx = fx / sx
        F = np.fft.rfft(fx, nfft)
        cv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
        LL = np.concatenate(([0.0], cv, [0.0]))
        num = np.sum(LL[:-1] ** 2 + LL[:-1] * LL[1:] + LL[1:] ** 2) / 3.0
        mm = float(np.max(LL))
        e = np.exp(np.clip(_beta * (LL - mm), -700.0, 0.0))
        ss = e.sum()
        lse = mm + math.log(ss) / _beta if _beta > 0 else mm
        phi = e / ss
        phi_obj = _lam * lse - num
        w = _lam * phi - _dnum_of(LL)
        g = _corr_with_weights(fx, w[1:-1])
        g = (g - np.dot(g, fx)) / sx
        return phi_obj, g[idx]

    try:
        rem = deadline - time.process_time()
        it = min(maxiter, max(20, int(rem * 30)))
        res = minimize(obj, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * len(idx),
                       options={'maxiter': it, 'ftol': 1e-20,
                                'gtol': 1e-15, 'maxcor': 30})
        fnew = np.zeros(n)
        fnew[idx] = np.maximum(res.x, 0.0)
        sn = fnew.sum()
        if sn > 0:
            fnew /= sn
            Rn = _knot_R(fnew)
            if Rn > R_before + 1e-15:
                return fnew, Rn, True
    except Exception:
        pass
    return fw, R_before, False


def _band_descent(h, R, deadline, t_start, tag="BD", max_stall=4,
                  max_backtracks=30, free_mask=None):
    n = len(h)
    h = np.maximum(h, 0.0).copy()
    if free_mask is not None:
        h[~free_mask] = 0.0
    s = h.sum()
    if s <= 0:
        return h, R
    h /= s
    best_h = h.copy()
    best_R = R
    nfft = _nfft_for(n, 3)
    step = None
    it = 0
    stall = 0
    while time.process_time() < deadline:
        it += 1
        F = np.fft.rfft(h, nfft)
        cv = np.fft.irfft(F * F, nfft)[:2 * n - 1]
        L = np.concatenate(([0.0], cv, [0.0]))
        M = float(np.max(L))
        if M <= 0:
            break
        phi = L / M
        B = (phi >= 0.1) & (phi <= 0.9)
        if not np.any(B):
            break
        w = np.zeros(2 * n - 1)
        idxB = np.where(B[1:-1])[0]
        w[idxB] = (1.0 - 2.0 * phi[1:-1][idxB]) / M
        g = _corr_with_weights(h, w)
        sh = h.sum()
        if sh > 0:
            g = g - (np.dot(g, h) / sh)
        if free_mask is not None:
            g[~free_mask] = 0.0
        gn = np.linalg.norm(g)
        if gn <= 0:
            break
        if step is None:
            base = np.max(h) / max(gn, 1e-30)
            chosen = None
            for k in range(-6, 3):
                st = (2.0 ** k) * base
                h2 = np.maximum(h - st * g, 0.0)
                if free_mask is not None:
                    h2[~free_mask] = 0.0
                s2 = h2.sum()
                if s2 <= 0:
                    continue
                h2 /= s2
                if _knot_R(h2) > best_R + 1e-15:
                    chosen = st
                    break
            step = chosen if chosen is not None else 0.02 * base
        improved = False
        for _ in range(max_backtracks):
            h2 = np.maximum(h - step * g, 0.0)
            if free_mask is not None:
                h2[~free_mask] = 0.0
            s2 = h2.sum()
            if s2 <= 0:
                step *= 0.5
                continue
            h2 /= s2
            R2 = _knot_R(h2)
            if R2 > best_R + 1e-15:
                h = h2
                best_R = R2
                best_h = h.copy()
                step *= 1.3
                improved = True
                stall = 0
                break
            step *= 0.5
            if step < 1e-12:
                break
        if not improved:
            stall += 1
            if stall >= max_stall or step < 1e-12:
                break
    print(f"  [{tag}] it={it} R={best_R:.10f} t={time.process_time()-t_start:.1f}s")
    return best_h, best_R


def _m1_full(h, deadline, t_start, maxiter=20000, tag="m1"):
    n = len(h)
    nfft = _nfft_for(n)
    fw = np.maximum(h, 0.0).copy()
    s = fw.sum()
    if s <= 0:
        return h, _knot_R(h), False
    fw /= s
    R_before = _knot_R(fw)
    x0 = fw.copy()

    def obj(x):
        if time.process_time() >= deadline:
            raise TimeoutError
        fx = np.maximum(x, 0.0)
        sx = fx.sum()
        if sx <= 0:
            return 1e10, np.zeros(n)
        fx = fx / sx
        F = np.fft.rfft(fx, nfft)
        cv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
        LL = np.concatenate(([0.0], cv, [0.0]))
        num = np.sum(LL[:-1] ** 2 + LL[:-1] * LL[1:] + LL[1:] ** 2) / 3.0
        mm = float(np.max(LL))
        if mm <= 0:
            return 1e10, np.zeros(n)
        val = -num / mm
        dnum = _dnum_of(LL)
        am = int(np.argmax(LL))
        wmax = np.zeros_like(LL)
        wmax[am] = 1.0
        gnum = _corr_with_weights(fx, dnum[1:-1])
        gmm = _corr_with_weights(fx, wmax[1:-1])
        g = -(gnum * mm - num * gmm) / (mm * mm)
        g = (g - np.dot(g, fx)) / sx
        return val, g

    try:
        rem = deadline - time.process_time()
        it = min(maxiter, max(20, int(rem * 30)))
        res = minimize(obj, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * n,
                       options={'maxiter': it, 'ftol': 1e-22,
                                'gtol': 1e-16, 'maxcor': 40})
        fnew = np.maximum(res.x, 0.0)
        sn = fnew.sum()
        if sn > 0:
            fnew /= sn
            Rn = _knot_R(fnew)
            if Rn > R_before + 1e-15:
                return fnew, Rn, True
    except Exception:
        pass
    return fw, R_before, False


# ===== New: one-sided band-lift objective =====
def _band_lift(h, deadline, t_start, mu, tag="lift", maxiter=400):
    """L-BFGS-B on F = num/Linf + mu * sum_{j in B} log(phi_j),
    phi = Lz/max(Lz), B = {0.30 <= phi <= 0.98} excluding +-5 around argmax."""
    n = len(h)
    nfft = _nfft_for(n)
    fw = np.maximum(h, 0.0).copy()
    s = fw.sum()
    if s <= 0:
        return h, _knot_R(h), False
    fw /= s
    R_before = _knot_R(fw)
    x0 = fw.copy()

    def obj(x):
        if time.process_time() >= deadline:
            raise TimeoutError
        fx = np.maximum(x, 0.0)
        sx = fx.sum()
        if sx <= 0:
            return 1e10, np.zeros(n)
        fx = fx / sx
        F = np.fft.rfft(fx, nfft)
        cv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
        LL = np.concatenate(([0.0], cv, [0.0]))
        num = np.sum(LL[:-1] ** 2 + LL[:-1] * LL[1:] + LL[1:] ** 2) / 3.0
        mm = float(np.max(LL))
        if mm <= 0:
            return 1e10, np.zeros(n)
        am = int(np.argmax(LL))
        phi = LL / mm
        # band mask
        B = (phi >= 0.30) & (phi <= 0.98)
        lo = max(0, am - 5)
        hi = min(len(LL), am + 6)
        B[lo:hi] = False
        # objective: num/mm + mu * sum log(phi_j) over B
        logphi = np.log(np.maximum(phi[B], 1e-300))
        val = num / mm + mu * float(np.sum(logphi))
        # gradient of num
        dnum = _dnum_of(LL)
        gnum = _corr_with_weights(fx, dnum[1:-1])
        # gradient of mm (argmax knot)
        wmax = np.zeros_like(LL)
        wmax[am] = 1.0
        gmm = _corr_with_weights(fx, wmax[1:-1])
        # d(num/mm) = (gnum*mm - num*gmm)/mm^2
        g = (gnum * mm - num * gmm) / (mm * mm)
        # gradient of mu * sum log(phi_j) = mu * sum (dL_j/L_j - dmm/mm)
        # d/d f of L_j is corr with delta at j (via _corr_with_weights)
        # accumulate: for each j in B, weight 1/L_j on knot j, minus (1/mm) on argmax
        wband = np.zeros_like(LL)
        idxB = np.where(B)[0]
        if len(idxB) > 0:
            wband[idxB] = 1.0 / np.maximum(LL[idxB], 1e-300)
            # subtract contribution from max: sum_j (1/L_j) * (L_j/mm) * dmm = (|B|/mm)*dmm
            wband[am] -= float(len(idxB)) / mm
            gband = _corr_with_weights(fx, wband[1:-1])
            g = g + mu * gband
        g = (g - np.dot(g, fx)) / sx
        return val, g

    try:
        rem = deadline - time.process_time()
        it = min(maxiter, max(20, int(rem * 30)))
        res = minimize(obj, x0, jac=True, method='L-BFGS-B',
                       bounds=[(0, None)] * n,
                       options={'maxiter': it, 'ftol': 1e-22,
                                'gtol': 1e-16, 'maxcor': 40})
        fnew = np.maximum(res.x, 0.0)
        sn = fnew.sum()
        if sn > 0:
            fnew /= sn
            Rn = _knot_R(fnew)
            return fnew, Rn, True
    except Exception:
        pass
    return fw, R_before, False


def construct(budget_seconds, start):
    t_start = time.process_time()
    total = min(budget_seconds - 3.0, budget_seconds * 0.97)
    if total <= 0.5:
        total = max(budget_seconds * 0.5, 0.1)
    deadline = t_start + total
    hard_stop = deadline - 1.0

    start_arr = None
    start_R = -1.0
    if start is not None:
        try:
            a = np.asarray(start, dtype=float).ravel()
            a = np.maximum(a, 0.0)
            s = a.sum()
            if s > 0:
                start_arr = a / s
                start_R = _knot_R(start_arr)
        except Exception:
            start_arr = None

    N0 = 50000
    if start_arr is not None:
        N0 = len(start_arr)

    if start_arr is None:
        x = (np.arange(N0) + 0.5) / N0
        h0 = np.exp(-((x - 0.45) ** 2) / 0.03)
        start_arr = h0 / h0.sum()
        start_R = _knot_R(start_arr)

    print(f"start: R={start_R:.10f} N={N0} t={time.process_time()-t_start:.1f}s")

    best_h = start_arr.copy()
    best_R = start_R
    alt_h = None
    alt_R = -1.0

    def report(tag, h, R):
        w01, w1, w5 = _shares(h)
        mm = float(np.max(h)) / max(float(np.mean(h)), 1e-30)
        print(f"  [{tag}] R={R:.10f} shares={w01:.4f}/{w1:.4f}/{w5:.4f} "
              f"max/mean={mm:.2f} t={time.process_time()-t_start:.1f}s")

    # ===== Phase A: band-lift with annealed mu =====
    phaseA_end = t_start + total * 0.60
    mus = [1e-3, 3e-3, 1e-2, 3e-2, 1e-1]
    n_round = 0
    for mu in mus:
        if time.process_time() >= phaseA_end - 1.0:
            break
        n_round += 1
        dl = min(time.process_time() + 12.0, phaseA_end - 0.5)
        hn, Rn, ok = _band_lift(best_h, dl, t_start, mu,
                                tag=f"lift{mu:.0e}", maxiter=600)
        if ok and Rn > best_R + 1e-15:
            if Rn > best_R + 1e-12:
                alt_h, alt_R = best_h.copy(), best_R
            best_h, best_R = hn, Rn
        report(f"lift mu={mu:.0e}", best_h, best_R)

    report("after_band_lift", best_h, best_R)

    # ===== Phase B: exact-R polish (m1 + m-ladder + trim) =====
    now = time.process_time()
    if hard_stop - now > 2.0:
        hn, Rn, acc = _m1_full(best_h, min(now + 8.0, hard_stop - 0.5),
                               t_start, maxiter=5000, tag="B_m1")
        if acc and Rn > best_R + 1e-15:
            best_h, best_R = hn, Rn
        report("B_m1", best_h, best_R)

    now = time.process_time()
    if hard_stop - now > 1.5:
        hc, Rc = best_h, best_R
        for mm in [80, 25, 8, 3, 1]:
            if time.process_time() >= hard_stop - 0.5:
                break
            fm = (hc > 0)
            dl = min(time.process_time() + max(1.0,
                      (hard_stop - time.process_time()) / 3.0),
                     hard_stop - 0.5)
            hn, Rn, acc = _lbfgs_target_m(hc, dl, float(mm),
                                          maxiter=800, free_mask=fm)
            if acc and Rn > Rc + 1e-15:
                hc, Rc = hn, Rn
        if Rc > best_R + 1e-15:
            best_h, best_R = hc, Rc
        report("B_ladder", best_h, best_R)

    # Support trim at 1e-6*max + one more exact-R polish
    now = time.process_time()
    if hard_stop - now > 1.5:
        m = np.max(best_h)
        if m > 0:
            mask = best_h > 1e-6 * m
            if 50 < mask.sum() < len(best_h):
                ht = np.where(mask, best_h, 0.0)
                st = ht.sum()
                if st > 0:
                    ht /= st
                    Rt = _knot_R(ht)
                    if Rt > best_R - 1e-6:
                        hn, Rn, acc = _m1_full(ht, hard_stop - 0.5, t_start,
                                               maxiter=5000, tag="B_trim_m1")
                        if acc and Rn > best_R + 1e-15:
                            best_h, best_R = hn, Rn
                        report("B_trim", best_h, best_R)

    if best_R < start_R:
        best_h = start_arr.copy()
        best_R = start_R

    print(f"final: R={best_R:.10f} (start {start_R:.10f}, "
          f"gain {best_R-start_R:+.3e}) lift_rounds={n_round} "
          f"t={time.process_time()-t_start:.1f}s")

    if alt_h is not None and alt_R > start_R + 1e-12 and alt_R < best_R - 1e-12:
        return {"best": best_h, "alternative": alt_h}
    return best_h
