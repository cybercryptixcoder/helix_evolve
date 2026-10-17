"""A run's trace, digested: what the search did and how well, in a few dozen lines.

Used by the meta loop (the outer Researcher reads digests of inner runs), the dashboard and the CLI:

    python -m helix3.digest runs/binpack2d/<run>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def load(run_dir):
    run_dir = Path(run_dir)
    events = []
    p = run_dir / "trace.jsonl"
    if p.exists():
        for line in p.open():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    return events


def stats(events):
    """Numbers about how the search behaved (not just where it got)."""
    start = next((e for e in events if e["type"] == "run_start"), {})
    gens = [e for e in events if e["type"] == "gen_end"]
    feats = {}
    for e in events:
        if e["type"] == "feature_done":
            f = e["feature"]
            feats[f["id"]] = f
    curve = [g.get("progress") or 0.0 for g in gens]
    final = curve[-1] if curve else 0.0
    plateau = next((i for i, v in enumerate(curve) if final > 0 and v >= 0.9 * final), len(curve) - 1) if curve else 0
    flat_tail = 0
    for a, b in zip(curve[::-1][1:], curve[::-1]):
        if b - a > 0.05:
            break
        flat_tail += 1
    by = Counter()
    for f in feats.values():
        by[(f["origin"], f["status"])] += 1
    deep = [f for f in feats.values() if f["origin"] == "deep"]
    wide = [f for f in feats.values() if f["origin"] == "wide"]
    preds = [f["prediction"] for f in deep if (f.get("prediction") or {}).get("checked")]
    kinds = Counter(f.get("kind") for f in deep)
    plans = Counter(e["plan"].get("source") for e in events if e["type"] == "plan")
    calls = [e for e in events if e["type"] == "call"]
    end = next((e for e in events if e["type"] == "run_end"), {})
    return {
        "problem": start.get("problem"), "label": start.get("label"),
        "generations": max(0, len(gens) - 1),
        "progress_curve": curve, "valid_curve": [g.get("valid_progress") for g in gens],
        "final_progress": final, "final_valid_progress": gens[-1].get("valid_progress") if gens else None,
        "test_progress": (end.get("test") or {}).get("progress"),
        "auc": round(sum(curve[1:]) / max(1, len(curve) - 1), 2) if len(curve) > 1 else 0.0,
        "gens_to_90pct": plateau, "flat_tail": flat_tail,
        "features": len(feats), "deep": len(deep), "wide": len(wide),
        "kept_deep": sum(f["status"] in ("kept", "retired") for f in deep),
        "kept_wide": sum(f["status"] in ("kept", "retired") for f in wide),
        "duplicates": sum(f["status"] == "duplicate" for f in feats.values()),
        "certified": sum(f["status"] in ("inert", "span") for f in feats.values()),
        "invalid": sum(f["status"] == "invalid" for f in feats.values()),
        "probe_rejected": sum(f["status"] == "rejected" for f in feats.values()),
        "tried": sum(f.get("d_valid") is not None for f in feats.values()),
        "predictions_checked": len(preds), "predictions_held": sum(bool(p.get("held")) for p in preds),
        "probe_experiments": kinds.get("probe", 0), "improve_experiments": kinds.get("improve", 0),
        "plans": dict(plans), "calls": len(calls),
        "tokens_in": sum(c.get("tokens_in") or 0 for c in calls), "tokens_out": sum(c.get("tokens_out") or 0 for c in calls),
        "reasoning_tokens": sum(c.get("reasoning_tokens") or 0 for c in calls),
        "seconds": round(sum(g.get("seconds") or 0 for g in gens), 1),
        "nodes": (gens[-1].get("nodes") if gens else {}) or {},
    }


def text(events, max_lines=60):
    """A readable digest: one block per generation."""
    s = stats(events)
    feats = {}
    for e in events:
        if e["type"] == "feature_done":
            feats[e["feature"]["id"]] = e["feature"]
    out = [f"Run on {s['problem']}: {s['generations']} generations, progress {s['final_progress']:.1f}% train "
           f"(valid {s['final_valid_progress'] or 0:.1f}%, test {s['test_progress'] if s['test_progress'] is not None else '?'}%), "
           f"AUC {s['auc']:.1f}, 90% of the final gain by gen {s['gens_to_90pct']}, flat for the last {s['flat_tail']} gens.",
           f"Features: {s['features']} ({s['deep']} deep, {s['wide']} wide); kept {s['kept_deep']} deep + {s['kept_wide']} wide; "
           f"{s['duplicates']} duplicates, {s['certified']} certified inert/span, {s['invalid']} invalid, "
           f"{s['probe_rejected']} rejected by the probe, {s['tried']} reached a trial. Predictions held "
           f"{s['predictions_held']}/{s['predictions_checked']}. Experiments: {s['probe_experiments']} probe, "
           f"{s['improve_experiments']} improve. Plans: {s['plans']}. Calls {s['calls']}, {s['seconds']:.0f}s."]
    for e in events:
        if e["type"] == "plan":
            p = e["plan"]
            out.append(f"G{e['gen']} plan ({p.get('source')}): research " +
                       ", ".join(f"{r['approach']}/{r['mode']}" for r in p.get("research", [])) +
                       f"; vary {p.get('mutate', {}).get('vary')}; fresh {p.get('mutate', {}).get('fresh')}; "
                       f"combine {p.get('combine')}; prune {p.get('prune')}")
        elif e["type"] == "gen_end" and e["gen"] > 0:
            fl = [feats[i] for i in e.get("features", []) if i in feats]
            items = []
            for f in fl:
                tag = f["status"]
                if f.get("d_valid") is not None:
                    tag += f" v{f['d_valid']:+.3f}"
                elif f.get("best_probe") is not None:
                    tag += f" p{f['best_probe']:+.2f}"
                pr = f.get("prediction") or {}
                if pr.get("checked"):
                    tag += " pred✓" if pr.get("held") else " pred✗"
                items.append(f"{f['origin'][0]}:{f['name'][:28]}={tag}")
            out.append(f"G{e['gen']} → progress {e.get('progress') or 0:.1f}%, kept {e.get('accepted')}: " + "; ".join(items))
    return "\n".join(out[:max_lines])


def main():
    ev = load(sys.argv[1])
    print(text(ev, 200))
    print(json.dumps({k: v for k, v in stats(ev).items() if k not in ("progress_curve", "valid_curve")}, indent=1))


if __name__ == "__main__":
    main()
