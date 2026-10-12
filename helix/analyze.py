"""Diagnose a run: where the time went, whether each loop is doing its job, and where it gets stuck.

  python -m helix.analyze                  the newest run
  python -m helix.analyze helix/runs/<run> a given run (a finished or a running one)

Plain text, meant to be read or pasted into a chat. Each section answers one question:
  calls       Are the agents answering, or burning time on replies that get cut off?
  champions   Which branch found each new best, building on whose program?
  wide        Does the Mutator make variants of its parent, or rewrite it from scratch, and does it pay?
  deep        Do the Researcher's tests move the score, and do the verdicts mean anything?
  tune        How much do the tuned numbers add?
  pool        Does the pool remember good programs, or only the latest batch?
  features    (feature engine) What did each branch's features add, and does validation agree with train?
  headroom    How far is the best program from an offline packer that sees every job in advance?
"""
import difflib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .peek import latest_run, read_json, read_jsonl
from .bounds import family_floor
from .metrics import units
from .reference import gap_closed, offline_reference

CUT_OFF_SHARE = 0.98      # a reply this close to its token limit counts as cut off (older logs have no finish reason)


def analyze(run_dir):
    d = Path(run_dir)
    cfg = read_json(d / "config.json", {}) or {}
    status = read_json(d / "status.json", {}) or {}
    calls = read_jsonl(d / "llm_calls.jsonl")
    progs = {p["id"]: p for p in read_jsonl(d / "programs.jsonl")}
    hyps = read_jsonl(d / "hypotheses.jsonl")
    gens = read_jsonl(d / "generations.jsonl")
    out = [f"HELIX ANALYSIS  {d.name}"]

    # ------------------------------------------------------------ overview
    seed = next((p for p in progs.values() if p["branch"] == "seed"), None)
    leaders = [p for p in progs.values() if p.get("valid") and not p.get("probe") and not p.get("trial")]
    best = max(leaders, key=lambda p: p["score"], default=None)
    secs = [g["seconds"] for g in gens if g.get("seconds")]
    minutes = ((status.get("finished") or status.get("updated") or 0) - status.get("started", 0)) / 60 if status.get("started") else None
    out.append(f"{len(gens) - 1 if gens else 0} generations, {len(progs)} programs, {len(calls)} LLM calls"
               + (f", {minutes:.0f} min" if minutes else "")
               + (f", median generation {statistics.median(secs):.0f}s" if secs else ""))
    if best and seed:
        try:
            ref = offline_reference("train")["score"]
        except Exception:
            ref = None
        closed = gap_closed(best["score"], seed["score"], ref)
        out.append(f"Best {best['score']:.3f} ({best['id']}, {best['branch']}) from Code Zero {seed['score']:.3f}: "
                   f"{100 * (best['score'] - seed['score']) / -seed['score']:.1f}% less waste"
                   + (f"; {closed:.0f}% of the gap to the offline packer ({ref:.3f}) closed" if closed is not None else ""))

    # ------------------------------------------------------------ calls
    out.append("\n== Calls: are the agents answering?")
    w = max([18] + [len(c.get("role") or "?") for c in calls])
    out.append(f"{'role':{w}s} {'calls':>5s} {'errors':>6s} {'median s':>8s} {'cut off':>7s} {'thinking':>8s}")
    default_limit = (cfg.get("max_tokens") or 8000)
    by_role = defaultdict(list)
    for c in calls:
        by_role[c.get("role", "?")].append(c)
    wasted_tokens = wasted_secs = 0
    total_tokens = sum(c.get("tokens_out") or 0 for c in calls)
    total_secs = sum(c.get("seconds") or 0 for c in calls)
    for role, cs in sorted(by_role.items()):
        cut = [c for c in cs if _cut_off(c, default_limit)]
        wasted_tokens += sum(c.get("tokens_out") or 0 for c in cut)
        wasted_secs += sum(c.get("seconds") or 0 for c in cut)
        out.append(f"{role:{w}s} {len(cs):5d} {sum(bool(c.get('error')) for c in cs):6d} "
                   f"{statistics.median(c.get('seconds') or 0 for c in cs):8.1f} {len(cut):7d} "
                   f"{sum(bool(c.get('reasoning')) for c in cs):8d}")
    if total_tokens:
        out.append(f"Cut-off replies used {100 * wasted_tokens / total_tokens:.0f}% of output tokens and "
                   f"{100 * wasted_secs / max(total_secs, 1):.0f}% of LLM time. 'thinking' = the model returned hidden "
                   "reasoning (it slipped into thinking mode).")

    # ------------------------------------------------------------ champions
    out.append("\n== Champions: who found each new best, building on whom?")
    running = float("-inf")
    for p in sorted(progs.values(), key=lambda p: int(p["id"][1:])):
        if p.get("valid") and not p.get("probe") and not p.get("trial") and p["score"] is not None and p["score"] > running:
            parent = progs.get(p.get("parent_id") or "")
            gain = f"+{p['score'] - running:.3f}" if running > float("-inf") else "start"
            out.append(f"gen {p['generation']:>3}  {p['id']}  {p['branch']:5s} {p['score']:.3f} ({gain})"
                       + (f"  from {parent['id']} ({parent['branch']})" if parent else ""))
            running = p["score"]
    streak, longest, last_best = 0, 0, float("-inf")
    for g in gens:
        if g.get("best_score") is not None and g["best_score"] > last_best + 1e-9:
            last_best, streak = g["best_score"], 0
        else:
            streak += 1
            longest = max(longest, streak)
    out.append(f"Longest run of generations without a new best: {longest}")

    if cfg.get("engine") == "features" and cfg.get("mode") != "zero-shot":
        out.append(features_section(d, gens, hyps))
        _headroom(out, best, seed)
        return "\n".join(out)

    # ------------------------------------------------------------ wide
    wide = [p for p in progs.values() if p["branch"] == "wide" and p.get("valid") and p["generation"] > 0]
    if wide:
        out.append("\n== Wide: variants or rewrites, and do they pay?")
        rows = []
        for p in wide:
            parent = progs.get(p.get("parent_id") or "")
            if parent and parent.get("valid"):
                rows.append((shared_lines(parent["code"], p["code"]), p["score"] - parent["score"]))
        out.append(f"a child keeps a median {100 * statistics.median(s for s, _ in rows):.0f}% of its parent's lines")
        for lo, hi, name in ((0, .25, "rewrite (<25% kept)"), (.25, .75, "big change"), (.75, 1.01, "variant (>75% kept)")):
            sel = [dlt for sim, dlt in rows if lo <= sim < hi]
            if sel:
                out.append(f"{name:24s} n {len(sel):3d}  median vs parent {statistics.median(sel):+.3f}  "
                           f"better than parent {sum(x > 0 for x in sel)}")
        fresh = [p for p in wide if not p.get("parent_id")]
        if fresh:
            out.append(f"fresh ideas (no parent)  n {len(fresh):3d}  best {max(p['score'] for p in fresh):.3f}")
        out.append(f"repaired: {sum(bool(p.get('repaired')) for p in wide)} of {len(wide)} valid wide programs")

    # ------------------------------------------------------------ deep
    if hyps:
        out.append("\n== Deep: do the tests move the score, and do the verdicts mean anything?")
        out.append("verdicts: " + ", ".join(f"{k} {v} {n}" for (k, v), n in Counter((h.get("kind", "improve"), h["verdict"])
                                                                                      for h in hyps).most_common()))
        imp = [h for h in hyps if h.get("kind", "improve") == "improve" and h.get("delta") is not None]
        if imp:
            ds = [h["delta"] for h in imp]
            out.append(f"improve tests: {len(ds)}, better than base {sum(x > 0 for x in ds)}, worse {sum(x < 0 for x in ds)}, "
                       f"median {statistics.median(ds):+.3f}, best {max(ds):+.3f} (epsilon {cfg.get('epsilon')})")
            tuned = [h for h in imp if h.get("raw_delta") is not None]
            if tuned:
                lift = [h["delta"] - h["raw_delta"] for h in tuned]
                out.append(f"tune-then-judge: {len(tuned)} tests had their new numbers tuned, median lift {statistics.median(lift):+.3f}; "
                           f"{sum(h['raw_delta'] <= 0 < h['delta'] for h in tuned)} went from worse to better")
        bases = Counter(h["base_id"] for h in hyps)
        top_base, n_top = bases.most_common(1)[0]
        out.append(f"most-tested base: {top_base} with {n_top} of {len(hyps)} tests")
        sims = []
        for h in hyps:
            p, b = progs.get(h.get("program_id") or ""), progs.get(h["base_id"])
            if p and b and p.get("code") and h.get("kind", "improve") == "improve":
                sims.append(shared_lines(b["code"], p["code"]))
        if sims:
            out.append(f"improve programs keep a median {100 * statistics.median(sims):.0f}% of their base's lines")
        skipped = [g["generation"] for g in gens if "deep" in g.get("branches", []) and not (g.get("deep") or {}).get("tested")]
        if skipped:
            out.append(f"generations where the deep branch produced nothing: {skipped}")

    # ------------------------------------------------------------ tune
    tuned_progs = [p for p in progs.values() if p["branch"] == "tune"]
    if tuned_progs or any(g.get("tune") for g in gens):
        out.append("\n== Tune")
        tries = sum((g.get("tune") or {}).get("tried", 0) for g in gens)
        gains = [p["score"] - progs[p["parent_id"]]["score"] for p in tuned_progs if p.get("parent_id") in progs]
        out.append(f"{len(tuned_progs)} tuned programs kept from {tries} evaluations"
                   + (f"; gains {', '.join(f'{x:+.3f}' for x in gains[:12])}" if gains else ""))

    # ------------------------------------------------------------ pool
    if gens:
        out.append("\n== Pool: does it remember good programs?")
        ages, latest_share, worst = [], [], []
        for g in gens[1:]:
            members = [progs[i] for i in g.get("pool", []) if i in progs]
            if members:
                ages.append(statistics.mean(g["generation"] - p["generation"] for p in members))
                latest_share.append(sum(p["generation"] == g["generation"] for p in members) / len(members))
                worst.append(min(p["score"] for p in members if p.get("score") is not None))
        if ages:
            out.append(f"mean age of pool programs {statistics.mean(ages):.1f} generations; "
                       f"{100 * statistics.mean(latest_share):.0f}% of the pool is from the latest generation; "
                       f"median worst member {statistics.median(worst):.2f}")

    _headroom(out, best, seed)
    return "\n".join(out)


