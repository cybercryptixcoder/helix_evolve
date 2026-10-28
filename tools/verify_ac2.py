"""Independent verification of a lower bound for the second autocorrelation constant C2.

    python tools/verify_ac2.py results/v4/atlas-s1/best.npy [more.npy ...]
    python tools/verify_ac2.py --alphaevolve-may-2025        # DeepMind's published 50-step function, for comparison

For a non-negative step function with heights h (N equal steps), C2 >= ||f*f||_2^2 / (||f*f||_1 ||f*f||_inf), and
f*f is piecewise linear with knots at the values of the discrete autoconvolution h*h, so every norm is exact. The
score is computed three independent ways:

1. Helix's evaluator (`helix4.problems.ac2.score`).
2. A line-by-line port of DeepMind's own verification cell (google-deepmind/alphaevolve_results,
   mathematical_results.ipynb, section B.2, and alphaevolve_repository_of_problems, autocorrelation_problems.ipynb):
   piecewise-linear integration on [-1/2, 1/2] with N+1 equal intervals.
3. Exact rational arithmetic, no floating point at all: up to 12,000 steps on the float heights themselves (every
   float is an exact dyadic rational); above that on a copy with the heights rounded to integers, which is itself a
   valid construction, so its exact value is a certified lower bound (rounding moves the score by ~1e-6).

Nothing here is used by the search: the agents never see this file.
"""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helix4.problems import ac2  # noqa: E402

# DeepMind, AlphaEvolve (May 2025): "AlphaEvolve found a step function with 50 equally-spaced intervals on [-1/4,1/4]
# that gives a slightly better lower bound 0.8962 <= C2" (alphaevolve_results/mathematical_results.ipynb, B.2)
ALPHAEVOLVE_MAY_2025 = [
    0.0022217502753395443, 0.798058737836952, 0.4369294656327977, 1.1704958412868685, 1.3413665690827143,
    1.5342366222696133, 1.7690742844401723, 1.9329450122360183, 2.2225113878900893, 1.9363966992163675,
    2.0382191032475467, 2.2010898310433933, 2.0229605588392388, 2.029541518023742, 2.2636974412575626,
    1.9622346498507677, 2.0781053776466134, 2.9856571697702514, 3.4418422600649374, 3.3477129878607825,
    3.253250196453988, 3.420135507780267, 3.2509579118114464, 3.2308578066681575, 3.4707132763246245,
    2.6462657430572087, 0.9614362498214617, 0, 0.0008733532713782356, 0.00041056186458359313,
    0.00029587319086208687, 5.039012949497012e-06, 0, 0.5858888998745988, 6.741440691998236, 7.934548956206666e-06,
    0.00013382382526231794, 4.551621108101551e-06, 0.0008898629473865954, 1.083008496291632e-05,
    0.0006121618352774956, 0.0011493704284828532, 7.157034681754761, 9.111886252846807, 3.3127569806426527,
    8.556232703271356e-06, 0.00017950056213609822, 2.7122354902710758e-06, 1.4036462843158317e-05,
    1.1451768709981007e-05]


def deepmind_score(heights):
    """DeepMind's verification cell, ported line by line (only the loop is vectorised; above 200,000 steps the
    convolution is done by FFT, since np.convolve's direct sum would take days at 2,000,000)."""
    h = np.asarray(heights, dtype=float)
    if len(h) <= 200_000:
        convolution_2 = np.convolve(h, h)
    else:
        from scipy.signal import fftconvolve
        convolution_2 = fftconvolve(h, h)
    num_points = len(convolution_2)
    x_points = np.linspace(-0.5, 0.5, num_points + 2)
    x_intervals = np.diff(x_points)
    y_points = np.concatenate(([0], convolution_2, [0]))
    y1, y2 = y_points[:-1], y_points[1:]
    l2_norm_squared = float(np.sum((x_intervals / 3) * (y1 ** 2 + y1 * y2 + y2 ** 2)))
    norm_1 = np.sum(np.abs(convolution_2)) / (len(convolution_2) + 1)
    norm_inf = np.max(np.abs(convolution_2))
    return l2_norm_squared / (norm_1 * norm_inf)


def _ratio(conv_ints, l1):
    g = [0] + [int(v) for v in conv_ints] + [0]
    l2x3 = sum(a * a + a * b + b * b for a, b in zip(g[:-1], g[1:]))     # 3 * sum(...) as an exact integer
    return Fraction(l2x3, 3 * l1 * max(g))


