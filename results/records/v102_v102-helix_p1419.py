# v10.2 seed 1: first above ThetaEvolve with RL (0.9469)
# Run: results/v102/v102-helix   program p1419   round 227   written by: deep loop   parent: p1415
# Score R = 0.9475925569591929   steps n = 50000   CPU seconds used: 140.87
# Extracted verbatim from results/v102/v102-helix/programs/ (gzipped parts);
# the model calls of that round: results/v102/v102-helix/trace/part-0023.jsonl.gz
# Its intent, as the agent wrote it: R = 1 - S/sum(phi) with phi = L/max L and S = sum_j w_j phi_j(1-phi_j) (F7). The record's remaining loss is concentrated where phi is near 0.5, and every previous phase optimised a surrogate of the ratio (Dinkelbach/LSE) or exact single-coordinate moves, never S itself. Descending S with an LSE-smo…

import numpy as np
import time
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


def _stats(h):
    conv = _conv_of(h)
    L = np.concatenate(([0.0], conv, [0.0]))
    m = np.max(L)
    if m <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    within01 = np.mean(L >= m * 0.999)
    within1 = np.mean(L >= m * 0.99)
    within5 = np.mean(L >= m * 0.95)
    return within01, within1, within5, m, np.mean(h > 0)


def _smooth_max_lbfgs(f, deadline, cs=(1e6,), maxiter=200, start_R=None,
                      verbose=False):
    n = len(f)
    nfft = _nfft_for(n)
    best = f.copy()
    best_R = _knot_R(f) if start_R is None else start_R
    for c in cs:
        if time.process_time() >= deadline - 0.3:
            break
        fw = best.copy()
        F = np.fft.rfft(fw, nfft)
        conv = np.fft.irfft(F * F, nfft)[: 2 * n - 1]
        L0 = np.concatenate(([0.0], conv, [0.0]))
        num0 = np.sum(L0[:-1] ** 2 + L0[:-1] * L0[1:] + L0[1:] ** 2) / 3.0
        m0 = np.max(L0)
        if m0 <= 0:
            continue
        beta = c / m0
        e0 = np.exp(beta * (L0 - m0))
        s0 = e0.sum()
        lse0 = m0 + np.log(s0) / beta
        lam = num0 / lse0 if lse0 > 0 else 1.0

        def obj(x, _beta=beta, _lam=lam):
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
            m = np.max(LL)
            e = np.exp(_beta * (LL - m))
            s = e.sum()
            lse = m + np.log(s) / _beta
            phi = _lam * lse - num
            w = _lam * (e / s) - _dnum_of(LL)
            g = _corr_with_weights(fx, w[1:-1])
            g = (g - np.dot(g, fx)) / sx
            return phi, g

        try:
            rem = deadline - time.process_time()
            it = min(maxiter, max(20, int(rem * 50)))
            res = minimize(obj, fw, jac=True, method='L-BFGS-B',
                           bounds=[(0, None)] * n,
                           options={'maxiter': it, 'ftol': 1e-20, 'gtol': 1e-15,
                                    'maxcor': 30})
            fnew = np.maximum(res.x, 0.0)
            s = fnew.sum()
            if s > 0:
                fnew /= s
                Rn = _knot_R(fnew)
                if Rn > best_R:
                    best_R = Rn
                    best = fnew.copy()
                else:
                    best = fnew.copy()
        except Exception:
            pass
        if verbose:
            print(f"  c={c:.0e} beta={beta:.3e} R={best_R:.10f} "
                  f"t={time.process_time():.1f}s")
    return best, best_R


