import numpy as np
import time
from scipy.optimize import minimize


def _Rknot(L, s):
    L2 = L * L
    num = np.sum(L2[:-1] + L[:-1] * L[1:] + L2[1:]) / 3.0
    den = s * s * L.max()
    if den <= 0:
        return 0.0
    return num / den


def _R(h):
    h = np.asarray(h, dtype=float)
    if h.sum() <= 0:
        return 0.0
    L = np.convolve(h, h)
    L = np.concatenate(([0.0], L, [0.0]))
    return _Rknot(L, h.sum())


def _compact(h, tol=1e-12):
    nz = np.nonzero(h > tol * (h.max() if h.size else 0.0) + 1e-300)[0]
    if nz.size == 0:
        return h.copy()
    return h[nz[0]:nz[-1] + 1].copy()


class _Stop(Exception):
    pass


def _nfft_for(n):
    f = 1
    while f < 3 * n:
        f *= 2
    return f


def _conv_L(h, nfft):
    H = np.fft.rfft(h, nfft)
    conv = np.fft.irfft(H * H, nfft)[:2 * h.size - 1]
    return conv, H


def _dnum_vec(L):
    dnum = np.zeros_like(L)
    dnum[:-1] += (2 * L[:-1] + L[1:]) / 3.0
    dnum[1:] += (L[:-1] + 2 * L[1:]) / 3.0
    return dnum


def _exact_lbfgs_log(h, nfft, n_iter, deadline, mask_tol=1e-9):
    n = h.size

    def fg(v):
        hh = np.exp(np.clip(v, -700.0, 700.0))
        s = hh.sum()
        if s <= 0:
            return 0.0, np.zeros_like(v)
        conv, H = _conv_L(hh, nfft)
        L = np.concatenate(([0.0], conv, [0.0]))
        L2 = L * L
        num = np.sum(L2[:-1] + L[:-1] * L[1:] + L2[1:]) / 3.0
        Lmax = L.max()
        den = s * s * Lmax
        if den <= 0:
            return 0.0, np.zeros_like(v)
        dnum = _dnum_vec(L)
        mask = L >= Lmax * (1.0 - mask_tol)
        k = max(mask.sum(), 1)
        dden = np.zeros_like(L)
        dden[mask] = (s * s) / k
        dR_dL = (dnum * den - num * dden) / (den * den)
        dR_ds = -num * 2.0 * s * Lmax / (den * den)
        gL = dR_dL[1:2 * n]
        conv2 = np.fft.irfft(np.fft.rfft(gL[::-1], nfft) * H, nfft)
        grad_h = 2.0 * conv2[2 * n - 2 - np.arange(n)] + dR_ds
        grad_v = grad_h * hh
        R = num / den
        return -R, -grad_v

    v0 = np.log(np.maximum(h, 1e-300))

    def cb(v):
        if time.process_time() >= deadline:
            raise _Stop()

    try:
        res = minimize(fg, v0, jac=True, method='L-BFGS-B', callback=cb,
                       options={'maxiter': n_iter, 'ftol': 1e-18, 'gtol': 1e-16})
        hh = np.exp(np.clip(res.x, -700.0, 700.0))
        if hh.sum() <= 0:
            return h
        return hh
    except _Stop:
        return h


