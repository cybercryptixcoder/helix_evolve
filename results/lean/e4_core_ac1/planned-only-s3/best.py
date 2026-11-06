import numpy as np
import time
import random
from scipy.optimize import minimize, least_squares


def _C(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    N = len(h)
    return 2.0 * N * np.max(np.convolve(h, h)) / (s * s)


def construct(budget_seconds, start):
    t0 = time.process_time()
    N = 1600

    def make_h(c):
        return np.clip(np.asarray(c, dtype=float), 0.0, None)

    def exact_obj(c):
        return _C(make_h(c))

    def lp_obj_grad_factory(p):
        def fg(c):
            h = np.clip(np.asarray(c, dtype=float), 0.0, None)
            s = h.sum()
            if s <= 0:
                return 1e30, np.zeros_like(c)
            conv = np.convolve(h, h)
            cp = np.power(conv, p)
            scp = cp.sum()
            if scp <= 0:
                return 1e30, np.zeros_like(c)
            norm = scp ** (1.0 / p)
            val = 2.0 * N * norm / (s * s)
            w = np.power(conv, p - 1) / (scp ** (1.0 - 1.0 / p))
            g_h = 2.0 * np.convolve(w, h[::-1])[len(h) - 1:2 * len(h) - 1]
            grad_h = 2.0 * N / (s * s) * g_h - 4.0 * N * norm / (s ** 3)
            return val, grad_h
        return fg

    def lse_obj_grad_factory(tau):
        def fg(c):
            h = np.clip(np.asarray(c, dtype=float), 0.0, None)
            s = h.sum()
            if s <= 0:
                return 1e30, np.zeros_like(c)
            conv = np.convolve(h, h)
            m = conv.max()
            e = np.exp((conv - m) / tau)
            se = e.sum()
            lse = m + tau * np.log(se)
            val = 2.0 * N * lse / (s * s)
            w = e / se
            g_h = 2.0 * np.convolve(w, h[::-1])[len(h) - 1:2 * len(h) - 1]
            grad_h = 2.0 * N / (s * s) * g_h - 4.0 * N * lse / (s ** 3)
            return val, grad_h
        return fg

    ref = None
    ref_C = np.inf
    if start is not None:
        s = np.asarray(start, dtype=float)
        if s.size > 0 and s.sum() > 0:
            ref = s.copy()
            ref_C = _C(ref)
            x_s = np.linspace(0, 1, s.size)
            x_n = np.linspace(0, 1, N)
            init = np.interp(x_n, x_s, s)
        else:
            init = np.ones(N)
    else:
        base16 = np.array([1.28894011, 1.39333361, 0.97940025, 0.72779826,
                           0.98915561, 0.05485589, 0.06227411, 0.68757259,
                           1.17863761, 1.98217381, 2.05474282, 0.85525968,
                           1.23634265, 1.01046962, 1.33994863, 1.39572973])
        x16 = np.linspace(0, 1, 16)
        x_n = np.linspace(0, 1, N)
        init = np.interp(x_n, x16, base16)

    init = np.clip(init, 1e-6, None)
    bounds = [(0.0, None)] * N

    best_c = init.copy()
    best_val = _C(init)
    if ref is not None and ref_C < best_val:
        best_c = ref.copy()
        best_val = ref_C

    # Phase 1: full-height Lp homotopy.
    ps = [16, 32, 64, 128, 256, 512, 1024, 2048]
    cc = np.clip(best_c, 1e-6, None)
    for p in ps:
        if time.process_time() - t0 > budget_seconds * 0.30:
            break
        try:
            res = minimize(lp_obj_grad_factory(p), np.clip(cc, 1e-6, None),
                           jac=True, method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': 300, 'ftol': 1e-15, 'gtol': 1e-11})
            cc = np.clip(res.x, 0.0, None)
            v = _C(cc)
            if v < best_val:
                best_val = v
                best_c = cc.copy()
        except Exception:
            break

    # Phase 2: logsumexp homotopy.
    taus = [1e-5, 3e-6, 1e-6, 3e-7, 1e-7, 3e-8, 1e-8, 3e-9, 1e-9]
    cc = np.clip(best_c, 1e-6, None)
    for tau in taus:
        if time.process_time() - t0 > budget_seconds * 0.50:
            break
        try:
            res = minimize(lse_obj_grad_factory(tau), np.clip(cc, 1e-6, None),
                           jac=True, method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': 400, 'ftol': 1e-16, 'gtol': 1e-12})
            cc = np.clip(res.x, 0.0, None)
            v = _C(cc)
            if v < best_val:
                best_val = v
                best_c = cc.copy()
        except Exception:
            break

    # Phase 3: exact-C polish.
    try:
        res = minimize(exact_obj, np.clip(best_c, 1e-6, None),
                       method='L-BFGS-B', bounds=bounds,
                       options={'maxiter': 2000, 'ftol': 1e-15, 'gtol': 1e-12})
        val = res.fun
        cand = np.clip(res.x, 0.0, None)
        if val < best_val:
            best_val = val
            best_c = cand
    except Exception:
        pass

    # Phase 4: second deeper Lp/lse cycle.
    ps2 = [64, 256, 1024, 4096, 8192]
    cc = np.clip(best_c, 1e-6, None)
    for p in ps2:
        if time.process_time() - t0 > budget_seconds * 0.68:
            break
        try:
            res = minimize(lp_obj_grad_factory(p), np.clip(cc, 1e-6, None),
                           jac=True, method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': 300, 'ftol': 1e-15, 'gtol': 1e-11})
            cc = np.clip(res.x, 0.0, None)
            v = _C(cc)
            if v < best_val:
                best_val = v
                best_c = cc.copy()
        except Exception:
            break

    taus2 = [3e-8, 1e-8, 3e-9, 1e-9, 3e-10]
    cc = np.clip(best_c, 1e-6, None)
    for tau in taus2:
        if time.process_time() - t0 > budget_seconds * 0.82:
            break
        try:
            res = minimize(lse_obj_grad_factory(tau), np.clip(cc, 1e-6, None),
                           jac=True, method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': 400, 'ftol': 1e-16, 'gtol': 1e-12})
            cc = np.clip(res.x, 0.0, None)
            v = _C(cc)
            if v < best_val:
                best_val = v
                best_c = cc.copy()
        except Exception:
            break

    # Phase 5: final exact-C polish.
    if time.process_time() - t0 < budget_seconds * 0.85:
        try:
            res = minimize(exact_obj, np.clip(best_c, 1e-6, None),
                           method='L-BFGS-B', bounds=bounds,
                           options={'maxiter': 1000, 'ftol': 1e-16, 'gtol': 1e-13})
            val = res.fun
            cand = np.clip(res.x, 0.0, None)
            if val < best_val:
                best_val = val
                best_c = cand
        except Exception:
            pass

    # EXPERIMENT: coarse-to-fine continuation with KKT polishing at each level.
    def kkt_polish(h_in, n_top=5, active_set=None, max_nfev=800):
        """Bounded KKT least_squares polish. Returns h or None."""
        h_base = np.clip(np.asarray(h_in, dtype=float), 0.0, None)
        if h_base.sum() <= 0:
            return None
        Nl = len(h_base)
        h_norm = h_base / h_base.sum()
        conv0 = np.convolve(h_norm, h_norm)
        n = conv0.size
        F = np.where(h_base > 1e-12)[0]
        if F.size == 0:
            F = np.arange(Nl)
        nF = F.size
        if active_set is None:
            k = min(n_top, n)
            idx_all = np.argpartition(conv0, n - k)[n - k:]
            top = np.sort(idx_all[np.argsort(-conv0[idx_all])][:k])
            A = [int(x) for x in top]
        else:
            A = sorted(int(x) for x in active_set)
        nA = len(A)

        def residuals(z):
            hF = z[:nF]
            m = z[nF]
            lam = z[nF + 1:nF + 1 + nA]
            mu = z[nF + 1 + nA]
            h = np.zeros(Nl)
            h[F] = hF
            conv = np.convolve(h, h)
            r = np.empty(nA + 1 + nF)
            r[:nA] = conv[A] - m
            r[nA] = hF.sum() - 1.0
            r[nA + 1] = lam.sum() - 1.0
            lam_full = np.zeros(n)
            lam_full[A] = lam
            g = 2.0 * np.convolve(lam_full, h[::-1])[Nl - 1:Nl - 1 + Nl]
            r[nA + 2:] = g[F] + mu
            return r

        def jacobian(z):
            hF = z[:nF]
            lam = z[nF + 1:nF + 1 + nA]
            h = np.zeros(Nl)
            h[F] = hF
            J = np.zeros((nA + 1 + nF, nF + 1 + nA + 1))
            for ai, kk in enumerate(A):
                for jj in range(nF):
                    j = F[jj]
                    idx = kk - j
                    if 0 <= idx < Nl:
                        J[ai, jj] = 2.0 * h[idx]
                J[ai, nF] = -1.0
            J[nA, :nF] = 1.0
            J[nA + 1, nF + 1:nF + 1 + nA] = 1.0
            for jj in range(nF):
                i = F[jj]
                s = 0.0
                for ai, kk in enumerate(A):
                    idx = kk - i
                    if 0 <= idx < Nl:
                        s += lam[ai] * 2.0 * h[idx]
                J[nA + 2 + jj, jj] = 2.0 * s
                for ai, kk in enumerate(A):
                    idx = kk - i
                    if 0 <= idx < Nl:
                        J[nA + 2 + jj, nF + 1 + ai] = 2.0 * h[idx]
                J[nA + 2 + jj, nF + 1 + nA] = 1.0
            return J

        m0 = float(conv0[A].max())
        hF0 = h_norm[F].copy()
        lam0 = np.ones(nA) / nA
        mu0 = 0.0
        z0 = np.concatenate([hF0, [m0], lam0, [mu0]])
        lb = np.concatenate([np.zeros(nF), [-np.inf],
                             np.zeros(nA), [-np.inf]])
        ub = np.concatenate([np.full(nF, np.inf), [np.inf],
                             np.full(nA, np.inf), [np.inf]])
        try:
            sol = least_squares(residuals, z0, jac=jacobian, bounds=(lb, ub),
                                method='trf', xtol=1e-15, ftol=1e-15,
                                gtol=1e-15, max_nfev=max_nfev)
        except Exception:
            return None
        resid = np.max(np.abs(residuals(sol.x)))
        if resid > 1e-9:
            return None
        z = sol.x
        hF_new = np.clip(z[:nF], 0.0, None)
        lam_new = z[nF + 1:nF + 1 + nA]
        if lam_new.min() < -1e-10:
            return None
        h_new = np.zeros(Nl)
        h_new[F] = hF_new
        if h_new.sum() <= 0:
            return None
        return h_new

    def level_refine(h_in, level_N, maxiter=300):
        """Interpolate to level_N, exact-C L-BFGS-B, then KKT polish."""
        h_in = np.clip(np.asarray(h_in, dtype=float), 0.0, None)
        if h_in.sum() <= 0:
            return None, np.inf
        x_s = np.linspace(0, 1, len(h_in))
        x_n = np.linspace(0, 1, level_N)
        h_l = np.interp(x_n, x_s, h_in)
        h_l = np.clip(h_l, 1e-8, None)
        bnds = [(0.0, None)] * level_N

        def obj(c):
            hh = np.clip(c, 0.0, None)
            s = hh.sum()
            if s <= 0:
                return 1e30
            return 2.0 * level_N * np.max(np.convolve(hh, hh)) / (s * s)

        try:
            res = minimize(obj, h_l, method='L-BFGS-B', bounds=bnds,
                           options={'maxiter': maxiter, 'ftol': 1e-15,
                                    'gtol': 1e-12})
            h_l = np.clip(res.x, 0.0, None)
        except Exception:
            pass
        v = _C(h_l)
        hk = kkt_polish(h_l, n_top=5)
        if hk is not None:
            vk = _C(hk)
            if vk < v:
                h_l = hk
                v = vk
        return h_l, v

    if time.process_time() - t0 < budget_seconds * 0.88:
        try:
            h_cur = np.clip(best_c, 0.0, None).astype(float)
            levels = [400, 800, 1200, 1600]
            for lvl in levels:
                if time.process_time() - t0 > budget_seconds * 0.94:
                    break
                h_new, v_new = level_refine(h_cur, lvl, maxiter=300)
                if h_new is None:
                    continue
                print("level", lvl, "C =", v_new)
                if v_new < best_val:
                    if lvl != N:
                        x_s = np.linspace(0, 1, lvl)
                        x_n = np.linspace(0, 1, N)
                        h_full = np.interp(x_n, x_s, h_new)
                    else:
                        h_full = h_new
                    h_full = np.clip(h_full, 0.0, None)
                    vf = _C(h_full)
                    if vf < best_val:
                        best_val = vf
                        best_c = h_full.copy()
                h_cur = h_new
            if time.process_time() - t0 < budget_seconds * 0.96:
                try:
                    res = minimize(exact_obj, np.clip(best_c, 1e-12, None),
                                   method='L-BFGS-B', bounds=bounds,
                                   options={'maxiter': 500, 'ftol': 1e-16,
                                            'gtol': 1e-13})
                    val = res.fun
                    cand = np.clip(res.x, 0.0, None)
                    if val < best_val:
                        best_val = val
                        best_c = cand
                except Exception:
                    pass
        except Exception as e:
            print("continuation failed:", e)

    # EXPERIMENT: random active-set enumeration of sizes 11..16 from top 16.
    if time.process_time() - t0 < budget_seconds * 0.92:
        try:
            h_exp = np.clip(best_c, 0.0, None).astype(float)
            if h_exp.sum() > 0:
                hn = h_exp / h_exp.sum()
                conv0 = np.convolve(hn, hn)
                n = conv0.size
                k16 = min(16, n)
                idx_all = np.argpartition(conv0, n - k16)[n - k16:]
                top16 = list(np.sort(idx_all[np.argsort(-conv0[idx_all])][:k16]))
                top16 = [int(x) for x in top16]
                top3 = top16[:3]
                rest = top16[3:]
                rng = random.Random(12345)
                best_exp_h = None
                best_exp_v = best_val
                tried = 0
                max_tries = 300
                for size in range(11, 17):
                    need = size - 3
                    if need < 0 or need > len(rest):
                        continue
                    for _ in range(max_tries):
                        if time.process_time() - t0 > budget_seconds * 0.93:
                            break
                        sub = rng.sample(rest, need)
                        A = sorted(top3 + sub)
                        tried += 1
                        hk = kkt_polish(h_exp, active_set=A)
                        if hk is None:
                            continue
                        vk = _C(hk)
                        if vk < best_exp_v:
                            best_exp_v = vk
                            best_exp_h = hk
                    if time.process_time() - t0 > budget_seconds * 0.93:
                        break
                print("active-set tried", tried, "best", best_exp_v)
                if best_exp_h is not None:
                    try:
                        res = minimize(exact_obj,
                                       np.clip(best_exp_h, 1e-12, None),
                                       method='L-BFGS-B',
                                       bounds=[(0.0, None)] * len(best_exp_h),
                                       options={'maxiter': 1000, 'ftol': 1e-16,
                                                'gtol': 1e-13})
                        cand = np.clip(res.x, 0.0, None)
                        vc = _C(cand)
                        if vc < best_exp_v:
                            best_exp_v = vc
                            best_exp_h = cand
                    except Exception:
                        pass
                    if best_exp_v < best_val:
                        best_val = best_exp_v
                        best_c = np.asarray(best_exp_h, dtype=float).copy()
        except Exception as e:
            print("active-set experiment failed:", e)

    # EXPERIMENT: larger active-set cardinality enumeration (sizes 17..24).
    if time.process_time() - t0 < budget_seconds * 0.95:
        try:
            h_exp = np.clip(best_c, 0.0, None).astype(float)
            if h_exp.sum() > 0:
                hn = h_exp / h_exp.sum()
                conv0 = np.convolve(hn, hn)
                n = conv0.size
                k30 = min(30, n)
                idx_all = np.argpartition(conv0, n - k30)[n - k30:]
                top30 = list(np.sort(idx_all[np.argsort(-conv0[idx_all])][:k30]))
                top30 = [int(x) for x in top30]
                top3 = top30[:3]
                rest = top30[3:]
                rng = random.Random(987654)
                best_big_h = None
                best_big_v = best_val
                tried_big = 0
                max_tries_big = 500
                sizes_big = list(range(17, 25))
                for _ in range(max_tries_big):
                    if time.process_time() - t0 > budget_seconds * 0.96:
                        break
                    size = rng.choice(sizes_big)
                    need = size - 3
                    if need < 0 or need > len(rest):
                        continue
                    sub = rng.sample(rest, need)
                    A = sorted(top3 + sub)
                    tried_big += 1
                    hk = kkt_polish(h_exp, active_set=A, max_nfev=600)
                    if hk is None:
                        continue
                    vk = _C(hk)
                    if vk < best_big_v:
                        best_big_v = vk
                        best_big_h = hk
                print("big active-set tried", tried_big, "best", best_big_v)
                if best_big_h is not None:
                    try:
                        res = minimize(exact_obj,
                                       np.clip(best_big_h, 1e-12, None),
                                       method='L-BFGS-B',
                                       bounds=[(0.0, None)] * len(best_big_h),
                                       options={'maxiter': 500, 'ftol': 1e-16,
                                                'gtol': 1e-13})
                        cand = np.clip(res.x, 0.0, None)
                        vc = _C(cand)
                        if vc < best_big_v:
                            best_big_v = vc
                            best_big_h = cand
                    except Exception:
                        pass
                    if best_big_v < best_val:
                        best_val = best_big_v
                        best_c = np.asarray(best_big_h, dtype=float).copy()
        except Exception as e:
            print("big active-set experiment failed:", e)

    h = make_h(best_c)

    if ref is not None and ref_C <= _C(h):
        print("kept start, C =", ref_C)
        return ref

    print("final C =", _C(h))
    return h
