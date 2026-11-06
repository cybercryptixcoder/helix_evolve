import numpy as np
import time
from scipy.signal import fftconvolve
from scipy.optimize import minimize


def _R(h):
    h = np.asarray(h, dtype=float)
    if h.ndim != 1 or h.size == 0:
        return -1.0
    s = h.sum()
    if s <= 0 or not np.all(np.isfinite(h)) or np.any(h < 0):
        return -1.0
    L = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], L, [0.0]))
    l2 = (L[:-1]*L[:-1] + L[:-1]*L[1:] + L[1:]*L[1:]).sum() / 3.0
    m = L.max()
    if m <= 0:
        return -1.0
    return l2 / (s*s*m)


def _R_and_peak_info(h):
    h = np.asarray(h, dtype=float)
    s = h.sum()
    L = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], L, [0.0]))
    l2 = (L[:-1]*L[:-1] + L[:-1]*L[1:] + L[1:]*L[1:]).sum() / 3.0
    m = L.max()
    return l2 / (s*s*m), L, m


def _grad_z(z, tau):
    eps = 1e-6
    h = np.exp(z) - eps
    h = np.clip(h, 0.0, None)
    s = h.sum()
    if s <= 0:
        return 1e6, np.zeros_like(z)
    L = fftconvolve(h, h, mode='full')
    L = np.concatenate(([0.0], L, [0.0]))
    l2 = (L[:-1]*L[:-1] + L[:-1]*L[1:] + L[1:]*L[1:]).sum() / 3.0
    n = L.size
    dL2 = np.empty_like(L)
    dL2[0] = (2*L[0] + L[1])/3.0
    dL2[-1] = (L[-2] + 2*L[-1])/3.0
    if n > 2:
        dL2[1:-1] = (L[:-2] + 4*L[1:-1] + L[2:])/3.0
    M = L.max()
    if tau > 0:
        w = np.exp((L - M) / tau)
        Z = w.sum()
        Mp = M + tau * np.log(Z)
        dMp = w / Z
    else:
        Mp = M
        if Mp <= 0:
            return 1e6, np.zeros_like(z)
        tol = 1e-12 * max(1.0, M)
        active = L >= (M - tol)
        k = max(1, int(active.sum()))
        dMp = np.zeros_like(L)
        dMp[active] = 1.0 / k
    if Mp <= 0:
        return 1e6, np.zeros_like(z)
    R = l2 / (s*s*Mp)
    denom = s*s*Mp
    dR_dL = (dL2 * denom - l2 * s*s * dMp) / (denom*denom)
    g = dR_dL[1:-1]
    N = h.size
    corr = fftconvolve(g, h[::-1], mode='full')
    dR_dh = 2.0 * corr[N-1:2*N-1]
    dR_dz = dR_dh * (h + eps)
    return -R, -dR_dz


def _lbfgs(h, R_cur, deadline, t0, grad_fn, args, maxiter=60, maxfun=120,
           ftol=1e-15, gtol=1e-11):
    if time.process_time() - t0 > deadline:
        return h, R_cur
    eps = 1e-6
    hh = np.asarray(h, dtype=float)
    mx = hh.max()
    if mx > 0:
        hh = hh / mx
    z0 = np.log(np.clip(hh, 0.0, None) + eps)
    try:
        res = minimize(grad_fn, z0, args=args, jac=True, method='L-BFGS-B',
                       options={'maxiter': maxiter, 'maxfun': maxfun,
                                'ftol': ftol, 'gtol': gtol})
        z = res.x
    except Exception:
        return h, R_cur
    h_try = np.clip(np.exp(z) - eps, 0.0, None)
    if h_try.sum() <= 0:
        return h, R_cur
    r_try = _R(h_try)
    if r_try > R_cur:
        return h_try, r_try
    return h, R_cur


def _pair_golden(h, R_cur, deadline, t0, rng, n_idx, lo, hi, iters, idx_pool=None):
    h = h.copy()
    N = h.size
    if N < 4:
        return h, R_cur
    invphi = (np.sqrt(5.0) - 1.0) / 2.0
    for _ in range(n_idx):
        if time.process_time() - t0 > deadline:
            break
        if idx_pool is not None:
            i = int(idx_pool[rng.integers(0, idx_pool.size)])
        else:
            i = int(rng.integers(0, N))
        j = int(rng.integers(0, N))
        if i == j:
            continue

        def eval_t(t):
            trial = h.copy()
            trial[i] = max(0.0, h[i] * np.exp(t))
            trial[j] = max(0.0, h[j] * np.exp(-t))
            return _R(trial)

        a, b = -lo, hi
        c = b - invphi * (b - a)
        d = a + invphi * (b - a)
        fc = eval_t(c)
        fd = eval_t(d)
        for _ in range(iters):
            if time.process_time() - t0 > deadline:
                break
            if fc > fd:
                b, d, fd = d, c, fc
                c = b - invphi * (b - a)
                fc = eval_t(c)
            else:
                a, c, fc = c, d, fd
                d = a + invphi * (b - a)
                fd = eval_t(d)
        best_t = c if fc > fd else d
        best_f = max(fc, fd)
        if best_f > R_cur:
            h[i] = max(0.0, h[i] * np.exp(best_t))
            h[j] = max(0.0, h[j] * np.exp(-best_t))
            R_cur = best_f
    return h, R_cur