def features_section(d, gens, hyps):
    """The feature engine: what each branch wrote, what was kept, and whether validation agrees with train."""
    feats = {}
    for f in read_jsonl(d / "features.jsonl"):
        feats[f["id"]] = f                      # the latest record of each feature
    made = [f for f in feats.values() if f.get("branch") != "seed"]
    out = ["\n== Features: what did each branch add?"]
    out.append(f"{'branch':6s} {'written':>7s} {'invalid':>7s} {'tried':>5s} {'kept':>4s} {'retired':>7s} "
               f"{'median valid':>12s} {'best valid':>10s}")
    for b in ("deep", "wide"):
        fs = [f for f in made if f.get("branch") == b]
        if not fs:
            continue
        tried = [f for f in fs if f.get("delta_valid") is not None]
        dv = [f["delta_valid"] for f in tried]
        out.append(f"{b:6s} {len(fs):7d} {sum(f.get('status') == 'invalid' for f in fs):7d} {len(tried):5d} "
                   f"{sum(f.get('status') in ('active', 'retired') for f in fs):4d} {sum(f.get('status') == 'retired' for f in fs):7d} "
                   + (f"{statistics.median(dv):+12.3f} {max(dv):+10.3f}" if dv else f"{'-':>12s} {'-':>10s}"))
    tried = [f for f in made if f.get("delta_valid") is not None and f.get("delta_train") is not None]
    if tried:
        over = [f for f in tried if f["delta_train"] > 0 > f["delta_valid"]]
        out.append(f"train gain but validation loss (overfitting): {len(over)} of {len(tried)} tried")
    fh = [h for h in hyps if h.get("kind") == "feature"]
    if fh:
        out.append("Researcher's ideas: " + ", ".join(f"{v} {n}" for v, n in Counter(h["verdict"] for h in fh).most_common()))
    kept = [f for f in made if f.get("status") in ("active", "retired")]
    if kept:
        out.append("kept:")
        for f in sorted(kept, key=lambda f: int(f["id"][1:])):
            imp = sum(x or 0 for x in (f.get("importance") or []))
            out.append(f"  gen {f.get('generation'):>3}  {f['id']}  {f['branch']:4s} {f.get('name', '')[:34]:34s} "
                       f"valid {f.get('delta_valid') or 0:+.3f}  importance {imp:+.3f}  {f.get('status')}")
    errors = Counter((f.get("error") or "").split("\n")[-1][:70] for f in made if f.get("status") == "invalid")
    if errors:
        out.append("most common reasons a feature was invalid: " + "; ".join(f"{e} ({n})" for e, n in errors.most_common(3)))
    ph = [g.get("phase_seconds") for g in gens if g.get("phase_seconds")]
    if ph:
        a, ft = sum(x.get("agents", 0) for x in ph), sum(x.get("fit", 0) for x in ph)
        out.append(f"time: agents {a / 60:.0f} min, fitting {ft / 60:.0f} min "
                   f"({sum((g.get('fit') or {}).get('evals', 0) for g in gens)} evaluations)")
    sizes = [(g["generation"], sum(len(r.get("columns") or []) for r in g.get("library") or [])) for g in gens if g.get("library")]
    if sizes:
        out.append("weights in the policy by generation: " + " ".join(f"{g}:{n}" for g, n in sizes))
    vs = [(g["generation"], g.get("best_score"), g.get("valid_score")) for g in gens if g.get("valid_score") is not None]
    if vs:
        out.append("champion by generation (train / validation): "
                   + "  ".join(f"{g}: {t:.3f}/{v:.3f}" for g, t, v in vs[-12:]))
    return "\n".join(out)


