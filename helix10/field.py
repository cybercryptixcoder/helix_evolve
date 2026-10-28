"""The field's constructions (helix10/sota.py, IMPORTS): fetched from their sources, verified, and kept on GitHub.

    python -m helix10.field fetch --out runs/field              # from EinsteinArena's API and the authors' repos
    python -m helix10.field store --dir runs/field               # into the repo: data/field_ac2 (13 MB, gzipped)
    python -m helix10.field get --out runs/field                 # from the repo (what a job does)

Every construction is verified when fetched and again when read back: re-scored with the problem's own scorer, it must
match the score listed in sota.py to 1e-9 (the arena's verifier and ours agree to 12 digits). A file that fails is
refused, never used. data/field_ac2 holds one gzipped .npy per construction and a manifest with the source, score and
SHA-256 of each, so a copy is checked byte for byte. (`upload`/`--release` keep them as a GitHub release instead.)

These constructions are public (EinsteinArena publishes every solution; Jaech & Joseph released theirs). Each keeps
its author's name, date and source in the manifest, and every use of them in this project credits them.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

from helix10.sota import API, IMPORTS

TAG = "field-ac2"
REPO_DIR = Path(__file__).resolve().parent.parent / "data" / "field_ac2"
TOL = 1e-9


def score(h):
    from helix4.problems.ac2 import score as s
    a = np.maximum(np.asarray(h, dtype=float), 0.0)
    return s(a / a.max())


def _get(url, timeout=600):
    req = urllib.request.Request(url, headers={"User-Agent": "helix-evolve/1.0 (research; github.com/cybercryptixcoder)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def arena_solutions(limit=60):
    raw = _get(f"{API}/solutions/best?problem_id=3&limit={limit}")
    rows = json.loads(raw)
    rows = rows.get("solutions", rows) if isinstance(rows, dict) else rows
    return {int(r["id"]): r for r in rows}


def values_of(row):
    d = row.get("data")
    if isinstance(d, str):
        d = json.loads(d)
    v = d.get("values") if isinstance(d, dict) else d
    return np.asarray(v, dtype=float)


def check(key, arr, log=print):
    """(ok, score): arr must be a finite non-negative array matching the listed score of import `key`."""
    item = next(x for x in IMPORTS if x["key"] == key)
    if arr.ndim != 1 or arr.size != item["n"] or not np.all(np.isfinite(arr)) or arr.min() < -1e-6:
        log(f"field: {key} refused: shape {arr.shape} (expected {item['n']} steps), or not finite and non-negative")
        return False, None
    s = score(arr)
    if abs(s - item["score"]) > TOL:
        log(f"field: {key} refused: scores {s:.12f}, listed {item['score']:.12f}")
        return False, s
    return True, s


def fetch(out, keys=None, log=print):
    """Downloads the imports from their sources into `out` (<key>.npy), each verified. Returns {key: score}."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = None
    got = {}
    for item in IMPORTS:
        if keys and item["key"] not in keys:
            continue
        f = out / f"{item['key']}.npy"
        if f.exists():
            ok, s = check(item["key"], np.load(f), log)
            if ok:
                got[item["key"]] = s
                continue
        try:
            if item.get("arena_id") is not None:
                rows = rows or arena_solutions()
                if item["arena_id"] not in rows:
                    log(f"field: {item['key']} is no longer among the arena's listed solutions")
                    continue
                arr = values_of(rows[item["arena_id"]])
            else:
                arr = np.asarray(json.loads(_get(item["url"])), dtype=float)
        except Exception as exc:                                        # noqa: BLE001
            log(f"field: {item['key']}: download failed ({type(exc).__name__}: {str(exc)[:160]})")
            continue
        arr = np.maximum(arr, 0.0)
        ok, s = check(item["key"], arr, log)
        if ok:
            np.save(f, arr)
            got[item["key"]] = s
            log(f"field: {item['key']} ({item['who']}, n = {item['n']:,}): {s:.12f}, verified")
    return got


def manifest(folder):
    folder = Path(folder)
    rows = {}
    for item in IMPORTS:
        f = folder / f"{item['key']}.npy"
        if f.exists():
            rows[item["key"]] = {k: item.get(k) for k in ("who", "date", "score", "n", "family", "how", "arena_id", "url")}
    return rows


