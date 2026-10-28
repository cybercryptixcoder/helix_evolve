"""The continuation pack: what a run needs to continue on any machine, from GitHub alone (docs/V9_JOB.md).

A run folder pushed to GitHub has every program's code, score and history, but not the constructions (a few hundred
KB each, thousands of them) nor, for the autocorrelation problem, the signatures (computed from the constructions).
Without them a continuation knows only the record's construction (best.npy): every other base, and the whole map of
hills, would be lost.

    python -m helix9.pack build --run results/v8warm/v8-s1 --search runs/v8warm/v8-s1/constructions,runs/v7warm/v7-s1/constructions
    python -m helix9.pack restore --pack results/v8warm/v8-s1/pack --out runs/v9warm/v9-s1

- **build** (once, on the machine that has the constructions): finds each program's construction in the given
  folders (in order) and **verifies it**: re-scored with the problem's own scorer, it must give the score the run
  recorded (to 1e-12, relative) and the recorded number of steps. Only verified constructions are used, so a messy
  folder can't slip a wrong one in. Then it writes:
  - `signatures.jsonl`: the output signature of every verified program (64 numbers each: small);
  - `constructions-NNN.npz`: the constructions of the programs a continuation may build on, in order of importance
    (the record, the tops of known hills, every track's best, the record's lineage, the strongest programs, the
    latest generations) until the size budget is used (default 80 MB, in files of at most 40 MB: GitHub refuses
    files over 100 MB), compressed losslessly (float64);
  - `manifest.json`: what was found, verified, rejected and packed, with a SHA-256 of every packed array.
  With `--base` (an earlier run's pack, e.g. the pack of the run this one continued), constructions already in the
  base (same SHA-256) are not packed again: the new pack holds only what is new and names its base.
- **restore**: unpacks the constructions into a run folder (its base's first, checking each SHA-256) and adds the
  signatures.

A continuation built on a pack is lossless for every packed program. A program outside the pack keeps its code,
score and place in the history; if the run ever needs its construction (to build on it), v9 rebuilds it by running
its code again from its nearest packed ancestor (helix9/run.py, `ensure_construction`), and says so.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import importlib
import io
import json
import time
from pathlib import Path

import numpy as np

from helix8.hills import shape_signature


def read_text(path):
    """A file's text, in any form a run folder pushed to GitHub has it: `name.jsonl`, `name.jsonl.gz`, or `name/` in
    gzipped chunks with an index.json (helix9/publish.py)."""
    p = Path(path)
    if p.exists():
        return p.read_text()
    gz = p.with_name(p.name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt") as f:
            return f.read()
    folder = p.with_name(p.name.split(".")[0])
    if (folder / "index.json").exists():
        from helix9.publish import read_chunks
        return read_chunks(folder).decode()
    return None


def jl(path):
    text = read_text(path)
    if text is None:
        return []
    out = []
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def sha(arr):
    return hashlib.sha256(np.ascontiguousarray(np.asarray(arr, dtype=float)).tobytes()).hexdigest()


def problem_module(name, config=None):
    """The problem's scorer, with the run's own size limit (v4.7 and later raise ac2's step limit with `max_n`; judging
    a run's constructions by the module's default limit rejected valid ones)."""
    mod = importlib.import_module(f"helix4.problems.{name}")
    max_n = (config or {}).get("max_n")
    if max_n and getattr(mod, "MAX_N", None) and int(max_n) > int(mod.MAX_N):
        from helix47.run import ProblemView
        return ProblemView(mod, max_n)
    return mod


def verify(problem, arr, p, rtol=1e-12):
    """True if `arr` is p's construction: same number of steps, and the problem's scorer gives p's recorded score."""
    try:
        h, why = problem.check(arr)
    except Exception:                       # noqa: BLE001
        return False, "unreadable"
    if h is None:
        return False, f"invalid: {why}"
    if p.get("n") and len(h) != int(p["n"]):
        return False, f"{len(h)} steps, recorded {p['n']}"
    s = float(problem.score(h))
    ref = float(p["score"])
    if abs(s - ref) > rtol * max(abs(ref), 1e-12):
        return False, f"scores {s!r}, recorded {ref!r}"
    return True, ""


