import numpy as np
import time
from scipy.optimize import linprog


def _C(h):
    s = h.sum()
    if s <= 0:
        return np.inf
    return 2.0 * h.size * float(np.max(np.convolve(h, h))) / (s * s)


def _norm(h):
    h = np.maximum(h, 0.0)
    s = h.sum()
    if s <= 0:
        return np.ones_like(h) / h.size
    return h / s


def _resample(hh, N):
    m = hh.size
    if m == N:
        return hh.copy()
    # area-preserving resample
    xi = (np.arange(N) + 0.5) / N * m - 0.5
    xi = np.clip(xi, 0, m - 1)
    i0 = np.floor(xi).astype(int)
    i1 = np.minimum(i0 + 1, m - 1)
    f = xi - i0
    out = hh[i0] * (1 - f) + hh[i1] * f
    # preserve integral approximately
    if out.sum() > 0:
        out = out * (hh.sum() / out.sum())
    return out


def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds - 1.2

    s = None
    if start is not None:
        a = np.asarray(start, dtype=float).ravel()
        if a.size >= 1 and a.size <= 30000 and np.all(np.isfinite(a)) and a.sum() > 0:
            s = a
    if s is None:
        N = 160
        x = (np.arange(N) + 0.5) / N - 0.5
        s = np.maximum(np.cos(np.pi * x) ** 2, 1e-6)
    best = _norm(s).copy()
    bestC = _C(best)
    print(f"start C={bestC:.7f} N={best.size}")

    rng = np.random.default_rng(31337)

    def slp(h, max_iter=200, dl=None, thresh=0.9, cap=160, reexpand=False):
        h = _norm(h).copy()
        n = h.size
        cur = _C(h)
        stall = 0
        for it in range(max_iter):
            if dl is not None and time.process_time() >= dl:
                break
            hh = np.convolve(h, h)
            M0 = float(hh.max())
            th = thresh
            if reexpand and it < 6:
                th = max(thresh, 0.78)
            active = np.flatnonzero(hh >= th * M0)
            if active.size > cap:
                order = np.argsort(-hh[active])
                active = np.sort(active[order[:cap]])
            nk = active.size
            A_ub = np.zeros((nk, n + 1))
            b_ub = hh[active].copy()
            for row in range(nk):
                k = int(active[row])
                lo = max(0, k - (n - 1))
                hi = min(n - 1, k)
                ii = np.arange(lo, hi + 1)
                A_ub[row, ii] = 2.0 * h[k - ii]
                A_ub[row, -1] = -1.0
            A_eq = np.zeros((1, n + 1))
            A_eq[0, :n] = 1.0
            cobj = np.zeros(n + 1)
            cobj[-1] = 1.0
            bounds = [(0, None)] * n + [(0, None)]
            try:
                res = linprog(cobj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq,
                              b_eq=np.array([1.0]), bounds=bounds, method='highs')
            except Exception:
                break
            if not res.success:
                break
            h_new = _norm(res.x[:n])
            newC = _C(h_new)
            improved = False
            if newC < cur - 1e-15:
                h, cur, improved = h_new, newC, True
            else:
                for alpha in (0.7, 0.5, 0.35, 0.2, 0.1, 0.05, 0.02):
                    h_mid = _norm((1 - alpha) * h + alpha * h_new)
                    midC = _C(h_mid)
                    if midC < cur - 1e-15:
                        h, cur, improved = h_mid, midC, True
                        break
            if not improved:
                stall += 1
                if stall >= 2:
                    break
            else:
                stall = 0
        return h, cur

    def coord(h, cur, dl, rounds=100):
        h = h.copy()
        n = h.size
        c = np.convolve(h, h)
        S = h.sum()
        for _ in range(rounds):
            if time.process_time() >= dl:
                break
            improved = False
            for a in rng.permutation(n):
                if time.process_time() >= dl:
                    break
                k = int(np.argmax(c))
                M = c[k]
                lo = max(0, k - (n - 1))
                hi = min(n - 1, k)
                if a < lo or a > hi:
                    continue
                b = k - a
                ha = h[a]
                if a == b:
                    R = M - ha * ha
                    Sn = S - ha
                    if Sn <= 1e-15:
                        continue
                    nv = R / Sn
                else:
                    hb = h[b]
                    R = M - 2.0 * ha * hb
                    Sn = S - ha
                    nv = (hb * Sn - R) / (2.0 * hb) if hb > 1e-15 else 0.0
                if nv < 0:
                    nv = 0.0
                if abs(nv - ha) < 1e-15:
                    continue
                delta = nv - ha
                kk = np.arange(a, a + n)
                upd = 2.0 * delta * h[kk - a]
                c[kk] += upd
                S += delta
                h[a] = nv
                cc = 2.0 * n * float(c.max()) / (S * S)
                if cc < cur - 1e-16:
                    cur = cc
                    improved = True
                else:
                    c[kk] -= upd
                    S -= delta
                    h[a] = ha
            if not improved:
                break
        return h, cur

    def smooth_perturb(h, cur, dl):
        n = h.size
        if n < 8:
            return h, cur
        besth, bestc = h, cur
        for sigma in (0.35, 0.5, 0.7, 1.0, 1.4, 2.0):
            r = max(1, int(3 * sigma))
            if r * 2 + 1 > n:
                continue
            x = np.arange(-r, r + 1)
            k = np.exp(-0.5 * (x / sigma) ** 2)
            k /= k.sum()
            hp = np.convolve(np.pad(h, r, mode='edge'), k, mode='valid')
            hp = _norm(hp)
            cp = _C(hp)
            if cp < bestc - 1e-14:
                besth, bestc = hp, cp
        return besth, bestc

    def local_polish(h, dl, rounds=3):
        c = _C(h)
        for r in range(rounds):
            if time.process_time() >= dl:
                break
            h2, c2 = slp(h, max_iter=140, dl=dl, thresh=0.85, cap=300, reexpand=True)
            if c2 < c:
                h, c = h2, c2
            h2, c2 = coord(h, c, dl, rounds=250)
            if c2 < c:
                h, c = h2, c2
            h2, c2 = smooth_perturb(h, c, dl)
            if c2 < c:
                h, c = h2, c2
            if r < rounds - 1 and time.process_time() < dl - 0.5:
                for trial in range(3):
                    hp = _norm(h * (1.0 + 0.006 * rng.standard_normal(h.size)))
                    hp, cp = slp(hp, max_iter=50, dl=min(dl, time.process_time() + 0.5),
                                 thresh=0.85, cap=200, reexpand=True)
                    if cp < c:
                        h, c = hp, cp
                        break
        return h, c

    # Phase 1: strong polish of start
    p1 = min(deadline, t0 + budget_seconds * 0.24)
    h, c = local_polish(best, p1, rounds=2)
    if c < bestC:
        best, bestC = h.copy(), c
    print(f"p1 C={bestC:.7f} N={best.size}")

    # Phase 2: multi-N exploration with both up and down sweeps
    p2 = min(deadline, t0 + budget_seconds * 0.80)
    base0 = best.size
    tried = set()
    # alternate up/down sweep from base
    deltas = []
    for k in [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7, -8, 8,
              -10, 10, -12, 12, -14, 14, -16, 16, -20, 20, -24, 24, -30, 30,
              -36, 36, -44, 44, -52, 52, -64, 64, -80, 80, -100, 100]:
        deltas.append(k)
    idx = 0
    while time.process_time() < p2 - 0.4:
        if idx < len(deltas):
            Nn = base0 + deltas[idx]
            idx += 1
        else:
            r = int(rng.integers(-200, 200))
            Nn = best.size + r
        if Nn < 8 or Nn > 30000 or Nn in tried:
            continue
        tried.add(Nn)
        h0 = _norm(_resample(best, Nn))
        if rng.random() < 0.5:
            h0 = _norm(h0 * (1.0 + 0.03 * rng.standard_normal(Nn)))
        dl = min(p2 - 0.25, time.process_time() + 1.4)
        h0, c0 = slp(h0, max_iter=100, dl=dl, thresh=0.85, cap=220, reexpand=True)
        h0, c0 = coord(h0, c0, min(dl, time.process_time() + 0.7), rounds=120)
        h0, c0 = smooth_perturb(h0, c0, dl)
        if c0 < bestC - 1e-13:
            best, bestC = h0.copy(), c0
            print(f"best C={bestC:.7f} N={best.size}")

    # Phase 3: final aggressive polish
    p3 = deadline - 0.15
    h, c = local_polish(best, p3, rounds=3)
    if c < bestC:
        best, bestC = h.copy(), c
    h, c = slp(best, max_iter=500, dl=p3, thresh=0.80, cap=400, reexpand=True)
    if c < bestC:
        best, bestC = h.copy(), c
        h, c = coord(best, bestC, p3, rounds=300)
        if c < bestC:
            best, bestC = h.copy(), c

    print(f"final C={bestC:.7f} N={best.size}")
    return np.asarray(best, dtype=float)
