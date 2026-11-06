import numpy as np
import time
from scipy.optimize import minimize, linprog


def _make_M(N):
    M = 1
    while M < 3 * N:
        M *= 2
    return M


def _conv(h, M=None):
    n = len(h)
    if M is None:
        M = _make_M(n)
    H = np.fft.rfft(h, M)
    c = np.fft.irfft(H * H, M)[:2 * n - 1]
    return np.maximum(c, 0)


def _C(h, M=None):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * len(h) * _conv(h, M).max() / (s * s)


def _golden(f, a, b, iters=40):
    gr = (np.sqrt(5.0) - 1.0) / 2.0
    c1 = b - gr * (b - a)
    d1 = a + gr * (b - a)
    f1 = f(c1)
    f2 = f(d1)
    for _ in range(iters):
        if f1 < f2:
            b, d1, f2 = d1, c1, f1
            c1 = b - gr * (b - a)
            f1 = f(c1)
        else:
            a, c1, f1 = c1, d1, f2
            d1 = a + gr * (b - a)
            f2 = f(d1)
    return (a + b) / 2.0


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 0.6
    phase2_deadline = t0 + budget_seconds - 4.5

    N = 23750
    u = (np.arange(N) + 0.5) / N

    h = None
    if start is not None:
        s = np.asarray(start, dtype=float).ravel()
        s = np.maximum(s, 0.0)
        if s.sum() > 0 and len(s) >= 2:
            if len(s) == N:
                h = s.copy()
            else:
                xp = (np.arange(len(s)) + 0.5) / len(s)
                h = np.interp(u, xp, s)
            h = np.maximum(h, 0.0)
            if h.sum() > 0:
                h = h / h.sum()
            else:
                h = None
    if h is None:
        h = np.cos(np.pi * (u - 0.5)) ** 2 + 1e-6
        h = h / h.sum()

    M = _make_M(N)
    idx_neg = (-np.arange(N)) % M

    best_h = h.copy()
    best_C = _C(best_h, M)
    print(f"start C={best_C:.10f} N={N}")

    # ---- Phase 1: softmax L-BFGS with adaptive beta tightening ----
    def softmax_obj_grad(z, beta_scale):
        zmax = z.max()
        e = np.exp(z - zmax)
        se = e.sum()
        hh = e / se
        H = np.fft.rfft(hh, M)
        c_full = np.fft.irfft(H * H, M)
        c = c_full[:2 * N - 1]
        cmax = c.max()
        if cmax <= 0:
            return 1e10, np.zeros_like(z)
        beta = beta_scale / (cmax + 1e-12)
        bc = beta * (c - cmax)
        w = np.exp(bc)
        sw = w.sum()
        lse = cmax + np.log(sw) / beta
        w /= sw
        W = np.fft.rfft(w, M)
        gcorr = np.fft.irfft(np.conj(W) * H, M)
        gh = gcorr[idx_neg]
        hgh = np.dot(gh, hh)
        gz = hh * (gh - hgh)
        return lse, gz

    z = np.log(np.maximum(h, 1e-12))
    z -= z.max()

    betas = [4000.0, 8000.0, 16000.0, 32000.0, 64000.0,
             128000.0, 256000.0, 512000.0, 1000000.0, 2000000.0, 4000000.0]

    for bs in betas:
        if time.process_time() > phase2_deadline - 3.0:
            break
        try:
            res = minimize(lambda zz: softmax_obj_grad(zz, bs), z,
                           method='L-BFGS-B', jac=True,
                           options={'maxiter': 400, 'ftol': 1e-18, 'gtol': 1e-15})
            if np.all(np.isfinite(res.x)):
                z = res.x.copy()
        except Exception:
            pass
        zz = z - z.max()
        e = np.exp(zz)
        hh = e / e.sum()
        Cc = _C(hh, M)
        if Cc < best_C:
            best_C = Cc
            best_h = hh.copy()
        print(f"beta={bs:.0f} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")

    # ---- Phase 2: multiplicative gradient descent with line search ----
    def make_dir(h, beta_scale=8e6):
        c = _conv(h, M)
        cmax = c.max()
        beta = beta_scale / (cmax + 1e-12)
        bc = beta * (c - cmax)
        w = np.exp(bc); w /= w.sum()
        H = np.fft.rfft(h, M)
        W = np.fft.rfft(w, M)
        gcorr = np.fft.irfft(np.conj(W) * H, M)
        gh = gcorr[idx_neg]
        hgh = np.dot(gh, h)
        g = h * (gh - hgh)
        gn = np.linalg.norm(g)
        if gn <= 0:
            return None
        return g / gn

    def phase2_step(h, span):
        d = make_dir(h)
        if d is None:
            return h, span, False
        base_C = _C(h, M)

        def f(t, h=h, d=d):
            hn = h * np.exp(t * d)
            s = hn.sum()
            if s <= 0:
                return np.inf
            return _C(hn / s, M)

        fbest = base_C
        tbest = 0.0
        for sgn in (1.0, -1.0):
            a, b = 0.0, span
            fa = f(sgn * a)
            fb = f(sgn * b)
            tries = 0
            while fb < fa and tries < 6:
                a = b
                fa = fb
                b = b * 2.0
                fb = f(sgn * b)
                tries += 1
            tt = _golden(lambda x: f(sgn * x), a, b, iters=40)
            ft = f(sgn * tt)
            if ft < fbest:
                fbest = ft
                tbest = sgn * tt

        improved = False
        if fbest < base_C - 1e-15:
            hn = h * np.exp(tbest * d)
            s = hn.sum()
            if s > 0:
                h = hn / s
                improved = True
                span = max(span, abs(tbest) * 2.0)
        if not improved:
            span *= 0.5
        return h, span, improved

    h = best_h.copy()
    span = 2e-3
    pass_no = 0
    while time.process_time() < phase2_deadline:
        pass_no += 1
        h, span, improved = phase2_step(h, span)
        Cc = _C(h, M)
        if Cc < best_C:
            best_C = Cc
            best_h = h.copy()
        if not improved and span < 1e-10:
            break
        if pass_no % 5 == 0:
            print(f"pass={pass_no} C={best_C:.10f} span={span:.2e} cpu={time.process_time()-t0:.2f}s")

    # ---- Phase 3: cluster line searches on near-max knots ----
    def cluster_dirs(h):
        c = _conv(h, M)
        cmax = c.max()
        idx = np.where(c >= 0.9995 * cmax)[0]
        if len(idx) == 0:
            return []
        clusters = []
        cur = [idx[0]]
        for k in idx[1:]:
            if k - cur[-1] <= 4 and len(cur) < 64:
                cur.append(k)
            else:
                clusters.append(cur)
                cur = [k]
        clusters.append(cur)
        dirs = []
        for K in clusters:
            d = np.zeros(N)
            for k in K:
                lo = max(0, k - N + 1)
                hi = min(N - 1, k)
                d[lo:hi + 1] += h[k - hi:k - lo + 1][::-1]
            gn = np.linalg.norm(d)
            if gn > 0:
                dirs.append(d / gn)
        return dirs

    def phase3_step(h):
        dirs = cluster_dirs(h)
        if not dirs:
            return h, False
        any_improved = False
        for d in dirs:
            if time.process_time() >= deadline:
                break

            def f(t, h=h, d=d):
                hn = h * np.exp(t * d)
                s = hn.sum()
                if s <= 0:
                    return np.inf
                return _C(hn / s, M)

            cur_C = _C(h, M)
            fbest = cur_C
            tbest = 0.0
            for sgn in (1.0, -1.0):
                a, b = 0.0, 1e-3
                fa = f(sgn * a)
                fb = f(sgn * b)
                tries = 0
                while fb < fa and tries < 7:
                    a = b
                    fa = fb
                    b = b * 2.0
                    fb = f(sgn * b)
                    tries += 1
                tt = _golden(lambda x: f(sgn * x), a, b, iters=40)
                ft = f(sgn * tt)
                if ft < fbest:
                    fbest = ft
                    tbest = sgn * tt
            if fbest < cur_C - 1e-16:
                hn = h * np.exp(tbest * d)
                s = hn.sum()
                if s > 0:
                    h = hn / s
                    any_improved = True
        return h, any_improved

    h = best_h.copy()
    cpass = 0
    while time.process_time() < deadline:
        cpass += 1
        h, any_improved = phase3_step(h)
        Cc = _C(h, M)
        if Cc < best_C:
            best_C = Cc
            best_h = h.copy()
        if cpass % 5 == 0:
            print(f"cpass={cpass} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")
        if not any_improved:
            break

    # ---- Phase 4: alternate global multiplicative and cluster polish ----
    h = best_h.copy()
    span = 2e-3
    alt = 0
    while time.process_time() < deadline:
        alt += 1
        seg_end = min(time.process_time() + 1.5, deadline)
        inner = 0
        while time.process_time() < seg_end:
            inner += 1
            h, span, improved = phase2_step(h, span)
            Cc = _C(h, M)
            if Cc < best_C:
                best_C = Cc
                best_h = h.copy()
            if not improved and span < 1e-10:
                span = 2e-3
                break
        while time.process_time() < deadline:
            h, any_improved = phase3_step(h)
            Cc = _C(h, M)
            if Cc < best_C:
                best_C = Cc
                best_h = h.copy()
            if not any_improved:
                break
        print(f"alt={alt} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")

    # ---- Phase 5: fine block-coordinate multiplicative moves ----
    h = best_h.copy()
    factors = np.array([0.995, 0.998, 1.002, 1.005])
    block_sizes = [16, 8, 4]
    sweep = 0
    while time.process_time() < deadline:
        sweep += 1
        any_improved = False
        for B in block_sizes:
            stride = max(1, B // 2)
            for st in range(0, N, stride):
                if time.process_time() >= deadline:
                    break
                en = min(N, st + B)
                if en <= st:
                    continue
                cur_C = _C(h, M)
                best_f = 1.0
                best_local = cur_C
                for fac in factors:
                    h2 = h.copy()
                    h2[st:en] *= fac
                    s = h2.sum()
                    if s <= 0:
                        continue
                    h2 /= s
                    Cc = _C(h2, M)
                    if Cc < best_local - 1e-16:
                        best_local = Cc
                        best_f = fac
                if best_f != 1.0:
                    h[st:en] *= best_f
                    s = h.sum()
                    if s > 0:
                        h /= s
                        any_improved = True
                        if best_local < best_C:
                            best_C = best_local
                            best_h = h.copy()
        if sweep % 2 == 0:
            print(f"bsweep={sweep} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")
        if not any_improved:
            break

    # ---- Phase 6: exact per-block multiplicative line searches, random offsets ----
    rng = np.random.RandomState(12345)
    h = best_h.copy()
    block_sizes6 = [64, 32, 16, 8, 4, 2, 1]
    sweep6 = 0
    while time.process_time() < deadline:
        sweep6 += 1
        any_improved = False
        for B in block_sizes6:
            stride = max(1, B // 2)
            r = int(rng.randint(0, stride))
            for st in range(r, N, stride):
                if time.process_time() >= deadline:
                    break
                en = min(N, st + B)
                if en <= st:
                    continue
                cur_C = _C(h, M)

                def f(t, h=h, st=st, en=en):
                    hn = h.copy()
                    hn[st:en] *= np.exp(t)
                    s = hn.sum()
                    if s <= 0:
                        return np.inf
                    return _C(hn / s, M)

                tt = _golden(f, -0.05, 0.05, iters=30)
                ft = f(tt)
                if ft < cur_C - 1e-15:
                    h[st:en] *= np.exp(tt)
                    s = h.sum()
                    if s > 0:
                        h /= s
                        any_improved = True
                        if ft < best_C:
                            best_C = ft
                            best_h = h.copy()
        print(f"lsweep={sweep6} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")
        if not any_improved:
            break

    # ---- Phase 7: pairwise additive mass transfers guided by active knots ----
    h = best_h.copy()
    rng7 = np.random.RandomState(98765)
    seps = (2, 4, 8)
    pair_pass = 0
    while time.process_time() < deadline:
        pair_pass += 1
        c = _conv(h, M)
        cmax = c.max()
        idx = np.where(c >= 0.9995 * cmax)[0]
        if len(idx) > 2000:
            idx = idx[rng7.choice(len(idx), 2000, replace=False)]
        if len(idx) == 0:
            break
        order = rng7.permutation(len(idx))
        any_improved = False
        for oi in order:
            if time.process_time() >= deadline:
                break
            k = int(idx[oi])
            lo = max(0, k - N + 1)
            hi = min(N - 1, k)
            if hi - lo < 2:
                continue
            for s in seps:
                if hi - lo < s:
                    continue
                i = int(rng7.randint(lo, hi - s + 1))
                j = i + s
                if i < 0 or j >= N:
                    continue
                cur_C = _C(h, M)

                def f(t, h=h, i=i, j=j):
                    hn = h.copy()
                    hn[i] += t
                    hn[j] -= t
                    if hn[i] < 0 or hn[j] < 0:
                        return np.inf
                    ssum = hn.sum()
                    if ssum <= 0:
                        return np.inf
                    return _C(hn / ssum, M)

                tt = _golden(f, -0.005, 0.005, iters=30)
                ft = f(tt)
                if ft < cur_C - 1e-15:
                    h[i] += tt
                    h[j] -= tt
                    if h[i] < 0:
                        h[i] = 0.0
                    if h[j] < 0:
                        h[j] = 0.0
                    ssum = h.sum()
                    if ssum > 0:
                        h /= ssum
                        any_improved = True
                        if ft < best_C:
                            best_C = ft
                            best_h = h.copy()
        print(f"pair={pair_pass} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")
        if not any_improved:
            break

    # ================================================================
    # Phase 8: alternate pairwise sweeps and threshold-cycled exact
    # max-ratio projected-gradient loop, WITH MOMENTUM.
    # ================================================================
    h = best_h.copy()
    cur_C = best_C

    def pairwise_block(h, cur_C, block_end):
        rng8 = np.random.RandomState(55555 + int(cur_C * 1e6) % 1000)
        seps_local = (2, 4, 8, 16)
        improved_any = False
        while time.process_time() < block_end:
            c = _conv(h, M)
            cmax = c.max()
            idx = np.where(c >= 0.9995 * cmax)[0]
            if len(idx) > 1500:
                idx = idx[rng8.choice(len(idx), 1500, replace=False)]
            if len(idx) == 0:
                break
            order = rng8.permutation(len(idx))
            any_improved = False
            for oi in order:
                if time.process_time() >= block_end:
                    break
                k = int(idx[oi])
                lo = max(0, k - N + 1)
                hi = min(N - 1, k)
                if hi - lo < 2:
                    continue
                for s in seps_local:
                    if hi - lo < s:
                        continue
                    i = int(rng8.randint(lo, hi - s + 1))
                    j = i + s
                    if i < 0 or j >= N:
                        continue
                    cur_C_loc = _C(h, M)

                    def f(t, h=h, i=i, j=j):
                        hn = h.copy()
                        hn[i] += t
                        hn[j] -= t
                        if hn[i] < 0 or hn[j] < 0:
                            return np.inf
                        ssum = hn.sum()
                        if ssum <= 0:
                            return np.inf
                        return _C(hn / ssum, M)

                    tt = _golden(f, -0.005, 0.005, iters=30)
                    ft = f(tt)
                    if ft < cur_C_loc - 1e-15:
                        h[i] += tt
                        h[j] -= tt
                        if h[i] < 0:
                            h[i] = 0.0
                        if h[j] < 0:
                            h[j] = 0.0
                        ssum = h.sum()
                        if ssum > 0:
                            h /= ssum
                            any_improved = True
                            improved_any = True
                            if ft < cur_C:
                                cur_C = ft
            if not any_improved:
                break
        return h, cur_C, improved_any

    def pg_block(h, cur_C, block_end):
        """Threshold-cycled exact max-ratio projected gradient WITH MOMENTUM."""
        improved_any = False
        thresholds = [0.99999, 0.9999, 0.999, 0.995, 0.99, 0.98, 0.95]
        t_idx = 0
        v = np.zeros(N)
        while time.process_time() < block_end:
            c = _conv(h, M)
            cmax = c.max()
            if cmax <= 0:
                break
            thr = thresholds[t_idx % len(thresholds)]
            t_idx += 1
            mask = c >= thr * cmax
            w = mask.astype(float)
            sw = w.sum()
            if sw <= 0:
                continue
            w /= sw
            W = np.fft.rfft(w, M)
            H = np.fft.rfft(h, M)
            gcorr = np.fft.irfft(np.conj(W) * H, M)
            gh = gcorr[idx_neg]
            s = h.sum()
            if s <= 0:
                break
            d = 2.0 * gh / (s * s) - 4.0 * cmax / (s * s * s)
            v = 0.5 * v + d
            vn = np.linalg.norm(v)
            if vn <= 0:
                continue
            vdir = v / vn
            scale = np.max(np.abs(h)) + 1e-12
            step0 = 0.5 * scale

            def f_step(t, h=h, vdir=vdir):
                hn = h - t * vdir
                hn = np.maximum(hn, 0.0)
                ssum = hn.sum()
                if ssum <= 0:
                    return np.inf
                return _C(hn / ssum, M)

            cur_C_loc = _C(h, M)
            a, b = 0.0, step0
            fa = cur_C_loc
            fb = f_step(b)
            tries = 0
            while fb < fa and tries < 8:
                a = b
                fa = fb
                b = b * 2.0
                fb = f_step(b)
                tries += 1
            tt = _golden(f_step, a, b, iters=30)
            ft = f_step(tt)
            if ft < cur_C_loc - 1e-16:
                hn = h - tt * vdir
                hn = np.maximum(hn, 0.0)
                ssum = hn.sum()
                if ssum > 0:
                    h = hn / ssum
                    cur_C = ft
                    improved_any = True
        return h, cur_C, improved_any

    alt8 = 0
    while time.process_time() < deadline:
        alt8 += 1
        block_end = min(time.process_time() + 2.0, deadline)
        h_try, C_try, imp = pairwise_block(h.copy(), cur_C, block_end)
        if C_try < cur_C - 1e-16:
            h = h_try
            cur_C = C_try
            if cur_C < best_C:
                best_C = cur_C
                best_h = h.copy()
        else:
            h = best_h.copy()
            cur_C = best_C
        print(f"alt8a={alt8} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")

        if time.process_time() >= deadline:
            break

        block_end = min(time.process_time() + 2.0, deadline)
        h_try, C_try, imp = pg_block(h.copy(), cur_C, block_end)
        if C_try < cur_C - 1e-16:
            h = h_try
            cur_C = C_try
            if cur_C < best_C:
                best_C = cur_C
                best_h = h.copy()
        else:
            h = best_h.copy()
            cur_C = best_C
        print(f"alt8b={alt8} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")

    # ================================================================
    # Phase 9 (experiment): small LP step on the active set.
    # Linearise (f*f)_k = sum_i h_i h_{k-i} about h: J_k,i = 2 h_{k-i}.
    # Minimise t s.t. J_k . delta - t <= -c_k for active knots,
    # sum(delta)=0, -0.02 h <= delta <= 0.02 h. Then exact-C line search
    # between h and normalize(max(h+delta,0)).
    # ================================================================
    lp_deadline = t0 + budget_seconds - 0.8
    h = best_h.copy()
    cur_C = best_C
    lp_pass = 0

    def lp_step(h, cur_C, lp_end):
        c = _conv(h, M)
        cmax = c.max()
        if cmax <= 0:
            return h, cur_C, False
        idx = np.where(c >= 0.9998 * cmax)[0]
        if len(idx) == 0:
            return h, cur_C, False
        if len(idx) > 2000:
            # keep the largest c values among active
            sel = np.argsort(c[idx])[-2000:]
            idx = idx[sel]
        K = len(idx)

        # Build sparse-ish constraint matrix A_ub (K x (N+1)) for [delta, t]:
        #   J_k . delta - t <= -c_k
        # J_k,i = 2*h[k-i] for 0 <= k-i <= N-1, i.e. i in [k-N+1, k] ∩ [0,N-1]
        A_ub = np.zeros((K, N + 1))
        b_ub = np.zeros(K)
        for r, k in enumerate(idx):
            lo = max(0, k - N + 1)
            hi = min(N - 1, k)
            # i from lo..hi, k-i from k-hi..k-lo, reversed h slice
            A_ub[r, lo:hi + 1] = 2.0 * h[k - hi:k - lo + 1][::-1]
            A_ub[r, N] = -1.0
            b_ub[r] = -c[k]

        # Equality: sum(delta) = 0
        A_eq = np.zeros((1, N + 1))
        A_eq[0, :N] = 1.0
        b_eq = np.array([0.0])

        # Bounds: -0.02 h <= delta <= 0.02 h ; t free
        lb = np.empty(N + 1)
        ub = np.empty(N + 1)
        lb[:N] = -0.02 * h
        ub[:N] = 0.02 * h
        lb[N] = -np.inf
        ub[N] = np.inf

        # Objective: minimize t
        obj = np.zeros(N + 1)
        obj[N] = 1.0

        try:
            res = linprog(obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                          bounds=list(zip(lb, ub)), method='highs')
        except Exception:
            return h, cur_C, False
        if not res.success or res.x is None:
            return h, cur_C, False
        delta = res.x[:N]
        if not np.all(np.isfinite(delta)):
            return h, cur_C, False
        if np.max(np.abs(delta)) < 1e-14:
            return h, cur_C, False

        h_new = np.maximum(h + delta, 0.0)
        s = h_new.sum()
        if s <= 0:
            return h, cur_C, False
        h_new /= s

        # Exact-C line search between h and h_new (convex combination)
        def f_lin(t, h=h, h_new=h_new):
            hn = (1.0 - t) * h + t * h_new
            ssum = hn.sum()
            if ssum <= 0:
                return np.inf
            return _C(hn / ssum, M)

        fbest = cur_C
        tbest = 0.0
        tt = _golden(f_lin, 0.0, 1.0, iters=40)
        ft = f_lin(tt)
        if ft < fbest:
            fbest = ft
            tbest = tt
        # also try slight extrapolation
        for tex in (1.2, 1.5):
            ft2 = f_lin(tex)
            if ft2 < fbest:
                fbest = ft2
                tbest = tex

        if fbest < cur_C - 1e-16:
            hn = (1.0 - tbest) * h + tbest * h_new
            ssum = hn.sum()
            if ssum > 0:
                return hn / ssum, fbest, True
        return h, cur_C, False

    while time.process_time() < lp_deadline:
        lp_pass += 1
        h_try, C_try, imp = lp_step(h.copy(), cur_C, lp_deadline)
        if imp and C_try < cur_C - 1e-16:
            h = h_try
            cur_C = C_try
            if cur_C < best_C:
                best_C = cur_C
                best_h = h.copy()
        else:
            h = best_h.copy()
            cur_C = best_C
        print(f"lp={lp_pass} C={best_C:.10f} cpu={time.process_time()-t0:.2f}s")
        if not imp:
            break

    print(f"final C={best_C:.10f}, N={len(best_h)}, cpu={time.process_time()-t0:.2f}s")
    return np.asarray(best_h, dtype=float)