def _cascade(h, deadline, iters=80, max_beta_rel=1e12):
    n = h.size
    nfft = _nfft_for(n)
    h = np.maximum(h, 1e-300)
    h = h / h.sum()

    def make_fg(beta):
        def fg(v):
            hh = np.exp(np.clip(v, -700.0, 700.0))
            s = hh.sum()
            if s <= 0:
                return 0.0, np.zeros_like(v)
            conv, H = _conv_L(hh, nfft)
            L = np.concatenate(([0.0], conv, [0.0]))
            L2 = L * L
            num = np.sum(L2[:-1] + L[:-1] * L[1:] + L2[1:]) / 3.0
            Lmax = L.max()
            z = beta * (L - Lmax)
            zmax = z.max()
            ez = np.exp(z - zmax)
            se = ez.sum()
            lse = Lmax + (np.log(se) + zmax) / beta
            if lse <= 0:
                return 0.0, np.zeros_like(v)
            den = s * s * lse
            dnum = _dnum_vec(L)
            w = ez / se
            dden = (s * s) * w
            dR_dL = (dnum * den - num * dden) / (den * den)
            dR_ds = -num * 2.0 * s * lse / (den * den)
            gL = dR_dL[1:2 * n]
            conv2 = np.fft.irfft(np.fft.rfft(gL[::-1], nfft) * H, nfft)
            grad_h = 2.0 * conv2[2 * n - 2 - np.arange(n)] + dR_ds
            grad_v = grad_h * hh
            R = num / den
            return -R, -grad_v
        return fg

    betas_rel = (1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11, 1e12, 1e13, 1e14, 1e15)
    for beta_rel in betas_rel:
        if beta_rel > max_beta_rel:
            break
        if time.process_time() >= deadline:
            break
        conv = np.convolve(h, h)
        Lmax = conv.max() if conv.size else 0.0
        if Lmax <= 0:
            break
        beta = beta_rel / (1e-3 * Lmax)
        fg = make_fg(beta)
        v0 = np.log(np.maximum(h, 1e-300))

        def cb(v, _dl=deadline):
            if time.process_time() >= _dl:
                raise _Stop()

        try:
            res = minimize(fg, v0, jac=True, method='L-BFGS-B', callback=cb,
                           options={'maxiter': iters, 'ftol': 1e-18, 'gtol': 1e-16})
            hh = np.exp(np.clip(res.x, -700.0, 700.0))
            if hh.sum() > 0:
                h = hh / hh.sum()
        except _Stop:
            break
    return h


def _shares(h):
    conv = np.convolve(h, h)
    L = np.concatenate(([0.0], conv, [0.0]))
    Lmax = L.max()
    if Lmax <= 0:
        return 0.0, 0.0, 0.0
    return (float(np.mean(L >= Lmax * 0.999)),
            float(np.mean(L >= Lmax * 0.99)),
            float(np.mean(L >= Lmax * 0.95)))


def _grad_exact(h, nfft, mask_tol=1e-6):
    n = h.size
    conv, H = _conv_L(h, nfft)
    L = np.concatenate(([0.0], conv, [0.0]))
    s = h.sum()
    if s <= 0:
        return np.zeros(n)
    L2 = L * L
    num = np.sum(L2[:-1] + L[:-1] * L[1:] + L2[1:]) / 3.0
    Lmax = L.max()
    den = s * s * Lmax
    if den <= 0:
        return np.zeros(n)
    dnum = _dnum_vec(L)
    mask = L >= Lmax * (1.0 - mask_tol)
    k = max(mask.sum(), 1)
    dden = np.zeros_like(L)
    dden[mask] = (s * s) / k
    dR_dL = (dnum * den - num * dden) / (den * den)
    dR_ds = -num * 2.0 * s * Lmax / (den * den)
    gL = dR_dL[1:2 * n]
    conv2 = np.fft.irfft(np.fft.rfft(gL[::-1], nfft) * H, nfft)
    grad_h = 2.0 * conv2[2 * n - 2 - np.arange(n)] + dR_ds
    return grad_h


