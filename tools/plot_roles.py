"""Every program of one or more runs, by the role that wrote it, with the record line and Code Zero.

    python tools/plot_roles.py OUT.png RUN_DIR [RUN_DIR ...] [--ylim LO HI] [--ylabel TEXT]

Reads programs.jsonl or programs/part-*.jsonl.gz (v10.2's layout). Used for docs/analysis/WIDE_LOOP.md.
"""
import argparse
import gzip
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLOURS = {"deep": "#0969da", "planned": "#0969da", "wide": "#bf3989", "mutation": "#bf3989", "alt": "#9a6700"}
NAMES = {"deep": "deep (planned)", "planned": "planned", "wide": "wide (mutation)", "mutation": "mutation",
         "alt": "alternative result"}


def load(d):
    d = Path(d)
    if (d / "programs.jsonl").exists():
        return [json.loads(l) for l in open(d / "programs.jsonl") if l.strip()]
    return [json.loads(l) for f in sorted((d / "programs").glob("part-*.jsonl.gz")) for l in gzip.open(f, "rt")
            if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--ylim", nargs=2, type=float)
    ap.add_argument("--ylabel", default="score")
    a = ap.parse_args()
    fig, axs = plt.subplots(1, len(a.runs), figsize=(5.5 * len(a.runs), 4.2), sharey=True, squeeze=False)
    for ax, d in zip(axs[0], a.runs):
        progs = load(d)
        ok = [(i, p) for i, p in enumerate(progs) if p.get("valid") and p.get("score") is not None]
        best, line = progs[0]["score"], []
        for i, p in ok:
            best = max(best, p["score"])
            line.append((i, best))
        for role in [r for r in ("deep", "planned", "wide", "mutation", "alt") if any(p["role"] == r for _, p in ok)]:
            pts = [(i, p["score"]) for i, p in ok if p["role"] == role]
            ax.scatter(*zip(*pts), s=8, alpha=.45, lw=0, color=COLOURS[role], label=NAMES[role])
        ax.plot(*zip(*line), color="#24292f", lw=1.4, label="record")
        ax.axhline(progs[0]["score"], color="#6e7781", lw=.8, ls="--")
        ax.annotate("Code Zero", (0.01, progs[0]["score"]), xycoords=("axes fraction", "data"), xytext=(0, 3),
                    textcoords="offset points", fontsize=8, color="#57606a")
        ax.set_title(Path(d).name, loc="left")
        ax.set_xlabel("program")
        if a.ylim:
            ax.set_ylim(*a.ylim)
        ax.grid(color="#d0d7de", lw=.5)
        ax.spines[["top", "right"]].set_visible(False)
    axs[0][0].set_ylabel(a.ylabel)
    axs[0][0].legend(frameon=False, fontsize=8, loc="lower right", markerscale=2, bbox_to_anchor=(1, 0.08))
    fig.tight_layout()
    fig.savefig(a.out, dpi=150)


if __name__ == "__main__":
    main()
