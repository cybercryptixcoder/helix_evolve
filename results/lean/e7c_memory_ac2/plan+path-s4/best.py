import time
import numpy as np
from scipy.optimize import minimize
from scipy.signal import fftconvolve
from scipy.ndimage import gaussian_filter1d


def _exact_R(h):
    h = np.asarray(h, dtype=float)
    if h.sum() <= 0:
        return 0.0
    L = np.concatenate(([0.0], fftconvolve(h, h), [0.0]))
    num = np.sum(L[:-1]**2 + L[:-1] * L[1:] + L[1:]**2) / 3.0
    den = (np.sum(h)**2) * np.max(L)
    return num / den if den > 0 else 0.0


def _correlate_valid(gc, h):
    n = len(h)
    full = fftconvolve(gc, h[::-1])
    return full[n - 1: n - 1 + (len(gc) - n + 1)]


def _objective_grad_h_exact(h):
    if np.any(h < 0):
        return 1e10, np.zeros_like(h)
    L = np.concatenate(([0.0], fftconvolve(h, h), [0.0]))
    s = np.sum(h)
    if s <= 0:
        return 1e10, np.zeros_like(h)
    num = np.sum(L[:-1]**2 + L[:-1] * L[1:] + L[1:]**2) / 3.0
    g = np.zeros_like(L)
    g[:-1] += (2.0 * L[:-1] + L[1:]) / 3.0
    g[1:] += (2.0 * L[1:] + L[:-1]) / 3.0
    gc = g[1:-1]
    dnum_dh = 2.0 * _correlate_valid(gc, h)
    M = np.max(L)
    if M <= 0:
        return 1e10, np.zeros_like(h)
    dM_dL = np.zeros_like(L)
    ties = L >= M * (1.0 - 1e-12)
    nties = np.count_nonzero(ties)
    dM_dL[ties] = 1.0 / nties / M
    dM_dh = 2.0 * _correlate_valid(dM_dL[1:-1], h)
    den = (s**2) * M
    if den <= 0:
        return 1e10, np.zeros_like(h)
    R = num / den
    dden_dh = 2.0 * s * M + (s**2) * dM_dh
    grad = -(dnum_dh * den - num * dden_dh) / (den**2)
    return -R, grad


def _refine_h(h, maxiter, deadline):
    if time.process_time() > deadline:
        return h
    try:
        res = minimize(
            _objective_grad_h_exact, h, method='L-BFGS-B',
            jac=True, bounds=[(0.0, None)] * len(h),
            options={'maxiter': maxiter, 'maxfun': 20 * maxiter,
                     'ftol': 1e-16, 'gtol': 1e-12},
        )
        return res.x
    except Exception:
        return h


def _block_objective_grad_h(hb, h_full, lo, hi):
    h = h_full.copy()
    h[lo:hi] = hb
    val, grad = _objective_grad_h_exact(h)
    return val, grad[lo:hi]


def _refine_block_h(h, lo, hi, maxiter, deadline):
    if time.process_time() > deadline:
        return h, False
    hb0 = h[lo:hi].copy()
    try:
        res = minimize(
            _block_objective_grad_h, hb0, args=(h, lo, hi),
            method='L-BFGS-B', jac=True,
            bounds=[(0.0, None)] * (hi - lo),
            options={'maxiter': maxiter, 'maxfun': 20 * maxiter,
                     'ftol': 1e-16, 'gtol': 1e-12},
        )
        hnew = h.copy()
        hnew[lo:hi] = res.x
        return hnew, True
    except Exception:
        return h, False


def _block_ascent_h(h, best_R, deadline, nblocks, iters_per_block, rng, max_passes=3):
    N = len(h)
    pass_idx = 0
    while pass_idx < max_passes and time.process_time() < deadline:
        edges = np.linspace(0, N, nblocks + 1).astype(int)
        blocks = [(edges[i], edges[i + 1]) for i in range(nblocks) if edges[i + 1] > edges[i]]
        order = list(range(len(blocks)))
        rng.shuffle(order)
        accepted_this = 0
        for bi in order:
            if time.process_time() > deadline:
                break
            lo, hi = blocks[bi]
            h_try, ok = _refine_block_h(h, lo, hi, iters_per_block, deadline)
            if not ok:
                continue
            R_try = _exact_R(h_try)
            if R_try > best_R + 1e-15:
                h = h_try
                best_R = R_try
                accepted_this += 1
        print("  h-pass %d (nb=%d): accepted %d, R=%.12f" % (
            pass_idx, nblocks, accepted_this, best_R))
        pass_idx += 1
        if accepted_this == 0:
            break
    return h, best_R


def _upsample_linear(h, N_new):
    n = len(h)
    if n == N_new:
        return h.copy()
    x_old = (np.arange(n) + 0.5) / n
    x_new = (np.arange(N_new) + 0.5) / N_new
    return np.interp(x_new, x_old, h)


def _downsample_mass(h, N_new):
    """Area-preserving (mass-weighted average) downsample of piecewise-constant h."""
    n = len(h)
    if n == N_new:
        return h.copy()
    x_old = np.linspace(0.0, 1.0, n + 1)
    x_new = np.linspace(0.0, 1.0, N_new + 1)
    cum = np.concatenate(([0.0], np.cumsum(h)))
    mass_at_new = np.interp(x_new, x_old, cum)
    mass_cells = np.diff(mass_at_new)
    widths = np.diff(x_new)
    return mass_cells / widths


