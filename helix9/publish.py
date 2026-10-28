"""Copies a run's results into the folder pushed to GitHub, the way docs/AETHER.md section 5 asks (docs/V9_JOB.md).

    python -m helix9.publish --run runs/v9warm/v9-s1 --out results/v9warm/v9-s1 --log runs/v9warm/v9-s1.log
    python -m helix9.publish --join results/v9warm/v9-s1 --out /tmp/v9-s1      # plain files again, for any tool

Every push sends everything the run has (constructions aside: the continuation pack, helix9/pack.py, carries those):
- **small files as they are:** state, summary, history, noise, the codebook's current form, the log;
- **big, growing files in fixed gzipped chunks:** programs, the trace (every model call, in full), tracks, hills, plans,
  findings, the design map's rows (codebook, coordinates, readings, discoveries, rebuilt constructions) and
  signatures go to `<name>/part-NNNN.jsonl.gz` with `<name>/index.json`. These files only grow (a resume trims the
  unfinished generation's lines, then appends), so a chunk of a fixed number of lines, once full, never changes:
  each push adds only what is new, and gzip runs deterministically (mtime 0), so an unchanged chunk is byte-identical.
  A chunk whose lines did change (a resume trimmed lines already pushed) is written again; the index's SHA-256 of
  each chunk's lines decides;
- **mapview.json:** the map and the charts for viz/mapview.html, which can follow the run live from GitHub.

Reading: helix9's tools (warm, pack, mapview, replay, report via `helix9.pack.jl`) read a file in any of its forms
(name.jsonl, name.jsonl.gz, or name/ in chunks), so a continuation from GitHub needs nothing else. `--join` writes the
plain files back for anything else. Every file is written to a temporary name and renamed, so a push never sends half
a file.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

CHUNK_MB = float(os.environ.get("PUBLISH_CHUNK_MB", "4"))     # raw size a chunk aims at (chosen once per file)
PLAIN = ("state.json", "summary.json", "history.jsonl", "noise.json", "codebook.json", "env.json", "borrowed.json",
         "gc.jsonl")
CHUNKED = ("programs.jsonl", "trace.jsonl", "tracks.jsonl", "hills.jsonl", "plans.jsonl", "findings.jsonl",
           "codebook.jsonl", "coords.jsonl", "annotations.jsonl", "discoveries.jsonl", "rebuilt.jsonl",
           "signatures.jsonl", "refs.jsonl")
FULL_ONLY = ("best.py", "best.npy")


def atomic_bytes(path, data):
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def gz_bytes(data):
    import io
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, filename="") as f:
        f.write(data)
    return buf.getvalue()


def lines_of(path):
    """The file's whole lines (a line cut off by a hard stop is left out: it is not part of the run yet)."""
    raw = Path(path).read_bytes()
    if not raw:
        return []
    out = raw.split(b"\n")
    if out and out[-1] == b"":
        out.pop()
    elif out:
        out.pop()                     # no newline at the end: the last line is still being written
    return [l + b"\n" for l in out]


