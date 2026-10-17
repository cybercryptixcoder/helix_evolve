"""The meta-evaluator: how good is a *strategy* (a version of how Helix searches) at improving programs?

    python -m meta.evaluate --strategy helix3/strategy --problems binpack1d,knapsack,tsp --held-out coloring \\
        --generations 5 --repeats 2 --parallel 4 --out meta_runs/eval-baseline

For each problem and repeat it runs the inner engine (`python -m helix3.run`) from Code Zero with the strategy,
in a separate process with a wall-clock limit, and reads back its summary and trace. Per run it measures:

  final     held-out test progress % at the end (0% = Code Zero, 100% = the reference)
  auc       mean validation progress over the generations (rewards getting there sooner)
  plateau   the generation by which 90% of the final gain was reached; flat_tail: generations at the end without gain
  cost      model calls, tokens, minutes; crashes

run score = 0.6 * final + 0.4 * auc. A problem's score is the mean over repeats; the strategy's **score** is the mean
over the search problems (each counts equally). Held-out problems are scored the same way but reported separately:
the outer loop never sees their traces, and promotion requires that they don't get worse.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helix3 import digest  # noqa: E402

W_FINAL, W_AUC = 0.6, 0.4


def run_one(strategy, problem, gens, seed, out, timeout, workers, fake=False):
    t = time.time()
    cmd = [sys.executable, "-m", "helix3.run", problem, "-g", str(gens), "--strategy", str(strategy),
           "--seed", str(seed), "--out", str(out), "--label", f"meta-{problem}-r{seed}"]
    if workers:
        cmd += ["--workers", str(workers)]
    if fake:
        cmd += ["--fake"]
    out.mkdir(parents=True, exist_ok=True)
    rec = {"problem": problem, "seed": seed, "dir": str(out)}
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        (out / "stdout.log").write_text(p.stdout[-20000:] + "\n--- stderr ---\n" + p.stderr[-20000:])
        if p.returncode != 0 or not (out / "summary.json").exists():
            rec["crash"] = (p.stderr or p.stdout)[-3000:]
    except subprocess.TimeoutExpired:
        rec["crash"] = f"timed out after {timeout}s"
    rec["minutes"] = round((time.time() - t) / 60, 2)
    ev = digest.load(out)
    if ev:
        st = digest.stats(ev)
        rec["stats"] = st
        vc = [v for v in st.get("valid_curve", [])[1:] if v is not None]
        final = st["test_progress"] if st.get("test_progress") is not None else (st.get("final_valid_progress") or 0.0)
        auc = sum(vc) / len(vc) if vc else 0.0
        rec.update(final=round(final, 2), auc=round(auc, 2), score=round(W_FINAL * final + W_AUC * auc, 2),
                   plateau=st["gens_to_90pct"], flat_tail=st["flat_tail"], calls=st["calls"],
                   tokens=st["tokens_in"] + st["tokens_out"])
        (out / "digest.txt").write_text(digest.text(ev, 80))
    if "crash" in rec:
        rec["score"] = 0.0
    return rec


def evaluate(strategy, problems, held_out=(), gens=5, repeats=2, parallel=4, out=None, timeout=3600, workers=None,
             seeds=None, fake=False):
    strategy = Path(strategy).resolve()
    out = Path(out or ROOT / "meta_runs" / f"eval-{time.strftime('%Y%m%d-%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)
    seeds = seeds or list(range(repeats))
    jobs = [(p, s) for p in list(problems) + list(held_out) for s in seeds]
    t = time.time()
    with ThreadPoolExecutor(parallel) as ex:
        runs = list(ex.map(lambda j: run_one(strategy, j[0], gens, j[1], out / f"{j[0]}-r{j[1]}", timeout, workers, fake), jobs))

    def block(names):
        res = {}
        for name in names:
            rs = [r for r in runs if r["problem"] == name]
            scores = [r["score"] for r in rs]
            res[name] = {"score": round(statistics.mean(scores), 2) if scores else 0.0,
                         "spread": round(statistics.pstdev(scores), 2) if len(scores) > 1 else None,
                         "final": round(statistics.mean([r.get("final", 0) for r in rs]), 2),
                         "auc": round(statistics.mean([r.get("auc", 0) for r in rs]), 2),
                         "plateau": statistics.mean([r.get("plateau", gens) for r in rs]) if rs else None,
                         "crashes": sum("crash" in r for r in rs)}
        return res

    search, held = block(problems), block(held_out)
    score = round(statistics.mean([v["score"] for v in search.values()]), 2) if search else 0.0
    spreads = [v["spread"] for v in search.values() if v["spread"] is not None]
    result = {"strategy": str(strategy), "score": score, "worst": min((v["score"] for v in search.values()), default=0.0),
              "noise": round(statistics.mean(spreads), 2) if spreads else None,
              "held_out_score": round(statistics.mean([v["score"] for v in held.values()]), 2) if held else None,
              "problems": search, "held_out": held, "runs": [{k: v for k, v in r.items() if k != "stats"} for r in runs],
              "generations": gens, "repeats": len(seeds), "minutes": round((time.time() - t) / 60, 1),
              "calls": sum(r.get("calls", 0) for r in runs), "tokens": sum(r.get("tokens", 0) for r in runs),
              "crashes": [{"problem": r["problem"], "seed": r["seed"], "error": r["crash"][-600:]} for r in runs if "crash" in r]}
    (out / "result.json").write_text(json.dumps(result, indent=1))
    (out / "report.md").write_text(report(result))
    return result


def report(r):
    lines = [f"# Meta-evaluation: score {r['score']:.1f}", "",
             f"Strategy `{r['strategy']}`; {r['generations']} generations × {r['repeats']} repeats; {r['minutes']} min, "
             f"{r['calls']} model calls.", "",
             "| Problem | Score | Final test progress | AUC (valid) | 90% by gen | Spread | Crashes |", "|---|---|---|---|---|---|---|"]
    for title, block in (("", r["problems"]), (" (held out)", r["held_out"])):
        for name, v in block.items():
            lines.append(f"| {name}{title} | {v['score']:.1f} | {v['final']:.1f}% | {v['auc']:.1f}% | "
                         f"{v['plateau'] if v['plateau'] is not None else '-'} | {v['spread'] if v['spread'] is not None else '-'} | {v['crashes']} |")
    if r["crashes"]:
        lines += ["", "## Crashes", ""] + [f"- {c['problem']} r{c['seed']}: `{c['error'][-300:]}`" for c in r["crashes"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--strategy", default=str(ROOT / "helix3" / "strategy"))
    ap.add_argument("--problems", default="binpack1d,knapsack,tsp,scheduling")
    ap.add_argument("--held-out", default="coloring")
    ap.add_argument("--generations", type=int, default=5)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--parallel", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--workers", type=int, default=None, help="fitter processes per inner run")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--out", default=None)
    ap.add_argument("--fake", action="store_true", help="inner runs without model calls (a crash test)")
    a = ap.parse_args(argv)
    r = evaluate(a.strategy, [p for p in a.problems.split(",") if p], [p for p in a.held_out.split(",") if p],
                 a.generations, a.repeats, a.parallel, a.out, a.timeout, a.workers, fake=a.fake)
    print(report(r))


if __name__ == "__main__":
    main()
