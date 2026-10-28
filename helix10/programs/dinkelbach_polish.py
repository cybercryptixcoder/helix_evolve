"""The field's polish (ClaudeExplorer's iterated Dinkelbach, EinsteinArena threads 126/133 and
github.com/justinkang221/second-autocorrelation-inequality, src/dinkelbach_optimizer.py), rewritten for one CPU core
and a CPU-time budget.

R = ||g||_2^2 / (||g||_1 ||g||_inf), g = f*f, is a ratio. Dinkelbach: for a fixed lambda (the current R), maximise
    Phi(f) = ||g||_2^2 - lambda * ||g||_1 * smoothmax(g)
then set lambda to the new R and repeat. The smooth max is a LogSumExp normalised by max(g), with beta annealed
upward (the leaders went from 1e5 to 1e9, later to 1e14). f = w^2 keeps f >= 0 (a cell at zero stays at zero).
The inner problem is solved with L-BFGS. Every function evaluation also gives the exact R for free (g is already
computed), so the best exact iterate is kept and returned: the result is never worse than the start.
"""
import time

import numpy as np
from scipy import fft as sfft
from scipy.optimize import minimize


class _Out(Exception):
    pass


def exact_ratio(g):
    """The problem's score from g = f*f (knots [0, g, 0])."""
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
        """grad[k] = sum_i G[i] f[i - k]"""
        A = sfft.rfft(G, self.M)
        B = sfft.rfft(f[::-1], self.M)
        return sfft.irfft(A * B, self.M)[self.N - 1: 2 * self.N - 1]

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
            L = m * np.exp(lse / beta)                       # smooth max, >= max(g)
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

    def start_beta(self, k=1000):
        """A beta that resolves the top of f*f as it is: about 10 / (the relative gap below the max of its k-th
        largest lag). A fresh start gets 1e5 (the leaders' first level); a polished one starts much sharper."""
        g = self.conv(self.best_f)
        k = min(k, len(g) - 1)
        top = np.partition(g, len(g) - k)[len(g) - k:]
        d = 1.0 - top.min() / g.max()
        return float(np.clip(10.0 / max(d, 1e-14), 1e5, 1e12))

    def run(self, betas=None, rounds=4, iters=60, log=print):
        if betas is None:
            b0 = self.start_beta()
            betas = [b for b in (1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11, 1e12, 1e13, 1e14) if b >= b0 / 3]
            log(f"betas from {betas[0]:.0e} (the top of f*f as it is resolves at about {b0:.0e})")
        for beta in betas:
            for _ in range(rounds):
                if time.process_time() > self.deadline:
                    return self.best_f, self.best
                before = self.best
                w0 = np.sqrt(self.best_f)
                g = self.conv(self.best_f)
                scale = 1.0 / (g.sum() * g.max())
                try:
                    minimize(self.objective(self.best, beta, scale), w0, jac=True, method="L-BFGS-B",
                             options={"maxiter": iters, "maxcor": 10, "ftol": 1e-16, "gtol": 1e-20})
                except _Out:
                    return self.best_f, self.best
                if self.best <= before + 1e-15:
                    break                                    # this beta is spent: a sharper one
            log(f"beta {beta:.0e}: R = {self.best:.13f} ({self.evals} evaluations, "
                f"{time.process_time():.0f} s CPU)")
        return self.best_f, self.best


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + 0.9 * budget_seconds - 3.0
    if start is None:
        x = np.linspace(-0.5, 0.5, 20002)[1:-1]
        start = 1.0 / np.sqrt(1.0 - 4.0 * x * x)               # arcsine density: a smooth start
    p = Polisher(start, deadline)
    r0 = p.best
    f, r = p.run()
    print(f"start {r0:.13f} -> {r:.13f} ({r - r0:+.3e}), n = {len(f)}, {p.evals} evaluations")
    return f
