import numpy as np
import time
from scipy.optimize import linprog, minimize


def exact_C(h):
    N = h.size
    S = h.sum()
    c = np.convolve(h, h)
    return 2.0 * N * c.max() / (S * S)


def _active_knots(c, tol=1e-6, cap=128):
    M = c.max()
    active = np.where(c >= M - tol * M)[0]
    if active.size > cap:
        active = active[np.argsort(c[active])[-cap:]]
    return active


def adam_polish(z, N, deadline, best_h, best_C, lr0=0.0015, top_k=1):
    beta1, beta2 = 0.9, 0.999
    eps = 1e-8
    m = np.zeros(N)
    v = np.zeros(N)
    step = 0
    js = np.arange(N)
    while True:
        if time.process_time() > deadline:
            break
        lr = lr0 * 0.5 ** (step // 1500)
        h = np.exp(z)
        S = h.sum()
        c = np.convolve(h, h)
        if top_k == 1:
            k = int(np.argmax(c))
            ck = c[k]
            g_h = np.zeros(N)
            j_lo = max(0, k - (N - 1))
            j_hi = min(N - 1, k)
            if j_lo <= j_hi:
                jj = np.arange(j_lo, j_hi + 1)
                idx = k - jj
                g_h[jj] = h[idx]
            g_h = 4.0 * N * (g_h * S - ck) / (S * S * S)
        else:
            active = _active_knots(c)
            acc = np.zeros(N)
            for k in active:
                idx = k - js
                valid = (idx >= 0) & (idx <= N - 1)
                contrib = np.zeros(N)
                contrib[valid] = h[idx[valid]] * S - c[k]
                acc += contrib
            g_h = 4.0 * N * acc / (active.size * S * S * S)
        g_z = g_h * h
        m = beta1 * m + (1 - beta1) * g_z
        v = beta2 * v + (1 - beta2) * (g_z * g_z)
        m_hat = m / (1 - beta1 ** (step + 1))
        v_hat = v / (1 - beta2 ** (step + 1))
        z = z - lr * m_hat / (np.sqrt(v_hat) + eps)
        step += 1
        if step % 300 == 0:
            z = z + 5e-4 * np.random.randn(N)
        if step % 15 == 0 or step == 1:
            h = np.exp(z)
            C = exact_C(h)
            if C < best_C:
                best_C = C
                best_h = h.copy()
    return z, best_h, best_C


def newton_targeted(h, best_h, best_C, deadline, n_iters=100,
                    tol_rel=1e-2, cap=1024, eta0=1e-3):
    N = h.size
    h = np.maximum(h, 0.0)
    s = h.sum()
    if s <= 0:
        return best_h, best_C
    h = h / s
    eta = eta0
    for _ in range(n_iters):
        if time.process_time() > deadline:
            break
        S = h.sum()
        c = np.convolve(h, h)
        M = c.max()
        active = np.where(c >= M - tol_rel * M)[0]
        if active.size > cap:
            active = active[np.argsort(c[active])[-cap:]]
        if active.size == 0:
            break
        A = np.zeros((active.size, N))
        for row, k in enumerate(active):
            j_lo = max(0, k - (N - 1))
            j_hi = min(N - 1, k)
            if j_lo > j_hi:
                continue
            jj = np.arange(j_lo, j_hi + 1)
            idx = k - jj
            A[row, jj] = 2.0 * h[idx]
        A_aug = np.vstack([A, np.ones((1, N))])
        accepted = False
        local_eta = eta
        for _eta_try in range(20):
            if time.process_time() > deadline:
                break
            target = (1.0 - local_eta) * M
            rhs = target - c[active]
            rhs_aug = np.concatenate([rhs, [0.0]])
            try:
                delta, *_ = np.linalg.lstsq(A_aug, rhs_aug, rcond=None)
            except Exception:
                local_eta *= 0.5
                continue
            alpha = 1.0
            for _ls in range(25):
                if time.process_time() > deadline:
                    break
                h_new = h + alpha * delta
                if np.any(h_new < 0):
                    alpha *= 0.5
                    continue
                s_new = h_new.sum()
                if s_new <= 0:
                    alpha *= 0.5
                    continue
                h_new = h_new / s_new
                C_new = exact_C(h_new)
                if C_new < best_C - 1e-14:
                    h = h_new
                    best_h = h_new.copy()
                    best_C = C_new
                    accepted = True
                    eta = max(1e-7, local_eta * 0.7)
                    break
                alpha *= 0.5
            if accepted:
                break
            local_eta *= 0.5
        if not accepted:
            eta *= 0.5
            if eta < 1e-7:
                break
    return best_h, best_C


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85
    rng = np.random.default_rng(12345)

    # ============================================================
    # EXPERIMENT: multi-restart from p0139's heights, then final Newton
    # ============================================================
    if start is not None:
        h0 = np.asarray(start, dtype=float).ravel()
        h0 = np.maximum(h0, 1e-12)
    else:
        h0 = np.ones(4800)
    h0 = h0 / h0.sum()
    N = h0.size

    best_h = h0.copy()
    best_C = exact_C(best_h)

    # Build 30 perturbed starts
    starts = []
    sigmas = [1e-3, 3e-3, 1e-2]
    for i in range(20):
        sigma = sigmas[i % 3]
        z = np.log(np.maximum(h0, 1e-12)) + sigma * rng.standard_normal(N)
        h = np.exp(z)
        h = h / h.sum()
        starts.append(h)
    # structured: 5 multiplicative eps*x, 5 tilted/skewed
    epss = [1e-2, 3e-2, 1e-2, 3e-2, 1e-2]
    for i in range(5):
        eps = epss[i]
        x = rng.standard_normal(N)
        h = h0 * (1.0 + eps * x)
        h = np.maximum(h, 1e-12)
        h = h / h.sum()
        starts.append(h)
    t = np.linspace(-0.5, 0.5, N)
    for i in range(5):
        amp = [1e-2, 3e-2, 1e-2, 3e-2, 1e-2][i]
        shape = [t, t * t, np.abs(t), np.sin(np.pi * t), np.cos(np.pi * t)][i]
        h = h0 * (1.0 + amp * shape)
        h = np.maximum(h, 1e-12)
        h = h / h.sum()
        starts.append(h)

    # Per-restart time slice: leave ~35% for final Newton
    n_restarts = len(starts)
    restart_budget = budget_seconds * 0.55
    slice_time = restart_budget / n_restarts

    for idx, hs in enumerate(starts):
        if time.process_time() > deadline:
            break
        slice_deadline = min(time.process_time() + slice_time, deadline)
        try:
            bh, bC = newton_targeted(
                hs.copy(), hs.copy(), exact_C(hs),
                deadline=slice_deadline, n_iters=60,
                tol_rel=1e-4, cap=512, eta0=1e-3)
            if bC < best_C:
                best_C = bC
                best_h = bh.copy()
        except Exception:
            continue

    # Final Newton polish
    if time.process_time() < deadline:
        best_h, best_C = newton_targeted(
            best_h.copy(), best_h, best_C,
            deadline=deadline, n_iters=200,
            tol_rel=1e-6, cap=1024, eta0=1e-5)

    return best_h