def _inc_phase(h, L, R, deadline, t_start, verbose=True):
    n = len(h)
    m = 2 * n - 1
    Lfull = np.concatenate(([0.0], L, [0.0]))
    mass = h.sum()
    best_h = h.copy()
    best_L = L.copy()
    best_R = R
    total_cand = 0
    total_acc = 0
    last_print = time.process_time()

    def R_of_Lfull(Lf, mass):
        sq = np.sum(Lf[:-1] ** 2 + Lf[:-1] * Lf[1:] + Lf[1:] ** 2) / 3.0
        linf = np.max(Lf)
        if linf <= 0 or mass <= 0:
            return 0.0
        return sq / (mass * mass * linf)

    def golden(f, lo, hi, iters=24):
        gr = (np.sqrt(5.0) - 1.0) / 2.0
        a, b = lo, hi
        c = b - gr * (b - a)
        d = a + gr * (b - a)
        fc = f(c)
        fd = f(d)
        for _ in range(iters):
            if fc > fd:
                b, d, fd = d, c, fc
                c = b - gr * (b - a)
                fc = f(c)
            else:
                a, c, fc = c, d, fd
                d = a + gr * (b - a)
                fd = f(d)
        if fc > fd:
            return c, fc
        return d, fd

    def make_c(i):
        c = np.zeros(m)
        c[i:i + n] = h
        return c

    empty_count = 0
    while time.process_time() < deadline:
        Lf = Lfull
        num = np.sum(Lf[:-1] ** 2 + Lf[:-1] * Lf[1:] + Lf[1:] ** 2) / 3.0
        linf = np.max(Lf)
        if linf <= 0:
            break
        am = np.argmax(Lf)
        dnum = _dnum_of(Lf)
        dlinf = np.zeros_like(Lf)
        dlinf[am] = 1.0
        denom = mass * mass * linf
        dR_dL = (dnum * denom - num * mass * mass * dlinf) / (denom * denom)
        w_int = dR_dL[1:-1]
        g = _corr_with_weights(h, w_int)
        score = np.abs(g) * (h + 1e-12)
        order = np.argsort(-score)
        top_single = order[:4000]
        top_pairs = order[:300]

        accepted_this_pass = 0
        for idx in top_single:
            if time.process_time() >= deadline:
                break
            i = int(idx)
            hi = h[i]
            if hi <= 1e-15:
                continue
            c = make_c(i)

            def fdelta(d, _c=c, _i=i, _Lf=Lf, _mass=mass):
                Ln = _Lf.copy()
                Ln[1:-1] += 2.0 * d * _c
                Ln[2 * _i + 1] += d * d
                return R_of_Lfull(Ln, _mass + d)
            d1, R1 = golden(fdelta, 0.0, hi, 20)
            d2, R2 = golden(fdelta, 0.0, 3.0 * hi, 20)
            if R2 > R1:
                d, Rnew = d2, R2
            else:
                d, Rnew = d1, R1
            total_cand += 1
            if Rnew > best_R + 1e-15:
                h[i] += d
                Lfull[1:-1] += 2.0 * d * c
                Lfull[2 * i + 1] += d * d
                mass += d
                best_R = Rnew
                best_h = h.copy()
                best_L = Lfull[1:-1].copy()
                accepted_this_pass += 1
                total_acc += 1

        for a in range(len(top_pairs)):
            if time.process_time() >= deadline:
                break
            i = int(top_pairs[a])
            for b in range(a + 1, len(top_pairs)):
                if time.process_time() >= deadline:
                    break
                j = int(top_pairs[b])
                if i == j:
                    continue
                hi_i = h[i]
                hi_j = h[j]
                dmax = min(hi_i, hi_j)
                if dmax <= 1e-15:
                    continue
                ci = make_c(i)
                cj = make_c(j)

                def fdelta2(d, _ci=ci, _cj=cj, _i=i, _j=j, _Lf=Lfull,
                            _mass=mass):
                    Ln = _Lf.copy()
                    Ln[1:-1] += 2.0 * d * (_cj - _ci)
                    Ln[2 * _j + 1] += d * d
                    Ln[2 * _i + 1] += d * d
                    Ln[_i + _j + 1] -= 2.0 * d * d
                    return R_of_Lfull(Ln, _mass)
                d, Rnew = golden(fdelta2, 0.0, dmax, 20)
                total_cand += 1
                if Rnew > best_R + 1e-15:
                    h[i] -= d
                    h[j] += d
                    Lfull[1:-1] += 2.0 * d * (cj - ci)
                    Lfull[2 * j + 1] += d * d
                    Lfull[2 * i + 1] += d * d
                    Lfull[i + j + 1] -= 2.0 * d * d
                    best_R = Rnew
                    best_h = h.copy()
                    best_L = Lfull[1:-1].copy()
                    accepted_this_pass += 1
                    total_acc += 1

        now = time.process_time()
        if verbose and (now - last_print > 5.0 or accepted_this_pass == 0):
            w01, w1, w5, linf, frac_pos = _stats(best_h)
            print(f"inc: R={best_R:.10f} w0.1={w01*100:.2f}% "
                  f"w1={w1*100:.2f}% acc={total_acc} cand={total_cand} "
                  f"t={now-t_start:.1f}s")
            last_print = now
        if accepted_this_pass == 0:
            empty_count += 1
            if empty_count >= 2:
                break
        else:
            empty_count = 0

    return best_h, best_L, best_R, total_cand, total_acc


