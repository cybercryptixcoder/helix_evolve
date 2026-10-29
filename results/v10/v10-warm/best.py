"""p4397 + support-revival experiment.

Adds, on top of p4397's machinery:
  (a) exact dlogR/dh gradient in h-space (not w^2), so zero cells are free;
  (b) diagnostic: max over zero cells of dlogR/dh and count of positive ones;
  (c) projected-gradient ascent in h-space with line search on exact R;
  (d) final bounded L-BFGS-B on the Dinkelbach objective in h-space.
Keeps p4397's coarse stage and full log-R polish as a fallback.
"""
import time

import numpy as np
from scipy import fft as sfft
from scipy.optimize import minimize


class _Out(Exception):
    pass


def exact_ratio(g):
    m = g.max()
    if m <= 0:
        return 0.0
    l2 = (2.0 * np.dot(g, g) + np.dot(g[:-1], g[1:])) / 3.0
    return l2 / (g.sum() * m)


def ratio_fast(f):
    N = len(f)
    M = sfft.next_fast_len(2 * N - 1)
    F = sfft.rfft(f, M)
    g = sfft.irfft(F * F, M)[: 2 * N - 1]
    return exact_ratio(g), g


def _conv(f, M, N):
    F = sfft.rfft(f, M)
    return sfft.irfft(F * F, M)[: 2 * N - 1]


def _corr(G, f, M, N):
    A = sfft.rfft(G, M)
    B = sfft.rfft(f[::-1], M)
    return sfft.irfft(A * B, M)[N - 1: 2 * N - 1]


def grad_logR(h, g, M, N):
    """Exact dlogR/dh (h-space). Returns (grad, R, S, m, N2)."""
    m = g.max()
    if m <= 0:
        return np.zeros(N), 0.0, 0.0, 0.0, 0.0
    S = g.sum()
    N2 = (2.0 * np.dot(g, g) + np.dot(g[:-1], g[1:])) / 3.0
    if N2 <= 0 or S <= 0:
        return np.zeros(N), 0.0, S, m, N2
    # tie-weighted max weight E
    thr = m * (1.0 - 1e-9)
    T = np.flatnonzero(g >= thr)
    E = np.zeros_like(g)
    if T.size > 0:
        E[T] = 1.0 / T.size
    else:
        beta = 1e5
        z = beta * (g / m - 1.0)
        zmax = z.max()
        e = np.exp(z - zmax)
        E = e / e.sum()
    A = (4.0 / 3.0) * g
    A[:-1] += g[1:] / 3.0
    A[1:] += g[:-1] / 3.0
    D = A / N2 - 1.0 / S - E / m
    grad = _corr(D, h, M, N)
    R = N2 / (S * m)
    return grad, R, S, m, N2


def logr_ascent(f0, deadline, betas, rounds=6, iters=80, log=None):
    """p4397's w^2 smooth-max ascent (kept as fallback / finisher)."""
    f = np.maximum(np.asarray(f0, dtype=float), 0.0)
    N = len(f)
    M = sfft.next_fast_len(2 * N - 1)

    def conv(f):
        return _conv(f, M, N)

    def corr(G, f):
        return _corr(G, f, M, N)

    state = {"best": exact_ratio(conv(f / max(f.max(), 1e-30))),
             "best_f": f / max(f.max(), 1e-30), "evals": 0}

    def objective(beta, scale):
        def fun(w):
            if time.process_time() > deadline:
                raise _Out()
            fv = w * w
            g = conv(fv)
            state["evals"] += 1
            r = exact_ratio(g)
            if r > state["best"] and np.isfinite(r):
                state["best"], state["best_f"] = r, fv.copy()
            m = g.max()
            if m <= 0:
                return 0.0, np.zeros_like(w)
            S = g.sum()
            N2 = (2.0 * np.dot(g, g) + np.dot(g[:-1], g[1:])) / 3.0
            if N2 <= 0 or S <= 0:
                return 0.0, np.zeros_like(w)
            z = beta * (g / m - 1.0)
            zmax = z.max()
            e = np.exp(z - zmax)
            Z = e.sum()
            lse = zmax + np.log(Z)
            L = m * np.exp(lse / beta)
            phi = np.log(N2) - np.log(S) - np.log(L)
            dN = 4.0 * g / 3.0
            dN[:-1] += g[1:] / 3.0
            dN[1:] += g[:-1] / 3.0
            dLdg = L * (e / Z) / m
            G = dN / N2 - 1.0 / S - dLdg / L
            gf = 2.0 * corr(G, fv)
            return -phi * scale, -(2.0 * w * gf) * scale
        return fun

    for beta in betas:
        for _ in range(rounds):
            if time.process_time() > deadline:
                return state["best_f"], state["best"]
            before = state["best"]
            w0 = np.sqrt(state["best_f"])
            g = conv(state["best_f"])
            scale = 1.0 / max(g.sum() * g.max(), 1e-30)
            try:
                minimize(objective(beta, scale), w0, jac=True, method="L-BFGS-B",
                         options={"maxiter": iters, "maxcor": 10,
                                  "ftol": 1e-16, "gtol": 1e-20})
            except _Out:
                return state["best_f"], state["best"]
            if state["best"] <= before + 1e-15:
                break
        if log:
            log(f"  beta {beta:.0e}: R = {state['best']:.10f} ({state['evals']} evals)")
    return state["best_f"], state["best"]


