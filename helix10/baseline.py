"""v10.1's bar: the world's best program under our constraint (docs/V10_JOB.md, v10.1).

The question v10.1 asks: given the same constraint (n <= 100,000 steps, the same CPU seconds per program and in
total, the same start), does Helix searching the field's ideas as axes beat the field's own best program? This job
runs that program: ClaudeExplorer's method (helix10/programs/: iterated Dinkelbach, alternating with the velocity
cycles behind the July 2026 record), chained (each round starts from the best so far), in streams:

- **axes**: from the axes run's record at its start (the same start as v101-axes);
- **warm**: from the warm run's record at its start (the field's best in the class, polished once: as v101-warm);
- **scratch**: from nothing (the program's own default start): what the world's best program finds by itself.

Each stream is matched in CPU seconds to its run (axes and scratch to v101-axes, warm to v101-warm): it runs a round
only while its own CPU total is below the run's (every program of the run since its start, failures included). A
stream that has gone `patience` rounds without any gain has converged and stops (more compute had stopped helping:
reported as such). Everything is written as it happens (field.jsonl, streams/<name>.json and .npy), so a restart
resumes; a stop signal finishes the round in progress.

    python -m helix10.baseline --out runs/v101/field --axes runs/v101/v101-axes --warm runs/v101/v101-warm
    python -m helix10.baseline --report runs/v101 --out results/v101/COMPARISON.md
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

import numpy as np

from helix10 import sota

PROGRAMS = ("dinkelbach_polish", "velocity_cycles")
STOP = {"asked": False}


def jl(path):
    from helix9.pack import jl as _jl
    return _jl(path)


def arm_state(arm):
    """(warm generation, best program dict at the start, CPU seconds spent since) for a v10.1 run folder."""
    arm = Path(arm)
    st = json.loads((arm / "state.json").read_text()) if (arm / "state.json").exists() else None
    if st is None:
        return None, None, 0.0
    w = st.get("warm_gen") if st.get("warm_gen") is not None else st["gen_done"]
    cap = (st.get("config") or {}).get("max_n")
    ext = json.loads((arm / "extents.json").read_text()) if (arm / "extents.json").exists() else {}
    progs = jl(arm / "programs.jsonl")
    inside = [p for p in progs if p.get("valid") and p.get("score") is not None and p["gen"] <= w
              and (not cap or (p.get("n") or 0) <= cap or (ext.get(p["id"]) or 10 ** 12) <= cap)]
    best = max(inside, key=lambda p: p["score"]) if inside else None
    cpu = sum(float(p.get("cpu") or 0.0) for p in progs if p["gen"] > w and p.get("role") != "import")
    return w, best, cpu


def arm_start(arm, pid, cap):
    from helix10.run import trim
    c = Path(arm) / "constructions" / f"{pid}.npy"
    ref = Path(arm) / "constructions" / f"{pid}.ref"
    if not c.exists() and ref.exists():
        c = Path(arm) / "constructions" / f"{ref.read_text().strip()}.npy"
    if not c.exists():
        return None
    a = np.load(c)
    return trim(a) if cap and len(a) > cap else a


class Stream:
    def __init__(self, out, name, arm, cap):
        self.out, self.name, self.arm, self.cap = Path(out), name, arm, cap
        self.sf = self.out / "streams" / f"{name}.json"
        self.cf = self.out / "streams" / f"{name}.npy"
        self.s = json.loads(self.sf.read_text()) if self.sf.exists() else None

    def start(self, log):
        if self.s is not None:
            return True
        w, best, _ = arm_state(self.arm)
        if self.name == "scratch":
            start, s0, src = None, None, "nothing (the program's own default start)"
        else:
            if best is None:
                return False
            start = arm_start(self.arm, best["id"], self.cap)
            if start is None:
                return False
            s0, src = best["score"], f"{Path(self.arm).name}'s record at its start, {best['id']} ({best['score']:.12f})"
        (self.out / "streams").mkdir(parents=True, exist_ok=True)
        if start is not None:
            np.save(self.cf, start)
        self.s = {"name": self.name, "arm": str(self.arm), "start": src, "start_score": s0, "best": s0,
                  "cpu": 0.0, "rounds": 0, "since_gain": 0, "finished": None}
        self.save()
        log(f"field: stream {self.name} starts from {src}")
        return True

    def save(self):
        tmp = self.sf.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.s, indent=1))
        os.replace(tmp, self.sf)

    def round(self, problem, budget, mem_mb, log):
        from helix47.evaluate import evaluate
        from helix10.programs import load
        name = PROGRAMS[self.s["rounds"] % len(PROGRAMS)]
        start = np.load(self.cf) if self.cf.exists() else None
        res = evaluate(problem, load(name, cap=self.cap), start, budget, mem_mb)
        cpu = float(res.get("cpu") or budget)
        gain = res["valid"] and res["score"] is not None and (self.s["best"] is None or res["score"] > self.s["best"])
        row = {"t": time.time(), "stream": self.name, "round": self.s["rounds"] + 1, "program": name,
               "valid": res["valid"], "score": res["score"], "start_score": res["start_score"], "cpu": cpu,
               "best_before": self.s["best"], "gain": bool(gain), "error": (res.get("error") or "")[:300]}
        if gain:
            tmp = self.cf.with_name(f".{self.name}.tmp.npy")
            np.save(tmp, np.asarray(res["construction"], dtype=float))
            os.replace(tmp, self.cf)
            self.s["best"], self.s["since_gain"] = res["score"], 0
        else:
            self.s["since_gain"] += 1
        self.s["rounds"] += 1
        self.s["cpu"] += cpu
        row["best"], row["cpu_total"] = self.s["best"], self.s["cpu"]
        with (self.out / "field.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")
        self.save()
        log(f"field: {self.name} round {self.s['rounds']} ({name}): "
            + (f"{res['score']:.12f}" if res["valid"] else f"failed ({row['error'][:80]})")
            + f"; best {self.s['best'] if self.s['best'] is not None else float('nan'):.12f}; "
              f"{self.s['cpu']:.0f} s CPU")


def run(out, arms, budget=300.0, cap=sota.CLASS_N, mem_mb=1500, patience=10, poll=60, hours=72.0, log=print):
    from helix4.problems import ac2
    from helix47.run import ProblemView
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    problem = ProblemView(ac2, cap)
    streams = [Stream(out, name, arm, cap) for name, arm in arms]
    deadline = time.time() + hours * 3600
    said = set()
    while not STOP["asked"] and time.time() < deadline:
        moved = False
        for st in streams:
            if STOP["asked"]:
                break
            if st.s is None and not st.start(log):
                if st.name not in said:
                    log(f"field: stream {st.name} waits for its run ({st.arm}) to start")
                    said.add(st.name)
                continue
            if st.s.get("finished"):
                continue
            _, _, arm_cpu = arm_state(st.arm)
            if st.s["cpu"] >= arm_cpu:                            # it runs only while its total is below the run's
                continue
            st.round(problem, budget, mem_mb, log)
            moved = True
            if st.s["since_gain"] >= patience:
                st.s["finished"] = (f"converged: no gain in {patience} rounds ({st.s['cpu']:.0f} s CPU; more "
                                    f"compute had stopped helping)")
                st.save()
                log(f"field: stream {st.name} {st.s['finished']}")
        if all(st.s is not None and st.s.get("finished") for st in streams):
            log("field: every stream has converged")
            return 0
        if not moved:
            for _ in range(poll):
                if STOP["asked"]:
                    break
                time.sleep(1)
    return 75 if STOP["asked"] else 0


def report(root, out=None):
    """COMPARISON.md: each run against the world's best program at the same constraint and the same CPU."""
    root = Path(root)
    lines = ["# v10.1: Helix against the world's best program, at the same constraint", "",
             f"Size class n <= {sota.CLASS_N:,} steps, the same CPU seconds per program and in total, the same start. "
             f"Bars: the best known construction in the class, {sota.CLASS_BEST['score']:.12f} "
             f"({sota.CLASS_BEST['who']}'s public seed), and the arena's best entry in the class, "
             f"{sota.CLASS_ARENA_BEST:.12f}.", "",
             "| Run | Start | Best | Gain | CPU (s) | The field's program, same start and CPU | Its CPU (s) | Helix ahead by |",
             "|---|---|---|---|---|---|---|---|"]
    fst = {}
    for f in sorted((root / "field" / "streams").glob("*.json")) if (root / "field" / "streams").exists() else []:
        s = json.loads(f.read_text())
        fst[s["name"]] = s
    for mode in ("axes", "warm"):
        arm = root / f"v101-{mode}"
        w, best0, cpu = arm_state(arm)
        if best0 is None:
            continue
        st = json.loads((arm / "state.json").read_text())
        cap = st["config"].get("max_n")
        ext = json.loads((arm / "extents.json").read_text()) if (arm / "extents.json").exists() else {}
        progs = [p for p in jl(arm / "programs.jsonl") if p.get("valid") and p.get("score") is not None
                 and ((p.get("n") or 0) <= cap or (ext.get(p["id"]) or 10 ** 12) <= cap)]
        b = max(progs, key=lambda p: p["score"])
        s = fst.get(mode) or {}
        fb = s.get("best")
        lines.append(f"| v101-{mode} | {best0['score']:.12f} | {b['score']:.12f} ({b['id']}) | "
                     f"{b['score'] - best0['score']:+.3e} | {cpu:.0f} | "
                     + (f"{fb:.12f} ({s.get('rounds')} rounds{'; ' + s['finished'] if s.get('finished') else ''})"
                        if fb is not None else "-")
                     + f" | {s.get('cpu', 0):.0f} | " + (f"{b['score'] - fb:+.3e}" if fb is not None else "-") + " |")
    if "scratch" in fst:
        s = fst["scratch"]
        lines += ["", f"The world's best program from nothing, at the same constraint: "
                      f"{s['best'] if s['best'] is not None else float('nan'):.12f} after {s['rounds']} rounds, "
                      f"{s['cpu']:.0f} s CPU" + (f" ({s['finished']})" if s.get("finished") else "") + "."]
    text = "\n".join(lines) + "\n"
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the field job's folder (or, with --report, the markdown file)")
    ap.add_argument("--axes", default=None, help="the axes run's folder")
    ap.add_argument("--warm", default=None, help="the warm run's folder")
    ap.add_argument("--budget", type=float, default=300.0)
    ap.add_argument("--cap", type=int, default=sota.CLASS_N)
    ap.add_argument("--patience", type=int, default=10)
    ap.add_argument("--hours", type=float, default=72.0)
    ap.add_argument("--report", default=None, help="write the comparison for this root folder (runs/v101)")
    a = ap.parse_args(argv)
    if a.report:
        print(report(a.report, a.out))
        return 0
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)   # noqa: E731

    def stop(signum, frame):
        if STOP["asked"]:
            os._exit(75)
        STOP["asked"] = True
        log("field: stop requested: finishing the round in progress, then stopping")
    for sg in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sg, stop)
    arms = [(n, d) for n, d in (("axes", a.axes), ("warm", a.warm), ("scratch", a.axes)) if d]
    return run(a.out, arms, a.budget, a.cap, patience=a.patience, hours=a.hours, log=log)


if __name__ == "__main__":
    sys.exit(main())