def _peak_indices(h, thresh):
    N = h.size
    L = fftconvolve(h, h, mode='full')
    M = L.max()
    if M <= 0:
        return np.arange(N)
    P = np.nonzero(L >= thresh * M)[0]
    if P.size == 0:
        P = np.array([int(np.argmax(L))])
    parts = []
    for p in P:
        c = p // 2
        parts.append(np.arange(max(0, c - 3), min(N - 1, c + 3) + 1))
    return np.unique(np.concatenate(parts))


def _ds_schedule(hL, RL, ds_deadline, t0, rng):
    def ds_left():
        return ds_deadline - (time.process_time() - t0)

    for tau in (1e-5, 3e-6, 1e-6, 3e-7):
        if ds_left() <= 0.3:
            break
        sub = min(ds_deadline, (time.process_time() - t0) + 0.9)
        hs, rs = _lbfgs(hL.copy(), RL, sub, t0, _grad_z, (tau,),
                        maxiter=70, maxfun=140)
        if rs > RL:
            hL, RL = hs, rs
    if ds_left() > 0.3:
        sub = min(ds_deadline, (time.process_time() - t0) + 0.9)
        hx, rx = _lbfgs(hL.copy(), RL, sub, t0, _grad_z, (0.0,),
                        maxiter=100, maxfun=200)
        if rx > RL:
            hL, RL = hx, rx
    if ds_left() > 0.3:
        sub = min(ds_deadline, (time.process_time() - t0) + 0.8)
        I = _peak_indices(hL, 0.99995)
        hpk, rpk = _pair_golden(hL.copy(), RL, sub, t0, rng,
                                n_idx=250, lo=0.6, hi=0.6, iters=16,
                                idx_pool=I)
        if rpk > RL:
            hL, RL = hpk, rpk
    if ds_left() > 0.2:
        sub = min(ds_deadline, (time.process_time() - t0) + 0.7)
        hpg, rpg = _pair_golden(hL.copy(), RL, sub, t0, rng,
                                n_idx=200, lo=0.6, hi=0.6, iters=14)
        if rpg > RL:
            hL, RL = hpg, rpg
    return hL, RL


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = budget_seconds - 1.2

    def time_left():
        return deadline - (time.process_time() - t0)

    best_h = None
    best_R = -1.0

    def consider(h):
        nonlocal best_h, best_R
        h = np.asarray(h, dtype=float)
        if h.ndim != 1 or h.size == 0 or h.size > 50000:
            return -1.0
        if not np.all(np.isfinite(h)) or np.any(h < 0) or h.sum() <= 0:
            return -1.0
        r = _R(h)
        if r > best_R:
            best_R = r
            best_h = h.copy()
        return r

    if start is not None:
        s0 = np.asarray(start, dtype=float)
        if (s0.ndim == 1 and s0.size > 0 and np.all(np.isfinite(s0))
                and s0.sum() > 0 and np.all(s0 >= 0)):
            consider(s0)

    if best_h is None:
        best_h = np.ones(100)
        best_R = _R(best_h)

    rng = np.random.default_rng(1234567 + int(best_h.size) * 11)

    # Tight exact subgradient polish.
    if time_left() > 1.0:
        sub = min(deadline, (time.process_time() - t0) + 2.0)
        hx, rx = _lbfgs(best_h.copy(), best_R, sub, t0, _grad_z, (0.0,),
                        maxiter=150, maxfun=300)
        consider(hx)
        print(f"exact R={best_R:.9f} t={time.process_time()-t0:.1f}")

    # --- Three-level integral-preserving downsample experiment ---
    if time_left() > 10.0 and best_h.size >= 32:
        N_orig = best_h.size
        hprev = best_h.copy()
        levels = []
        # Level 1 (N/2)
        if hprev.size % 2 == 1:
            hprev = np.concatenate([hprev, [0.0]])
        h1 = hprev[0::2] + hprev[1::2]
        if h1.size >= 4 and h1.max() > 0:
            h1 = h1 / h1.max()
            levels.append((h1, h1.size))
        # Level 2 (N/4)
        if levels:
            h2src = levels[-1][0]
            if h2src.size % 2 == 1:
                h2src = np.concatenate([h2src, [0.0]])
            h2 = h2src[0::2] + h2src[1::2]
            if h2.size >= 4 and h2.max() > 0:
                h2 = h2 / h2.max()
                levels.append((h2, h2.size))
        # Level 3 (N/8)
        if len(levels) == 2:
            h3src = levels[-1][0]
            if h3src.size % 2 == 1:
                h3src = np.concatenate([h3src, [0.0]])
            h3 = h3src[0::2] + h3src[1::2]
            if h3.size >= 4 and h3.max() > 0:
                h3 = h3 / h3.max()
                levels.append((h3, h3.size))

        if len(levels) == 3:
            h1, n1 = levels[0]
            h2, n2 = levels[1]
            h3, n3 = levels[2]
            R1 = _R(h1)
            R2 = _R(h2)
            R3 = _R(h3)
            print(f"ds L1 N={n1} R={R1:.9f} L2 N={n2} R={R2:.9f} "
                  f"L3 N={n3} R={R3:.9f} t={time.process_time()-t0:.1f}")

            # Optimize level 3 (~2.5s)
            d3 = min(deadline, (time.process_time() - t0) + 2.5)
            h3, R3 = _ds_schedule(h3, R3, d3, t0, rng)
            print(f"ds L3 done R={R3:.9f} t={time.process_time()-t0:.1f}")

            # Upsample level 3 -> level 2
            hf2 = np.repeat(h3 / 2.0, 2)
            if hf2.size > n2:
                hf2 = hf2[:n2]
            elif hf2.size < n2:
                hf2 = np.concatenate([hf2, np.zeros(n2 - hf2.size)])
            if hf2.max() > 0:
                hf2 = hf2 / hf2.max()
            Rf2 = _R(hf2)
            if Rf2 > R2:
                h2, R2 = hf2, Rf2
            print(f"ds up L3->L2 R={R2:.9f} t={time.process_time()-t0:.1f}")

            # Optimize level 2 (~2.5s)
            d2 = min(deadline, (time.process_time() - t0) + 2.5)
            h2, R2 = _ds_schedule(h2, R2, d2, t0, rng)
            print(f"ds L2 done R={R2:.9f} t={time.process_time()-t0:.1f}")

            # Upsample level 2 -> level 1
            hf1 = np.repeat(h2 / 2.0, 2)
            if hf1.size > n1:
                hf1 = hf1[:n1]
            elif hf1.size < n1:
                hf1 = np.concatenate([hf1, np.zeros(n1 - hf1.size)])
            if hf1.max() > 0:
                hf1 = hf1 / hf1.max()
            Rf1 = _R(hf1)
            if Rf1 > R1:
                h1, R1 = hf1, Rf1
            print(f"ds up L2->L1 R={R1:.9f} t={time.process_time()-t0:.1f}")

            # Optimize level 1 (~3s)
            d1 = min(deadline, (time.process_time() - t0) + 3.0)
            h1, R1 = _ds_schedule(h1, R1, d1, t0, rng)
            print(f"ds L1 done R={R1:.9f} t={time.process_time()-t0:.1f}")

            # Upsample level 1 -> original N
            hf = np.repeat(h1 / 2.0, 2)
            if hf.size > N_orig:
                hf = hf[:N_orig]
            elif hf.size < N_orig:
                hf = np.concatenate([hf, np.zeros(N_orig - hf.size)])
            if hf.max() > 0:
                hf = hf / hf.max()
            if hf.sum() > 0:
                consider(hf)
                print(f"ds upsample R={best_R:.9f} t={time.process_time()-t0:.1f}")

    rnd = 0
    while time_left() > 0.8:
        rnd += 1
        R_before = best_R

        for tau in (1e-5, 3e-6, 1e-6, 3e-7):
            if time_left() <= 0.7:
                break
            sub = min(deadline, (time.process_time() - t0) + 1.5)
            hs, rs = _lbfgs(best_h.copy(), best_R, sub, t0, _grad_z, (tau,),
                            maxiter=70, maxfun=140)
            consider(hs)

        if time_left() > 0.6:
            sub = min(deadline, (time.process_time() - t0) + 1.5)
            hx, rx = _lbfgs(best_h.copy(), best_R, sub, t0, _grad_z, (0.0,),
                            maxiter=100, maxfun=200)
            consider(hx)

        if time_left() > 0.5:
            sub = min(deadline, (time.process_time() - t0) + 1.5)
            I = _peak_indices(best_h, 0.99995)
            hpk, rpk = _pair_golden(best_h.copy(), best_R, sub, t0, rng,
                                    n_idx=400, lo=0.6, hi=0.6, iters=18,
                                    idx_pool=I)
            consider(hpk)

        if time_left() > 0.5:
            sub = min(deadline, (time.process_time() - t0) + 1.2)
            hpg, rpg = _pair_golden(best_h.copy(), best_R, sub, t0, rng,
                                    n_idx=300, lo=0.6, hi=0.6, iters=14)
            consider(hpg)

        gain = best_R - R_before
        print(f"round={rnd} R={best_R:.9f} gain={gain:.2e} t={time.process_time()-t0:.1f}")
        if gain < 5e-10:
            break

    if time_left() > 0.5:
        sub = min(deadline, (time.process_time() - t0) + 1.0)
        hx, rx = _lbfgs(best_h.copy(), best_R, sub, t0, _grad_z, (0.0,),
                        maxiter=120, maxfun=240)
        consider(hx)

    print(f"final R={best_R:.9f} t={time.process_time()-t0:.1f}")

    out = np.asarray(best_h, dtype=float)
    out = np.clip(out, 0.0, None)
    if out.sum() <= 0:
        out = np.ones(100)
    if out.size > 50000:
        out = out[:50000]
    return out