def chunk(src, dst_dir):
    """Writes src (a JSONL file) as fixed chunks into dst_dir. Returns (chunks written, chunks in all)."""
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    idx_f = dst_dir / "index.json"
    idx = json.loads(idx_f.read_text()) if idx_f.exists() else {}
    lines = lines_of(src)
    if not idx.get("lines_per_chunk"):
        avg = (sum(len(l) for l in lines) / len(lines)) if lines else 2000
        idx = {"file": Path(src).name, "lines_per_chunk": max(20, int(CHUNK_MB * 1e6 / max(avg, 1))), "parts": []}
    per = idx["lines_per_chunk"]
    parts, wrote = [], 0
    old = {p["name"]: p for p in idx.get("parts", [])}
    for k in range(0, len(lines), per):
        block = b"".join(lines[k:k + per])
        name = f"part-{k // per + 1:04d}.jsonl.gz"
        h = hashlib.sha256(block).hexdigest()
        gens = []
        for l in (lines[k], lines[min(k + per, len(lines)) - 1]):
            try:
                g = json.loads(l).get("gen")
                if g is None:
                    g = ((json.loads(l).get("meta") or {}).get("gen"))
                gens.append(g)
            except (ValueError, AttributeError):
                gens.append(None)
        if old.get(name, {}).get("sha256") != h or not (dst_dir / name).exists():
            atomic_bytes(dst_dir / name, gz_bytes(block))
            wrote += 1
        parts.append({"name": name, "lines": min(per, len(lines) - k), "sha256": h, "gens": gens})
    for name in old:                                  # chunks past the end (the file was trimmed): removed
        if name not in {p["name"] for p in parts} and (dst_dir / name).exists():
            (dst_dir / name).unlink()
    idx["parts"] = parts
    idx["lines"] = len(lines)
    atomic_bytes(idx_f, (json.dumps(idx, indent=1) + "\n").encode())
    return wrote, len(parts)


def read_chunks(folder):
    folder = Path(folder)
    idx = json.loads((folder / "index.json").read_text())
    out = []
    for p in idx["parts"]:
        with gzip.open(folder / p["name"], "rb") as f:
            out.append(f.read())
    return b"".join(out)


def publish(run, out, log_file=None, full=False, say=print):
    run, out = Path(run), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stats = {"plain": 0, "chunks_written": 0, "chunks": 0}
    for f in PLAIN + (FULL_ONLY if full else ()):
        if (run / f).exists():
            atomic_bytes(out / f, (run / f).read_bytes())
            stats["plain"] += 1
    if log_file and Path(log_file).exists():
        atomic_bytes(out / "run.log", Path(log_file).read_bytes())
    for f in CHUNKED:
        if (run / f).exists():
            w, n = chunk(run / f, out / Path(f).stem)
            stats["chunks_written"] += w
            stats["chunks"] += n
            for stale in (out / f, out / (f + ".gz")):      # an earlier plain copy would be read first: removed
                if stale.exists():
                    stale.unlink()
    try:
        from helix9.mapview import run_view
        atomic_bytes(out / "mapview.json", json.dumps(run_view(run), separators=(",", ":")).encode())
        stats["mapview"] = True
    except Exception as exc:                                     # noqa: BLE001
        say(f"   (the map view failed: {type(exc).__name__}: {str(exc)[:200]}; the run data are fine)")
    big = [str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.stat().st_size > 95e6]
    if big:
        say(f"   (warning: {', '.join(big)} over 95 MB: GitHub would refuse the push)")
    return stats


def join(src, out):
    """Plain files from a published folder (chunks joined, .gz unpacked)."""
    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in src.iterdir():
        if p.is_dir() and (p / "index.json").exists():
            atomic_bytes(out / (p.name + ".jsonl"), read_chunks(p))
        elif p.is_file() and p.name.endswith(".jsonl.gz") and p.name != "trace.jsonl.gz":
            with gzip.open(p, "rb") as f:
                atomic_bytes(out / p.name[:-3], f.read())
        elif p.is_file():
            shutil.copyfile(p, out / p.name)
        elif p.is_dir():
            shutil.copytree(p, out / p.name, dirs_exist_ok=True)
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", help="the run folder to publish")
    ap.add_argument("--join", help="a published folder to turn back into plain files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", default=None, help="the run's log, copied as run.log")
    ap.add_argument("--full", action="store_true", help="also the record (best.py, best.npy)")
    a = ap.parse_args(argv)
    if a.join:
        print(f"   {join(a.join, a.out)} files joined into {a.out}")
        return 0
    if not a.run:
        ap.error("--run or --join")
    s = publish(a.run, a.out, a.log, a.full)
    print(f"   published to {a.out}: {s['plain']} files, {s['chunks_written']} of {s['chunks']} chunks new or changed"
          + ("" if s.get("mapview") else ", no map view"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
