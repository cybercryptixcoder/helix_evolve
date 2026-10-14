"""Full, human-readable transcript for a finished run.

Every run keeps its raw records (`llm_calls.jsonl`, `features.jsonl`, `generations.jsonl`,
`programs.jsonl`); this module turns them into one readable document so a person (or an agent
reading the run later) can see every agent thought, every number and every change in order.

    python -m helix.transcript <run_dir>

writes `transcript.md` next to the records and prints its path.
"""
from __future__ import annotations

import json
from pathlib import Path


def _read_jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def write_transcript(run_dir, max_call_chars=None):
    """Write transcript.md for a run folder. Returns the path (or None if the folder has no records)."""
    run = Path(run_dir)
    gens = _read_jsonl(run / "generations.jsonl")
    feats = _read_jsonl(run / "features.jsonl")
    progs = _read_jsonl(run / "programs.jsonl")
    calls = _read_jsonl(run / "llm_calls.jsonl")
    if not (gens or feats or calls):
        return None

    L = []
    a = L.append
    a(f"# Full transcript — {run.name}\n")
    cfg = {}
    if (run / "config.json").exists():
        try:
            cfg = json.loads((run / "config.json").read_text())
        except json.JSONDecodeError:
            pass
    if cfg:
        keys = ("engine", "generations", "seed_features", "seed_program", "trial_evals", "trial_refit_evals",
                "champion_refit_evals", "refit_evals", "accept_margin", "probe_margin", "combo", "combine_refit",
                "revisit", "pairs", "gen_soft_seconds", "fit_split", "hypotheses", "variants")
        shown = ", ".join(f"{k}={cfg[k]}" for k in keys if k in cfg and cfg[k] is not None)
        if shown:
            a(f"Config: {shown}\n")

    # ---------------------------------------------------------------- generations
    if gens:
        a("\n## Generations\n")
        a("| gen | seconds | agents | fit | evals | accepted | best (fit) | champion | LLM calls |")
        a("|---|---|---|---|---|---|---|---|---|")
        for g in gens:
            ph = g.get("phase_seconds") or {}
            fit = g.get("fit") or {}
            champ = g.get("champion") or {}
            acc = ", ".join(g.get("accepted") or []) or "—"
            secs = g.get("seconds")
            a(f"| {g.get('generation')} | {round(secs) if isinstance(secs, (int, float)) else '—'} "
              f"| {round(ph.get('agents')) if ph.get('agents') is not None else '—'} "
              f"| {round(ph.get('fit')) if ph.get('fit') is not None else '—'} "
              f"| {fit.get('evals', '—')} | {acc} "
              f"| {g.get('best_score') if g.get('best_score') is None else round(g['best_score'], 3)} "
              f"| {champ.get('id', '—')} | {(g.get('llm') or {}).get('calls', '—')} |")

    # ---------------------------------------------------------------- features
    if feats:
        latest = {}
        for f in feats:
            latest[f["id"]] = f
        a("\n## Features (latest record per id)\n")
        a("| id | gen | branch | name | status | d_train | d_valid | columns | note |")
        a("|---|---|---|---|---|---|---|---|---|")
        for f in sorted(latest.values(), key=lambda x: x["id"]):
            dt = f.get("delta_train")
            dv = f.get("delta_valid")
            a(f"| {f['id']} | {f.get('generation')} | {f.get('branch')} | {f.get('name','')} "
              f"| {f.get('status')} | {round(dt, 3) if isinstance(dt, (int, float)) else ('—' if dt is None else dt)} "
              f"| {round(dv, 3) if isinstance(dv, (int, float)) else ('—' if dv is None else dv)} "
              f"| {len(f.get('columns') or [])} | {str(f.get('note') or '')[:80]} |")
        a("\n### Feature code\n")
        for f in sorted(latest.values(), key=lambda x: x["id"]):
            if f.get("status") in ("candidate", "invalid"):
                continue
            a(f"#### {f['id']} {f.get('name','')} ({f.get('branch')}, {f.get('status')})\n")
            if f.get("description"):
                a(f"{f['description']}\n")
            a("```python\n" + (f.get("code") or "") + "\n```\n")

    # ---------------------------------------------------------------- programs
    champs = [p for p in progs if p.get("valid") and not p.get("trial") and not p.get("probe")]
    if champs:
        a("\n## Champion programs (official evaluator scores)\n")
        a("| id | gen | branch | official | validation | note |")
        a("|---|---|---|---|---|---|")
        for p in sorted(champs, key=lambda x: x["generation"]):
            a(f"| {p['id']} | {p.get('generation')} | {p.get('branch')} | {p.get('score')} "
              f"| {p.get('valid_score') if p.get('valid_score') is None else round(p['valid_score'], 3)} "
              f"| {str(p.get('note') or '')[:90]} |")

    # ---------------------------------------------------------------- calls
    if calls:
        a("\n## Agent calls (full)\n")
        for i, c in enumerate(calls, 1):
            a(f"\n### {i}. [{c.get('time','')}] {c.get('role','?')} — gen {c.get('generation','?')}"
              f"{(' · ' + str(c.get('feature'))) if c.get('feature') else ''}"
              f"{(' · ' + str(round(c.get('seconds'))) + 's') if c.get('seconds') else ''}\n")
            sys_p = (c.get("system") or "").strip()
            usr_p = (c.get("user") or "").strip()
            rep = (c.get("reply") or "").strip()
            think = (c.get("reasoning") or "").strip()
            if max_call_chars:
                sys_p, usr_p, rep, think = (t[:max_call_chars] for t in (sys_p, usr_p, rep, think))
            if think:
                a("<details><summary>hidden reasoning</summary>\n\n```\n" + think + "\n```\n\n</details>\n")
            a("<details><summary>system prompt</summary>\n\n```\n" + sys_p + "\n```\n\n</details>\n")
            a("<details><summary>user message</summary>\n\n```\n" + usr_p + "\n```\n\n</details>\n")
            a("**reply:**\n\n```\n" + rep + "\n```\n")
            if c.get("finish") and c["finish"] != "stop":
                a(f"(finish: {c['finish']})\n")

    out = run / "transcript.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit("usage: python -m helix.transcript <run_dir>")
    p = write_transcript(sys.argv[1])
    print(f"wrote {p}" if p else "nothing to export")
