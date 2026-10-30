"""Figures and a short summary of the dry run: python report.py (reads results.json and results_climb.json)."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from pack import build  # noqa: E402

INK, MUTED, GRID = "#1f2328", "#6e7781", "#d0d7de"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})


def smooth_fig(r):
    g = r["smooth_grid"]
    sw = r["smooth_sweeps"]["sweeps"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9), gridspec_kw={"width_ratios": [1.2, 1, 1]})
    ax = axes[0]
    Z = np.array(g["radius"])
    im = ax.imshow(Z, origin="lower", aspect="auto", cmap="viridis",
                   extent=[g["shift"][0], g["shift"][-1], g["shake"][0], g["shake"][-1]])
    ax.set_xlabel("shift (0 = square grid, 0.5 = hexagonal)")
    ax.set_ylabel("shake size")
    ax.set_title(f"Height over two dials, n = {g['n']}", color=INK, loc="left")
    fig.colorbar(im, ax=ax, label="coin radius")
    for ax, names in ((axes[1], ("shift", "greedy", "shake")), (axes[2], ("push", "sharp"))):
        for nm, col in zip(names, ("#0969da", "#bf3989", "#1a7f37")):
            v = np.array(sw[nm]["values"], float)
            x = (v - v.min()) / max(v.max() - v.min(), 1e-12)
            ax.plot(x, sw[nm]["radius"], marker="o", ms=3.5, lw=2, color=col, label=nm)
        ax.set_xlabel("dial setting (low to high)")
        ax.set_ylabel("coin radius")
        ax.legend(frameon=False)
        ax.grid(color=GRID, lw=0.6)
    axes[1].set_title("Each dial turned alone", color=INK, loc="left")
    axes[2].set_title("The push's two dials", color=INK, loc="left")
    fig.tight_layout()
    fig.savefig("smoothness.png", dpi=150)


def climb_fig(c):
    ns = sorted(c["search"], key=int)
    fig, axes = plt.subplots(1, len(ns), figsize=(4.4 * len(ns), 3.6))
    for ax, n in zip(np.atleast_1d(axes), ns):
        s = c["search"][n]
        for cl in s["climbs"]:
            xs = [x.get("evals", 1) for x in cl["log"]]
            ax.plot(xs, [x["radius"] for x in cl["log"]], lw=1.8, marker="o", ms=2.5)
        if s.get("best_known"):
            ax.axhline(s["best_known"], color=INK, lw=1, ls="--")
            ax.text(1, s["best_known"], " best known", va="bottom", color=INK, fontsize=9)
        if s.get("random"):
            ax.axhline(s["random"]["best"], color="#cf222e", lw=1, ls=":")
            ax.text(1, s["random"]["best"], f" random sampling, {s['random']['evals']} tries", va="top",
                    color="#cf222e", fontsize=9)
        ax.set_title(f"n = {n}: five climbs from spread-out starts", color=INK, loc="left")
        ax.set_xlabel("evaluations")
        ax.set_ylabel("coin radius")
        ax.grid(color=GRID, lw=0.6)
    fig.tight_layout()
    fig.savefig("climbs.png", dpi=150)
    # the best packing found for each n
    fig, axes = plt.subplots(1, len(ns), figsize=(3.6 * len(ns), 3.6))
    for ax, n in zip(np.atleast_1d(axes), ns):
        s = c["search"][n]
        best = max(s["climbs"], key=lambda x: x["radius"])
        P, r = build(int(n), best["end"], 0)
        R = r
        Q = R + P * (1 - 2 * R)
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, ec=INK))
        for x, y in Q:
            ax.add_patch(plt.Circle((x, y), R, fc="#0969da", ec="white", alpha=0.85))
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_aspect("equal")
        ax.axis("off")
        bk = s.get("best_known")
        ax.set_title(f"n = {n}: r = {r:.5f}" + (f" ({100 * r / bk:.1f}% of best known)" if bk else ""),
                     color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig("packings.png", dpi=150)


def trace(c, n):
    s = c["search"][str(n)]
    best = max(s["climbs"], key=lambda x: x["radius"])
    return [f"{x['radius']:.5f}  {x['move']}" for x in best["log"]]


if __name__ == "__main__":
    r = json.load(open("results.json"))
    c = json.load(open("results_climb.json"))
    if "smooth_sweeps" in r:
        smooth_fig(r)
    climb_fig(c)
    for n in sorted(c["search"], key=int):
        s = c["search"][n]
        print(f"n={n}: climbs end", [round(x["radius"], 5) for x in s["climbs"]], "best known", s["best_known"],
              "random", s.get("random"))
        print("\n".join("   " + t for t in trace(c, int(n))))