def _coord_sweep(h, L, deadline, top_k=None):
    n = h.size
    nfft = _nfft_for(n)
    g = _grad_exact(h, nfft, mask_tol=1e-6)
    score = np.abs(g) * h
    order = np.argsort(-score)
    if top_k is not None and top_k < n:
        order = order[:top_k]
    s = h.sum()

    def R_from_L(Lcur, scur):
        L2 = Lcur * Lcur
        num = np.sum(L2[:-1] + Lcur[:-1] * Lcur[1:] + L2[1:]) / 3.0
        den = scur * scur * Lcur.max()
        if den <= 0:
            return 0.0
        return num / den

    Rcur = R_from_L(L, s)
    n_acc = 0
    n_proc = 0
    total_dR = 0.0
    max_dR = 0.0

    ts_scan = np.exp(np.linspace(np.log(0.30), np.log(3.0), 12))

    def eval_t(t, hi, S, i):
        d = (t - 1.0) * hi
        Ltry = L + d * S
        Ltry[2 * i + 1] += d * d
        s_try = s + d
        if s_try <= 0:
            return None, None
        return R_from_L(Ltry, s_try), d

    for i in order:
        if time.process_time() >= deadline:
            break
        i = int(i)
        hi = h[i]
        if hi <= 0:
            continue
        n_proc += 1
        S = np.zeros(2 * n + 1)
        S[i + 1:i + n + 1] += h[:n]
        b0 = max(0, i + 1 - (n - 1))
        b1 = i + 2
        S[b0:b1] += h[i + 1 - b0::-1][:b1 - b0]

        best_t = 1.0
        best_R = Rcur
        best_idx = -1
        Rs = np.empty(ts_scan.size)
        for k, t in enumerate(ts_scan):
            Rt, _ = eval_t(t, hi, S, i)
            if Rt is None:
                Rs[k] = -1.0
                continue
            Rs[k] = Rt
            if Rt > best_R:
                best_R = Rt
                best_t = t
                best_idx = k

        if best_idx >= 0:
            lo = ts_scan[max(0, best_idx - 1)]
            hi_t = ts_scan[min(ts_scan.size - 1, best_idx + 1)]
            gr = 0.6180339887498949
            c = hi_t - gr * (hi_t - lo)
            dpt = lo + gr * (hi_t - lo)
            Rc, _ = eval_t(c, hi, S, i)
            Rd, _ = eval_t(dpt, hi, S, i)
            if Rc is None:
                Rc = -1.0
            if Rd is None:
                Rd = -1.0
            for _ in range(30):
                if Rc > Rd:
                    hi_t = dpt
                    dpt = c
                    Rd = Rc
                    c = hi_t - gr * (hi_t - lo)
                    Rc, _ = eval_t(c, hi, S, i)
                    if Rc is None:
                        Rc = -1.0
                else:
                    lo = c
                    c = dpt
                    Rc = Rd
                    dpt = lo + gr * (hi_t - lo)
                    Rd, _ = eval_t(dpt, hi, S, i)
                    if Rd is None:
                        Rd = -1.0
            t_star = 0.5 * (lo + hi_t)
            R_star, _ = eval_t(t_star, hi, S, i)
            if R_star is not None and R_star > best_R:
                best_R = R_star
                best_t = t_star

        if best_t != 1.0 and best_R > Rcur + 1e-14:
            d = (best_t - 1.0) * hi
            L += d * S
            L[2 * i + 1] += d * d
            h[i] += d
            s += d
            gain = best_R - Rcur
            total_dR += gain
            if gain > max_dR:
                max_dR = gain
            Rcur = best_R
            n_acc += 1
    return n_proc, n_acc, total_dR, max_dR


