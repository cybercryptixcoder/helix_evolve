import numpy as np
import time

def _score(h):
    h = np.asarray(h, dtype=float)
    if h.size == 0 or not np.all(np.isfinite(h)) or h.sum() <= 0 or h.min() < 0:
        return -1.0
    conv = np.convolve(h, h)
    L = np.empty(conv.size + 2)
    L[0] = 0.0; L[-1] = 0.0; L[1:-1] = conv
    a = L[:-1]; b = L[1:]
    l2 = np.sum(a*a + a*b + b*b) / 3.0
    l1 = h.sum()**2
    linf = L.max()
    if linf <= 0 or l1 <= 0:
        return -1.0
    return l2/(l1*linf)

def construct(budget_seconds, start):
    t0 = time.process_time()
    deadline = t0 + budget_seconds * 0.85
    def oot():
        return time.process_time() > deadline

    best_h = None
    best_s = -1.0

    def consider(h):
        nonlocal best_h, best_s
        h = np.asarray(h, dtype=float)
        if h.size < 1 or h.size > 50000:
            return False
        if not np.all(np.isfinite(h)) or h.min() < 0 or h.sum() <= 0:
            return False
        s = _score(h)
        if s > best_s:
            best_s = s
            best_h = h.copy()
            return True
        return False

    if start is not None:
        try:
            consider(np.asarray(start, dtype=float))
        except Exception:
            pass
    if best_h is None:
        x = np.linspace(-1, 1, 70)
        best_h = np.cos(np.pi*x/2.0)**1.0
        best_s = _score(best_h)

    rng = np.random.default_rng(20240607)

    def normalize(h):
        h = np.clip(h, 0, None)
        s = h.sum()
        return h/s if s > 0 else h

    def local_refine(h, iters, scale0, patience=8, M=16):
        h = normalize(np.array(h, dtype=float))
        cur_s = _score(h)
        n = h.size
        scale = scale0
        stall = 0
        logh = np.log(h + 1e-300)
        for _ in range(iters):
            if oot():
                break
            cands = np.repeat(logh[None, :], M, axis=0)
            for j in range(M):
                bw = max(1, int(n*rng.uniform(0.02, 0.5)))
                lo = int(rng.integers(0, max(1, n-bw+1)))
                hi = min(n, lo+bw)
                cands[j, lo:hi] += rng.normal(0, scale, hi-lo)
            ch = np.exp(cands)
            sums = ch.sum(axis=1, keepdims=True)
            sums[sums <= 0] = 1.0
            ch = ch/sums
            scores = np.array([_score(c) for c in ch])
            k = int(np.argmax(scores))
            if scores[k] > cur_s + 1e-15:
                h = ch[k].copy()
                logh = np.log(h + 1e-300)
                cur_s = scores[k]
                stall = 0
                if cur_s > best_s:
                    consider(h)
            else:
                stall += 1
                if stall >= patience:
                    scale *= 0.55
                    stall = 0
                    if scale < 1e-9:
                        break
        return h

    def coord_refine(h, passes=3):
        h = normalize(np.asarray(h, dtype=float))
        n = h.size
        cur_s = _score(h)
        for _ in range(passes):
            if oot():
                break
            improved = False
            for i in range(n):
                if oot():
                    break
                base = h[i]
                best_val = base
                best_local = cur_s
                for mul in (0.85, 0.92, 0.97, 1.03, 1.08, 1.18):
                    h[i] = base * mul
                    s = _score(h)
                    if s > best_local + 1e-15:
                        best_local = s
                        best_val = base * mul
                h[i] = best_val
                if best_local > cur_s + 1e-15:
                    cur_s = best_local
                    improved = True
                    if cur_s > best_s:
                        consider(h)
            if not improved:
                break
        return h

    def resample(h, newN):
        if newN == h.size:
            return h.copy()
        xi = np.linspace(0, 1, h.size)
        xn = np.linspace(0, 1, newN)
        return np.interp(xn, xi, h)

    cur = local_refine(best_h, 300, 0.05, patience=10)
    cur = local_refine(cur, 250, 0.01, patience=8)

    sym = 0.5*(best_h + best_h[::-1])
    local_refine(sym, 250, 0.02, patience=8)
    consider(sym)

    coord_refine(best_h, passes=2)

    base_N = best_h.size
    for dn in [1, -1, 2, -2, 3, -3, 4, -4, 6, -6, 8, -8, 12, -12, 16, -16,
               20, -20, 30, -30, 40, -40, 60, -60, 80, -80, 100, -100,
               -150, 150, -200, 200]:
        if oot():
            break
        nn = base_N + dn
        if 4 <= nn <= 50000:
            cand = resample(best_h, nn)
            local_refine(cand, 180, 0.02, patience=6)
            consider(cand)

    last_polished = -1.0
    while not oot():
        cand = best_h.copy()
        op = int(rng.integers(0, 8))
        if op == 0:
            cand = cand * np.exp(rng.normal(0, 0.01, cand.size))
        elif op == 1:
            i = rng.integers(0, cand.size)
            w = max(1, cand.size//10)
            lo = max(0, i-w); hi = min(cand.size, i+w)
            cand[lo:hi] *= np.exp(rng.normal(0, 0.03, hi-lo))
        elif op == 2:
            k = int(rng.integers(2, max(3, cand.size//15+2)))
            cand = np.convolve(cand, np.ones(k)/k, mode='same')
        elif op == 3:
            newN = max(4, min(50000, cand.size + int(rng.integers(-max(1, cand.size//8), max(2, cand.size//8)))))
            cand = resample(cand, newN)
        elif op == 4:
            x = np.linspace(-1, 1, cand.size)
            cand = cand * np.exp(rng.normal(0, 0.04)*x)
        elif op == 5:
            n = cand.size
            k = max(2, n//12)
            pert = np.convolve(rng.normal(0, 1, n), np.ones(k)/k, mode='same')
            cand = cand * np.exp(0.03*pert)
        elif op == 6:
            cand = 0.5*(cand + cand[::-1])
        else:
            cand = cand * np.exp(rng.normal(0, 0.005, cand.size))
        cand = np.clip(cand, 0, None)
        if cand.sum() <= 0:
            continue
        if consider(cand):
            local_refine(cand, 200, 0.02, patience=6)
            if best_s > last_polished + 1e-7 and not oot():
                coord_refine(best_h, passes=1)
                last_polished = best_s

    return np.asarray(best_h, dtype=float)