def downsample(h, Nc):
    N = len(h)
    edges = np.linspace(0, N, Nc + 1).astype(int)
    out = np.empty(Nc)
    for i in range(Nc):
        a, b = edges[i], edges[i + 1]
        out[i] = 0.0 if b <= a else h[a:b].mean()
    return out


def upsample(hc, N):
    Nc = len(hc)
    edges = np.linspace(0, N, Nc + 1).astype(int)
    out = np.empty(N)
    for i in range(Nc):
        out[edges[i]: edges[i + 1]] = hc[i]
    return out


def block_coordinate_ascent(hc, deadline, rng, log=None, n_sweeps=40):
    hc = hc.copy()
    best, g = ratio_fast(hc)
    Nc = len(hc)
    if Nc < 4:
        return hc, best
    sweeps = 0
    while time.process_time() < deadline and sweeps < n_sweeps:
        sweeps += 1
        improved = False
        for frac in (0.002, 0.005, 0.01, 0.02, 0.05, 0.1):
            bs = max(2, int(frac * Nc))
            for _ in range(6):
                if time.process_time() > deadline:
                    break
                a = rng.integers(0, Nc - bs)
                b = a + bs
                for fac in (1.05, 0.95, 1.15, 0.87, 1.3, 0.77):
                    trial = hc.copy()
                    trial[a:b] *= fac
                    s = trial.sum()
                    if s <= 0:
                        continue
                    trial *= hc.sum() / s
                    r, gg = ratio_fast(trial)
                    if r > best + 1e-13:
                        best, hc = r, trial
                        improved = True
                        break
        if log and sweeps % 5 == 0:
            log(f"    bca sweep {sweeps}: R = {best:.10f}")
        if not improved:
            break
    return hc, best


def projected_gradient(h, deadline, log=None, max_iters=20):
    """Projected-gradient ascent in h-space with line search on exact R."""
    h = np.maximum(np.asarray(h, dtype=float), 0.0)
    N = len(h)
    M = sfft.next_fast_len(2 * N - 1)
    g = _conv(h, M, N)
    R = exact_ratio(g)
    best_h, best_R = h.copy(), R
    hmax = h.max()

    for it in range(max_iters):
        if time.process_time() > deadline:
            break
        grad, R, S, m, N2 = grad_logR(h, g, M, N)
        if R <= 0:
            break
        # diagnostic
        zero = (h == 0)
        if zero.any():
            gz = grad[zero]
            mx = gz.max()
            npos = int((gz > 0).sum())
        else:
            mx, npos = 0.0, 0
        if log:
            log(f"  pg it {it}: R = {R:.13f}, max_grad@zero = {mx:.3e}, "
                f"#pos@zero = {npos}")

        # direction: grad, but for zero cells with negative grad clip to 0
        d = grad.copy()
        d[(h == 0) & (d < 0)] = 0.0
        dmax = np.abs(d).max()
        if dmax <= 0:
            break
        # line search: scale so max|t*d| = factor * hmax
        factors = [1e-4, 1e-3, 1e-2, 0.1, 1.0, 10.0]
        best_trial, best_trial_R = None, R
        mass_before = h.sum()
        for fac in factors:
            if time.process_time() > deadline:
                break
            t = fac * hmax / dmax
            trial = np.maximum(0.0, h + t * d)
            s = trial.sum()
            if s <= 0:
                continue
            # keep mass roughly fixed? no - let it drift, exact R decides
            gt = _conv(trial, M, N)
            rt = exact_ratio(gt)
            if rt > best_trial_R + 1e-15:
                best_trial, best_trial_R = trial, rt
        if best_trial is None or best_trial_R <= R + 1e-13:
            if log:
                log(f"  pg it {it}: no improvement, stop")
            break
        # mass added to previously-zero cells
        added = best_trial[zero].sum() if zero.any() else 0.0
        h = best_trial
        g = _conv(h, M, N)
        R = best_trial_R
        hmax = h.max()
        if R > best_R:
            best_R, best_h = R, h.copy()
        if log:
            log(f"  pg it {it}: R -> {R:.13f}, mass added to zeros = {added:.3e}")

    return best_h, best_R


