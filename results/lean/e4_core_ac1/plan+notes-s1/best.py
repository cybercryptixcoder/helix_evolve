import numpy as np
import time
from scipy.optimize import minimize, lsq_linear


def _C_fft(h, L=None):
    s = h.sum()
    if s <= 0:
        return np.inf
    N = len(h)
    if L is None:
        L = 1
        while L < 2 * N:
            L *= 2
    H = np.fft.rfft(h, L)
    conv = np.fft.irfft(H * H, L)[:2 * N - 1]
    return 2.0 * N * np.max(conv) / (s * s)


def _convolve(h, L):
    H = np.fft.rfft(h, L)
    return np.fft.irfft(H * H, L)[:2 * len(h) - 1]


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 1.5

    N = 30000
    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        if s.size == 0 or not np.all(np.isfinite(s)) or s.sum() <= 0:
            s = None
    else:
        s = None

    if s is None:
        h = np.ones(N)
    else:
        s = np.maximum(s, 0.0)
        x_old = (np.arange(s.size) + 0.5) / s.size
        x_new = (np.arange(N) + 0.5) / N
        h = np.interp(x_new, x_old, s)
        if s.size != N:
            ker = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
            ker /= ker.sum()
            h = np.convolve(h, ker, mode='same')
    h = np.maximum(h, 0.0)
    if h.sum() <= 0:
        h = np.ones(N)
    h = h / h.sum()

    L = 1
    while L < 2 * N:
        L *= 2

    best = h.copy()
    bestC = _C_fft(best, L)

    eps = 1e-12

    def obj_grad(z, Trel):
        e = np.exp(z - z.max())
        S = e.sum()
        hh = e / S
        H = np.fft.rfft(hh, L)
        conv = np.fft.irfft(H * H, L)[:2 * N - 1]
        cmax = conv.max()
        M = cmax
        C = 2.0 * N * M
        T = max(Trel * cmax, 1e-30)
        w = np.exp((conv - cmax) / T)
        wsum = w.sum()
        hr = hh[::-1]
        Wc = np.fft.rfft(w, L)
        Hr = np.fft.rfft(hr, L)
        cc = np.fft.irfft(Wc * Hr, L)
        gcorr = cc[N - 1: N - 1 + N]
        dC_dh = 2.0 * N * (2.0 * gcorr / wsum - 2.0 * M)
        hd = hh * dC_dh
        sc = hd.sum()
        dC_dz = hd - hh * sc
        return C, dC_dz

    def make_obj_grad_exact(tol):
        def obj_grad_exact(z):
            e = np.exp(z - z.max())
            S = e.sum()
            hh = e / S
            H = np.fft.rfft(hh, L)
            conv = np.fft.irfft(H * H, L)[:2 * N - 1]
            cmax = conv.max()
            C = 2.0 * N * cmax
            sel = np.where(conv >= cmax * (1.0 - tol))[0]
            if sel.size == 0:
                sel = np.array([int(np.argmax(conv))])
            nsel = float(sel.size)
            acc = np.zeros(N)
            for t in sel:
                jlo = max(0, t - (N - 1))
                jhi = min(N - 1, t)
                if jhi >= jlo:
                    acc[jlo:jhi + 1] += hh[t - np.arange(jlo, jhi + 1)]
            acc /= nsel
            dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cmax)
            hd = hh * dC_dh
            sc = hd.sum()
            dC_dz = hd - hh * sc
            return C, dC_dz
        return obj_grad_exact

    def check(hh):
        return _C_fft(hh, L)

    # ---- L-BFGS-B on z with annealed softmax temperature ----
    if time.process_time() < deadline - 0.5:
        z = np.log(h + eps)
        Trels = [1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7]
        try:
            for Trel in Trels:
                if time.process_time() >= deadline - 0.4:
                    break
                res = minimize(lambda zz: obj_grad(zz, Trel), z, jac=True,
                               method='L-BFGS-B',
                               options={'maxiter': 60, 'maxfun': 150,
                                        'ftol': 1e-14, 'gtol': 1e-12})
                z = res.x
                e = np.exp(z - z.max())
                hh = e / e.sum()
                c = check(hh)
                if c < bestC:
                    best, bestC = hh.copy(), c
        except Exception:
            pass

    # ---- Adam on z with annealed Trel + EMA of iterates ----
    adam_deadline = min(deadline - 1.0, t0 + 14.5)
    if time.process_time() < adam_deadline - 0.5:
        z = np.log(best + eps)
        m = np.zeros_like(z)
        v = np.zeros_like(z)
        beta1, beta2 = 0.9, 0.999
        lr_start, lr_end = 3e-4, 1e-6
        Trels_adam = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9]
        n_seg = len(Trels_adam)
        ema_decay = 0.999
        z_ema = z.copy()
        it = 0
        adam_best = best.copy()
        adam_bestC = bestC
        t_adam0 = time.process_time()
        span = max(adam_deadline - t_adam0, 1e-9)
        try:
            while True:
                now = time.process_time()
                if now >= adam_deadline:
                    break
                frac = min(max((now - t_adam0) / span, 0.0), 1.0)
                lr = lr_end + 0.5 * (lr_start - lr_end) * (1.0 + np.cos(np.pi * frac))
                seg = min(int(frac * n_seg), n_seg - 1)
                Trel = Trels_adam[seg]
                C, g = obj_grad(z, Trel)
                it += 1
                m = beta1 * m + (1 - beta1) * g
                v = beta2 * v + (1 - beta2) * (g * g)
                mhat = m / (1 - beta1 ** it)
                vhat = v / (1 - beta2 ** it)
                z = z - lr * mhat / (np.sqrt(vhat) + 1e-8)
                z_ema = ema_decay * z_ema + (1 - ema_decay) * z
                if it % 100 == 0:
                    e = np.exp(z_ema - z_ema.max())
                    hh = e / e.sum()
                    c = check(hh)
                    if c < adam_bestC:
                        adam_bestC = c
                        adam_best = hh.copy()
        except Exception:
            pass
        for zz in (z_ema, z):
            e = np.exp(zz - zz.max())
            hh = e / e.sum()
            c = check(hh)
            if c < adam_bestC:
                adam_bestC = c
                adam_best = hh.copy()
        if adam_bestC < bestC:
            best, bestC = adam_best.copy(), adam_bestC

    # ---- dual-support EG polish ----
    total = deadline - t0

    def run_eg2(h0, eta_start, eta_end, thresh_frac, track_every, sub_frac):
        h = h0.copy()
        local_best = h.copy()
        local_bestC = check(h)
        it = 0
        sub_deadline = time.process_time() + sub_frac * max(deadline - time.process_time(), 0)
        while True:
            now = time.process_time()
            if now >= deadline or now >= sub_deadline:
                break
            frac = (now - t0) / max(total, 1e-9)
            frac = min(max(frac, 0.0), 1.0)
            eta = eta_start * (eta_end / eta_start) ** frac

            conv = _convolve(h, L)
            cmax = conv.max()
            thresh = cmax * (1.0 - thresh_frac)
            idxs = np.where(conv >= thresh)[0]
            if idxs.size > 800:
                idxs = idxs[:: max(1, idxs.size // 800)]

            grad = np.zeros(N)
            for t in idxs:
                jlo = max(0, t - (N - 1))
                jhi = min(N - 1, t)
                if jhi >= jlo:
                    grad[jlo:jhi + 1] += 2.0 * h[t - np.arange(jlo, jhi + 1)]
            grad /= max(idxs.size, 1)

            gmax = np.max(np.abs(grad))
            if gmax < 1e-14:
                break
            h = h * np.exp(-eta * grad / gmax)
            ssum = h.sum()
            if ssum <= 0 or not np.isfinite(ssum):
                break
            h = h / ssum

            it += 1
            if it % track_every == 0:
                C = check(h)
                if C < local_bestC:
                    local_bestC = C
                    local_best = h.copy()
        C = check(h)
        if C < local_bestC:
            local_bestC = C
            local_best = h.copy()
        return local_best, local_bestC

    if time.process_time() < deadline - 0.3:
        hh, cc = run_eg2(best, 0.15, 3e-5, 1.5e-4, 6, 0.85)
        if cc < bestC:
            best, bestC = hh, cc

    # ---- final L-BFGS-B polish at very low Trel ----
    if time.process_time() < deadline - 0.3:
        try:
            z = np.log(best + eps)
            res = minimize(lambda zz: obj_grad(zz, 1e-8), z, jac=True,
                           method='L-BFGS-B',
                           options={'maxiter': 60, 'maxfun': 150,
                                    'ftol': 1e-15, 'gtol': 1e-13})
            e = np.exp(res.x - res.x.max())
            hh = e / e.sum()
            c = check(hh)
            if c < bestC:
                best, bestC = hh, c
        except Exception:
            pass

    # ---- second short EG pass with much finer near-max threshold ----
    if time.process_time() < deadline - 0.5:
        hh, cc = run_eg2(best, 0.02, 1e-6, 1e-5, 4, 0.25)
        if cc < bestC:
            best, bestC = hh, cc

    # ---- EXPERIMENT: loose-to-tight active-set continuation with exact subgradient ----
    tols = [1e-6, 1e-8, 1e-10, 1e-12, 1e-14]
    if time.process_time() < deadline - 0.3:
        try:
            z = np.log(best + eps)
            for tol in tols:
                if time.process_time() >= deadline - 0.25:
                    break
                obj_exact = make_obj_grad_exact(tol)
                res = minimize(obj_exact, z, jac=True,
                               method='L-BFGS-B',
                               options={'maxiter': 60, 'maxfun': 150, 'maxcor': 50,
                                        'ftol': 1e-15, 'gtol': 1e-13})
                z = res.x
                e = np.exp(z - z.max())
                hh = e / e.sum()
                c = check(hh)
                if c < bestC:
                    best, bestC = hh.copy(), c
        except Exception:
            pass

    # ---- EXPERIMENT: p0077-style perturbed restarts after the ladder ----
    sigmas = [0.003, 0.007, 0.015, 0.03]
    smooth_ker = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
    smooth_ker /= smooth_ker.sum()
    for sigma in sigmas:
        if time.process_time() >= deadline - 0.3:
            break
        try:
            noise = np.random.randn(N)
            noise = np.convolve(noise, smooth_ker, mode='same')
            ns = noise.std()
            if ns > 0:
                noise = noise / ns
            z = np.log(best + eps) + sigma * noise
            obj_exact = make_obj_grad_exact(1e-12)
            res = minimize(obj_exact, z, jac=True,
                           method='L-BFGS-B',
                           options={'maxiter': 120, 'maxfun': 300, 'maxcor': 50,
                                    'ftol': 1e-15, 'gtol': 1e-13})
            e = np.exp(res.x - res.x.max())
            hh = e / e.sum()
            c = check(hh)
            if c < bestC:
                best, bestC = hh.copy(), c
        except Exception:
            pass

    # ---- dual-weighted active-knot gradient (helper) ----
    def dual_weighted_polish(h_cur, tol_list, maxiter=60, maxfun=150, maxcor=50):
        local_best = h_cur.copy()
        local_bestC = check(h_cur)
        for tol in tol_list:
            if time.process_time() >= deadline - 0.3:
                break
            try:
                conv = _convolve(h_cur, L)
                cmax = conv.max()
                act = np.where(conv >= cmax * (1.0 - tol))[0]
                if act.size > 128:
                    act = act[np.argsort(-conv[act])[:128]]
                    act = np.sort(act)
                if act.size < 1:
                    continue
                nA = act.size
                B = np.zeros((N, nA))
                for kk, t in enumerate(act):
                    jlo = max(0, t - (N - 1))
                    jhi = min(N - 1, t)
                    if jhi >= jlo:
                        js = np.arange(jlo, jhi + 1)
                        B[js, kk] = h_cur[t - js]
                Bc = B - B.mean(axis=0, keepdims=True)
                A = Bc
                b = np.zeros(nA)
                big = 1e3 * (np.sqrt((A * A).sum()) + 1.0)
                A2 = np.vstack([A, big * np.ones((1, nA))])
                b2 = np.concatenate([b, [big]])
                lam_res = lsq_linear(A2, b2, bounds=(0.0, np.inf),
                                     method='bvls', max_iter=200)
                lam = lam_res.x
                if lam.sum() > 0:
                    lam = lam / lam.sum()
                else:
                    lam = np.ones(nA) / nA

                def obj_grad_weighted(z):
                    e = np.exp(z - z.max())
                    S = e.sum()
                    hh = e / S
                    H = np.fft.rfft(hh, L)
                    cv = np.fft.irfft(H * H, L)[:2 * N - 1]
                    cm = cv.max()
                    C = 2.0 * N * cm
                    acc = np.zeros(N)
                    for kk, t in enumerate(act):
                        jlo = max(0, t - (N - 1))
                        jhi = min(N - 1, t)
                        if jhi >= jlo:
                            js = np.arange(jlo, jhi + 1)
                            acc[js] += lam[kk] * hh[t - js]
                    dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cm)
                    hd = hh * dC_dh
                    sc = hd.sum()
                    dC_dz = hd - hh * sc
                    return C, dC_dz

                z = np.log(h_cur + eps)
                res = minimize(obj_grad_weighted, z, jac=True,
                               method='L-BFGS-B',
                               options={'maxiter': maxiter, 'maxfun': maxfun,
                                        'maxcor': maxcor, 'ftol': 1e-15, 'gtol': 1e-13})
                e = np.exp(res.x - res.x.max())
                hh = e / e.sum()
                c = check(hh)
                if c < local_bestC:
                    local_bestC = c
                    local_best = hh.copy()
                    h_cur = hh.copy()
            except Exception:
                continue
        return local_best, local_bestC

    # ---- dual-weighted active-knot gradient ----
    if time.process_time() < deadline - 0.4:
        try:
            h_cur = best.copy()
            conv = _convolve(h_cur, L)
            cmax = conv.max()
            act = np.where(conv >= cmax * (1.0 - 1e-10))[0]
            if act.size > 128:
                act = act[np.argsort(-conv[act])[:128]]
                act = np.sort(act)
            if act.size >= 1:
                nA = act.size
                B = np.zeros((N, nA))
                for kk, t in enumerate(act):
                    jlo = max(0, t - (N - 1))
                    jhi = min(N - 1, t)
                    if jhi >= jlo:
                        js = np.arange(jlo, jhi + 1)
                        B[js, kk] = h_cur[t - js]
                Bc = B - B.mean(axis=0, keepdims=True)
                A = Bc
                b = np.zeros(nA)
                big = 1e3 * (np.sqrt((A * A).sum()) + 1.0)
                A2 = np.vstack([A, big * np.ones((1, nA))])
                b2 = np.concatenate([b, [big]])
                lam_res = lsq_linear(A2, b2, bounds=(0.0, np.inf),
                                     method='bvls', max_iter=200)
                lam = lam_res.x
                if lam.sum() > 0:
                    lam = lam / lam.sum()
                else:
                    lam = np.ones(nA) / nA

                def obj_grad_weighted(z):
                    e = np.exp(z - z.max())
                    S = e.sum()
                    hh = e / S
                    H = np.fft.rfft(hh, L)
                    cv = np.fft.irfft(H * H, L)[:2 * N - 1]
                    cm = cv.max()
                    C = 2.0 * N * cm
                    acc = np.zeros(N)
                    for kk, t in enumerate(act):
                        jlo = max(0, t - (N - 1))
                        jhi = min(N - 1, t)
                        if jhi >= jlo:
                            js = np.arange(jlo, jhi + 1)
                            acc[js] += lam[kk] * hh[t - js]
                    dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cm)
                    hd = hh * dC_dh
                    sc = hd.sum()
                    dC_dz = hd - hh * sc
                    return C, dC_dz

                z = np.log(h_cur + eps)
                res = minimize(obj_grad_weighted, z, jac=True,
                               method='L-BFGS-B',
                               options={'maxiter': 40, 'maxfun': 100, 'maxcor': 50,
                                        'ftol': 1e-15, 'gtol': 1e-13})
                e = np.exp(res.x - res.x.max())
                hh = e / e.sum()
                c = check(hh)
                if c < bestC:
                    best, bestC = hh.copy(), c
        except Exception:
            pass

    # ---- coarse-noise restarts + dual-weighted polish ----
    gk = 33
    gx = np.arange(gk) - (gk - 1) / 2.0
    gker = np.exp(-0.5 * (gx / 8.0) ** 2)
    gker /= gker.sum()
    coarse_sigmas = [0.03, 0.015, 0.007]
    tol_ladder = [1e-8, 1e-10, 1e-12, 1e-14]
    for sigma in coarse_sigmas:
        if time.process_time() >= deadline - 0.5:
            break
        try:
            noise = np.random.randn(N)
            noise = np.convolve(noise, gker, mode='same')
            ns = noise.std()
            if ns > 0:
                noise = noise / ns
            z = np.log(best + eps) + sigma * noise
            e = np.exp(z - z.max())
            h_start = e / e.sum()
            hh, cc = dual_weighted_polish(h_start, tol_ladder,
                                          maxiter=60, maxfun=150, maxcor=50)
            if cc < bestC:
                best, bestC = hh.copy(), cc
        except Exception:
            pass

    # ---- symmetry-enforced optimization ----
    if time.process_time() < deadline - 0.4:
        try:
            h_sym = 0.5 * (best + best[::-1])
            h_sym = np.maximum(h_sym, 0.0)
            if h_sym.sum() > 0:
                h_sym = h_sym / h_sym.sum()
                M = (N + 1) // 2

                def mirror(zh):
                    full = np.empty(N)
                    full[:M] = zh
                    full[M:] = zh[:N - M][::-1]
                    return full

                def obj_grad_sym(zh, tol):
                    zfull = mirror(zh)
                    e = np.exp(zfull - zfull.max())
                    S = e.sum()
                    hh = e / S
                    H = np.fft.rfft(hh, L)
                    conv = np.fft.irfft(H * H, L)[:2 * N - 1]
                    cmax = conv.max()
                    C = 2.0 * N * cmax
                    sel = np.where(conv >= cmax * (1.0 - tol))[0]
                    if sel.size == 0:
                        sel = np.array([int(np.argmax(conv))])
                    nsel = float(sel.size)
                    acc = np.zeros(N)
                    for t in sel:
                        jlo = max(0, t - (N - 1))
                        jhi = min(N - 1, t)
                        if jhi >= jlo:
                            acc[jlo:jhi + 1] += hh[t - np.arange(jlo, jhi + 1)]
                    acc /= nsel
                    dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cmax)
                    hd = hh * dC_dh
                    sc = hd.sum()
                    dC_dz_full = hd - hh * sc
                    g = dC_dz_full[:M].copy()
                    g[:N - M] += dC_dz_full[M:][::-1]
                    return C, g

                zh = np.log(h_sym[:M] + eps)
                sym_tols = [1e-8, 1e-10, 1e-12, 1e-14]
                sym_best = h_sym.copy()
                sym_bestC = check(h_sym)
                for tol in sym_tols:
                    if time.process_time() >= deadline - 0.25:
                        break
                    res = minimize(lambda zz: obj_grad_sym(zz, tol), zh, jac=True,
                                   method='L-BFGS-B',
                                   options={'maxiter': 80, 'maxfun': 200, 'maxcor': 50,
                                            'ftol': 1e-15, 'gtol': 1e-13})
                    zh = res.x
                    zfull = mirror(zh)
                    e = np.exp(zfull - zfull.max())
                    hh = e / e.sum()
                    c = check(hh)
                    if c < sym_bestC:
                        sym_bestC = c
                        sym_best = hh.copy()
                if sym_bestC < bestC:
                    best, bestC = sym_best.copy(), sym_bestC
        except Exception:
            pass

    # ---- dual-weighted polish on symmetric result ----
    if time.process_time() < deadline - 0.4:
        try:
            h_cur = best.copy()
            conv = _convolve(h_cur, L)
            cmax = conv.max()
            act = np.where(conv >= cmax * (1.0 - 1e-10))[0]
            if act.size > 256:
                act = act[np.argsort(-conv[act])[:256]]
                act = np.sort(act)
            if act.size >= 1:
                nA = act.size
                B = np.zeros((N, nA))
                for kk, t in enumerate(act):
                    jlo = max(0, t - (N - 1))
                    jhi = min(N - 1, t)
                    if jhi >= jlo:
                        js = np.arange(jlo, jhi + 1)
                        B[js, kk] = h_cur[t - js]
                Bc = B - B.mean(axis=0, keepdims=True)
                A = Bc
                b = np.zeros(nA)
                big = 1e3 * (np.sqrt((A * A).sum()) + 1.0)
                A2 = np.vstack([A, big * np.ones((1, nA))])
                b2 = np.concatenate([b, [big]])
                lam_res = lsq_linear(A2, b2, bounds=(0.0, np.inf),
                                     method='bvls', max_iter=200)
                lam = lam_res.x
                if lam.sum() > 0:
                    lam = lam / lam.sum()
                else:
                    lam = np.ones(nA) / nA

                def obj_grad_weighted2(z):
                    e = np.exp(z - z.max())
                    S = e.sum()
                    hh = e / S
                    H = np.fft.rfft(hh, L)
                    cv = np.fft.irfft(H * H, L)[:2 * N - 1]
                    cm = cv.max()
                    C = 2.0 * N * cm
                    acc = np.zeros(N)
                    for kk, t in enumerate(act):
                        jlo = max(0, t - (N - 1))
                        jhi = min(N - 1, t)
                        if jhi >= jlo:
                            js = np.arange(jlo, jhi + 1)
                            acc[js] += lam[kk] * hh[t - js]
                    dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cm)
                    hd = hh * dC_dh
                    sc = hd.sum()
                    dC_dz = hd - hh * sc
                    return C, dC_dz

                z = np.log(h_cur + eps)
                dw_best = h_cur.copy()
                dw_bestC = check(h_cur)
                for tol in tol_ladder:
                    if time.process_time() >= deadline - 0.25:
                        break
                    res = minimize(obj_grad_weighted2, z, jac=True,
                                   method='L-BFGS-B',
                                   options={'maxiter': 60, 'maxfun': 150, 'maxcor': 50,
                                            'ftol': 1e-15, 'gtol': 1e-13})
                    z = res.x
                    e = np.exp(z - z.max())
                    hh = e / e.sum()
                    c = check(hh)
                    if c < dw_bestC:
                        dw_bestC = c
                        dw_best = hh.copy()

                # re-symmetrize and final mirrored L-BFGS-B
                h_sym2 = 0.5 * (dw_best + dw_best[::-1])
                h_sym2 = np.maximum(h_sym2, 0.0)
                if h_sym2.sum() > 0:
                    h_sym2 = h_sym2 / h_sym2.sum()
                    M = (N + 1) // 2

                    def mirror2(zh):
                        full = np.empty(N)
                        full[:M] = zh
                        full[M:] = zh[:N - M][::-1]
                        return full

                    def obj_grad_sym2(zh, tol):
                        zfull = mirror2(zh)
                        e = np.exp(zfull - zfull.max())
                        S = e.sum()
                        hh = e / S
                        H = np.fft.rfft(hh, L)
                        conv = np.fft.irfft(H * H, L)[:2 * N - 1]
                        cmax = conv.max()
                        C = 2.0 * N * cmax
                        sel = np.where(conv >= cmax * (1.0 - tol))[0]
                        if sel.size == 0:
                            sel = np.array([int(np.argmax(conv))])
                        nsel = float(sel.size)
                        acc = np.zeros(N)
                        for t in sel:
                            jlo = max(0, t - (N - 1))
                            jhi = min(N - 1, t)
                            if jhi >= jlo:
                                acc[jlo:jhi + 1] += hh[t - np.arange(jlo, jhi + 1)]
                        acc /= nsel
                        dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cmax)
                        hd = hh * dC_dh
                        sc = hd.sum()
                        dC_dz_full = hd - hh * sc
                        g = dC_dz_full[:M].copy()
                        g[:N - M] += dC_dz_full[M:][::-1]
                        return C, g

                    zh = np.log(h_sym2[:M] + eps)
                    sym2_best = h_sym2.copy()
                    sym2_bestC = check(h_sym2)
                    for tol in [1e-10, 1e-12, 1e-14]:
                        if time.process_time() >= deadline - 0.2:
                            break
                        res = minimize(lambda zz: obj_grad_sym2(zz, tol), zh, jac=True,
                                       method='L-BFGS-B',
                                       options={'maxiter': 60, 'maxfun': 150, 'maxcor': 50,
                                                'ftol': 1e-15, 'gtol': 1e-13})
                        zh = res.x
                        zfull = mirror2(zh)
                        e = np.exp(zfull - zfull.max())
                        hh = e / e.sum()
                        c = check(hh)
                        if c < sym2_bestC:
                            sym2_bestC = c
                            sym2_best = hh.copy()
                    if sym2_bestC < bestC:
                        best, bestC = sym2_best.copy(), sym2_bestC
        except Exception:
            pass

    # ---- direct nonnegative half-height optimization under symmetry ----
    if time.process_time() < deadline - 0.4:
        try:
            h_sym = 0.5 * (best + best[::-1])
            h_sym = np.maximum(h_sym, 0.0)
            if h_sym.sum() > 0:
                h_sym = h_sym / h_sym.sum()
                M = (N + 1) // 2

                def mirror_q(q):
                    full = np.empty(N)
                    full[:M] = q
                    full[M:] = q[:N - M][::-1]
                    return full

                def obj_grad_q(q, tol):
                    hfull = mirror_q(q)
                    ssum = hfull.sum()
                    if ssum <= 0:
                        return 1e10, np.zeros(M)
                    hh = hfull / ssum
                    H = np.fft.rfft(hh, L)
                    conv = np.fft.irfft(H * H, L)[:2 * N - 1]
                    cmax = conv.max()
                    C = 2.0 * N * cmax
                    sel = np.where(conv >= cmax * (1.0 - tol))[0]
                    if sel.size == 0:
                        sel = np.array([int(np.argmax(conv))])
                    nsel = float(sel.size)
                    acc = np.zeros(N)
                    for t in sel:
                        jlo = max(0, t - (N - 1))
                        jhi = min(N - 1, t)
                        if jhi >= jlo:
                            acc[jlo:jhi + 1] += hh[t - np.arange(jlo, jhi + 1)]
                    acc /= nsel
                    dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cmax)
                    hd = hh * dC_dh
                    sc = hd.sum()
                    dC_dz_full = hd - hh * sc
                    g = dC_dz_full[:M].copy()
                    g[:N - M] += dC_dz_full[M:][::-1]
                    return C, g

                q = h_sym[:M].copy()
                q = np.maximum(q, 1e-12)
                q_best = h_sym.copy()
                q_bestC = check(h_sym)
                q_tols = [1e-6, 1e-8, 1e-10, 1e-12, 1e-14]
                for tol in q_tols:
                    if time.process_time() >= deadline - 0.3:
                        break
                    res = minimize(lambda qq: obj_grad_q(qq, tol), q, jac=True,
                                   method='L-BFGS-B',
                                   bounds=[(0.0, None)] * M,
                                   options={'maxiter': 60, 'maxfun': 150, 'maxcor': 50,
                                            'ftol': 1e-15, 'gtol': 1e-13})
                    q = np.maximum(res.x, 0.0)
                    hfull = mirror_q(q)
                    if hfull.sum() > 0:
                        hh = hfull / hfull.sum()
                        c = check(hh)
                        if c < q_bestC:
                            q_bestC = c
                            q_best = hh.copy()
                if q_bestC < bestC:
                    best, bestC = q_best.copy(), q_bestC

                hh, cc = dual_weighted_polish(best, tol_ladder,
                                              maxiter=60, maxfun=150, maxcor=50)
                if cc < bestC:
                    best, bestC = hh.copy(), cc
        except Exception:
            pass

    # ================= PLANNED EXPERIMENT =================
    # Half-resolution (N2=15000) cheap-basin restart, then full-N loop.
    def _half_res_restart(best_h):
        N2 = N // 2
        L2 = 1
        while L2 < 2 * N2:
            L2 *= 2
        h2 = 0.5 * (best_h[0::2] + best_h[1::2])[:N2]
        h2 = np.maximum(h2, 0.0)
        if h2.sum() <= 0:
            return best_h
        h2 = h2 / h2.sum()
        best2 = h2.copy()
        best2C = _C_fft(best2, L2)

        M2 = (N2 + 1) // 2

        def mirror2(q):
            full = np.empty(N2)
            full[:M2] = q
            full[M2:] = q[:N2 - M2][::-1]
            return full

        def obj_grad_q2(q, tol):
            hfull = mirror2(q)
            ssum = hfull.sum()
            if ssum <= 0:
                return 1e10, np.zeros(M2)
            hh = hfull / ssum
            H = np.fft.rfft(hh, L2)
            conv = np.fft.irfft(H * H, L2)[:2 * N2 - 1]
            cmax = conv.max()
            C = 2.0 * N2 * cmax
            sel = np.where(conv >= cmax * (1.0 - tol))[0]
            if sel.size == 0:
                sel = np.array([int(np.argmax(conv))])
            nsel = float(sel.size)
            acc = np.zeros(N2)
            for t in sel:
                jlo = max(0, t - (N2 - 1))
                jhi = min(N2 - 1, t)
                if jhi >= jlo:
                    acc[jlo:jhi + 1] += hh[t - np.arange(jlo, jhi + 1)]
            acc /= nsel
            dC_dh = 2.0 * N2 * (2.0 * acc - 2.0 * cmax)
            hd = hh * dC_dh
            sc = hd.sum()
            dC_dz_full = hd - hh * sc
            g = dC_dz_full[:M2].copy()
            g[:N2 - M2] += dC_dz_full[M2:][::-1]
            return C, g

        def dual_weighted_polish2(h_cur, tol_list, maxiter=60, maxfun=150, maxcor=50):
            local_best = h_cur.copy()
            local_bestC = _C_fft(h_cur, L2)
            for tol in tol_list:
                if time.process_time() >= deadline - 0.3:
                    break
                try:
                    conv = _convolve(h_cur, L2)
                    cmax = conv.max()
                    act = np.where(conv >= cmax * (1.0 - tol))[0]
                    if act.size > 128:
                        act = act[np.argsort(-conv[act])[:128]]
                        act = np.sort(act)
                    if act.size < 1:
                        continue
                    nA = act.size
                    B = np.zeros((N2, nA))
                    for kk, t in enumerate(act):
                        jlo = max(0, t - (N2 - 1))
                        jhi = min(N2 - 1, t)
                        if jhi >= jlo:
                            js = np.arange(jlo, jhi + 1)
                            B[js, kk] = h_cur[t - js]
                    Bc = B - B.mean(axis=0, keepdims=True)
                    A = Bc
                    b = np.zeros(nA)
                    big = 1e3 * (np.sqrt((A * A).sum()) + 1.0)
                    A2 = np.vstack([A, big * np.ones((1, nA))])
                    b2 = np.concatenate([b, [big]])
                    lam_res = lsq_linear(A2, b2, bounds=(0.0, np.inf),
                                         method='bvls', max_iter=200)
                    lam = lam_res.x
                    if lam.sum() > 0:
                        lam = lam / lam.sum()
                    else:
                        lam = np.ones(nA) / nA

                    def obj_grad_weighted(z):
                        e = np.exp(z - z.max())
                        S = e.sum()
                        hh = e / S
                        H = np.fft.rfft(hh, L2)
                        cv = np.fft.irfft(H * H, L2)[:2 * N2 - 1]
                        cm = cv.max()
                        C = 2.0 * N2 * cm
                        acc = np.zeros(N2)
                        for kk, t in enumerate(act):
                            jlo = max(0, t - (N2 - 1))
                            jhi = min(N2 - 1, t)
                            if jhi >= jlo:
                                js = np.arange(jlo, jhi + 1)
                                acc[js] += lam[kk] * hh[t - js]
                        dC_dh = 2.0 * N2 * (2.0 * acc - 2.0 * cm)
                        hd = hh * dC_dh
                        sc = hd.sum()
                        dC_dz = hd - hh * sc
                        return C, dC_dz

                    z = np.log(h_cur + eps)
                    res = minimize(obj_grad_weighted, z, jac=True,
                                   method='L-BFGS-B',
                                   options={'maxiter': maxiter, 'maxfun': maxfun,
                                            'maxcor': maxcor, 'ftol': 1e-15, 'gtol': 1e-13})
                    e = np.exp(res.x - res.x.max())
                    hh = e / e.sum()
                    c = _C_fft(hh, L2)
                    if c < local_bestC:
                        local_bestC = c
                        local_best = hh.copy()
                        h_cur = hh.copy()
                except Exception:
                    continue
            return local_best, local_bestC

        # 4 cycles of symmetrize + half-height L-BFGS-B with tol ladder
        for cycle in range(4):
            if time.process_time() >= deadline - 0.6:
                break
            h_sym = 0.5 * (best2 + best2[::-1])
            h_sym = np.maximum(h_sym, 0.0)
            if h_sym.sum() <= 0:
                break
            h_sym = h_sym / h_sym.sum()
            q = np.maximum(h_sym[:M2].copy(), 1e-12)
            for tol in [1e-8, 1e-10, 1e-12]:
                if time.process_time() >= deadline - 0.5:
                    break
                try:
                    res = minimize(lambda qq: obj_grad_q2(qq, tol), q, jac=True,
                                   method='L-BFGS-B',
                                   bounds=[(0.0, None)] * M2,
                                   options={'maxiter': 60, 'maxfun': 150, 'maxcor': 50,
                                            'ftol': 1e-15, 'gtol': 1e-13})
                    q = np.maximum(res.x, 0.0)
                    hfull = mirror2(q)
                    if hfull.sum() > 0:
                        hh = hfull / hfull.sum()
                        c = _C_fft(hh, L2)
                        if c < best2C:
                            best2C = c
                            best2 = hh.copy()
                except Exception:
                    pass
            # one dual-weighted polish per cycle
            if time.process_time() < deadline - 0.5:
                try:
                    hh, cc = dual_weighted_polish2(best2, [1e-10, 1e-12, 1e-14],
                                                   maxiter=50, maxfun=120, maxcor=50)
                    if cc < best2C:
                        best2C = cc
                        best2 = hh.copy()
                except Exception:
                    pass

        # upsample best N2 result to full N
        x_old2 = (np.arange(N2) + 0.5) / N2
        x_new = (np.arange(N) + 0.5) / N
        h_up = np.interp(x_new, x_old2, best2)
        h_up = np.maximum(h_up, 0.0)
        if h_up.sum() <= 0:
            return best_h
        h_up = h_up / h_up.sum()
        return h_up

    if time.process_time() < deadline - 0.8:
        try:
            h_up = _half_res_restart(best)
            c_up = check(h_up)
            if c_up < bestC:
                best, bestC = h_up.copy(), c_up
            # full-N q/dual inner loop on the upsampled result
            h_sym = 0.5 * (h_up + h_up[::-1])
            h_sym = np.maximum(h_sym, 0.0)
            if h_sym.sum() > 0:
                h_sym = h_sym / h_sym.sum()
                M = (N + 1) // 2

                def mirror_q(q):
                    full = np.empty(N)
                    full[:M] = q
                    full[M:] = q[:N - M][::-1]
                    return full

                def obj_grad_q(q, tol):
                    hfull = mirror_q(q)
                    ssum = hfull.sum()
                    if ssum <= 0:
                        return 1e10, np.zeros(M)
                    hh = hfull / ssum
                    H = np.fft.rfft(hh, L)
                    conv = np.fft.irfft(H * H, L)[:2 * N - 1]
                    cmax = conv.max()
                    C = 2.0 * N * cmax
                    sel = np.where(conv >= cmax * (1.0 - tol))[0]
                    if sel.size == 0:
                        sel = np.array([int(np.argmax(conv))])
                    nsel = float(sel.size)
                    acc = np.zeros(N)
                    for t in sel:
                        jlo = max(0, t - (N - 1))
                        jhi = min(N - 1, t)
                        if jhi >= jlo:
                            acc[jlo:jhi + 1] += hh[t - np.arange(jlo, jhi + 1)]
                    acc /= nsel
                    dC_dh = 2.0 * N * (2.0 * acc - 2.0 * cmax)
                    hd = hh * dC_dh
                    sc = hd.sum()
                    dC_dz_full = hd - hh * sc
                    g = dC_dz_full[:M].copy()
                    g[:N - M] += dC_dz_full[M:][::-1]
                    return C, g

                q = np.maximum(h_sym[:M].copy(), 1e-12)
                for tol in [1e-8, 1e-10, 1e-12, 1e-14]:
                    if time.process_time() >= deadline - 0.4:
                        break
                    try:
                        res = minimize(lambda qq: obj_grad_q(qq, tol), q, jac=True,
                                       method='L-BFGS-B',
                                       bounds=[(0.0, None)] * M,
                                       options={'maxiter': 60, 'maxfun': 150, 'maxcor': 50,
                                                'ftol': 1e-15, 'gtol': 1e-13})
                        q = np.maximum(res.x, 0.0)
                        hfull = mirror_q(q)
                        if hfull.sum() > 0:
                            hh = hfull / hfull.sum()
                            c = check(hh)
                            if c < bestC:
                                best, bestC = hh.copy(), c
                    except Exception:
                        pass
                if time.process_time() < deadline - 0.35:
                    try:
                        hh, cc = dual_weighted_polish(best, [1e-10, 1e-12, 1e-14],
                                                      maxiter=50, maxfun=120, maxcor=50)
                        if cc < bestC:
                            best, bestC = hh.copy(), cc
                    except Exception:
                        pass
        except Exception:
            pass

    best = np.maximum(best, 0.0)
    if best.sum() <= 0:
        best = np.ones(N)
    return best