def _transloss_descent(h0, deadline, t_start, verbose=True):
    """Descend S = sum_j w_j phi_j (1-phi_j) with phi = L / LSE_beta(L),
    for a ladder of beta. Keep best by exact R."""
    n = len(h0)
    nfft = _nfft_for(n)
    # trapezoid weights on Lfull of length 2n+1
    Lfull_len = 2 * n + 1
    wfull = np.ones(Lfull_len)
    wfull[0] = 0.5
    wfull[-1] = 0.5

    best = h0.copy()
    best_R = _knot_R(h0)
    cur = h0.copy()

    betas = [1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
    for beta in betas:
        if time.process_time() >= deadline - 0.5:
            break
        # scale beta relative to L scale
        cv = _conv_of(cur)
        Lc = np.concatenate(([0.0], cv, [0.0]))
        mscale = np.max(Lc)
        if mscale <= 0:
            break
        b = beta / mscale

        def obj(x, _beta=b):
            if time.process_time() >= deadline:
                raise TimeoutError
            fx = np.maximum(x, 0.0)
            sx = fx.sum()
            if sx <= 0:
                return 1e10, np.zeros(n)
            fx = fx / sx
            F = np.fft.rfft(fx, nfft)
            cvi = np.fft.irfft(F * F, nfft)[:2 * n - 1]
            Lx = np.concatenate(([0.0], cvi, [0.0]))
            mx = np.max(Lx)
            e = np.exp(_beta * (Lx - mx))
            s = e.sum()
            M = mx + np.log(s) / _beta
            phi = Lx / M
            wphi = wfull * phi
            denom = wphi.sum()
            if denom <= 0:
                return 1e10, np.zeros(n)
            S = np.sum(wfull * phi * (1.0 - phi)) / denom
            # dS/dphi
            dS_dphi = (wfull * (1.0 - 2.0 * phi) / denom
                       - S * wfull / denom)
            # dphi/dL_k = (delta_jk*M - Lx_j*softmax_k)/M^2
            soft = e / s
            # dS/dL_k = sum_j dS_dphi_j * (delta_jk*M - Lx_j*soft_k)/M^2
            #         = (dS_dphi_k * M - (sum_j dS_dphi_j*Lx_j)*soft_k)/M^2
            A = np.dot(dS_dphi, Lx)
            dS_dL = (dS_dphi * M - A * soft) / (M * M)
            g = _corr_with_weights(fx, dS_dL[1:-1])
            g = (g - np.dot(g, fx)) / sx
            return S, g

        try:
            rem = deadline - time.process_time()
            it = min(400, max(30, int(rem * 30)))
            res = minimize(obj, cur, jac=True, method='L-BFGS-B',
                           bounds=[(0, None)] * n,
                           options={'maxiter': it, 'ftol': 1e-22,
                                    'gtol': 1e-16, 'maxcor': 30})
            fnew = np.maximum(res.x, 0.0)
            s = fnew.sum()
            if s > 0:
                fnew /= s
                Rn = _knot_R(fnew)
                cur = fnew
                if Rn > best_R:
                    best_R = Rn
                    best = fnew.copy()
                if verbose:
                    w01, w1, w5, linf, frac_pos = _stats(fnew)
                    # compute S at new point
                    cvn = _conv_of(fnew)
                    Ln = np.concatenate(([0.0], cvn, [0.0]))
                    mxn = np.max(Ln)
                    en = np.exp(b * (Ln - mxn))
                    Mn = mxn + np.log(en.sum()) / b
                    phin = Ln / Mn
                    Sn = (np.sum(wfull * phin * (1 - phin))
                          / np.sum(wfull * phin))
                    print(f"tl: beta={beta:.0e} R={Rn:.10f} "
                          f"best={best_R:.10f} S={Sn:.6e} "
                          f"w1={w1*100:.2f}% w0.1={w01*100:.2f}% "
                          f"t={time.process_time()-t_start:.1f}s")
        except Exception as e:
            if verbose:
                print(f"tl beta={beta:.0e} err {e}")
    return best, best_R


def construct(budget_seconds, start):
    t_start = time.process_time()
    total = min(budget_seconds - 4.0, budget_seconds * 0.97)
    if total <= 0.5:
        total = max(budget_seconds * 0.5, 0.1)
    deadline = t_start + total
    hard_stop = deadline - 4.0

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

    if start_arr is None:
        n = 4096
        x = (np.arange(n) + 0.5) / n
        h0 = np.exp(-((x - 0.45) ** 2) / 0.03)
        start_arr = h0 / h0.sum()
        start_R = _knot_R(start_arr)

    best = start_arr.copy()
    best_R = start_R
    n = len(best)

    print(f"start: R={start_R:.10f} N={n} "
          f"t={time.process_time()-t_start:.1f}s")

    # Phase 1: short smooth-max cycle loop to lock R and snapshot (20 s).
    phase1_end = min(t_start + 20.0, hard_stop - 25.0)
    cycle = 0
    while time.process_time() < phase1_end:
        cycle += 1
        t_cyc = time.process_time()
        cand = best
        cand_R = best_R
        for c in (1e6, 1e9, 1e12):
            if time.process_time() >= phase1_end - 0.5:
                break
            try:
                dl = min(phase1_end - 0.2,
                         time.process_time() + max(2.0, 4.0))
                hf, Rf = _smooth_max_lbfgs(cand, dl, cs=(c,),
                                           maxiter=100, start_R=cand_R)
                Rf2 = _knot_R(hf)
                if Rf2 > cand_R + 1e-14:
                    cand, cand_R = hf, Rf2
            except Exception:
                pass
        if cand_R > best_R + 1e-13:
            best, best_R = cand, cand_R
            adopted = "ADOPT"
        else:
            adopted = "keep"
        w01, w1, w5, linf, frac_pos = _stats(best)
        print(f"cycle {cycle}: R={best_R:.10f} w0.1={w01*100:.2f}% "
              f"w1={w1*100:.2f}% {adopted} "
              f"t={time.process_time()-t_start:.1f}s "
              f"(cyc {time.process_time()-t_cyc:.1f}s)")

    h_snap = best.copy()
    R_snap = best_R
    print(f"snapshot: R={R_snap:.10f} t={time.process_time()-t_start:.1f}s")

    # Phase 2: trans-loss descent, reserving last 25 s for inc polish.
    tl_deadline = hard_stop - 25.0
    alt_h = None
    alt_R = -1.0
    if time.process_time() < tl_deadline - 1.0:
        try:
            h_tl, R_tl = _transloss_descent(h_snap.copy(), tl_deadline,
                                            t_start, verbose=True)
            print(f"tl done: R={R_tl:.10f} t={time.process_time()-t_start:.1f}s")
            if R_tl > best_R + 1e-15:
                best = h_tl.copy()
                best_R = R_tl
            if R_tl > R_snap + 1e-15:
                alt_h = h_tl.copy()
                alt_R = R_tl
        except Exception as e:
            print(f"tl phase error: {e}")

    # Phase 3: exact incremental polish (last ~25 s).
    inc_deadline = hard_stop - 1.0
    if time.process_time() < inc_deadline - 1.0:
        try:
            L_best = _conv_of(best)
            h_inc, L_inc, R_inc, ncand, nacc = _inc_phase(
                best.copy(), L_best.copy(), best_R,
                inc_deadline, t_start, verbose=True)
            print(f"inc done: R={R_inc:.10f} cand={ncand} acc={nacc} "
                  f"t={time.process_time()-t_start:.1f}s")
            if R_inc > best_R + 1e-15:
                best = h_inc.copy()
                best_R = R_inc
            if R_inc > R_snap + 1e-15 and (alt_h is None or R_inc > alt_R):
                alt_h = h_inc.copy()
                alt_R = R_inc
        except Exception as e:
            print(f"inc phase error: {e}")

    w01, w1, w5, linf, frac_pos = _stats(best)
    print(f"final: R={best_R:.10f} vs start {start_R:.10f} "
          f"({'BEATS' if best_R > start_R + 1e-13 else 'below'}) "
          f"t={time.process_time()-t_start:.1f}s")
    print(f"final: N={len(best)} within0.1%={w01*100:.2f}% "
          f"within1%={w1*100:.2f}% within5%={w5*100:.2f}% "
          f"pos={frac_pos*100:.1f}%")

    if best_R > start_R + 1e-13:
        if alt_h is not None and alt_R > start_R + 1e-13 and alt_R < best_R - 1e-15:
            return {"best": best, "alternative": alt_h}
        return best
    if alt_h is not None and alt_R > start_R + 1e-13:
        return {"best": alt_h, "alternative": best}
    return {"best": start_arr, "alternative": best}
