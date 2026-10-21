import numpy as np
import time


def _score(h):
    h = np.asarray(h, dtype=float)
    conv = np.convolve(h, h)
    L = np.concatenate(([0.0], conv, [0.0]))
    Lp = L[:-1]
    Ln = L[1:]
    num = np.sum(Lp * Lp + Lp * Ln + Ln * Ln) / 3.0
    s = np.sum(h)
    den1 = s * s
    mx = np.max(L)
    if den1 <= 0 or mx <= 0:
        return 0.0, L
    return num / (den1 * mx), L


def _resample(h, N):
    h = np.asarray(h, dtype=float)
    M = h.size
    if M == N:
        return h.copy()
    edges_old = np.arange(M + 1) / M
    cum = np.concatenate(([0.0], np.cumsum(h)))
    total = cum[-1]
    if total <= 0:
        return np.ones(N) / N
    cum = cum / total
    edges_new = np.arange(N + 1) / N
    Cnew = np.interp(edges_new, edges_old, cum)
    mass = np.maximum(np.diff(Cnew), 0.0)
    return mass * N


def construct(budget_seconds, start):
    t0 = time.process_time()

    def elapsed():
        return time.process_time() - t0

    rng = np.random.default_rng(20240619)

    # Baseline: use start if given, else a reasonable default.
    if start is not None:
        best_h = np.asarray(start, dtype=float).copy()
        if np.max(best_h) > 0:
            best_h = best_h / np.max(best_h)
        best_score, _ = _score(best_h)
    else:
        best_h = np.ones(300)
        best_score, _ = _score(best_h)
    keep_best(best_h)
    print("stage init: %.6f -> %.6f, %.3f s" % (best_score, best_score, elapsed()))

    def block_optimize(h, deadline, block=10, step0=0.15, max_passes=200):
        h = h.copy()
        sc, _ = _score(h)
        N = h.size
        step = step0
        nblocks = (N + block - 1) // block
        for _ in range(max_passes):
            if elapsed() > deadline:
                break
            improved = False
            order = rng.permutation(nblocks)
            for b in order:
                if elapsed() > deadline:
                    break
                i0 = b * block
                i1 = min(N, i0 + block)
                old = h[i0:i1].copy()
                mx = np.max(h) if np.max(h) > 0 else 1.0
                for fac in (1.0 + step, 1.0 / (1.0 + step), 1.0 - step):
                    if fac <= 0:
                        continue
                    h[i0:i1] = old * fac
                    s2, _ = _score(h)
                    if s2 > sc:
                        sc = s2
                        old = h[i0:i1].copy()
                        improved = True
                    else:
                        h[i0:i1] = old
                for delta in (step, -step):
                    h[i0:i1] = np.maximum(0.0, old + delta * mx)
                    s2, _ = _score(h)
                    if s2 > sc:
                        sc = s2
                        old = h[i0:i1].copy()
                        improved = True
                    else:
                        h[i0:i1] = old
            if not improved:
                step *= 0.5
                if step < 1e-4:
                    break
        return h, sc

    def apply_dents(h, n_dents, rng):
        """Multiplicative Gaussian dents near f*f argmax."""
        h = h.copy()
        N = h.size
        conv = np.convolve(h, h)
        L = np.concatenate(([0.0], conv, [0.0]))
        argmax = int(np.argmax(L))
        # map knot index (0..2N) to h index (0..N)
        center = argmax / 2.0 / max(N, 1)
        center = min(max(center, 0.0), 1.0)
        x = (np.arange(N) + 0.5) / N
        for _ in range(n_dents):
            amp = 0.001 + 0.049 * rng.random()
            width = 0.02 + 0.18 * rng.random()
            c = center + rng.normal(0, 0.05)
            g = np.exp(-0.5 * ((x - c) / width) ** 2)
            sign = -1.0 if rng.random() < 0.7 else 1.0
            h = h * (1.0 + sign * amp * g)
        h = np.maximum(h, 0.0)
        if np.max(h) > 0:
            h = h / np.max(h)
        return h

    # Stage: noisy multi-N restarts with interleaved dents.
    stage_start = best_score
    deadline = budget_seconds * 0.92
    Ns = [250, 300, 350, 400, 450]
    blocks = [4, 6, 8, 10, 12, 14, 16]
    restart_count = 0
    while elapsed() < deadline:
        rem = deadline - elapsed()
        cur_N = Ns[restart_count % len(Ns)]
        block = blocks[restart_count % len(blocks)]
        step0 = 0.10 + 0.05 * rng.random()
        base = _resample(best_h, cur_N)
        sigma = 0.004 + 0.026 * rng.random()
        noise = rng.normal(0, sigma, base.size)
        h = np.maximum(0.0, base * (1.0 + noise))
        if np.max(h) > 0:
            h = h / np.max(h)
        # every few restarts, apply dents
        if restart_count % 3 == 0:
            n_dents = 1 + int(rng.integers(0, 3))
            h = apply_dents(h, n_dents, rng)
        dl = elapsed() + max(0.15, rem * 0.55)
        h2, sc2 = block_optimize(h, dl, block=block, step0=step0, max_passes=100)
        restart_count += 1
        if sc2 > best_score:
            best_score = sc2
            best_h = h2
            keep_best(best_h)
            print("  improve -> %.6f (N=%d, block=%d, sigma=%.3f), %.3f s" % (
                best_score, h2.size, block, sigma, elapsed()))
    print("stage restarts: %.6f -> %.6f, %d restarts, %.3f s" % (
        stage_start, best_score, restart_count, elapsed()))

    # Stage: final coordinate polish on best.
    stage_start = best_score
    polish_deadline = budget_seconds * 0.97
    h, sc = block_optimize(best_h, polish_deadline, block=2, step0=0.05, max_passes=200)
    if sc > best_score:
        best_score = sc
        best_h = h
        keep_best(best_h)
    print("stage polish: %.6f -> %.6f, %.3f s" % (stage_start, best_score, elapsed()))

    keep_best(best_h)
    return best_h
