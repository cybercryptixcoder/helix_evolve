"""The polish behind the July 2026 record (ClaudeExplorer, github.com/justinkang221/second-autocorrelation-inequality,
experiments/12_hyra_campaign: run_velocity_continue.py and accelerated_optimizer.py), rewritten for one CPU core and
a CPU-time budget.

Velocity cycles: add small uniform noise (about 1e-8 x max f, on every cell, so dead cells can come back) plus
momentum along the last improving step, re-polish with iterated Dinkelbach, keep the result only if the exact R
improved; on a gain the momentum becomes that gain's step, otherwise it halves. On GPUs this kept gaining for 100+
cycles in the record's basin. The result is never worse than the start.
"""


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + 0.9 * budget_seconds - 3.0
    if start is None:
        x = np.linspace(-0.5, 0.5, 20002)[1:-1]
        start = 1.0 / np.sqrt(1.0 - 4.0 * x * x)
    rng = np.random.default_rng(int(time.time() * 1e6) % (2 ** 32))
    first = Polisher(start, deadline)
    r0 = first.best
    f_best, r_best = first.best_f, first.best
    v = np.zeros_like(f_best)
    noise, alpha, cycle = 1e-8, 0.3, 0
    per_cycle = max(20.0, (deadline - time.process_time()) / 4.0)       # about four cycles in the budget
    while time.process_time() < deadline - 5.0:
        cycle += 1
        pert = np.maximum(f_best + alpha * v + rng.uniform(0.0, noise * f_best.max(), size=len(f_best)), 0.0)
        p = Polisher(pert, min(deadline, time.process_time() + per_cycle))
        f_new, r_new = p.run(rounds=2, iters=40, log=lambda m: None)
        if r_new > r_best + 1e-15:
            v = f_new / f_new.max() - f_best / f_best.max()
            f_best, r_best = f_new / f_new.max(), r_new
            print(f"cycle {cycle}: R = {r_best:.13f} (gain)")
        else:
            v *= 0.5
            print(f"cycle {cycle}: no gain ({r_new:.13f})")
    print(f"start {r0:.13f} -> {r_best:.13f} ({r_best - r0:+.3e}), n = {len(f_best)}, {cycle} cycles")
    return f_best
