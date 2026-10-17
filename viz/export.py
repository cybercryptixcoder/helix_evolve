"""Export a Helix run as one trace, and build the run viewer page from it.

    python -m viz.export helix/runs/<run>                         # -> helix/runs/<run>/viewer.html
    python -m viz.export results/<run> --out /tmp/run.html        # a published run works too
    python -m viz.export helix/runs/<run> --json trace.json       # the trace alone (drop it on viz/viewer.html)
    python -m viz.export helix/runs/<run> --notes notes.json      # add a written interpretation of the run
    python -m viz.export helix/runs/<run> --summarize             # ask the model for a short summary of each call

What goes in the trace (everything the viewer shows comes from the run folder; nothing is recomputed except
the packing-comparison text and the progress units, which use the same helpers the run used):
- every agent call: role, generation, branch, the feature it belongs to, start and end time, the exact system
  prompt (deduplicated), the exact user message, the reply, any hidden reasoning, tokens and finish reason;
- every feature: its idea (deep loop), its code, the probe and trial results, its verdict;
- every generation: the champion before and after, what was kept or retired, the library's weights and
  importance, the packing comparison the Researcher read, timings, and the run's console lines for it;
- every champion program (the composed priority() code) with its official score and progress to optimal.

Only the feature engine is supported for now (runs 4 onward). The program engine's records have a different
shape; see viz/README.md for how to extend this.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "viewer.html"
PLACEHOLDER = "/*__HELIX_TRACE__*/null"
FORMAT = "helix-trace/1"


# ---------------------------------------------------------------- reading the run folder
def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        gz = path.with_name(path.name + ".gz")
        if not gz.exists():
            return []
        text = gzip.open(gz, "rt").read()
    else:
        text = path.read_text()
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass                        # a half-written last line from a killed run
    return out


def last_by_id(records):
    """features.jsonl appends a feature each time it changes: the last record is its final state."""
    out = {}
    for r in records:
        out[r["id"]] = r
    return out


# ---------------------------------------------------------------- times
def clock_seconds(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


def place_call_times(calls, gens):
    """llm_calls.jsonl stores only the local clock time (HH:MM:SS) a call ended. Turn it into an epoch time,
    using the generations' epoch start/end times to find the run machine's UTC offset and the day."""
    windows = {g["generation"]: (g.get("started_at"), g.get("finished_at")) for g in gens}
    timed = [c for c in calls if c.get("time") and windows.get(c.get("generation"), (None, None))[0]]
    if not timed:
        return
    best = None
    for quarter in range(-14 * 4, 14 * 4 + 1):         # UTC offsets in 15-minute steps
        offset = quarter * 900
        fits = 0
        for c in timed:
            start, end = windows[c["generation"]]
            t = _epoch(clock_seconds(c["time"]), start, offset)
            if start - 5 <= t <= (end or start + 3600) + 5:
                fits += 1
        if best is None or fits > best[0]:
            best = (fits, offset)
    offset = best[1]
    for c in calls:
        start = windows.get(c.get("generation"), (None, None))[0]
        if c.get("time") and start:
            c["_end"] = _epoch(clock_seconds(c["time"]), start, offset)


def _epoch(secs_of_day, near, offset):
    """The epoch time with this local clock time (local = UTC + offset) closest to `near`."""
    local_near = near + offset
    day0 = local_near - (local_near % 86400)
    cands = [day0 + d * 86400 + secs_of_day - offset for d in (-1, 0, 1)]
    return min(cands, key=lambda t: abs(t - near))


# ---------------------------------------------------------------- console lines
_MAG = re.compile(r"\[mag\]\s+(f\d+)\s+(.*)$")
_TIM = re.compile(r"\[tim\]\s+(f\d+)\s+(.*)$")
_GEN = re.compile(r"──\s*generation\s+(\d+)")


def parse_console(text):
    """[mag] lines (probe results per weight), [tim] lines (trial timing), and the readable lines per generation."""
    probes, timing, by_gen, gen = {}, {}, {}, None
    for raw in text.splitlines():
        line = raw.rstrip()
        m = _GEN.search(line)
        if m:
            gen = int(m.group(1))
        if (m := _MAG.search(line)):
            pts = []
            for tok in m.group(2).split():
                if ":" in tok:
                    w, d = tok.split(":", 1)
                    try:
                        pts.append({"w": float(w), "delta": float(d)})
                    except ValueError:
                        pass
            probes[m.group(1)] = pts
            continue
        if (m := _TIM.search(line)):
            t = {k: float(v) for k, v in re.findall(r"(probe|free|refit|valid|total)\s+([\d.]+)s", m.group(2))}
            t["rejected"] = "rejected" in m.group(2)
            t["gated"] = "GATED" in m.group(2)
            timing[m.group(1)] = t
            continue
        if "[tim]" in line or "[mag]" in line:
            continue
        if gen is not None and line.strip():
            by_gen.setdefault(gen, []).append(line)
    return probes, timing, by_gen


# ---------------------------------------------------------------- verdicts (same rules as helix/evolve.py)
def verdict(f, kept_ids, margin):
    if f.get("status") == "invalid":
        return "invalid"
    if f["id"] in kept_ids:
        return "kept"
    if f.get("status") == "redundant":
        return "redundant"
    dv, dt = f.get("delta_valid"), f.get("delta_train")
    if dv is None and dt is not None and dt < -margin:
        return "probe-rejected"
    if dv is not None and dv < -margin:
        return "refuted"
    return "flat"


# ---------------------------------------------------------------- building the trace
def build_trace(run_dir, console_path=None, notes_path=None):
    run_dir = Path(run_dir)
    config = json.loads((run_dir / "config.json").read_text()) if (run_dir / "config.json").exists() else {}
    if config.get("engine", "programs") != "features":
        raise SystemExit(f"{run_dir} is a program-engine run; the viewer only reads feature-engine runs so far "
                         "(see viz/README.md)")
    gens = read_jsonl(run_dir / "generations.jsonl")
    calls_raw = read_jsonl(run_dir / "llm_calls.jsonl")
    features = last_by_id(read_jsonl(run_dir / "features.jsonl"))
    hyps = read_jsonl(run_dir / "hypotheses.jsonl")
    programs = read_jsonl(run_dir / "programs.jsonl")
    margin = float(config.get("accept_margin", 0.03))

    console_text = ""
    for p in [console_path, run_dir / "console.log"]:
        if p and Path(p).exists():
            console_text = Path(p).read_text(errors="replace")
            break
    probes, timing, console_by_gen = parse_console(console_text)

    # ---- calls
    place_call_times(calls_raw, gens)
    prompts, calls = {}, []
    for i, c in enumerate(calls_raw, 1):
        sys_text = c.get("system") or ""
        key = "s" + hashlib.sha1(sys_text.encode()).hexdigest()[:8]
        prompts.setdefault(key, sys_text)
        role = c.get("role", "")
        user = c.get("user") or ""
        kind = "retry" if role.endswith("-retry") else ("repair" if user.startswith("Your program failed") else "first")
        end = c.get("_end")
        secs = c.get("seconds") or 0.0
        calls.append({
            "id": f"c{i:03d}", "gen": c.get("generation"), "branch": c.get("branch"), "feature": c.get("feature"),
            "role": role.replace("-retry", "").replace("feature_", ""), "kind": kind,
            "start": round(end - secs, 2) if end else None, "end": end, "seconds": secs,
            "temperature": c.get("temperature"), "max_tokens": c.get("max_tokens"),
            "tokens_in": c.get("tokens_in"), "tokens_out": c.get("tokens_out"), "finish": c.get("finish"),
            "model": c.get("model"), "system": key, "user": user, "reply": c.get("reply"),
            "reasoning": c.get("reasoning"), "error": c.get("error"),
        })

    # ---- features
    kept_ids = {fid for g in gens for fid in g.get("accepted") or []}
    kept_at = {fid: g["generation"] for g in gens for fid in g.get("accepted") or []}
    retired_at = {fid: g["generation"] for g in gens for fid in g.get("retired") or []}
    calls_by_feature = {}
    for c in calls:
        if c["feature"]:
            calls_by_feature.setdefault(c["feature"], []).append(c["id"])
    feats = []
    for fid, f in sorted(features.items(), key=lambda kv: int(kv[0][1:])):
        if f.get("branch") == "seed":
            continue
        feats.append({
            "id": fid, "name": f.get("name"), "branch": f.get("branch"), "gen": f.get("generation"),
            "hypothesis": f.get("hypothesis_id"), "parents": f.get("parent_ids") or [],
            "description": f.get("description"), "note": f.get("note"), "code": f.get("code"),
            "status": f.get("status"), "verdict": verdict(f, kept_ids, margin),
            "kept_at": kept_at.get(fid), "retired_at": retired_at.get(fid),
            "delta_train": f.get("delta_train"), "delta_valid": f.get("delta_valid"),
            "columns": f.get("columns"), "weights": f.get("weights"), "importance": f.get("importance"),
            "error": f.get("error"), "gated": f.get("gated"),
            "probe": probes.get(fid), "timing": timing.get(fid), "calls": calls_by_feature.get(fid, []),
        })

    ideas = [{"id": h["id"], "gen": h["generation"], "feature": h.get("feature_id"), "claim": h.get("claim"),
              "measure": h.get("change"), "target": h.get("prediction"), "builds_on": h.get("builds_on"),
              "verdict": h.get("verdict"), "delta": h.get("delta"), "base": h.get("base_id")}
             for h in hyps if h.get("kind") == "feature"]

    # ---- champions and units
    seed = next((p for p in programs if p.get("branch") == "seed"), None)
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from helix import instruments, metrics
    except Exception:                       # the viewer still works without the readable units
        instruments = metrics = None

    def progress(fams):
        if not (metrics and seed and fams):
            return None
        try:
            return metrics.progress(fams, seed.get("families") or {})
        except Exception:
            return None

    champs = {}
    for p in programs:
        if p.get("trial"):
            continue
        champs[p["id"]] = {"id": p["id"], "gen": p.get("generation"), "branch": p.get("branch"),
                           "parent": p.get("parent_id"), "code": p.get("code"), "score": p.get("score"),
                           "valid_score": p.get("valid_score"), "families": p.get("families"),
                           "features": p.get("features"), "note": p.get("note"),
                           "progress": progress(p.get("families"))}

    # ---- generations
    gen_out, prev = [], None
    for g in gens:
        ch = g.get("champion") or {}
        diag = g.get("diagnostics") or {}
        text = None
        if diag and instruments:
            try:
                text = instruments.text(diag)
            except Exception:
                text = None
        gen_out.append({
            "gen": g["generation"], "started": g.get("started_at"), "finished": g.get("finished_at"),
            "seconds": g.get("seconds"), "phase_seconds": g.get("phase_seconds"),
            "before": prev, "champion": ch.get("id"), "train": ch.get("train"), "valid": ch.get("valid"),
            "official": (champs.get(ch.get("id")) or {}).get("score"),
            "accepted": g.get("accepted") or [], "retired": g.get("retired") or [],
            "champion_refit": g.get("champion_refit"), "fit": g.get("fit"), "library": g.get("library") or [],
            "weights": ch.get("x"), "packings": diag or None, "packings_text": text,
            "llm": {k: v for k, v in (g.get("llm") or {}).items() if k in ("calls", "tokens_in", "tokens_out")},
            "console": console_by_gen.get(g["generation"], []),
        })
        prev = {"id": ch.get("id"), "train": ch.get("train"), "valid": ch.get("valid"),
                "official": (champs.get(ch.get("id")) or {}).get("score")}

    summary = {}
    if (run_dir / "summary.json").exists():
        summary = json.loads((run_dir / "summary.json").read_text())
    heldout = json.loads((run_dir / "heldout.json").read_text()) if (run_dir / "heldout.json").exists() else None
    final = champs.get(gens[-1]["champion"]["id"]) if gens and gens[-1].get("champion") else None

    keep_cfg = ("engine", "mode", "generations", "hypotheses", "variants", "fresh", "workers", "inspect",
                "fit_split", "accept_margin", "probe_margin", "trial_evals", "trial_refit_evals",
                "champion_refit_evals", "refit_evals", "combo", "max_combine", "overlap", "flash_model", "temperature")
    trace = {
        "format": FORMAT, "exported": time.strftime("%Y-%m-%d %H:%M"),
        "run": {"id": run_dir.name, "config": {k: config.get(k) for k in keep_cfg if k in config},
                "code_zero": seed and {"id": seed["id"], "score": seed.get("score"), "families": seed.get("families")},
                "final": final and {"id": final["id"], "score": final["score"], "progress": final["progress"]},
                "summary": summary or None, "heldout": heldout, "has_console": bool(console_text)},
        "prompts": prompts, "calls": calls, "features": feats, "ideas": ideas,
        "champions": champs, "generations": gen_out, "notes": {},
    }
    if notes_path:
        trace["notes"] = json.loads(Path(notes_path).read_text())
    elif (run_dir / "notes.json").exists():
        trace["notes"] = json.loads((run_dir / "notes.json").read_text())
    return trace


# ---------------------------------------------------------------- optional: short summaries by the model
SUMMARY_SYSTEM = ("You summarise one agent call from an LLM-driven evolutionary search for a bin-packing policy. "
                  "In two or three plain sentences say what the agent was asked to do and what it proposed or wrote, "
                  "naming the specific idea. No preamble, no lists.")


def summarize_calls(trace, max_chars=6000):
    """Fill trace['notes']['calls'] for calls that have no written note yet. One model call per agent call,
    sequential (about one a second keeps well inside Luminal's rate limit; see LUMINAL.md)."""
    from helix.llm import LLM, Settings
    llm = LLM(Settings.from_env())
    notes = trace.setdefault("notes", {}).setdefault("calls", {})
    auto = trace["notes"].setdefault("auto", [])
    for c in trace["calls"]:
        if c["id"] in notes or not c.get("reply"):
            continue
        user = c["user"] if len(c["user"]) < max_chars else c["user"][:max_chars // 2] + "\n[...]\n" + c["user"][-max_chars // 2:]
        msg = f"Role: {c['role']} (generation {c['gen']}).\n\nWhat it was sent:\n{user}\n\nWhat it replied:\n{c['reply'][:max_chars]}"
        try:
            r = llm.chat("summary", SUMMARY_SYSTEM, msg, temperature=0.2, max_tokens=300)
            notes[c["id"]] = r.text.strip()
            auto.append(c["id"])
        except Exception as exc:
            print(f"   summary of {c['id']} failed: {exc}", file=sys.stderr)
        time.sleep(1.0)
    return trace


# ---------------------------------------------------------------- writing
def to_html(trace, template=TEMPLATE):
    page = Path(template).read_text()
    if PLACEHOLDER not in page:
        raise SystemExit(f"{template} has no {PLACEHOLDER} slot")
    data = json.dumps(trace, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return page.replace(PLACEHOLDER, data, 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run", help="a run folder: helix/runs/<run> or results/<run>")
    ap.add_argument("--out", help="the viewer page to write (default <run>/viewer.html)")
    ap.add_argument("--json", help="also write the trace on its own to this file")
    ap.add_argument("--notes", help="a notes JSON (written interpretation) to include; default <run>/notes.json")
    ap.add_argument("--console", help="the run's console output, if it isn't <run>/console.log")
    ap.add_argument("--summarize", action="store_true", help="ask the model for a short summary of each call")
    a = ap.parse_args(argv)
    trace = build_trace(a.run, a.console, a.notes)
    if a.summarize:
        summarize_calls(trace)
    if a.json:
        Path(a.json).write_text(json.dumps(trace, ensure_ascii=False, indent=1))
        print(f"trace: {a.json}")
    out = Path(a.out) if a.out else Path(a.run) / "viewer.html"
    out.write_text(to_html(trace))
    print(f"viewer: {out} ({out.stat().st_size / 1e6:.1f} MB; {len(trace['calls'])} calls, "
          f"{len(trace['features'])} features, {len(trace['generations'])} generations)")


if __name__ == "__main__":
    main()
