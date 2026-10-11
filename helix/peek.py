"""Look inside a run while it's going.

  python -m helix.peek                  snapshot of the newest run
  python -m helix.peek helix/runs/<run> snapshot of a given run

The snapshot is plain text meant to be pasted into a chat: the current state, the
score history, the pool, what the Researcher was thinking last, the latest verdicts
and Mutator ideas, the most common failures, and the best program. The dashboard
(python -m helix.ui) reads runs through the same functions.
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "runs"
VERDICTS = ("matters", "minor", "removal-helps", "supported", "refuted", "flat", "no-effect", "invalid", "unchanged")


# ---------------------------------------------------------------- reading a run folder
def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass          # a line still being written
    except OSError:
        pass
    return out


def tail_jsonl(path, n):
    """The last n records of a JSONL file, without reading the whole (possibly large) file."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = size = f.tell()
            chunk, data = 1 << 16, b""
            while end > 0 and data.count(b"\n") <= n:
                start = max(0, end - chunk)
                f.seek(start)
                data = f.read(end - start) + data
                end = start
    except OSError:
        return []
    out = []
    for line in data.splitlines()[-n:] if size else []:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def tail_text(path, n):
    try:
        return "\n".join(Path(path).read_text(errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def pid_alive(pid):
    if not pid or os.name != "posix":
        return True           # can't check safely off POSIX; trust the status file
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def latest_run():
    runs = [p for p in RUNS_DIR.glob("*") if p.is_dir()] if RUNS_DIR.exists() else []
    return max(runs, key=lambda p: p.stat().st_mtime) if runs else None


def load_state(run_dir):
    """Everything the dashboard and the snapshot need, read from a run folder."""
    d = Path(run_dir)
    status = read_json(d / "status.json", {}) or {}
    if status.get("state") == "running" and not pid_alive(status.get("pid")):
        status["state"] = "died"     # the process ended without saying so (killed, laptop slept, ...)
    programs = read_jsonl(d / "programs.jsonl")
    hyps = read_jsonl(d / "hypotheses.jsonl")
    valid = [p for p in programs if p.get("valid")]
    leaders = [p for p in valid if not p.get("probe")]       # knock-out measurements never lead
    best = max(leaders, key=lambda p: p["score"]) if leaders else None
    seed = next((p for p in programs if p.get("branch") == "seed"), None)
    errors = Counter(_first_error_line(p["error"]) for p in programs if not p.get("valid") and p.get("error"))
    return {
        "name": d.name,
        "status": status,
        "config": read_json(d / "config.json", {}) or {},
        "generations": read_jsonl(d / "generations.jsonl"),
        "programs": [{k: p.get(k) for k in ("id", "generation", "branch", "parent_id", "hypothesis_id", "note",
                                            "valid", "score", "families", "repaired", "duplicate_of", "model", "probe")}
                     | {"error": _first_error_line(p.get("error"))} for p in programs],
        "hypotheses": hyps,
        "best": best,
        "seed_score": seed["score"] if seed else None,
        "counts": {"programs": len(programs), "valid": len(valid), "repaired": sum(bool(p.get("repaired")) for p in programs),
                   "duplicates": sum(p.get("duplicate_of") is not None for p in programs)},
        "errors": errors.most_common(5),
    }


def _first_error_line(error):
    if not error:
        return None
    lines = [line.strip() for line in str(error).strip().splitlines() if line.strip()]
    return lines[-1][:200] if lines else None


# ---------------------------------------------------------------- the snapshot
def snapshot(run_dir):
    s = load_state(run_dir)
    st, cfg = s["status"], s["config"]
    now = time.time()
    out = [f"HELIX SNAPSHOT  run {s['name']}  ({time.strftime('%H:%M:%S')})"]

    elapsed = (st.get("finished") or now) - st["started"] if st.get("started") else None
    llm = st.get("llm") or {}
    out.append(f"State: {st.get('state', 'unknown')} | generation {st.get('generation')}/{st.get('generations')} | "
               f"phase: {st.get('phase') or '-'} | elapsed {elapsed / 60:.1f} min" if elapsed else
               f"State: {st.get('state', 'unknown')}")
    out.append(f"Config: mode {cfg.get('mode')}, schedule {cfg.get('schedule')}, provider {cfg.get('provider')}, "
               f"model {cfg.get('flash_model')}" + (f", pro {cfg['pro_model']} every {cfg.get('pro_every')}" if cfg.get("pro_model") else "")
               + f", top_x {cfg.get('top_x')}, variants {cfg.get('variants')}, hypotheses {cfg.get('hypotheses')}")
    out.append(f"LLM so far: {llm.get('calls', 0)} calls ({llm.get('pro_calls', 0)} pro), "
               f"{llm.get('tokens_in', 0):,} tokens in, {llm.get('tokens_out', 0):,} out")
    c = s["counts"]
    out.append(f"Programs: {c['programs']} made, {c['valid']} valid, {c['repaired']} repaired, {c['duplicates']} duplicates")
    if st.get("error"):
        out.append("CRASH: " + st["error"].splitlines()[-1])
    best = s["best"]
    if best:
        gain = f", gain {best['score'] - s['seed_score']:+.3f} over Code Zero {s['seed_score']:.3f}" if s["seed_score"] is not None else ""
        out.append(f"Best: {best['id']} score {best['score']:.3f} ({best['branch']} branch, generation {best['generation']}){gain}")

    out.append("\n== Generations (score = -mean excess %, higher is better)")
    for g in s["generations"][-12:]:
        parts = [f"gen {g['generation']:>2}: best {g.get('best_score', 0):.3f}"]
        for b in ("deep", "wide"):
            r = g.get(b)
            if r:
                bn = f"{r['best_new']:.3f}" if r.get("best_new") is not None else "none"
                verdicts = ", ".join(f"{k} {v}" for k, v in r.items() if k in VERDICTS)
                parts.append(f"{b} {r['valid']}/{r['new']} valid, best new {bn}" + (f" [{verdicts}]" if verdicts else ""))
        t = g.get("tune")
        if t:
            bn = f", best {t['best_new']:.3f}" if t.get("best_new") is not None else ""
            parts.append(f"tune {t.get('improved', 0)}/{len(t.get('targets', []))} improved{bn} ({t.get('tried', 0)} tries)")
        if g.get("seconds"):
            parts.append(f"{g['seconds']}s")
        out.append(" | ".join(parts))

    if s["generations"]:
        pool = {p["id"]: p for p in s["programs"]}
        out.append("\n== Current pool, best first")
        ranked = sorted((pool[i] for i in s["generations"][-1].get("pool", []) if i in pool),
                        key=lambda p: p["score"] if p["score"] is not None else -1e9, reverse=True)
        for p in ranked[:5]:
            fams = " ".join(f"{f} {v:.1f}" for f, v in (p["families"] or {}).items())
            out.append(f"{p['id']} {p['score']:.3f} {p['branch']} | {fams} | {(p['note'] or '')[:120]}")

    calls = tail_jsonl(Path(run_dir) / "llm_calls.jsonl", 150)
    research = [c for c in calls if c.get("role") == "researcher" and c.get("reply")]
    if research:
        r = research[-1]
        out.append(f"\n== Latest Researcher call ({r.get('model')}, {r.get('seconds')}s)")
        if r.get("reasoning"):
            text = r["reasoning"]
            out.append("Reasoning (excerpt): " + (text if len(text) <= 2500 else text[:1800] + "\n[...]\n" + text[-700:]))
        out.append("Reply: " + r["reply"][:3000])

    if s["hypotheses"]:
        out.append("\n== Latest verdicts")
        for h in s["hypotheses"][-8:]:
            delta = f"{h['delta']:+.3f}" if h.get("delta") is not None else "n/a"
            out.append(f"{h['id']} gen {h['generation']} {h.get('kind', 'improve')} {h['verdict']} {delta} on {h['base_id']}"
                       + (f" (builds on {h['builds_on']})" if h.get("builds_on") else "")
                       + f": {h['claim'][:160]} || change: {h['change'][:120]}")

    ideas = [p for p in s["programs"] if p["branch"] == "wide" and p.get("note")][-5:]
    if ideas:
        out.append("\n== Latest Mutator ideas")
        for p in ideas:
            score = f"{p['score']:.3f}" if p["score"] is not None else "invalid"
            out.append(f"{p['id']} {score}: {p['note'][:180]}")

    if s["errors"]:
        out.append("\n== Most common failures")
        out += [f"{n}x {msg}" for msg, n in s["errors"]]

    if best:
        out.append(f"\n== Best program ({best['id']})\n{best['code'].strip()}")
    return "\n".join(out)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    if not target or not target.exists():
        sys.exit("No run found. Start one with python -m helix.run or from the dashboard.")
    print(snapshot(target))
