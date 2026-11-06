"""Experiments: several arms (settings) x several seeds, run side by side, then compared.

    python -m lean.bench experiments/lean/e1_core.json            # runs (or resumes) every run, then reports
    python -m lean.bench experiments/lean/e1_core.json --report   # the report only

An experiment file:
    {"name": "e1_core", "problem": "circles", "params": {"n": 26}, "rounds": 40, "budget": 10, "seeds": [1, 2, 3],
     "parallel": 3, "arms": {"floor": ["--planned", "0", "--mutations", "6", "--parents", "best", ...], ...}}

Runs go to runs/lean/<name>/<arm>-s<seed>; the report (report.md, curves.csv, curves.png) to the experiment's folder.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def jl(path):
    path = Path(path)
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def run_one(spec, arm, seed, log):
    out = ROOT / "runs" / "lean" / spec["name"] / f"{arm}-s{seed}"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "lean.run", "--out", str(out), "--problem", spec["problem"],
           "--rounds", str(spec["rounds"]), "--budget", str(spec["budget"]), "--seed", str(seed)]
    cmd += [x for k, v in (spec.get("params") or {}).items() for x in ("--param", f"{k}={v}")]
    cmd += spec["arms"][arm]
    for attempt in range(3):
        with (out / "run.log").open("a") as f:
            rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        if rc == 0:
            break
        log(f"{arm}-s{seed}: exit {rc}, retry {attempt + 1}")
        time.sleep(30)
    log(f"{arm}-s{seed}: done (exit {rc})")


def rechecked(d):
    """Ids that a later, stricter check found invalid (lean/recheck.py), if any."""
    f = Path(d) / "recheck.json"
    return set(json.loads(f.read_text())["invalid"]) if f.exists() else set()


def curve(d):
    """Best score after each program, in the order programs were recorded."""
    best, out, bad = None, [], rechecked(d)
    for p in jl(Path(d) / "programs.jsonl"):
        if p["valid"] and p["id"] not in bad and (best is None or p["score"] > best):
            best = p["score"]
        out.append(best)
    return out


def attribution(d):
    """Share of total gain, and number of records, by the role of the program that set each record."""
    best, gain, recs, bad = None, {}, {}, rechecked(d)
    for p in jl(Path(d) / "programs.jsonl"):
        if not p["valid"] or p["id"] in bad:
            continue
        if best is None:
            best = p["score"]
        elif p["score"] > best:
            gain[p["role"]] = gain.get(p["role"], 0) + p["score"] - best
            recs[p["role"]] = recs.get(p["role"], 0) + 1
            best = p["score"]
    return gain, recs


def report(spec, out_dir):
    """Scores are shown as the problem's own value: for a minimisation problem ("minimize": true; score = -value)
    the sign is flipped back, and a published value is passed when the run's value goes below it."""
    sign = -1 if spec.get("minimize") else 1
    base = ROOT / "runs" / "lean" / spec["name"]
    rows, curves = [], {}
    for arm in spec["arms"]:
        for s in spec["seeds"]:
            d = base / f"{arm}-s{s}"
            c = curve(d)
            if not c:
                continue
            c = [None if v is None else sign * v for v in c]
            curves[(arm, s)] = c
            summ = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else {}
            calls = jl(d / "calls.jsonl")
            progs = jl(d / "programs.jsonl")
            g, r = attribution(d)
            rows.append({"arm": arm, "seed": s, "programs": len(c), "best": c[-1],  # in the problem's own sense
                         "tokens": sum(x.get("tokens_in", 0) + x.get("tokens_out", 0) for x in calls),
                         "failed": sum(1 for p in progs if not p["valid"]), "gain": g, "records": r,
                         "finished": bool(summ)})
    marks = [m for m in (30, 60, 90, 120, 150, 180, 240, 300, 480, 600) if any(len(c) >= m for c in curves.values())]
    lines = [f"# {spec['name']}", "", spec.get("question", ""), "",
             f"Problem `{spec['problem']}` {spec.get('params') or ''}; {spec['rounds']} rounds; {spec['budget']} s of "
             f"CPU per program; seeds {spec['seeds']}. Arms:", ""]
    for arm, args in spec["arms"].items():
        lines.append(f"- **{arm}**: `{' '.join(args)}`" + (f": {spec.get('notes', {}).get(arm)}" if
                                                             spec.get("notes", {}).get(arm) else ""))
    lines += ["", f"## Best {'value (lower is better)' if sign < 0 else 'score'} after N programs (mean over seeds; "
                  "each seed in brackets)", "",
              "| Arm | " + " | ".join(str(m) for m in marks) + " |", "|---|" + "---|" * len(marks)]
    for arm in spec["arms"]:
        cells = []
        for m in marks:
            runs = [c for (a, s), c in curves.items() if a == arm]
            vals = [c[m - 1] for c in runs if len(c) >= m and c[m - 1] is not None]
            if not vals or len(vals) < len(runs):              # a mean over fewer seeds than the arm has misleads
                cells.append("-" if not vals else f"({len(vals)} of {len(runs)} seeds so far)")
            else:
                cells.append(f"{st.mean(vals):.7f} [{', '.join(f'{v:.7f}' for v in vals)}]")
        lines.append(f"| {arm} | " + " | ".join(cells) + " |")
    lines += ["", "## Per run", "", "| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |",
              "|---|---|---|---|---|---|---|"]
    for r in rows:
        tot = sum(r["gain"].values()) or 1
        lines.append(f"| {r['arm']}-s{r['seed']}{'' if r['finished'] else ' (running)'} | {r['programs']} | "
                     f"{r['best']:.9f} | {r['failed']} | {r['tokens']:,} | "
                     + ", ".join(f"{k} {v}" for k, v in r["records"].items()) + " | "
                     + ", ".join(f"{k} {v / tot:.0%}" for k, v in r["gain"].items()) + " |")
    refs = spec.get("references") or []
    if refs:
        lines += ["", "## Programs each run needed to pass each published value (- : not passed)", "",
                  "| Arm | " + " | ".join(f"{n} ({v})" for n, v in refs) + " |", "|---|" + "---|" * len(refs)]
        for arm in spec["arms"]:
            cells = []
            for _, v in refs:
                hits = []
                for (a, s), c in sorted(curves.items()):
                    if a == arm:
                        i = next((k for k, x in enumerate(c) if x is not None and sign * x > sign * v), None)
                        hits.append("-" if i is None else str(i + 1))
                cells.append(", ".join(hits))
            lines.append(f"| {arm} | " + " | ".join(cells) + " |")
        lines += ["", "## Published values (for scale)", ""] + [f"- {n}: {v}" for n, v in refs]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    with (out_dir / "curves.csv").open("w") as f:
        f.write("arm,seed,program,best\n")
        for (a, s), c in curves.items():
            for i, v in enumerate(c, 1):
                f.write(f"{a},{s},{i},{'' if v is None else v}\n")
    plot(spec, curves, out_dir / "curves.png")
    return "\n".join(lines)


