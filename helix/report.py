"""Summarise a run, check the result on held-out instances, and draw the progress chart.

  python -m helix.report helix/runs/<run>                       one run
  python -m helix.report RUN_FULL RUN_WIDE_ONLY RUN_ZERO_SHOT   compare runs (the first is the main one)

Writes report.md and progress.png (plus compare.png for several runs) into the
first run's folder. The held-out check scores the best program, Code Zero and
every program in programs/ on the evaluator's `test` split, which the search
never sees.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import metrics
from .population import Store
from .reference import gap_closed, offline_reference
from .sandbox import REPO_ROOT, evaluate_file

INK, MUTED, GRID = "#0b0b0b", "#8a8984", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]      # categorical slots 1-3, validated for colour-blind separation
BRANCH_STYLE = {"deep": (SERIES[0], "o"), "wide": (SERIES[1], "s"), "tune": (SERIES[2], "D")}


# ---------------------------------------------------------------- loading
def read_jsonl(path):
    out = []
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass   # a broken line left by a killed run
    return out


class Run:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.store, _ = Store.load(self.dir)
        self.gens = read_jsonl(self.dir / "generations.jsonl")
        cfg = self.dir / "config.json"
        self.config = json.loads(cfg.read_text()) if cfg.exists() else {}
        self.mode = self.config.get("mode", "?")
        self.calls = read_jsonl(self.dir / "llm_calls.jsonl")
        self.best = self.store.best()
        self.seed = next((p for p in self.store.programs.values() if p.branch == "seed"), None)

    def calls_by_generation(self):
        """Cumulative LLM calls at the end of each generation (counters restart on resume, so add offsets)."""
        out, offset, prev = [], 0, 0
        for g in self.gens:
            c = g.get("llm", {}).get("calls", 0)
            if c < prev:
                offset += prev
            prev = c
            out.append(offset + c)
        return out

    def best_new(self, generation, branch):
        progs = [p for p in self.store.programs.values()
                 if p.generation == generation and p.branch == branch and p.valid and p.duplicate_of is None]
        return max(progs, key=lambda p: p.score) if progs else None

    def improvements(self):
        """Each generation where the best score went up, which program did it, and by how much."""
        events, best = [], self.seed.score if self.seed else float("-inf")
        for gen in sorted({p.generation for p in self.store.programs.values()}):
            fresh = [p for p in self.store.programs.values()
                     if p.generation == gen and p.valid and p.duplicate_of is None and p.branch != "seed"]
            top = max(fresh, key=lambda p: p.score, default=None)
            if top and top.score > best:
                events.append((top, top.score - best if best > float("-inf") else None))
                best = top.score
        return events


# ---------------------------------------------------------------- held-out check
def score_both_splits(path):
    return evaluate_file(path, "train"), evaluate_file(path, "test")


def held_out_table(run):
    entries = []
    if run.best:
        entries.append((f"Evolved best ({run.best.id}, {run.best.branch})", run.store.candidate_path(run.best.id)))
    for path in sorted((REPO_ROOT / "programs").glob("*.py"), key=lambda p: (p.stem != "code_zero", p.stem)):
        label = "Code Zero" if path.stem == "code_zero" else f"Baseline: {path.stem}"
        entries.append((label, path))
    with ThreadPoolExecutor(max_workers=4) as ex:
        scores = list(ex.map(lambda e: score_both_splits(e[1]), entries))
    rows = [(label, train, test) for (label, _), (train, test) in zip(entries, scores)]
    train_fams = next((set(tr["families"]) for _, tr, _ in rows if tr["valid"]), set())
    test_fams = next((list(te["families"]) for _, _, te in rows if te["valid"]), [])
    held_out = [f for f in test_fams if f not in train_fams]
    return rows, held_out


# ---------------------------------------------------------------- charts
def _axes(plt, title, xlabel):
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.set_xlabel(xlabel, fontsize=10, color="#52514e")
    ax.set_ylabel("Score (higher is better)", fontsize=10, color="#52514e")
    return fig, ax


def progress_chart(run, baseline_train, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gens = [g["generation"] for g in run.gens]
    if not gens:
        return False
    fig, ax = _axes(plt, "Best score by generation", "Generation")
    best_so_far = [g["best_score"] for g in run.gens]
    ax.step(gens, best_so_far, where="post", color=INK, linewidth=2, label="Best so far", zorder=3)
    for branch, (color, marker) in BRANCH_STYLE.items():
        pts = [(g, p.score) for g in gens if (p := run.best_new(g, branch))]
        if pts:
            ax.scatter(*zip(*pts), color=color, marker=marker, s=40, edgecolor="#fcfcfb", linewidth=1.5,
                       label=f"Best new program, {branch} branch", zorder=4)
    refs = [("Code Zero", run.seed.score if run.seed else None)] + [(name, s) for name, s in baseline_train]
    for name, score in refs:
        if score is None:
            continue
        ax.axhline(score, color=MUTED, linestyle=(0, (4, 3)), linewidth=1, zorder=1)
        ax.annotate(name, (1.0, score), xycoords=("axes fraction", "data"), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=8, color="#52514e")
    ax.legend(loc="upper left", frameon=False, fontsize=9)   # the best-so-far line climbs to the right
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True


def compare_chart(runs, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = _axes(plt, "Best score for the same LLM budget", "LLM calls")
    for run, color in zip(runs, SERIES):
        xs, ys = run.calls_by_generation(), [g["best_score"] for g in run.gens]
        pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
        if not pts:
            continue
        xs, ys = zip(*pts)
        if len(xs) == 1:
            ax.scatter(xs, ys, color=color, s=50, label=run.mode, zorder=3)
        else:
            ax.step(xs, ys, where="post", color=color, linewidth=2, label=run.mode, zorder=3)
        ax.annotate(run.mode, (xs[-1], ys[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------- report text
REF_LABEL = "Reference: offline best-fit decreasing (sees every job in advance)"


def fmt(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def write_report(runs):
    main = runs[0]
    lines = [f"# Run report: {main.dir.name}", ""]
    cfg = main.config
    lines += [
        f"- Mode: **{main.mode}**, schedule {cfg.get('schedule', '?')}, {len(main.gens) - 1} generations after Code Zero",
        f"- Models: {cfg.get('flash_model', '?')}" + (f", pro {cfg['pro_model']} every {cfg.get('pro_every')} calls"
                                                         if cfg.get("pro_model") else ""),
        f"- LLM calls: {len(main.calls)} "
        f"({sum(c.get('tokens_in') or 0 for c in main.calls):,} tokens in, "
        f"{sum(c.get('tokens_out') or 0 for c in main.calls):,} out)",
        f"- Best train score: **{fmt(main.best.score if main.best else None)}** "
        f"(Code Zero {fmt(main.seed.score if main.seed else None)})",
        "",
    ]

    print("Scoring the best program, Code Zero and the baselines on the held-out test split...", flush=True)
    rows, held_out = held_out_table(main)
    ref = {split: offline_reference(split) for split in ("train", "test")}
    (main.dir / "heldout.json").write_text(json.dumps([
        {"label": label, "train_score": tr["score"], "test_score": te["score"], "valid": te["valid"],
         "test_families": {f: v["excess_pct"] for f, v in te["families"].items()}}
        for label, tr, te in rows] + [
        {"label": REF_LABEL, "train_score": ref["train"]["score"], "test_score": ref["test"]["score"], "valid": True,
         "test_families": ref["test"]["families"], "reference": True}], indent=2))
    lines += ["## Held-out check", "",
              "Scored on the evaluator's `test` split: new instances, plus families the search never saw "
              f"({', '.join(held_out) or 'none'}).", ""]
    header = "| Program | Train score | Test score | " + " | ".join(f"Test excess % on {f}" for f in held_out) + " |"
    lines += [header, "|" + "---|" * (3 + len(held_out))]
    for label, tr, te in rows:
        fams = [fmt(te["families"].get(f, {}).get("excess_pct"), 2) if te["valid"] else "invalid" for f in held_out]
        lines.append(f"| {label} | {fmt(tr['score'])} | {fmt(te['score'])} | " + " | ".join(fams) + " |")
    lines.append(f"| *{REF_LABEL}* | {fmt(ref['train']['score'])} | {fmt(ref['test']['score'])} | "
                 + " | ".join(fmt(ref["test"]["families"].get(f), 2) for f in held_out) + " |")
    lines.append("")
    best_row = next((r for r in rows if r[0].startswith("Evolved best")), None)
    zero_row = next((r for r in rows if r[0] == "Code Zero"), None)
    if best_row and zero_row and best_row[1]["valid"] and best_row[2]["valid"]:
        g_train = gap_closed(best_row[1]["score"], zero_row[1]["score"], ref["train"]["score"])
        g_test = gap_closed(best_row[2]["score"], zero_row[2]["score"], ref["test"]["score"])
        fam = lambda r: {f: v["excess_pct"] for f, v in r["families"].items()}
        u_train = metrics.units(fam(best_row[1]), fam(zero_row[1]), "train")
        u_test = metrics.units(fam(best_row[2]), fam(zero_row[2]), "test")
        if u_train["progress"] is not None:
            lines += [f"**Progress to optimal** (0% = Code Zero, 100% = the optimal packing, `helix/bounds.py`): "
                      f"**{u_train['progress']:.1f}%** on train"
                      + (f", **{u_test['progress']:.1f}%** on the held-out test split" if u_test["progress"] is not None else "")
                      + f". Extra bins per 100 the optimum needs: {u_train['waste']:.2f} on train"
                      + (f", {u_test['waste']:.2f} on test" if u_test["waste"] is not None else "") + ".", ""]
        lines += [f"The score counts bins above a lower bound that ignores job shapes, so 0 can't be reached. As a "
                  f"practical yardstick, an offline packer that sees every job before placing any scores "
                  f"{fmt(ref['train']['score'])} on train. The evolved program has closed **{fmt(g_train, 1)}%** of "
                  f"the gap between Code Zero and that packer on train, and **{fmt(g_test, 1)}%** on the held-out "
                  f"test split (`python -m helix.reference`).", ""]

    lines += ["## Where the improvements came from", "", "| Generation | Branch | Program | Score | Gain | What it did |",
              "|---|---|---|---|---|---|"]
    hyps = {h.id: h for h in main.store.hypotheses}
    for p, gain in main.improvements():
        what = hyps[p.hypothesis_id].claim if p.hypothesis_id in hyps else p.note
        what = " ".join(what.split()).replace("|", "/")[:160]
        lines.append(f"| {p.generation} | {p.branch} | {p.id} | {fmt(p.score)} | {'+' + fmt(gain) if gain else '—'} | {what} |")
    lines.append("")

    lines += ["## Branches", "", "| Branch | Programs | Valid | Repaired | Duplicates | New bests | Best score |",
              "|---|---|---|---|---|---|---|"]
    events = main.improvements()
    for branch in ("seed", "wide", "deep", "tune", "zeroshot"):
        progs = [p for p in main.store.programs.values() if p.branch == branch]
        if not progs:
            continue
        valid = [p for p in progs if p.valid]
        lines.append(f"| {branch} | {len(progs)} | {len(valid)} | {sum(p.repaired for p in progs)} | "
                     f"{sum(p.duplicate_of is not None for p in progs)} | {sum(p.branch == branch for p, _ in events)} | "
                     f"{fmt(max((p.score for p in valid), default=None))} |")
    lines.append("")

    if main.store.hypotheses:
        from collections import Counter
        counts = Counter(h.verdict for h in main.store.hypotheses)
        lines += ["## Research log", "",
                  "Verdicts: " + ", ".join(f"{n} {v}" for v, n in counts.most_common()), "",
                  "Supported hypotheses, largest gain first:", "",
                  "| Hypothesis | Base | Gain | Claim | Change | Families that moved most (excess %) |",
                  "|---|---|---|---|---|---|"]
        supported = sorted((h for h in main.store.hypotheses if h.verdict == "supported"), key=lambda h: -h.delta)
        for h in supported[:15]:
            moved = sorted(h.family_shift.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
            clean = lambda s: " ".join(s.split()).replace("|", "/")[:140]
            lines.append(f"| {h.id} | {h.base_id} | +{fmt(h.delta)} | {clean(h.claim)} | {clean(h.change)} | "
                         + ", ".join(f"{f} {v:+.2f}" for f, v in moved) + " |")
        lines.append("")

    if len(runs) > 1:
        print("Scoring each run's best program on the test split...", flush=True)
        with ThreadPoolExecutor(max_workers=4) as ex:
            tests = list(ex.map(lambda r: evaluate_file(r.store.candidate_path(r.best.id), "test") if r.best else None, runs))
        lines += ["## Compared runs", "", "| Run | Mode | LLM calls | Best train score | Test score |", "|---|---|---|---|---|"]
        for r, te in zip(runs, tests):
            lines.append(f"| {r.dir.name} | {r.mode} | {len(r.calls)} | {fmt(r.best.score if r.best else None)} | "
                         f"{fmt(te['score'] if te else None)} |")
        lines.append("")

    try:
        baseline_train = [(label.replace("Baseline: ", ""), tr["score"]) for label, tr, _ in rows
                          if label.startswith("Baseline") and tr["valid"]]
        best_baseline = max(baseline_train, key=lambda x: x[1], default=None)
        refs = ([best_baseline] if best_baseline else []) + [("Offline packer (sees all jobs)", ref["train"]["score"])]
        if progress_chart(main, refs, main.dir / "progress.png"):
            lines += ["![Best score by generation](progress.png)", ""]
        if len(runs) > 1:
            compare_chart(runs, main.dir / "compare.png")
            lines += ["![Best score for the same LLM budget](compare.png)", ""]
    except ImportError:
        lines += ["(Charts skipped: matplotlib isn't installed.)", ""]

    out = main.dir / "report.md"
    out.write_text("\n".join(lines))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m helix.report RUN_FOLDER [MORE_RUN_FOLDERS ...]")
    path = write_report([Run(p) for p in sys.argv[1:]])
    print(f"wrote {path}")