def priorities(run):
    """Programs in the order a continuation needs their constructions, with why."""
    progs = {p["id"]: p for p in jl(run / "programs.jsonl")}
    valid = {k: p for k, p in progs.items() if p.get("valid") and p.get("score") is not None}
    order = []

    def add(pid, why):
        if pid in valid and pid not in dict(order):
            order.append((pid, why))
    best = max(valid.values(), key=lambda p: p["score"]) if valid else None
    if best:
        add(best["id"], "the record")
    hills = (jl(run / "hills.jsonl")[-1:] or [{}])[0].get("hills", [])
    for h in sorted(hills, key=lambda h: -(h.get("top_score") or 0)):
        add(h.get("top"), "a hill's top")
    tracks = (jl(run / "tracks.jsonl")[-1:] or [{}])[0].get("tracks", [])
    for t in sorted(tracks, key=lambda t: -(t.get("best") or -1e300)):
        add(t.get("best_id"), f"the best of track {t.get('id')}")
    lin, q = [], best
    while q is not None and len(lin) < 30:
        lin.append(q["id"])
        q = progs.get(q.get("parent")) if q.get("parent") else None
    for pid in lin:
        add(pid, "the record's lineage")
    for p in sorted(valid.values(), key=lambda p: -p["score"])[:60]:
        add(p["id"], "a strong program")
    last = max((p["gen"] for p in valid.values()), default=0)
    for p in sorted(valid.values(), key=lambda p: -p["gen"]):
        if p["gen"] >= last - 9:
            add(p["id"], "the latest generations")
    for t in tracks:
        add(t.get("root"), f"the root of track {t.get('id')}")
    return order, progs


def pack_chain(pack):
    """[pack, its base, the base's base, ...] (each a folder with manifest.json)."""
    chain, seen = [], set()
    pack = Path(pack)
    while pack is not None and (pack / "manifest.json").exists() and pack.resolve() not in seen:
        seen.add(pack.resolve())
        chain.append(pack)
        base = json.loads((pack / "manifest.json").read_text()).get("base")
        pack = (pack / base) if base else None
    return chain