def dinkelbach_h(h0, deadline, lam, betas, rounds=4, iters=40, log=None):
    """Bounded L-BFGS-B on Dinkelbach objective in h-space (bounds [0, inf))."""
    h = np.maximum(np.asarray(h0, dtype=float), 0.0)
    N = len(h)
    M = sfft.next_fast_len(2 * N - 1)
    state = {"best": exact_ratio(_conv(h, M, N)), "best_h": h.copy()}

    def objective(beta, scale):
        def fun(hv):
            if time.process_time() > deadline:
                raise _Out()
            g = _conv(hv, M, N)
            r = exact_ratio(g)
            if r > state["best"] and np.isfinite(r):
                state["best"], state["best_h"] = r, hv.copy()
            m = g.max()
            if m <= 0:
                return 0.0, np.zeros_like(hv)
            S = g.sum()
            N2 = (2.0 * np.dot(g, g) + np.dot(g[:-1], g[1:])) / 3.0
            if N2 <= 0 or S <= 0:
                return 0.0, np.zeros_like(hv)
            z = beta * (g / m - 1.0)
            zmax = z.max()
            e = np.exp(z - zmax)
            Z = e.sum()
            lse = zmax + np.log(Z)
            L = m * np.exp(lse / beta)
            # Dinkelbach: maximize N2 - lam * S * L  (log-ish form)
            # use log form: log(N2) - log(S) - log(L)  (same argmax as R)
            phi = np.log(N2) - np.log(S) - np.log(L)
            dN = 4.0 * g / 3.0
            dN[:-1] += g[1:] / 3.0
            dN[1:] += g[:-1] / 3.0
            dLdg = L * (e / Z) / m
            G = dN / N2 - 1.0 / S - dLdg / L
            gf = _corr(G, hv, M, N)
            return -phi * scale, -gf * scale
        return fun

    for beta in betas:
        for _ in range(rounds):
            if time.process_time() > deadline:
                return state["best_h"], state["best"]
            before = state["best"]
            g = _conv(state["best_h"], M, N)
            scale = 1.0 / max(g.sum() * g.max(), 1e-30)
            try:
                minimize(objective(beta, scale), state["best_h"].copy(),
                         jac=True, method="L-BFGS-B",
                         bounds=[(0.0, None)] * N,
                         options={"maxiter": iters, "maxcor": 10,
                                  "ftol": 1e-16, "gtol": 1e-20})
            except _Out:
                return state["best_h"], state["best"]
            if state["best"] <= before + 1e-15:
                break
        if log:
            log(f"  dink beta {beta:.0e}: R = {state['best']:.13f}")
    return state["best_h"], state["best"]


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + 0.92 * budget_seconds - 3.0
    pg_deadline = t0 + 0.85 * budget_seconds - 3.0
    log = print
    if start is None:
        x = np.linspace(-0.5, 0.5, 20002)[1:-1]
        start = 1.0 / np.sqrt(1.0 - 4.0 * x * x)
    start = np.maximum(np.asarray(start, dtype=float), 0.0)
    r_start, _ = ratio_fast(start)
    log(f"start R = {r_start:.13f}, N = {len(start)}")

    best_f = start / start.max()
    best_r = r_start
    N = len(start)
    rng = np.random.default_rng(12345)

    # ---- New: support-revival via projected gradient in h-space ----
    h_pg, r_pg = projected_gradient(best_f, pg_deadline, log=log, max_iters=20)
    log(f"projected-gradient: R = {r_pg:.13f} (start {r_start:.13f})")
    if r_pg > best_r:
        best_r, best_f = r_pg, h_pg / h_pg.max()

    # ---- New: bounded L-BFGS-B in h-space on Dinkelbach objective ----
    if time.process_time() < deadline:
        h_dk, r_dk = dinkelbach_h(best_f, deadline,
                                  lam=best_r,
                                  betas=[1e8, 1e10, 1e12, 1e13],
                                  rounds=4, iters=40, log=log)
        log(f"h-space Dinkelbach: R = {r_dk:.13f}")
        if r_dk > best_r:
            best_r, best_f = r_dk, h_dk / h_dk.max()

    # ---- Fallback: p4397's w^2 polish if time remains ----
    if time.process_time() < deadline - 5.0:
        ff, rf = logr_ascent(best_f, deadline, [1e10, 1e12, 1e14],
                             rounds=3, iters=60, log=log)
        if rf > best_r:
            best_r, best_f = rf, ff / ff.max()
            log(f"w^2 polish: R = {best_r:.13f}")

    if best_r <= r_start:
        best_f, best_r = start / start.max(), r_start

    print(f"start {r_start:.13f} -> {best_r:.13f} ({best_r - r_start:+.3e}), n = {len(best_f)}")
    if best_r <= r_start + 1e-12:
        return {"best": start, "alternative": best_f}
    return best_f