def _upsample_mass(h, N_new):
    """Mass-preserving upsample: each old cell's mass spread evenly over new cells."""
    n = len(h)
    if n == N_new:
        return h.copy()
    x_old = np.linspace(0.0, 1.0, n + 1)
    x_new = np.linspace(0.0, 1.0, N_new + 1)
    cum = np.concatenate(([0.0], np.cumsum(h)))
    mass_at_new = np.interp(x_new, x_old, cum)
    mass_cells = np.diff(mass_at_new)
    widths = np.diff(x_new)
    return mass_cells / widths


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.9

    if start is not None:
        h0 = np.asarray(start, dtype=float).copy()
        h0 = np.maximum(h0, 0.0)
        if h0.sum() <= 0:
            h0 = np.ones(max(1, len(h0)))
    else:
        N = 101
        i = np.arange(N)
        h0 = 1.0 + np.minimum(i, N - 1 - i).astype(float)

    best_h = h0.copy()
    best_R = _exact_R(best_h)
    print("init R = %.12f, N=%d, zeros=%d" % (best_R, len(best_h),
                                              np.count_nonzero(best_h == 0)))

    rng = np.random.RandomState(2024)

    # --- Stage A: coarse random restarts at N=2000 ---
    Nc = 2000
    h_coarse_base = _downsample_mass(best_h, Nc)
    R_coarse_base = _exact_R(h_coarse_base)
    print("  coarse base (N=%d) R=%.12f" % (Nc, R_coarse_base))

    best_coarse_h = h_coarse_base.copy()
    best_coarse_R = R_coarse_base

    n_restarts = 30
    # reserve time for later stages: ~40% of budget for restarts
    restart_deadline = t0 + budget_seconds * 0.40

    for k in range(n_restarts):
        if time.process_time() > restart_deadline:
            print("  restart loop stopped at k=%d (time)" % k)
            break
        mode = k % 3
        base = h_coarse_base.copy()
        if mode == 0:
            # Gaussian-filtered multiplicative noise
            sigma = rng.uniform(0.3, 1.0)
            corr = rng.choice([5, 10, 20, 40, 70, 100])
            noise = rng.standard_normal(Nc)
            noise = gaussian_filter1d(noise, corr, mode='wrap')
            noise = noise / (np.std(noise) + 1e-12)
            cand = base * np.exp(sigma * noise)
        elif mode == 1:
            # random smooth bumps
            cand = base.copy()
            nb = rng.randint(2, 6)
            for _ in range(nb):
                c = rng.uniform(0, Nc)
                w = rng.uniform(Nc * 0.02, Nc * 0.15)
                amp = rng.uniform(-0.5, 1.0)
                x = np.arange(Nc)
                bump = np.exp(-0.5 * ((x - c) / w) ** 2)
                cand = cand * (1.0 + amp * bump)
        else:
            # smooth random profile blended with base
            noise = rng.standard_normal(Nc)
            corr = rng.choice([5, 15, 40, 100])
            noise = gaussian_filter1d(noise, corr, mode='wrap')
            noise = noise / (np.std(noise) + 1e-12)
            alpha = rng.uniform(0.3, 0.9)
            cand = base * (1.0 - alpha) + alpha * base.mean() * np.exp(0.5 * noise)
        cand = np.maximum(cand, 0.0)
        if cand.sum() <= 0:
            continue
        R_cand0 = _exact_R(cand)
        cand_opt = _refine_h(cand, 200, deadline)
        R_cand = _exact_R(cand_opt)
        if R_cand > best_coarse_R:
            best_coarse_R = R_cand
            best_coarse_h = cand_opt.copy()
            print("  restart %d (mode %d): NEW best coarse R=%.12f (base %.12f)" % (
                k, mode, best_coarse_R, R_coarse_base))
        else:
            print("  restart %d (mode %d): R=%.12f (no improve, best %.12f)" % (
                k, mode, R_cand, best_coarse_R))

    print("  best coarse R=%.12f (base %.12f, delta=%.2e)" % (
        best_coarse_R, R_coarse_base, best_coarse_R - R_coarse_base))

    # --- Stage B: mass-preserving upsample to N=50000, refine + block ascent ---
    N50 = 50000
    h50 = _upsample_mass(best_coarse_h, N50)
    R50 = _exact_R(h50)
    print("  upsample to N=%d: R=%.12f" % (N50, R50))
    if R50 > best_R:
        best_h, best_R = h50.copy(), R50

    if time.process_time() < deadline:
        h_try = _refine_h(h50.copy(), 2000, deadline)
        R_try = _exact_R(h_try)
        if R_try > best_R:
            best_R, best_h = R_try, h_try.copy()
        print("  N50 full refine: R=%.12f" % best_R)

    if time.process_time() < deadline:
        for nb in (512, 1024, 2048, 4096, 8192):
            if time.process_time() > deadline:
                break
            best_h, best_R = _block_ascent_h(
                best_h, best_R, deadline, nb, 20, rng, max_passes=1)
            print("  after N50 nb=%d: R=%.12f" % (nb, best_R))

    print("final exact R = %.12f, N=%d" % (best_R, len(best_h)))
    return best_h