def exact_score(heights):
    """(Fraction, how) - the exact value of the construction, or of a rounded copy of it (itself a valid construction).

    N <= 12,000: the float heights themselves, exactly (each float is a dyadic rational; scaled to integers).
    larger: heights rounded to integers at 2^30, exact integer convolution (three 10-bit limbs by FFT, checked).
    """
    h = np.asarray(heights, dtype=float)
    n = len(h)
    if n > 400_000:
        return None, "skipped above 400,000 steps (too slow in exact integers); the arena's own verifier is the judge"
    if n <= 12000:
        fr = [Fraction(float(x)) for x in h]
        den = max(f.denominator for f in fr)
        hi = [int(f * den) for f in fr]
        conv = [0] * (2 * n - 1)
        for i, a in enumerate(hi):
            if a:
                for j, b in enumerate(hi):
                    conv[i + j] += a * b
        return _ratio(conv, sum(hi) ** 2), "exact, the float heights themselves"
    # larger N: heights rounded to integers at 2^30 (a valid construction itself; rounding moves the score ~1e-9),
    # split into three 10-bit limbs; each limb-by-limb convolution is done by FFT (every value < 2^38, so float64
    # rounding error is far below 0.5) and rounded to exact integers (checked), then recombined exactly
    hi = np.rint(h / h.max() * ((1 << 30) - 1)).astype(np.int64)      # < 2^30, so three 10-bit limbs hold it
    limbs = [(hi >> (10 * k)) & 1023 for k in range(3)]
    size = 1 << int(np.ceil(np.log2(2 * n - 1)))
    F = [np.fft.rfft(l.astype(float), size) for l in limbs]
    conv = [0] * (2 * n - 1)
    worst = 0.0
    for i in range(3):
        for j in range(i, 3):
            c = np.fft.irfft(F[i] * F[j], size)[: 2 * n - 1]
            ci = np.rint(c)
            worst = max(worst, float(np.max(np.abs(c - ci))))
            mult = (1 << (10 * (i + j))) * (1 if i == j else 2)
            conv = [x + int(v) * mult for x, v in zip(conv, ci.astype(np.int64))]
    if worst > 0.25:
        return None, f"FFT not accurate enough for an exact check (error {worst:.2f})"
    return _ratio(conv, int(hi.sum()) ** 2), "exact, heights rounded at 2^30, integer convolution by limbs (checked)"


def arena_score(h):
    """EinsteinArena's verifier for this problem (problem 3, as its API publishes it), line by line."""
    from scipy.signal import oaconvolve
    f = np.maximum(np.asarray(h, dtype=float), 0.0)
    convolution = oaconvolve(f, f, mode="full")
    num_conv_points = len(convolution)
    x_points = np.linspace(-0.5, 0.5, num_conv_points + 2)
    x_intervals = np.diff(x_points)
    y_points = np.concatenate(([0], convolution, [0]))
    y1, y2 = y_points[:-1], y_points[1:]
    l2_norm_squared = float(np.sum((x_intervals / 3) * (y1 ** 2 + y1 * y2 + y2 ** 2)))
    norm_1 = np.sum(np.abs(convolution)) / (num_conv_points + 1)
    norm_inf = np.max(np.abs(convolution))
    return float(l2_norm_squared / (norm_1 * norm_inf))


def verify(heights, label="", max_n=None):
    old = ac2.MAX_N
    ac2.MAX_N = max(old, int(max_n or 0))           # v4.7 and later allow larger constructions (v10: 2,000,000)
    try:
        h, problem = ac2.check(np.asarray(heights, dtype=float))
    finally:
        ac2.MAX_N = old
    if h is None:
        return {"label": label, "valid": False, "problem": problem}
    out = {"label": label, "valid": True, "N": int(len(h)), "helix": ac2.score(h), "deepmind_code": deepmind_score(h),
           "arena_code": arena_score(h)}
    frac, how = exact_score(h)
    out["exact_how"] = how
    if frac is not None:
        out["exact"] = float(frac)
        out["exact_str"] = str(frac.numerator * 10 ** 12 // frac.denominator).rjust(13, "0")
        out["exact_str"] = out["exact_str"][:-12] + "." + out["exact_str"][-12:]
    out["agree"] = (abs(out["helix"] - out["deepmind_code"]) < 1e-9 and abs(out["helix"] - out["arena_code"]) < 1e-9
                    and (frac is None or abs(float(frac) - out["helix"]) < 1e-7))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help=".npy files of step heights")
    ap.add_argument("--alphaevolve-may-2025", action="store_true", help="also verify DeepMind's published construction")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows = []
    if a.alphaevolve_may_2025 or not a.files:
        rows.append(verify(ALPHAEVOLVE_MAY_2025, "AlphaEvolve (May 2025), 50 steps"))
    for f in a.files:
        rows.append(verify(np.load(f), f))
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    for r in rows:
        if not r["valid"]:
            print(f"{r['label']}: INVALID ({r['problem']})")
            continue
        ex = r.get("exact_str", "-")
        print(f"{r['label']}\n   N = {r['N']}\n   Helix evaluator   {r['helix']:.12f}\n   DeepMind's code   "
              f"{r['deepmind_code']:.12f}\n   exact rational    {ex}  ({r['exact_how']}; digits truncated, not rounded)"
              f"\n   all agree: {r['agree']}")


if __name__ == "__main__":
    main()