def _headroom(out, best, seed):
    # ------------------------------------------------------------ headroom
    if best and best.get("families"):
        try:
            ref = offline_reference("train")["families"]
            floor = family_floor("train")
            out.append("\n== Headroom by family (excess % over the simple bound, lower is better)")
            out.append(f"{'family':12s} {'best':>7s} {'optimum':>8s} {'room':>7s} {'offline':>8s}" + (f" {'Code Zero':>9s}" if seed else ""))
            for f, v in best["families"].items():
                opt = floor.get(f, {}).get("lower") if floor else None
                out.append(f"{f:12s} {v:7.2f} " + (f"{opt:8.2f} {v - opt:7.2f} " if opt is not None else f"{'?':>8s} {'?':>7s} ")
                           + f"{ref.get(f, float('nan')):8.2f}" + (f" {seed['families'].get(f, float('nan')):9.2f}" if seed else ""))
            if best.get("families") and seed and seed.get("families"):
                u = units(best["families"], seed["families"], "train")
                if u["progress"] is not None:
                    out.append(f"progress to optimal {u['progress']:.1f}% (0% = Code Zero, 100% = optimum); "
                               f"{u['waste']:.2f} extra bins per 100 the optimum needs")
        except Exception as exc:
            out.append(f"(no headroom table: {exc})")


def shared_lines(old, new):
    """How much of `old` survives in `new`, by non-blank lines (1.0 = identical)."""
    a = [x.strip() for x in old.splitlines() if x.strip()]
    b = [x.strip() for x in new.splitlines() if x.strip()]
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _cut_off(call, default_limit):
    if call.get("finish"):
        return call["finish"] in ("length", "thinking")
    limit = call.get("max_tokens") or default_limit
    return (call.get("tokens_out") or 0) >= CUT_OFF_SHARE * limit


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    if not target or not target.exists():
        sys.exit("No run found.")
    print(analyze(target))