def plot(spec, curves, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    colours = ["#0969da", "#bf3989", "#1a7f37", "#9a6700", "#8250df", "#cf222e"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, arm in enumerate(spec["arms"]):
        for (a, s), c in curves.items():
            if a == arm:
                ys = [v if v is not None else float("nan") for v in c]
                ax.plot(range(1, len(ys) + 1), ys, color=colours[i % len(colours)], lw=1.6, alpha=0.8,
                        label=arm if s == spec["seeds"][0] else None)
    lo, hi = spec.get("plot_min"), spec.get("plot_max")
    if lo is not None:
        ax.set_ylim(bottom=lo)
    if hi is not None:
        ax.set_ylim(top=hi)
    for n, v in spec.get("references") or []:
        ax.axhline(v, color="#6e7781", lw=0.8, ls="--")
    ax.set_xlabel("programs evaluated")
    ax.set_ylabel("best value so far (lower is better)" if spec.get("minimize") else "best score so far")
    ax.set_title(spec["name"], loc="left")
    ax.grid(color="#d0d7de", lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    spec_path = Path(a.spec)
    spec = json.loads(spec_path.read_text())
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)  # noqa: E731
    if not a.report:
        jobs = [(arm, s) for s in spec["seeds"] for arm in spec["arms"]]
        with ThreadPoolExecutor(max_workers=spec.get("parallel", 3)) as ex:
            list(ex.map(lambda j: run_one(spec, j[0], j[1], log), jobs))
    print(report(spec, ROOT / "results" / "lean" / spec["name"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
