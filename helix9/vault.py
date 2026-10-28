"""Every construction of a run, kept on GitHub as release files, so a continuation can rely on GitHub alone.

    python -m helix9.vault upload --run results/v8warm/v8-s1 --folder runs/v8warm/v8-s1/constructions --tag constructions-v8-s1
    python -m helix9.vault download --tag constructions-v8-s1 --out runs/vault/v8-s1

The git repo carries the run's records and a small continuation pack (helix9/pack.py); the constructions themselves
(about 0.8 MB each, thousands per run) would bloat the repo's history, so they go to a GitHub Release instead: files
of at most CHUNK_MB (losslessly compressed float64 arrays) and a manifest with every array's SHA-256. Upload verifies
each construction against the run's recorded score first (only verified ones are kept) and is resumable (files already
on the release are skipped); download checks every SHA-256.

GitHub access: the `gh` command if it is installed and logged in, else the REST API with a token from GH_TOKEN /
GITHUB_TOKEN or from git's credential helper (the one `git push` uses).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from helix9.pack import jl, problem_module, sha, verify

CHUNK_MB = float(os.environ.get("VAULT_CHUNK_MB", "400"))


# ---------------------------------------------------------------------------------------------- GitHub
def repo_slug():
    url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
    path = url.split("github.com", 1)[-1].lstrip(":/")
    return path[:-4] if path.endswith(".git") else path


def token():
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
    if "@github.com" in url and "://" in url:                  # https://user:token@github.com/...
        cred = url.split("://", 1)[1].split("@", 1)[0]
        if ":" in cred:
            return urllib.parse.unquote(cred.split(":", 1)[1])
    try:
        out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                             capture_output=True, text=True, timeout=20).stdout
        for line in out.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1]
    except Exception:                                            # noqa: BLE001
        pass
    return None


class GitHub:
    def __init__(self, slug=None):
        self.slug = slug or repo_slug()
        self.gh = shutil.which("gh") and subprocess.run(["gh", "api", f"repos/{self.slug}", "--jq", ".id"],
                                                        capture_output=True, text=True).returncode == 0
        self.tok = None if self.gh else token()

    def api(self, method, url, data=None, ctype="application/json", path=None):
        if self.gh:
            cmd = ["gh", "api", "--method", method, url]
            if path is not None:
                cmd += ["-H", f"Content-Type: {ctype}", "--input", str(path)]
            elif data is not None:
                cmd += ["--input", "-"]
            r = subprocess.run(cmd, input=json.dumps(data) if data is not None and path is None else None,
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"gh api {method} {url}: {(r.stderr or r.stdout)[:300]}")
            return json.loads(r.stdout) if r.stdout.strip() else None
        if not self.tok:
            raise RuntimeError("no GitHub access: install and log in `gh`, or set GH_TOKEN")
        full = url if url.startswith("http") else f"https://api.github.com/{url}"
        body = open(path, "rb") if path is not None else (json.dumps(data).encode() if data is not None else None)
        req = urllib.request.Request(full, data=body, method=method, headers={
            "Authorization": f"Bearer {self.tok}", "Accept": "application/vnd.github+json", "Content-Type": ctype})
        if path is not None:
            req.add_header("Content-Length", str(Path(path).stat().st_size))
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                raw = r.read()
            return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {full}: {e.code} {e.read()[:300]!r}") from None
        finally:
            if hasattr(body, "close"):
                body.close()

    def release(self, tag, create=False, note=""):
        try:
            if self.gh or self.tok:
                return self.api("GET", f"repos/{self.slug}/releases/tags/{tag}")
            with urllib.request.urlopen(f"https://api.github.com/repos/{self.slug}/releases/tags/{tag}",
                                        timeout=60) as r:              # public: readable without a token
                return json.loads(r.read())
        except (RuntimeError, urllib.error.HTTPError):
            if not create:
                return None
        return self.api("POST", f"repos/{self.slug}/releases",
                        {"tag_name": tag, "name": tag, "body": note, "prerelease": True})

    def upload(self, rel, path, name):
        url = (rel["upload_url"].split("{")[0] + "?name=" + urllib.parse.quote(name))
        return self.api("POST", url, ctype="application/octet-stream", path=path)

    def delete_asset(self, asset_id):
        self.api("DELETE", f"repos/{self.slug}/releases/assets/{asset_id}")

    def download(self, asset, dest):
        if self.gh:
            r = subprocess.run(["gh", "api", "-H", "Accept: application/octet-stream",
                                f"repos/{self.slug}/releases/assets/{asset['id']}"], capture_output=True)
            if r.returncode != 0:
                raise RuntimeError(f"download {asset['name']}: {r.stderr[:300]!r}")
            Path(dest).write_bytes(r.stdout)
            return
        # a public repo's release files download without a token
        req = urllib.request.Request(asset["browser_download_url"]) if not self.tok else urllib.request.Request(
            asset["url"], headers={"Accept": "application/octet-stream", "Authorization": f"Bearer {self.tok}"})
        with urllib.request.urlopen(req, timeout=1800) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)


# ---------------------------------------------------------------------------------------------- upload / download
def manifest_of(tag, gh):
    """The manifest of release `tag`, or None."""
    rel = gh.release(tag)
    assets = {a["name"]: a for a in (rel or {}).get("assets", [])}
    if "manifest.json" not in assets:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="vault-", dir=os.environ.get("VAULT_TMP") or None))
    try:
        gh.download(assets["manifest.json"], tmp / "manifest.json")
        return json.loads((tmp / "manifest.json").read_text())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def held_by(tags, gh):
    """{program id: tag} for every construction the releases `tags` (and their own bases) hold."""
    held = {}
    for tag in tags or []:
        man = manifest_of(tag, gh)
        if man is None:
            raise RuntimeError(f"base release {tag} is missing or incomplete")
        held.update(held_by(man.get("base"), gh))
        held.update({pid: tag for pid in man["sha256"]})
    return held


def upload(run, folders, tag, log=print, gh=None, base=None):
    """Every verified construction of the run's programs into release `tag`, except those the releases `base` already
    hold (a download of `tag` restores those too). Returns the manifest."""
    run = Path(run)
    gh = gh or GitHub()
    base = [b for b in (base or []) if b and b != tag]
    held = held_by(base, gh)
    rel = gh.release(tag, create=True, note=f"Every verified construction of {run.name} (helix9/vault.py).")
    have = {a["name"]: a for a in rel.get("assets", [])}
    if "manifest.json" in have:
        log(f"vault: {tag} is complete already ({len(have) - 1} files)")
        return None
    state = json.loads((run / "state.json").read_text()) if (run / "state.json").exists() else {}
    prob = problem_module((state.get("config") or {}).get("problem") or "ac2", state.get("config"))
    progs = [p for p in jl(run / "programs.jsonl") if p.get("valid") and p.get("score") is not None]
    folders = [Path(f) for f in folders if f and Path(f).is_dir()]
    found, rejected, missing = {}, 0, 0
    for p in progs:
        if p["id"] in held:
            continue
        seen = False
        for f in folders:
            c = f / f"{p['id']}.npy"
            if c.exists():
                seen = True
                try:
                    arr = np.load(c)
                except Exception:                                # noqa: BLE001
                    continue
                if verify(prob, arr, p)[0]:
                    found[p["id"]] = c
                    break
        if p["id"] not in found:
            if seen:
                rejected += 1
            else:
                missing += 1
    ids = sorted(found, key=lambda pid: int(pid[1:]) if pid[1:].isdigit() else 0)
    manifest = {"run": run.name, "tag": tag, "programs": len(progs), "verified": len(ids), "rejected": rejected,
                "missing": missing, "base": base, "in_base": sum(p["id"] in held for p in progs),
                "files": {}, "sha256": {}}
    tmp = Path(tempfile.mkdtemp(prefix="vault-", dir=os.environ.get("VAULT_TMP") or None))
    try:
        part, chunk, size = 0, {}, 0

        def flush():
            nonlocal part, chunk, size
            if not chunk:
                return
            part += 1
            name = f"constructions-{part:03d}.npz"
            manifest["files"][name] = sorted(chunk)
            if name not in have:
                path = tmp / name
                np.savez_compressed(path, **chunk)
                gh.upload(rel, path, name)
                path.unlink()
                log(f"vault: uploaded {name} ({len(chunk)} constructions)")
            chunk, size = {}, 0
        for pid in ids:
            arr = np.asarray(np.load(found[pid]), dtype=float)
            manifest["sha256"][pid] = sha(arr)
            chunk[pid] = arr
            size += arr.nbytes * 0.5                             # compresses to about half
            if size >= CHUNK_MB * 1e6:
                flush()
        flush()
        mpath = tmp / "manifest.json"
        mpath.write_text(json.dumps(manifest))
        gh.upload(rel, mpath, "manifest.json")                  # last: its presence means the upload is complete
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log(f"vault: {tag}: {len(ids)} of {len(progs)} constructions verified and uploaded in {part} files "
        f"({manifest['in_base']} held by {', '.join(base) or 'no base'}, {rejected} failed the check, {missing} not found)")
    return manifest


def download(tag, out, log=print, gh=None, _seen=None):
    """Restores release `tag`, and first the releases it names as its base, into folder `out` (each array checked
    against its SHA-256). Returns the count."""
    gh = gh or GitHub()
    _seen = _seen if _seen is not None else set()
    if tag in _seen:
        return 0
    _seen.add(tag)
    rel = gh.release(tag)
    if rel is None:
        raise SystemExit(f"vault: no release {tag}")
    assets = {a["name"]: a for a in rel.get("assets", [])}
    if "manifest.json" not in assets:
        raise SystemExit(f"vault: {tag} is incomplete (no manifest.json)")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vault-", dir=os.environ.get("VAULT_TMP") or None))
    try:
        gh.download(assets["manifest.json"], tmp / "manifest.json")
        man = json.loads((tmp / "manifest.json").read_text())
        n, bad = 0, []
        for b in man.get("base") or []:
            n += download(b, out, log=log, gh=gh, _seen=_seen)
        for name, pids in man["files"].items():
            if all((out / f"{pid}.npy").exists() for pid in pids):
                n += len(pids)
                continue
            gh.download(assets[name], tmp / name)
            with np.load(tmp / name) as z:
                for pid in z.files:
                    arr = z[pid]
                    if man["sha256"].get(pid) != sha(arr):
                        bad.append(pid)
                        continue
                    np.save(out / f"{pid}.npy", arr)
                    n += 1
            (tmp / name).unlink()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        raise SystemExit(f"vault: {len(bad)} constructions failed their SHA-256 check")
    log(f"vault: restored {n} constructions from {tag} into {out}")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("upload")
    u.add_argument("--run", required=True)
    u.add_argument("--folder", required=True, help="comma-separated folders of <id>.npy constructions")
    u.add_argument("--tag", required=True)
    u.add_argument("--base", default="", help="comma-separated releases already holding part of the run")
    d = sub.add_parser("download")
    d.add_argument("--tag", required=True)
    d.add_argument("--out", required=True)
    e = sub.add_parser("exists")
    e.add_argument("--tag", required=True)
    a = ap.parse_args(argv)
    try:
        return _main(a)
    except (RuntimeError, OSError, urllib.error.URLError) as exc:
        print(f"vault: failed: {str(exc)[:300]}", flush=True)
        return 1


def _main(a):
    if a.cmd == "upload":
        upload(a.run, a.folder.split(","), a.tag, base=[b for b in a.base.split(",") if b])
    elif a.cmd == "download":
        download(a.tag, a.out)
    else:
        rel = GitHub().release(a.tag)
        ok = rel is not None and any(x["name"] == "manifest.json" for x in rel.get("assets", []))
        print("complete" if ok else "missing")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
