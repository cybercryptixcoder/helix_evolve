"""The field's exact resolution moves, then the polish (EinsteinArena threads 180, 211, 212, 255; ClaudeExplorer's
experiments/12_hyra_campaign), rewritten for one CPU core and a CPU-time budget.

R is unchanged, exactly, when every step is repeated k times (np.repeat(f, k)) and when zeros are added at either
end. A finer grid gives the polish more freedom per tooth of the comb, and padding to the size cap left room the July
record grew new structure into. So: repeat the start as many whole times as fit under the cap, pad it to the cap
(half on each side), add tiny noise so padded cells can come alive, then polish with iterated Dinkelbach. Linear
interpolation is never used: it smears the tuned comb (losses of 7e-3 and more).
"""
CAP = 2_000_000


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + 0.9 * budget_seconds - 3.0
    if start is None:
        x = np.linspace(-0.5, 0.5, 20002)[1:-1]
        start = 1.0 / np.sqrt(1.0 - 4.0 * x * x)
    f = np.maximum(np.asarray(start, dtype=float), 0.0)
    f = f / f.max()
    k = max(1, CAP // len(f))
    if k > 1:
        f = np.repeat(f, k)
    pad = CAP - len(f)
    if pad > 0:
        f = np.concatenate([np.zeros(pad // 2), f, np.zeros(pad - pad // 2)])
    rng = np.random.default_rng(1)
    f_noisy = f + rng.uniform(0.0, 1e-12, size=len(f))
    p = Polisher(f_noisy, deadline)
    r_exact = exact_ratio(p.conv(f))
    if r_exact > p.best:                                   # the noise must not cost anything: keep the exact copy
        p.best, p.best_f = r_exact, f
    r0 = p.best
    out, r = p.run()
    print(f"repeated {k}x and padded to {len(f):,} steps: R = {r0:.13f}; polished: {r:.13f} ({r - r0:+.3e})")
    return out