def _make_masks(h):
    n = h.size
    masks = []
    order = np.argsort(h)
    for frac in (0.05, 0.10, 0.20, 0.30):
        k = int(frac * n)
        if k <= 0 or k >= n:
            continue
        hm = h.copy()
        hm[order[:k]] = 0.0
        if hm.sum() > 0:
            masks.append((f"smallest{int(frac*100)}%", hm))
    conv = np.convolve(h, h)
    amax = int(np.argmax(conv))
    if amax < n:
        half_lo, half_hi = n // 2, n
    else:
        half_lo, half_hi = 0, n // 2
    if half_hi - half_lo > 64:
        box = np.ones(64) / 64.0
        hs = np.convolve(h, box, mode='same')
        seg = hs[half_lo:half_hi]
        cmin = half_lo + int(np.argmin(seg))
    else:
        cmin = n // 2
    for frac in (0.02, 0.04, 0.08):
        w = int(frac * n)
        if w <= 0:
            continue
        lo = max(0, cmin - w // 2)
        hi = min(n, lo + w)
        hm = h.copy()
        hm[lo:hi] = 0.0
        if hm.sum() > 0:
            masks.append((f"band{int(frac*100)}%@{cmin}", hm))
    thr = 1e-3 * h.max()
    hm = h.copy()
    hm[hm < thr] = 0.0
    if hm.sum() > 0 and np.count_nonzero(hm) < n:
        masks.append(("below1e-3max", hm))
    return masks


# ---------------- Blueprint family ----------------

def _build_blueprint(params, N):
    """Build blueprint height array of length N from ~14 params.

    params = [log_p, c, phase_frac, m, log_wb, gap_frac, mirror,
              k0, k1, k2, k3, k4, k5, k6]  (k's are log10 heights at 8 knots;
              last knot fixed at 1.0 -> we use 7 free + implicit)
    """
    log_p, c, phase_frac, m, log_wb, gap_frac, mirror, \
        k0, k1, k2, k3, k4, k5, k6 = params

    p = float(np.exp(np.clip(log_p, np.log(40.0), np.log(400.0))))
    c = float(np.clip(c, 0.0, 0.95))
    phase = float(phase_frac) * p
    m = float(np.clip(m, 0.10, 0.50))
    wb = int(np.exp(np.clip(log_wb, np.log(100.0), np.log(6000.0))))
    wb = max(50, min(N // 3, wb))
    gap = int(float(np.clip(gap_frac, 0.0, 0.30)) * N)
    gap = max(0, min(N - wb - 100, gap))

    # 8 knots spanning 1e-4..1 of block height
    knot_logs = np.array([k0, k1, k2, k3, k4, k5, k6, 0.0])
    knot_logs = np.clip(knot_logs, -4.0, 0.0)
    knot_h = 10.0 ** knot_logs  # in units of block height

    idx = np.arange(N, dtype=float)

    # Decide layout: block at one end, gap beside it, envelope over rest.
    # total mass fraction m in block; envelope covers remaining (1-m).
    # We'll allocate cells: block occupies wb cells; gap occupies gap cells;
    # envelope occupies the rest (N - wb - gap).
    rest = N - wb - gap
    if rest < 10:
        rest = 10
        wb = min(wb, N - gap - 10)
        if wb < 10:
            wb = 10
        gap = max(0, N - wb - rest)

    # envelope over 'rest' cells: piecewise linear in log-height through 8 knots
    env_x = np.linspace(0.0, 1.0, rest)
    knot_x = np.linspace(0.0, 1.0, 8)
    env_log = np.interp(env_x, knot_x, knot_logs)
    env_h = 10.0 ** env_log

    # lattice modulation
    lat = 1.0 + c * np.cos(2.0 * np.pi * (idx - phase) / p)

    h = np.zeros(N)
    if mirror < 0.5:
        # block at left, gap, then envelope
        block_idx = np.arange(wb)
        h[:wb] = lat[:wb]
        # gap is zeros
        env_start = wb + gap
        h[env_start:env_start + rest] = env_h * lat[env_start:env_start + rest]
        # normalize block to have mass fraction m (block raw mass)
        block_mass = h[:wb].sum()
        env_mass = h[env_start:env_start + rest].sum()
        if block_mass > 0 and env_mass > 0:
            # scale block so block_mass/(block_mass+env_mass) = m
            # block_mass * x / (block_mass*x + env_mass) = m
            # x = m*env_mass / ((1-m)*block_mass)
            x = m * env_mass / ((1.0 - m) * block_mass)
            h[:wb] *= x
    else:
        # mirror: envelope, gap, block at right
        h[:rest] = env_h * lat[:rest]
        block_start = rest + gap
        block_end = block_start + wb
        block_end = min(block_end, N)
        h[block_start:block_end] = lat[block_start:block_end]
        block_mass = h[block_start:block_end].sum()
        env_mass = h[:rest].sum()
        if block_mass > 0 and env_mass > 0:
            x = m * env_mass / ((1.0 - m) * block_mass)
            h[block_start:block_end] *= x

    h = np.maximum(h, 0.0)
    return h


def _score_blueprint(params, N, nfft):
    h = _build_blueprint(params, N)
    s = h.sum()
    if s <= 0:
        return -1.0
    h = h / s
    conv, _ = _conv_L(h, nfft)
    L = np.concatenate(([0.0], conv, [0.0]))
    return _Rknot(L, 1.0)


def _transition_width(h):
    """Number of lags between phi=0.99 and phi=0.05 of f*f."""
    conv = np.convolve(h, h)
    if conv.size == 0:
        return 0
    Lmax = conv.max()
    if Lmax <= 0:
        return 0
    phi = conv / Lmax
    # walk from peak outward (both sides), find first lag where phi<0.99 and phi<0.05
    peak = int(np.argmax(phi))
    # right side
    i99 = None
    i05 = None
    for j in range(peak, phi.size):
        if i99 is None and phi[j] < 0.99:
            i99 = j
        if phi[j] < 0.05:
            i05 = j
            break
    if i99 is None or i05 is None:
        return 0
    return i05 - i99


def construct(budget_seconds, start):
    t0 = time.process_time()
    hard_end = t0 + 0.97 * budget_seconds
    loop_end = t0 + 0.94 * budget_seconds

    start_h = None
    start_R = None
    if start is not None and np.asarray(start).size > 0:
        st = np.asarray(start, dtype=float)
        if st.sum() > 0:
            start_h = _compact(st / st.sum())
            start_R = _R(start_h)

    best = None
    bestR = -1.0

    def offer(hh):
        nonlocal best, bestR
        if hh is None or hh.sum() <= 0:
            return False
        hh = _compact(hh / hh.sum())
        rr = _R(hh)
        if rr > bestR + 1e-13:
            best = hh.copy()
            bestR = rr
            return True
        return False

    if start_h is not None:
        offer(start_h)

    N = 49998
    nfft = _nfft_for(N)

    if best is None:
        x = np.linspace(-1, 1, N)
        offer(np.exp(-3.0 * x * x))

    # ---- Phase 1: confirm polish of start (0-8%) ----
    if best is not None and time.process_time() < loop_end - 1.0:
        pend = min(loop_end, t0 + 0.08 * budget_seconds)
        h2 = _exact_lbfgs_log(best, nfft, 200, pend, mask_tol=1e-9)
        if h2.sum() > 0:
            offer(h2 / h2.sum())
        print(f"confirm: R={bestR:.9f} elapsed={time.process_time()-t0:.1f}")

    # ---- Phase 2: mask experiments (8% - 30%) ----
    base_h = best.copy() if best is not None else None
    if base_h is not None:
        masks = _make_masks(base_h)
        print(f"masks: {len(masks)} candidates")
        n_masks = max(1, len(masks))
        mask_end = t0 + 0.30 * budget_seconds
        per_mask = max(1.0, (mask_end - time.process_time()) / n_masks)
        for mi, (name, hm) in enumerate(masks):
            if time.process_time() >= mask_end - 0.5:
                print(f"mask {name}: skipped (time)")
                break
            mstart = time.process_time()
            c_end = min(mask_end, mstart + 0.35 * per_mask)
            s_end = min(mask_end, mstart + 0.80 * per_mask)
            p_end = min(mask_end, mstart + 1.00 * per_mask)

            hc = _cascade(hm, c_end, iters=60, max_beta_rel=1e12)
            if hc.sum() > 0:
                hc = hc / hc.sum()
            else:
                hc = hm / hm.sum()

            Lc = np.convolve(hc, hc)
            Lc = np.concatenate(([0.0], Lc, [0.0]))
            top_k = min(hc.size, 20000)
            try:
                _coord_sweep(hc, Lc, s_end - 0.2, top_k=top_k)
            except Exception:
                pass
            if hc.sum() > 0:
                hc = hc / hc.sum()

            hp = _exact_lbfgs_log(hc, nfft, 200, p_end - 0.1, mask_tol=1e-9)
            if hp.sum() > 0:
                hp = hp / hp.sum()
            else:
                hp = hc

            Rc = _R(hp)
            zf = float(np.mean(hp <= 1e-12 * (hp.max() if hp.size else 1.0)))
            s01, s1, s5 = _shares(hp)
            print(f"mask {name}: R={Rc:.9f} zero={zf*100:.2f}% "
                  f"shares={s01*100:.2f}/{s1*100:.2f}/{s5*100:.2f} "
                  f"elapsed={time.process_time()-t0:.1f}")
            offer(hp)

    # ---- Phase 3: blueprint family (30% - 80%) ----
    bp_best_h = None
    bp_best_R = -1.0
    bp_best_params = None
    rng = np.random.default_rng(12345)

    stageA_end = t0 + 0.42 * budget_seconds
    stageB_end = t0 + 0.62 * budget_seconds
    stageC_end = t0 + 0.80 * budget_seconds

    # parameter box
    def sample_params():
        return np.array([
            rng.uniform(np.log(80.0), np.log(260.0)),   # log_p
            rng.uniform(0.0, 0.95),                     # c
            rng.uniform(0.0, 1.0),                      # phase_frac
            rng.uniform(0.15, 0.45),                    # m
            rng.uniform(np.log(200.0), np.log(4000.0)), # log_wb
            rng.uniform(0.0, 0.10),                     # gap_frac
            rng.uniform(0.0, 1.0),                      # mirror
            rng.uniform(-4.0, -0.5),                    # k0
            rng.uniform(-4.0, -0.5),                    # k1
            rng.uniform(-4.0, -0.5),                    # k2
            rng.uniform(-4.0, -0.5),                    # k3
            rng.uniform(-4.0, -0.5),                    # k4
            rng.uniform(-4.0, -0.5),                    # k5
            rng.uniform(-4.0, -0.5),                    # k6
        ])

    # Stage A: 200 random draws
    n_draws = 200
    scored = []
    for i in range(n_draws):
        if time.process_time() >= stageA_end - 0.5:
            break
        pr = sample_params()
        try:
            Rv = _score_blueprint(pr, N, nfft)
        except Exception:
            Rv = -1.0
        scored.append((Rv, pr))
    scored.sort(key=lambda x: -x[0])
    top5 = scored[:5]
    if top5:
        bp_best_R = top5[0][0]
        bp_best_params = top5[0][1].copy()
        bp_best_h = _build_blueprint(bp_best_params, N)
        if bp_best_h.sum() > 0:
            bp_best_h = bp_best_h / bp_best_h.sum()
    print(f"stageA: draws={len(scored)} bestR={bp_best_R:.9f} "
          f"elapsed={time.process_time()-t0:.1f}")

    # Stage B: Nelder-Mead on top 5
    from scipy.optimize import minimize as _min
    for idx in range(len(top5)):
        if time.process_time() >= stageB_end - 0.5:
            break
        pr0 = top5[idx][1]
        per = max(1.0, (stageB_end - time.process_time()) / max(1, len(top5) - idx))
        this_end = time.process_time() + per

        def neg_score(pr):
            if time.process_time() >= this_end:
                raise _Stop()
            try:
                return -_score_blueprint(pr, N, nfft)
            except _Stop:
                raise
            except Exception:
                return 0.0

        try:
            res = _min(neg_score, pr0, method='Nelder-Mead',
                       options={'maxiter': 400, 'xatol': 1e-3, 'fatol': 1e-6})
            prb = res.x
            Rb = -res.fun
        except _Stop:
            prb = pr0
            Rb = -neg_score_safe(pr0, N, nfft)
        if Rb > bp_best_R:
            bp_best_R = Rb
            bp_best_params = prb.copy()
            hb = _build_blueprint(prb, N)
            if hb.sum() > 0:
                bp_best_h = hb / hb.sum()
    print(f"stageB: bestR={bp_best_R:.9f} elapsed={time.process_time()-t0:.1f}")

    # Stage C: cascade (max_beta_rel=1e6) + coord sweep on top-3000
    if bp_best_h is not None and time.process_time() < stageC_end - 1.0:
        hc = _cascade(bp_best_h, stageC_end - 5.0, iters=60, max_beta_rel=1e6)
        if hc.sum() > 0:
            hc = hc / hc.sum()
            Rc = _R(hc)
            if Rc > bp_best_R:
                bp_best_R = Rc
                bp_best_h = hc.copy()
        # coord sweep
        if time.process_time() < stageC_end - 1.0:
            Lc = np.convolve(bp_best_h, bp_best_h)
            Lc = np.concatenate(([0.0], Lc, [0.0]))
            try:
                _coord_sweep(bp_best_h, Lc, stageC_end - 0.5, top_k=3000)
            except Exception:
                pass
            if bp_best_h.sum() > 0:
                bp_best_h = bp_best_h / bp_best_h.sum()
                Rb = _R(bp_best_h)
                if Rb > bp_best_R:
                    bp_best_R = Rb
    print(f"stageC: bestR={bp_best_R:.9f} elapsed={time.process_time()-t0:.1f}")

    # offer blueprint best
    if bp_best_h is not None and bp_best_h.sum() > 0:
        offer(bp_best_h)
        if bp_best_params is not None:
            p_fit = float(np.exp(np.clip(bp_best_params[0], np.log(40.0), np.log(400.0))))
            c_fit = float(np.clip(bp_best_params[1], 0.0, 0.95))
            m_fit = float(np.clip(bp_best_params[3], 0.10, 0.50))
            g_fit = float(np.clip(bp_best_params[5], 0.0, 0.30)) * N
            print(f"blueprint fit: p={p_fit:.1f} c={c_fit:.3f} m={m_fit:.3f} g={g_fit:.0f}")

    # ---- Phase 4: final polish of best (80-97%) ----
    if best is not None and time.process_time() < hard_end - 0.5:
        cend = hard_end - 1.0
        if cend > time.process_time():
            hc = _cascade(best, cend, iters=40, max_beta_rel=1e12)
            if hc.sum() > 0:
                offer(hc / hc.sum())
        if time.process_time() < hard_end - 0.2:
            h2 = _exact_lbfgs_log(best, nfft, 400, hard_end - 0.2, mask_tol=1e-9)
            if h2.sum() > 0:
                offer(h2 / h2.sum())
        print(f"final polish: R={bestR:.9f} elapsed={time.process_time()-t0:.1f}")

    if best is not None:
        s01, s1, s5 = _shares(best)
        tw = _transition_width(best)
        print(f"final: R={bestR:.9f} n={best.size} "
              f"shares={s01*100:.2f}/{s1*100:.2f}/{s5*100:.2f} tw={tw}")

    # Return: best if it beats start, else alternative
    if start_h is not None:
        if best is not None and bestR > start_R + 1e-9:
            return best
        if best is not None and bp_best_h is not None and bp_best_R > 0:
            # genuinely different construction: return as alternative
            return {"best": start_h, "alternative": bp_best_h}
        if best is not None and best.shape != start_h.shape:
            return {"best": start_h, "alternative": best}
        return start_h

    return best if best is not None else start_h


def neg_score_safe(pr, N, nfft):
    try:
        return -_score_blueprint(pr, N, nfft)
    except Exception:
        return 0.0