def build(run, search, out=None, budget_mb=80.0, problem=None, chunk_mb=40.0, base=None, log=print):
    run = Path(run)
    out = Path(out) if out else run / "pack"
    state = json.loads((run / "state.json").read_text()) if (run / "state.json").exists() else {}
    prob = problem_module(problem or (state.get("config") or {}).get("problem") or "ac2", state.get("config"))
    order, progs = priorities(run)
    folders = [Path(f) for f in search if f and Path(f).is_dir()]
    found, rejected, missing = {}, {}, []
    best_npy = run / "best.npy"
    best_id = order[0][0] if order else None
    t0 = time.time()
    for pid, p in progs.items():
        if not p.get("valid") or p.get("score") is None:
            continue
        cands = [f / f"{pid}.npy" for f in folders]
        if pid == best_id and best_npy.exists():
            cands.append(best_npy)
        ok = False
        for c in cands:
            if not c.exists():
                continue
            try:
                arr = np.load(c)
            except Exception as exc:                      # noqa: BLE001
                rejected[pid] = f"{c}: unreadable ({exc})"
                continue
            good, why = verify(prob, arr, p)
            if good:
                found[pid] = (c, arr)
                ok = True
                break
            rejected[pid] = f"{c}: {why}"
        if not ok and pid not in rejected:
            missing.append(pid)
    in_base = {}
    for b in (pack_chain(base) if base else []):
        for pid, h in (json.loads((b / "manifest.json").read_text()).get("sha256") or {}).items():
            in_base.setdefault(pid, h)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "manifest.json").exists():               # written last: present only for a finished pack
        (out / "manifest.json").unlink()
    for old in out.glob("constructions-*.npz"):
        old.unlink()
    sigs = []
    if hasattr(prob, "score") and prob.NAME == "ac2":
        for pid, (_, arr) in found.items():
            s = shape_signature(arr)
            if s is not None:
                sigs.append({"id": pid, "sig": [round(float(x), 10) for x in s]})
    (out / "signatures.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sorted(sigs, key=lambda r: r["id"])))
    packed, why_packed, used, chunk, chunk_bytes, n_chunk, hashes, from_base = [], {}, 0, {}, 0, 0, {}, []

    def flush():
        nonlocal chunk, chunk_bytes, n_chunk
        if not chunk:
            return
        n_chunk += 1
        np.savez_compressed(out / f"constructions-{n_chunk:03d}.npz", **chunk)
        chunk, chunk_bytes = {}, 0
    for pid, why in order:
        if pid not in found:
            continue
        arr = np.asarray(found[pid][1], dtype=float)
        if in_base.get(pid) == sha(arr):
            from_base.append(pid)
            continue
        buf = io.BytesIO()
        np.savez_compressed(buf, a=arr)
        size = len(buf.getvalue())
        if used + size > budget_mb * 1e6:
            continue
        used += size
        chunk[pid] = arr
        chunk_bytes += size
        packed.append(pid)
        why_packed[pid] = why
        hashes[pid] = sha(arr)
        if chunk_bytes >= chunk_mb * 1e6:
            flush()
    flush()
    manifest = {"built": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "run": str(run), "problem": prob.NAME,
                "search": [str(f) for f in folders], "programs": len(progs),
                "valid": sum(1 for p in progs.values() if p.get("valid") and p.get("score") is not None),
                "verified": len(found), "rejected": rejected, "missing": len(missing), "signatures": len(sigs),
                "packed": packed, "why": why_packed, "sha256": hashes, "bytes": used, "budget_mb": budget_mb,
                "chunks": n_chunk, "seconds": round(time.time() - t0, 1),
                "base": os.path.relpath(Path(base).resolve(), out.resolve()) if base and in_base else None,
                "in_base": from_base,
                "not_packed": [pid for pid, _ in order if pid in found and pid not in hashes and pid not in from_base]}
    (out / ".manifest.json.tmp").write_text(json.dumps(manifest, indent=1))
    os.replace(out / ".manifest.json.tmp", out / "manifest.json")
    log(f"pack: {len(found)} of {manifest['valid']} valid programs verified ({len(rejected)} rejected, {len(missing)} "
        f"not found); {len(sigs)} signatures; {len(packed)} constructions packed ({used / 1e6:.1f} MB of "
        f"{budget_mb:g}) in {n_chunk} files" + (f", {len(from_base)} more already in the base pack" if from_base else "")
        + (f"; {len(manifest['not_packed'])} of the programs a continuation may build on didn't fit (rebuilt on demand)"
           if manifest["not_packed"] else ""))
    return manifest


def restore(pack, out, log=print):
    """Unpacks a pack (and its base packs) into run folder `out`: constructions/<id>.npy (each checked against its
    SHA-256) and the signatures (merged into signatures.jsonl, for programs the run has)."""
    out = Path(out)
    chain = pack_chain(pack)
    if not chain:
        raise SystemExit(f"pack: {pack} has no manifest.json")
    (out / "constructions").mkdir(parents=True, exist_ok=True)
    n, bad = 0, []
    for pk in reversed(chain):                           # the oldest base first; a newer pack overrides
        man = json.loads((pk / "manifest.json").read_text())
        for f in sorted(pk.glob("constructions-*.npz")):
            with np.load(f) as z:
                for pid in z.files:
                    arr = z[pid]
                    if man["sha256"].get(pid) != sha(arr):
                        bad.append(pid)
                        continue
                    np.save(out / "constructions" / f"{pid}.npy", arr)
                    n += 1
    have = {p["id"] for p in jl(out / "programs.jsonl")}
    old = {r["id"] for r in jl(out / "signatures.jsonl")}
    add, seen = [], set(old)
    for pk in chain:
        for r in jl(pk / "signatures.jsonl"):
            if r["id"] in have and r["id"] not in seen:
                seen.add(r["id"])
                add.append(r)
    with (out / "signatures.jsonl").open("a") as f:
        for r in add:
            f.write(json.dumps(r) + "\n")
    log(f"restored {n} constructions and {len(add)} signatures into {out}" + (f"; {len(bad)} failed their check: {bad[:5]}" if bad else ""))
    if bad:
        raise SystemExit(f"pack: {len(bad)} constructions failed their SHA-256 check")
    return n, len(add)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--run", required=True, help="the run folder as on GitHub (programs.jsonl, hills, tracks, best.npy)")
    b.add_argument("--search", default="", help="comma-separated folders holding <id>.npy constructions")
    b.add_argument("--out", default=None, help="default: <run>/pack")
    b.add_argument("--budget-mb", type=float, default=80.0)
    b.add_argument("--base", default=None, help="an earlier pack: constructions it holds are not packed again")
    r = sub.add_parser("restore")
    r.add_argument("--pack", required=True)
    r.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(a.run, [s for s in a.search.split(",") if s], a.out, a.budget_mb, base=a.base)
    else:
        restore(a.pack, a.out)


if __name__ == "__main__":
    main()
