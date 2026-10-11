"""Publish a run into results/<run>/, a folder that's committed to the repo, so reviewers can see the trace.

  python -m helix.publish helix/runs/<run>            copy the trace (real runs do this every generation)
  python -m helix.publish helix/runs/<run> --report   also run the held-out check: report.md, heldout.json, charts
  python -m helix.publish helix/runs/<run> --push     then git add, commit and push results/<run>

results/<run>/ holds:
  summary.json         headline numbers: Code Zero, best score, gain, held-out score, generations, LLM calls
  config.json, generations.jsonl, hypotheses.jsonl, programs.jsonl     the full trace of the search
  llm_calls.jsonl.gz   every prompt, reply and model reasoning, compressed
  best_program.py, snapshot.txt, progress.png
  report.md, heldout.json, compare.png                                 after --report (or at the end of a run)
results/README.md lists every published run.
"""
import argparse
import gzip
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from .peek import load_state, read_json, snapshot
from .sandbox import REPO_ROOT

RESULTS_DIR = REPO_ROOT / "results"
TRACE_FILES = ["config.json", "status.json", "generations.jsonl", "hypotheses.jsonl", "programs.jsonl",
               "best_program.py", "report.md", "heldout.json", "progress.png", "compare.png"]


def export(run_dir, report=False):
    """Copy a run's trace into results/<run>/. Returns the destination folder."""
    run_dir = Path(run_dir)
    if report:
        from .report import Run, write_report
        write_report([Run(run_dir)])
    dest = RESULTS_DIR / run_dir.name
    dest.mkdir(parents=True, exist_ok=True)

    for name in TRACE_FILES:
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, dest / name)
    calls = run_dir / "llm_calls.jsonl"
    if calls.exists():
        with calls.open("rb") as f_in, gzip.open(dest / "llm_calls.jsonl.gz", "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    (dest / "snapshot.txt").write_text(snapshot(run_dir))
    if not (run_dir / "report.md").exists():
        _quick_chart(run_dir, dest / "progress.png")

    summary = _summary(run_dir)
    (dest / "summary.json").write_text(json.dumps(summary, indent=2))
    _write_index()
    return dest


def push(dest):
    """git add + commit + pull --rebase + push for one results folder. Returns (ok, output)."""
    rel = Path(dest).resolve().relative_to(REPO_ROOT)
    summary = read_json(Path(dest) / "summary.json", {}) or {}
    msg = f"Publish run {rel.name}"
    if summary.get("best_score") is not None and summary.get("code_zero") is not None:
        msg += f": best {summary['best_score']:.3f} from Code Zero {summary['code_zero']:.3f}"
    steps = [["git", "add", str(rel), "results/README.md"],
             ["git", "commit", "-m", msg],
             ["git", "pull", "--rebase"],
             ["git", "push"]]
    log = []
    for cmd in steps:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        out = (proc.stdout + proc.stderr).strip()
        log.append(f"$ {' '.join(cmd)}\n{out}" if out else f"$ {' '.join(cmd)}")
        if proc.returncode != 0 and not (cmd[1] == "commit" and "nothing to commit" in out):
            return False, "\n".join(log)
    return True, "\n".join(log)


# ---------------------------------------------------------------- helpers
def _summary(run_dir):
    s = load_state(run_dir)
    cfg, st = s["config"], s["status"]
    best = s["best"]
    heldout = read_json(Path(run_dir) / "heldout.json", None)
    best_test = code_zero_test = None
    if heldout:
        best_test = next((r["test_score"] for r in heldout if r["label"].startswith("Evolved best")), None)
        code_zero_test = next((r["test_score"] for r in heldout if r["label"] == "Code Zero"), None)
    llm = st.get("llm") or {}
    return {
        "run": s["name"],
        "published": time.strftime("%Y-%m-%d %H:%M:%S"),
        "state": st.get("state"),
        "mode": cfg.get("mode"),
        "schedule": cfg.get("schedule"),
        "provider": cfg.get("provider"),
        "model": cfg.get("flash_model"),
        "pro_model": cfg.get("pro_model") or None,
        "generations_completed": max((g["generation"] for g in s["generations"]), default=None),
        "code_zero": s["seed_score"],
        "best_score": best["score"] if best else None,
        "best_id": best["id"] if best else None,
        "best_branch": best["branch"] if best else None,
        "gain": round(best["score"] - s["seed_score"], 4) if best and s["seed_score"] is not None else None,
        "best_test_score": best_test,
        "code_zero_test_score": code_zero_test,
        "programs": s["counts"]["programs"],
        "hypotheses": dict(Counter(h["verdict"] for h in s["hypotheses"])),
        "llm_calls": llm.get("calls"),
        "tokens_in": llm.get("tokens_in"),
        "tokens_out": llm.get("tokens_out"),
    }


def _quick_chart(run_dir, path):
    try:
        from .report import Run, progress_chart
        progress_chart(Run(run_dir), [], path)
    except Exception:
        pass   # charts are a nice-to-have; never let them stop a publish


def _write_index():
    rows = []
    for f in sorted(RESULTS_DIR.glob("*/summary.json")):
        s = read_json(f, None)
        if s:
            rows.append(s)
    fmt = lambda x: "—" if x is None else f"{x:.3f}"
    lines = ["# Results", "",
             "Each folder is one run of the two-loop search, published from `helix/runs/` by `python -m helix.publish`.",
             "Scores are −(mean excess % over the lower bound): higher is better, 0 would be perfect. "
             "The held-out score uses the evaluator's `test` split, which the search never sees.", "",
             "| Run | Mode | Model | Generations | Code Zero | Best (train) | Gain | Best (held-out) | LLM calls | State |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for s in rows:
        gain = f"+{s['gain']:.3f}" if s.get("gain") is not None else "—"
        lines.append(f"| [{s['run']}]({s['run']}/) | {s.get('mode')} | {s.get('model')} | {s.get('generations_completed')} | "
                     f"{fmt(s.get('code_zero'))} | {fmt(s.get('best_score'))} | {gain} | {fmt(s.get('best_test_score'))} | "
                     f"{s.get('llm_calls')} | {s.get('state')} |")
    lines += ["", "In each folder: `report.md` (held-out check, where improvements came from, research log), "
              "`progress.png`, `best_program.py`, the full trace as JSONL, and every agent call in `llm_calls.jsonl.gz`."]
    (RESULTS_DIR / "README.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m helix.publish", description="Publish a run into results/.")
    ap.add_argument("run", help="a run folder, e.g. helix/runs/<run>")
    ap.add_argument("--report", action="store_true", help="run the held-out check first")
    ap.add_argument("--push", action="store_true", help="git add, commit and push the results folder")
    a = ap.parse_args()
    if not Path(a.run).is_dir():
        sys.exit(f"{a.run} isn't a run folder")
    out = export(a.run, report=a.report)
    print(f"published to {out}")
    if a.push:
        ok, log = push(out)
        print(log)
        sys.exit(0 if ok else 1)
