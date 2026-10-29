"""F3880: exact-R derivative-free coordinate/pair ascent with incremental
autoconvolution (O(N) per move, no FFT), then the base's Dinkelbach polish.
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


class Polisher:
    def __init__(self, f, deadline):
        f = np.maximum(np.asarray(f, dtype=float), 0.0)
        self.N = len(f)
        self.M = sfft.next_fast_len(2 * self.N - 1)
        self.deadline = deadline
        self.best_f = f / f.max()
        self.best = exact_ratio(self.conv(self.best_f))
        self.evals = 0

    def conv(self, f):
        F = sfft.rfft(f, self.M)
        return sfft.irfft(F * F, self.M)[: 2 * self.N - 1]

    def corr(self, G, f):
        A = sfft.rfft(G, self.M)
        B = sfft.rfft(f[::-1], self.M)
        return sfft.irfft(A * B, self.M)[self.N - 1: 2 * self.N - 1]

    def band_free(self, f, frac):
        g = self.conv(f)
        m = g.max()
        if m <= 0:
            return np.arange(self.N)
        phi = g / m
        band = (phi > 0.1) & (phi < 0.9)
        if band.sum() < 500:
            band = (phi > 0.02) & (phi < 0.98)
        d = np.abs(self.corr(band.astype(float), f))
        k = max(1, int(frac * self.N))
        k = min(k, self.N)
        idx = np.argpartition(d, -k)[-k:]
        idx.sort()
        return idx

    def objective(self, lam, beta, scale):
        def fun(w):
            if time.process_time() > self.deadline:
                raise _Out()
            f = w * w
            g = self.conv(f)
            self.evals += 1
            r = exact_ratio(g)
            if r > self.best and np.isfinite(r):
                self.best, self.best_f = r, f.copy()
            m = g.max()
            z = beta * (g / m - 1.0)
            zmax = z.max()
            e = np.exp(z - zmax)
            Z = e.sum()
            lse = zmax + np.log(Z)
            L = m * np.exp(lse / beta)
            S = g.sum()
            N2 = (2.0 * np.dot(g, g) + np.dot(g[:-1], g[1:])) / 3.0
            phi = N2 - lam * S * L
            dN = 4.0 * g / 3.0
            dN[:-1] += g[1:] / 3.0
            dN[1:] += g[:-1] / 3.0
            G = dN - lam * (L + S * (L / m) * (e / Z))
            gf = 2.0 * self.corr(G, f)
            return -phi * scale, -(2.0 * w * gf) * scale
        return fun

    def subspace_objective(self, lam, beta, scale, free):
        base = self.objective(lam, beta, scale)

        def fun(wf):
            w = self._w_work.copy()
            w[free] = wf
            val, grad = base(w)
            return val, grad[free]
        return fun

    def lbfgs(self, beta, iters):
        w0 = np.sqrt(self.best_f)
        g = self.conv(self.best_f)
        scale = 1.0 / (g.sum() * g.max())
        minimize(self.objective(self.best, beta, scale), w0, jac=True, method="L-BFGS-B",
                 options={"maxiter": iters, "maxcor": 10, "ftol": 1e-16, "gtol": 1e-20})

    def subspace_lbfgs(self, beta, iters, frac):
        w0 = np.sqrt(self.best_f)
        g = self.conv(self.best_f)
        scale = 1.0 / (g.sum() * g.max())
        free = self.band_free(self.best_f, frac)
        self._w_work = w0.copy()
        fun = self.subspace_objective(self.best, beta, scale, free)
        minimize(fun, w0[free].copy(), jac=True, method="L-BFGS-B",
                 options={"maxiter": iters, "maxcor": 10, "ftol": 1e-16, "gtol": 1e-20})
        w = self._w_work
        f = w * w
        r = exact_ratio(self.conv(f))
        if r > self.best and np.isfinite(r):
            self.best, self.best_f = r, f.copy()
        return len(free)

    def dinkelbach(self, beta, iters, stop_frac, log, tag):
        rnd = 0
        while True:
            if time.process_time() > self.deadline * stop_frac:
                break
            before = self.best
            try:
                self.lbfgs(beta, iters)
            except _Out:
                break
            rnd += 1
            log(f"{tag} beta {beta:.0e} round {rnd}: lambda = {self.best:.13f} "
                f"({self.evals} evals, {time.process_time():.0f} s CPU)")
            if self.best <= before + 1e-12:
                break
        return rnd


def _add_delta(g, f, i, delta):
    """g += contribution of changing f[i] by delta (exact, O(N))."""
    N = len(f)
    # 2*delta*f[k-i] for k-i in [0,N-1] => k in [i, i+N-1]
    g[i:i + N] += 2.0 * delta * f
    g[2 * i] += delta * delta


def coord_ascent(p, phase_deadline, rng, log):
    N = p.N
    f = p.best_f.copy()
    g = p.conv(f)
    best = exact_ratio(g)
    best_f = f.copy()
    eta = 1e-3
    props = 0
    acc = 0
    gain0 = best
    while True:
        if time.process_time() > phase_deadline:
            break
        props += 1
        z = rng.standard_normal()
        if rng.random() < 0.5:
            # single-coordinate multiplicative move
            i = int(rng.integers(0, N))
            delta = f[i] * (np.exp(eta * z) - 1.0)
            if delta == 0.0:
                continue
            _add_delta(g, f, i, delta)
            r = exact_ratio(g)
            if r > best and np.isfinite(r):
                f[i] += delta
                best = r
                best_f = f.copy()
                acc += 1
                eta *= 1.4
            else:
                _add_delta(g, f, i, -delta)
                eta *= 0.9
        else:
            # pair mass transfer
            i = int(rng.integers(0, N))
            j = int(rng.integers(0, N))
            if i == j:
                eta *= 0.9
                continue
            d = eta * 0.5 * (f[i] + f[j]) * z
            if f[i] + d < 0.0:
                d = -f[i]
            if f[j] - d < 0.0:
                d = f[j]
            if d == 0.0:
                eta *= 0.9
                continue
            _add_delta(g, f, i, d)
            _add_delta(g, f, j, -d)
            r = exact_ratio(g)
            if r > best and np.isfinite(r):
                f[i] += d
                f[j] -= d
                best = r
                best_f = f.copy()
                acc += 1
                eta *= 1.4
            else:
                _add_delta(g, f, i, -d)
                _add_delta(g, f, j, d)
                eta *= 0.9
        eta = min(max(eta, 1e-7), 1e-1)

        if props % 2000 == 0:
            g = p.conv(f)
            best = exact_ratio(g)
            if best > p.best:
                p.best, p.best_f = best, f.copy()
        if props % 20000 == 0:
            p.best, p.best_f = best, best_f.copy()
            try:
                p.lbfgs(1e10, 20)
            except _Out:
                break
            f = p.best_f.copy()
            g = p.conv(f)
            best = p.best
            best_f = f.copy()
        if props % 5000 == 0:
            log(f"  coord props {props} acc {acc} ({acc / props:.3f}) eta {eta:.2e} "
                f"R {best:.13f} ({best - gain0:+.3e})")

    p.best, p.best_f = best, best_f.copy()
    log(f"Phase A done: {props} proposals, {acc} accepted ({acc / max(props,1):.4f}), "
        f"R {gain0:.13f} -> {best:.13f} ({best - gain0:+.3e})")
    return best - gain0


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + 0.9 * budget_seconds - 3.0
    if start is None:
        x = np.linspace(-0.5, 0.5, 20002)[1:-1]
        start = 1.0 / np.sqrt(1.0 - 4.0 * x * x)
    p = Polisher(start, deadline)
    r0 = p.best
    print(f"start R = {r0:.13f}, n = {p.N}")

    rng = np.random.default_rng(12345)

    # Phase A: exact-R coordinate/pair ascent with incremental autoconvolution.
    phaseA_end = t0 + 0.6 * budget_seconds
    coord_ascent(p, phaseA_end, rng, print)

    # Phase B: base's subspace ladder as consolidation.
    fracs = (0.05, 0.2, 0.5)
    betas = (1e6, 1e10, 1e14)
    for frac in fracs:
        for beta in betas:
            if time.process_time() > deadline * 0.85:
                break
            before = p.best
            try:
                nfree = p.subspace_lbfgs(beta, 200, frac)
            except _Out:
                break
            print(f"subspace frac {frac:.2f} beta {beta:.0e}: R = {p.best:.13f} "
                  f"({p.best - before:+.3e}, free = {nfree}, {p.evals} evals, "
                  f"{time.process_time():.0f} s CPU)")
            if time.process_time() < deadline * 0.85:
                try:
                    p.lbfgs(1e10, 60)
                except _Out:
                    break
                print(f"  full polish beta 1e+10: R = {p.best:.13f} "
                      f"({p.evals} evals, {time.process_time():.0f} s CPU)")
        if time.process_time() > deadline * 0.85:
            break

    # Phase C: final Dinkelbach.
    if time.process_time() < deadline * 0.9:
        try:
            p.dinkelbach(1e10, 200, 0.95, print, "final10")
            p.dinkelbach(1e14, 200, 0.99, print, "final14")
        except _Out:
            pass

    f, r = p.best_f, p.best
    print(f"done: start {r0:.13f} -> {r:.13f} ({r - r0:+.3e}), n = {len(f)}, "
          f"{p.evals} evals")
    if r > r0:
        return f
    return {"best": f, "alternative": f}