def upload(folder, tag=TAG, log=print):
    from helix9.vault import GitHub
    gh = GitHub()
    folder = Path(folder)
    rel = gh.release(tag, create=True, note="The field's constructions for the second autocorrelation inequality "
                                            "(helix10/sota.py, IMPORTS): public solutions from EinsteinArena and the "
                                            "authors' repositories, each verified; credited in the manifest.")
    have = {a["name"]: a for a in rel.get("assets", [])}
    man = {"tag": tag, "constructions": manifest(folder), "sha256": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for key in man["constructions"]:
            arr = np.load(folder / f"{key}.npy")
            ok, s = check(key, arr, log)
            if not ok:
                raise SystemExit(f"field: {key} fails verification; nothing uploaded for it")
            buf = io.BytesIO()
            np.save(buf, arr)
            gz = Path(tmp) / f"{key}.npy.gz"
            gz.write_bytes(gzip.compress(buf.getvalue(), 6, mtime=0))
            man["sha256"][key] = hashlib.sha256(gz.read_bytes()).hexdigest()
            if gz.name in have:
                gh.delete_asset(have[gz.name]["id"])
            gh.upload(rel, gz, gz.name)
            log(f"field: uploaded {key} ({gz.stat().st_size / 1e6:.1f} MB)")
        mf = Path(tmp) / "manifest.json"
        mf.write_text(json.dumps(man, indent=1))
        if "manifest.json" in have:
            gh.delete_asset(have["manifest.json"]["id"])
        gh.upload(rel, mf, "manifest.json")
    log(f"field: release {tag}: {len(man['sha256'])} constructions")
    return man


def store(folder, dest=REPO_DIR, log=print):
    """The verified constructions of `folder` into the repo folder `dest` (gzipped, with a manifest)."""
    folder, dest = Path(folder), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    man = {"what": "The field's constructions for the second autocorrelation inequality (helix10/sota.py, IMPORTS): "
                   "public solutions from EinsteinArena and the authors' repositories, each verified; credited here.",
           "constructions": manifest(folder), "sha256": {}}
    for key in man["constructions"]:
        arr = np.load(folder / f"{key}.npy")
        ok, s = check(key, arr, log)
        if not ok:
            raise SystemExit(f"field: {key} fails verification; not stored")
        buf = io.BytesIO()
        np.save(buf, arr)
        raw = gzip.compress(buf.getvalue(), 9, mtime=0)
        (dest / f"{key}.npy.gz").write_bytes(raw)
        man["sha256"][key] = hashlib.sha256(raw).hexdigest()
    (dest / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    log(f"field: {len(man['sha256'])} constructions stored in {dest}")
    return man


def get(out, src=REPO_DIR, log=print):
    """The constructions of the repo folder `src` into `out` (<key>.npy), each checked by SHA-256 and re-scored."""
    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads((src / "manifest.json").read_text())
    got = {}
    for key, sha in man["sha256"].items():
        f = out / f"{key}.npy"
        if f.exists():
            ok, s = check(key, np.load(f), log)
            if ok:
                got[key] = s
                continue
        raw = (src / f"{key}.npy.gz").read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            log(f"field: {key} refused: its SHA-256 doesn't match the manifest")
            continue
        arr = np.load(io.BytesIO(gzip.decompress(raw)), allow_pickle=False)
        ok, s = check(key, arr, log)
        if ok:
            np.save(f, arr)
            got[key] = s
    log(f"field: {len(got)} of {len(man['sha256'])} constructions at hand in {out}, each verified")
    return got


def get_release(out, tag=TAG, log=print):
    """The release's constructions into `out` (<key>.npy), each checked by SHA-256 and re-scored. {key: score}."""
    from helix9.vault import GitHub
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    got = {}
    pending = [x["key"] for x in IMPORTS if not (out / f"{x['key']}.npy").exists()]
    for key in [x["key"] for x in IMPORTS if x["key"] not in pending]:
        ok, s = check(key, np.load(out / f"{key}.npy"), log)
        if ok:
            got[key] = s
        else:
            pending.append(key)
    if not pending:
        return got
    gh = GitHub()
    rel = gh.release(tag)
    if rel is None:
        raise SystemExit(f"field: release {tag} not found")
    assets = {a["name"]: a for a in rel.get("assets", [])}
    with tempfile.TemporaryDirectory() as tmp:
        gh.download(assets["manifest.json"], Path(tmp) / "manifest.json")
        man = json.loads((Path(tmp) / "manifest.json").read_text())
        for key in pending:
            name = f"{key}.npy.gz"
            if name not in assets or key not in man["sha256"]:
                log(f"field: {key} is not in release {tag}")
                continue
            gh.download(assets[name], Path(tmp) / name)
            raw = (Path(tmp) / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != man["sha256"][key]:
                log(f"field: {key} refused: its SHA-256 doesn't match the manifest")
                continue
            arr = np.load(io.BytesIO(gzip.decompress(raw)), allow_pickle=False)
            ok, s = check(key, arr, log)
            if ok:
                np.save(out / f"{key}.npy", arr)
                got[key] = s
    log(f"field: {len(got)} of {len(IMPORTS)} constructions at hand in {out}, each verified")
    return got


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out", required=True)
    st = sub.add_parser("store")
    st.add_argument("--dir", required=True)
    u = sub.add_parser("upload")
    u.add_argument("--dir", required=True)
    u.add_argument("--tag", default=TAG)
    g = sub.add_parser("get")
    g.add_argument("--out", required=True)
    g.add_argument("--release", default=None, help="read from this GitHub release instead of data/field_ac2")
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        got = fetch(a.out)
        print(f"field: {len(got)} of {len(IMPORTS)} fetched and verified")
    elif a.cmd == "store":
        store(a.dir)
    elif a.cmd == "upload":
        upload(a.dir, a.tag)
    else:
        got = get_release(a.out, a.release) if a.release else get(a.out)
        if not got:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
