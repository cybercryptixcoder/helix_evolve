"""Offload everything Helix keeps on the VM to GitHub, losslessly, so the VM can be cleared (docs/OFFLOAD.md).

Every unit (one folder under runs/, the checkout's untracked files, a private folder) becomes one GitHub release
`archive-<unit>` holding:
    <unit>.tar.gz.000, .001, ...   a byte-for-byte tar of the folder (gzip, split into parts under GitHub's 2 GiB limit)
    <unit>.files.jsonl.gz          every file: path, size, mode, mtime, SHA-256 (the proof that a restore is exact)
    <unit>.parts.json              every part's size and SHA-256, and the unit's totals (written last: a unit is complete
                                   only when its parts.json is there and every part matches it)

The tar is deterministic (sorted names, fixed gzip header), so running again after any stop rebuilds identical parts and
skips the ones GitHub already holds with the same SHA-256. Nothing is ever deleted on the VM.

    python3 tools/offload.py inventory --out DIR            # read-only: what is on this machine, what GitHub has
    python3 tools/offload.py archive --unit NAME --src DIR [--src DIR ...] [--repo owner/name] [--exclude REL ...]
    python3 tools/offload.py verify --unit NAME [--repo owner/name]
    python3 tools/offload.py restore --unit NAME --out DIR [--repo owner/name]   # anyone, anywhere: exact restore

Before a unit is uploaded, every file in it (gzip files decompressed) is scanned for the values of the keys in .env and
the lines of .offload_forbid (gitignored); a unit with a hit is not uploaded, and the report names the files.

OFFLOAD_FAKE_DIR=<dir> replaces GitHub with a local folder (tests).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PART_BYTES = int(float(os.environ.get("OFFLOAD_PART_MB", "1900")) * 1024 * 1024)
LEVEL = int(os.environ.get("OFFLOAD_GZIP_LEVEL", "3"))
TMP = Path(os.environ.get("OFFLOAD_TMP", "runs/.offload_tmp"))
SKIP_NAMES = {"__pycache__", ".offload_tmp"} | (set() if os.environ.get("OFFLOAD_KEEP_GIT") == "1" else {".git"})


def secret_file(name):
    """Key files never go into an archive (.env and .env.*, except an example file)."""
    return (name == ".env" or name.startswith(".env.") or name.endswith(".env")) and "example" not in name
SKIP_SUFFIX = (".pyc",)


def now():
    return time.strftime("%H:%M", time.gmtime())


def say(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------------------------- where files go
class GitHub:
    """GitHub releases through the REST API (uploads stream from disk; no gh, so nothing is held in memory)."""

    def __init__(self, slug):
        self.slug = slug
        self.tok = self._token()

    @staticmethod
    def _token():
        for k in ("GH_TOKEN", "GITHUB_TOKEN"):
            if os.environ.get(k):
                return os.environ[k]
        if shutil.which("gh"):
            r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        try:
            out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                                 capture_output=True, text=True, timeout=20).stdout
            for line in out.splitlines():
                if line.startswith("password="):
                    return line.split("=", 1)[1]
        except Exception:                                            # noqa: BLE001
            pass
        return None

    def _req(self, method, url, body=None, ctype="application/json", length=None, accept="application/vnd.github+json"):
        full = url if url.startswith("http") else f"https://api.github.com/{url}"
        headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
        if self.tok:
            headers["Authorization"] = f"Bearer {self.tok}"
        if body is not None:
            headers["Content-Type"] = ctype
        if length is not None:
            headers["Content-Length"] = str(length)
        data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
        req = urllib.request.Request(full, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                raw = r.read()
            return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise RuntimeError(f"{method} {full.split('?')[0]}: {e.code} {e.read()[:300]!r}") from None

    def repo(self):
        return self._req("GET", f"repos/{self.slug}")

    def release(self, tag, create=False, note=""):
        rel = self._req("GET", f"repos/{self.slug}/releases/tags/{urllib.parse.quote(tag)}")
        if rel is None and create:
            body = {"tag_name": tag, "name": tag, "body": note, "prerelease": True}
            try:
                rel = self._req("POST", f"repos/{self.slug}/releases", body)
            except RuntimeError as e:
                if "Repository is empty" not in str(e):
                    raise
                # GitHub can't hold a release in a repo with no commit: give it one (a README), then retry
                import base64
                text = (f"# {self.slug.split('/')[-1]}\n\nArchives only: each release `archive-<unit>` is a byte-for-byte "
                        "copy of a folder, restored with `python3 tools/offload.py restore` (helix_evolve, "
                        "docs/OFFLOAD.md).\n")
                self._req("PUT", f"repos/{self.slug}/contents/README.md",
                          {"message": "Archives only (see README)", "content": base64.b64encode(text.encode()).decode()})
                rel = self._req("POST", f"repos/{self.slug}/releases", body)
        return rel

    def assets(self, rel):
        out, page = [], 1
        while True:
            got = self._req("GET", f"repos/{self.slug}/releases/{rel['id']}/assets?per_page=100&page={page}") or []
            out += got
            if len(got) < 100:
                return {a["name"]: a for a in out}
            page += 1

    def upload(self, rel, path, name):
        url = rel["upload_url"].split("{")[0] + "?name=" + urllib.parse.quote(name)
        size = Path(path).stat().st_size
        with open(path, "rb") as f:
            return self._req("POST", url, body=f, ctype="application/octet-stream", length=size)

    def delete(self, asset):
        self._req("DELETE", f"repos/{self.slug}/releases/assets/{asset['id']}")

    def open(self, asset):
        if self.tok:
            req = urllib.request.Request(asset["url"], headers={"Accept": "application/octet-stream",
                                                                "Authorization": f"Bearer {self.tok}"})
        else:
            req = urllib.request.Request(asset["browser_download_url"])
        return urllib.request.urlopen(req, timeout=3600)


class FakeGitHub:
    """A local folder standing in for GitHub releases (tests)."""

    def __init__(self, slug, root):
        self.slug, self.root = slug, Path(root) / slug.replace("/", "__")
        self.root.mkdir(parents=True, exist_ok=True)

    def repo(self):
        return {"private": os.environ.get("OFFLOAD_FAKE_PRIVATE", "0") == "1", "full_name": self.slug}

    def release(self, tag, create=False, note=""):
        d = self.root / tag
        if not d.exists():
            if not create:
                return None
            d.mkdir(parents=True)
            (d / ".note").write_text(note)
        return {"id": tag, "tag_name": tag, "dir": str(d)}

    def assets(self, rel):
        d = Path(rel["dir"])
        out = {}
        for p in sorted(d.iterdir()):
            if p.name.startswith("."):
                continue
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            out[p.name] = {"name": p.name, "size": p.stat().st_size, "digest": f"sha256:{h}", "state": "uploaded",
                           "path": str(p), "id": str(p)}
        return out

    def upload(self, rel, path, name):
        if os.environ.get("OFFLOAD_FAKE_FAIL_AT") == name:
            raise RuntimeError(f"fake upload failure at {name}")
        shutil.copyfile(path, Path(rel["dir"]) / name)

    def delete(self, asset):
        Path(asset["path"]).unlink()

    def open(self, asset):
        return open(asset["path"], "rb")


def hub(slug):
    fake = os.environ.get("OFFLOAD_FAKE_DIR")
    return FakeGitHub(slug, fake) if fake else GitHub(slug)


def origin_slug():
    import re
    url = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True).stdout.strip()
    m = re.findall(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{m[-1][0]}/{m[-1][1]}" if m else url


# ---------------------------------------------------------------------------------------------- the files of a unit
def walk(srcs, excludes=()):
    """[(archive name, absolute path)] for every file, dir and link under the sources, sorted, minus the excluded."""
    out = []
    excl = {os.path.abspath(e) for e in excludes}
    for src in srcs:
        src = Path(os.path.abspath(src))
        base = src.parent
        for root, dirs, files in os.walk(src, followlinks=False):
            r = Path(root)
            links = [d for d in dirs if (r / d).is_symlink()]
            dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES and d not in links and str(r / d) not in excl)
            out.append((str(r.relative_to(base)), r))
            for f in sorted(files) + sorted(links):
                p = r / f
                if f.endswith(SKIP_SUFFIX) or secret_file(f) or str(p) in excl:
                    continue
                out.append((str(p.relative_to(base)), p))
    return sorted(set(out), key=lambda x: x[0])


def forbidden_strings(checkout="."):
    """Key values from .env and the lines of .offload_forbid: none of these may leave the machine."""
    out = set()
    env = Path(checkout) / ".env"
    if env.exists():
        for line in env.read_text(errors="replace").splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip("'\"")
            if any(w in k.upper() for w in ("KEY", "TOKEN", "SECRET", "PASS")):
                for piece in v.replace(";", ",").split(","):
                    piece = piece.strip()
                    if len(piece) >= 12:
                        out.add(piece)
    forbid = Path(checkout) / ".offload_forbid"
    if forbid.exists():
        out |= {l.strip() for l in forbid.read_text(errors="replace").splitlines() if len(l.strip()) >= 3}
    return sorted(out)


def scan(entries, strings):
    """Files under the unit that contain any forbidden string (gzip files are read decompressed)."""
    if not strings:
        return []
    pats = [s.encode() for s in strings] + [s.lower().encode() for s in strings if s.isalpha()]
    keep = max(len(p) for p in pats)
    hits = []
    for name, p in entries:
        if p.is_symlink() or not p.is_file():
            continue
        try:
            raw = open(p, "rb")
            f = gzip.open(raw) if p.name.endswith(".gz") else raw
            tail = b""
            while True:
                try:
                    chunk = f.read(8 << 20)
                except (OSError, EOFError):
                    break
                if not chunk:
                    break
                buf = tail + chunk
                low = buf.lower()
                if any(pat in buf or pat in low for pat in pats):
                    hits.append(name)
                    break
                tail = buf[-keep:]
            raw.close()
        except OSError:
            continue
    return hits


# ---------------------------------------------------------------------------------------------- writing the parts
class HashReader:
    def __init__(self, f):
        self.f, self.h, self.n = f, hashlib.sha256(), 0

    def read(self, n=-1):
        b = self.f.read(n)
        self.h.update(b)
        self.n += len(b)
        return b


class Parts:
    """A write-only stream cut into numbered part files; each full part is handed to `done(index, path, sha, size)`."""

    def __init__(self, unit, done):
        self.unit, self.done, self.i = unit, done, 0
        TMP.mkdir(parents=True, exist_ok=True)
        self._open()

    def _open(self):
        self.path = TMP / f"{self.unit}.tar.gz.{self.i:03d}"
        self.f, self.h, self.size = open(self.path, "wb"), hashlib.sha256(), 0

    def _finish(self):
        self.f.close()
        self.done(self.i, self.path, self.h.hexdigest(), self.size)
        if self.path.exists():
            self.path.unlink()

    def write(self, b):
        total = len(b)
        b = memoryview(b).cast("B")
        while len(b):
            room = PART_BYTES - self.size
            piece = b[:room]
            self.f.write(piece)
            self.h.update(piece)
            self.size += len(piece)
            b = b[len(piece):]
            if self.size >= PART_BYTES:
                self._finish()
                self.i += 1
                self._open()
        return total

    def flush(self):
        pass

    def close(self):
        if self.size or self.i == 0:
            self._finish()
        else:
            self.f.close()
            self.path.unlink()


def put(gh, rel, have, path, name, sha, size):
    """Upload one file unless GitHub already holds it with the same SHA-256; returns 'kept' or 'uploaded'."""
    a = have.get(name)
    if a is not None:
        if a.get("state", "uploaded") == "uploaded" and a.get("size") == size:
            if a.get("digest") == f"sha256:{sha}" or (not a.get("digest") and same_bytes(gh, a, sha)):
                return "kept"
        gh.delete(a)
    err = None
    for i in range(4):
        try:
            gh.upload(rel, path, name)
            err = None
            break
        except Exception as e:                                       # noqa: BLE001
            err = e
            stale = gh.assets(rel).get(name)
            if stale is not None:
                gh.delete(stale)
            time.sleep(10 * (i + 1))
    if err is not None:
        raise RuntimeError(f"upload of {name} failed 4 times: {err}")
    return "uploaded"


def same_bytes(gh, asset, sha):
    h = hashlib.sha256()
    with gh.open(asset) as r:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest() == sha


def archive(unit, srcs, slug, excludes=(), note="", checkout=".", files_from=None):
    srcs = [Path(s) for s in srcs if Path(s).exists()]
    loose = []
    if files_from:
        for line in Path(files_from).read_text().splitlines():
            p = Path(line.strip())
            if line.strip() and (p.is_file() or p.is_symlink()) and not p.name.endswith(SKIP_SUFFIX) and not secret_file(p.name):
                loose.append((line.strip().lstrip("/"), Path(os.path.abspath(p))))
    if not srcs and not loose:
        say(f"== {unit}: nothing to archive (no such folder)")
        return {"unit": unit, "status": "empty"}
    entries = sorted(set(walk(srcs, excludes) + loose), key=lambda x: x[0])
    if not srcs:
        srcs = [Path(files_from)]
    files = [(n, p) for n, p in entries if p.is_file() and not p.is_symlink()]
    total = sum(p.stat().st_size for _, p in files)
    say(f"== {unit}: {len(files):,} files, {total / 1e9:.2f} GB from {', '.join(str(s) for s in srcs)}")
    hits = scan(entries, forbidden_strings(checkout))
    if hits:
        say(f"   NOT uploaded: {len(hits)} files contain a key or a forbidden string: " + ", ".join(hits[:20]))
        return {"unit": unit, "status": "blocked", "blocked_files": hits}
    gh = hub(slug)
    tag = f"archive-{unit}"
    rel = gh.release(tag, create=True, note=note or f"A byte-for-byte archive of `{unit}` from the VM (tools/offload.py). "
                     f"Restore: `python3 tools/offload.py restore --unit {unit} --out <dir>`.")
    have = gh.assets(rel)
    # always rebuilt: the stream is deterministic, so parts GitHub already holds (same SHA-256) are kept, not re-sent,
    # and any file that changed since the last run is caught
    parts, t0, sent = [], time.time(), [0]

    def done(i, path, sha, size):
        name = f"{unit}.tar.gz.{i:03d}"
        how = put(gh, rel, have, path, name, sha, size)
        parts.append({"name": name, "size": size, "sha256": sha})
        sent[0] += size
        say(f"== {now()} progress: {unit} part {i + 1} {how} ({size / 1e6:.0f} MB; {sent[0] / 1e9:.2f} GB of the "
            f"compressed stream so far; {(time.time() - t0) / 60:.0f} min)")

    manifest = []
    stream = Parts(unit, done)
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=stream, compresslevel=LEVEL, mtime=0)
    with tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT) as tar:
        for name, p in entries:
            ti = tar.gettarinfo(str(p), arcname=name)
            if ti.isreg():
                with open(p, "rb") as f:
                    hr = HashReader(f)
                    tar.addfile(ti, hr)
                if hr.n != ti.size:
                    raise RuntimeError(f"{p} changed while it was archived ({hr.n} != {ti.size} bytes): run again")
                manifest.append({"path": name, "type": "file", "size": ti.size, "mode": ti.mode, "mtime": ti.mtime,
                                 "sha256": hr.h.hexdigest()})
            else:
                tar.addfile(ti)
                manifest.append({"path": name, "type": "link" if ti.issym() else "dir", "mode": ti.mode,
                                 "mtime": ti.mtime, **({"target": ti.linkname} if ti.issym() else {})})
    gz.close()
    stream.close()
    # the file manifest, then parts.json last (its presence marks the unit complete)
    TMP.mkdir(parents=True, exist_ok=True)
    fm = TMP / f"{unit}.files.jsonl.gz"
    with gzip.GzipFile(fm, "wb", mtime=0) as f:
        for row in manifest:
            f.write((json.dumps(row, sort_keys=True) + "\n").encode())
    fsha = hashlib.sha256(fm.read_bytes()).hexdigest()
    have = gh.assets(rel)
    put(gh, rel, have, fm, fm.name, fsha, fm.stat().st_size)
    stale = [n for n in have if n.startswith(f"{unit}.tar.gz.") and n not in {p["name"] for p in parts}]
    for n in stale:
        gh.delete(have[n])
    pj = TMP / f"{unit}.parts.json"
    info = {"unit": unit, "sources": [str(s.resolve()) for s in srcs], "excluded": [str(e) for e in excludes],
            "files": len(files), "bytes": total, "entries": len(manifest), "parts": parts,
            "files_manifest": {"name": fm.name, "sha256": fsha, "size": fm.stat().st_size},
            "made": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": os.uname().nodename,
            "format": "tar (PAX) | gzip, split; restore: python3 tools/offload.py restore --unit " + unit}
    pj.write_text(json.dumps(info, indent=1))
    put(gh, rel, gh.assets(rel), pj, pj.name, hashlib.sha256(pj.read_bytes()).hexdigest(), pj.stat().st_size)
    fm.unlink()
    pj.unlink()
    res = verify(unit, slug, quiet=True)
    say(f"== {unit}: {res['status']} ({len(parts)} parts, {sum(p['size'] for p in parts) / 1e9:.2f} GB compressed, "
        f"{(time.time() - t0) / 60:.0f} min)")
    return res


# ---------------------------------------------------------------------------------------------- checking and restoring
def read_asset(gh, asset):
    with gh.open(asset) as r:
        return r.read()


def verify(unit, slug, quiet=False):
    """Is the unit complete on GitHub: parts.json there, every part present with its size and SHA-256?"""
    gh = hub(slug)
    rel = gh.release(f"archive-{unit}")
    if rel is None:
        res = {"unit": unit, "status": "missing"}
        quiet or say(json.dumps(res))
        return res
    have = gh.assets(rel)
    if f"{unit}.parts.json" not in have:
        res = {"unit": unit, "status": "incomplete (no parts.json)"}
        quiet or say(json.dumps(res))
        return res
    info = json.loads(read_asset(gh, have[f"{unit}.parts.json"]))
    bad = []
    for p in info["parts"] + [info["files_manifest"]]:
        a = have.get(p["name"])
        if a is None or a.get("size") != p["size"] or a.get("state", "uploaded") != "uploaded":
            bad.append(p["name"])
        elif a.get("digest") and a["digest"] != f"sha256:{p['sha256']}":
            bad.append(p["name"])
        elif not a.get("digest") and not same_bytes(gh, a, p["sha256"]):
            bad.append(p["name"])
    res = {"unit": unit, "status": "verified" if not bad else "BAD", "bad": bad, "files": info["files"],
           "bytes": info["bytes"], "parts": len(info["parts"]),
           "compressed": sum(p["size"] for p in info["parts"]), "sources": info["sources"]}
    if not quiet:
        say(json.dumps(res))
    return res


class Concat(io.RawIOBase):
    """The parts, downloaded one after another, as one stream; each part's SHA-256 is checked as it is read."""

    def __init__(self, gh, have, parts):
        self.gh, self.have, self.parts, self.cur, self.h, self.k = gh, have, list(parts), None, None, -1

    def readable(self):
        return True

    def readinto(self, b):
        while True:
            if self.cur is None:
                self.k += 1
                if self.k >= len(self.parts):
                    return 0
                self.cur, self.h = self.gh.open(self.have[self.parts[self.k]["name"]]), hashlib.sha256()
            n = self.cur.readinto(b) if hasattr(self.cur, "readinto") else None
            if n is None:
                data = self.cur.read(len(b))
                n = len(data)
                b[:n] = data
            if n:
                self.h.update(b[:n])
                return n
            self.cur.close()
            if self.h.hexdigest() != self.parts[self.k]["sha256"]:
                raise RuntimeError(f"{self.parts[self.k]['name']}: SHA-256 mismatch")
            self.cur = None


def restore(unit, slug, out):
    gh = hub(slug)
    rel = gh.release(f"archive-{unit}")
    if rel is None:
        raise SystemExit(f"no release archive-{unit} in {slug}")
    have = gh.assets(rel)
    info = json.loads(read_asset(gh, have[f"{unit}.parts.json"]))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stream = io.BufferedReader(Concat(gh, have, info["parts"]), 1 << 20)
    with gzip.GzipFile(fileobj=stream) as gz, tarfile.open(fileobj=gz, mode="r|") as tar:
        for m in tar:
            if m.name.startswith("/") or ".." in Path(m.name).parts:
                raise RuntimeError(f"unsafe path in archive: {m.name}")
            tar.extract(m, out, set_attrs=True, **({"filter": "fully_trusted"} if sys.version_info >= (3, 12) else {}))
    man = gzip.decompress(read_asset(gh, have[info["files_manifest"]["name"]])).decode().splitlines()
    bad = 0
    for line in man:
        row = json.loads(line)
        if row["type"] != "file":
            continue
        p = out / row["path"]
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        if h.hexdigest() != row["sha256"] or p.stat().st_size != row["size"]:
            bad += 1
            say(f"   mismatch: {row['path']}")
        os.utime(p, (row["mtime"], row["mtime"]))
    say(f"== restored {unit} into {out}: {info['files']:,} files, {info['bytes'] / 1e9:.2f} GB; "
        + ("every file matches its SHA-256" if not bad else f"{bad} files DO NOT match"))
    return bad == 0


# ---------------------------------------------------------------------------------------------- inventory
def du(p):
    r = subprocess.run(["du", "-sb", str(p)], capture_output=True, text=True)
    try:
        return int(r.stdout.split()[0])
    except (IndexError, ValueError):
        return -1


def inventory(out, home, checkout="."):
    """Read-only: every folder in the home directory and in runs/, every run's state, and what GitHub has of each."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rep = {"made": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": os.uname().nodename}
    rep["df"] = subprocess.run(["df", "-B1", "/"], capture_output=True, text=True).stdout
    rep["free"] = subprocess.run(["free", "-m"], capture_output=True, text=True).stdout
    rep["home"] = sorted(({"path": str(p), "bytes": du(p), "dir": p.is_dir()} for p in Path(home).iterdir()),
                         key=lambda x: -x["bytes"])
    subprocess.run(["git", "fetch", "-q", "origin"], capture_output=True)
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout  # noqa: E731
    rep["git"] = {"head": g("rev-parse", "HEAD").strip(), "origin": g("rev-parse", "origin/main").strip(),
                  "status": g("status", "--porcelain").splitlines(),
                  "unpushed": g("log", "--oneline", "origin/main..HEAD").splitlines(),
                  "untracked_outside_runs": [l for l in g("ls-files", "-o", "--directory").splitlines()
                                             if not l.startswith("runs/")]}
    on_github = set(g("ls-tree", "-r", "--name-only", "origin/main", "results").splitlines())
    runs = []
    root = Path(checkout) / "runs"
    for st in sorted(root.rglob("state.json")) if root.exists() else []:
        d = st.parent
        if ".offload_tmp" in d.parts or "vault" in d.parts[:2]:
            continue
        try:
            s = json.loads(st.read_text())
        except Exception:                                            # noqa: BLE001
            s = {}
        sha = hashlib.sha256(st.read_bytes()).hexdigest()
        match = [p for p in on_github if p.endswith(f"/{d.name}/state.json")]
        same = False
        for p in match:
            blob = subprocess.run(["git", "show", f"origin/main:{p}"], capture_output=True).stdout
            same = same or hashlib.sha256(blob).hexdigest() == sha
        cons = d / "constructions"
        runs.append({"run": str(d.relative_to(checkout)), "bytes": du(d),
                     "gens_done": s.get("gens_done", s.get("gen")), "best": s.get("best"),
                     "results_on_github": match, "state_same_as_github": same,
                     "constructions": len(list(cons.glob("*.npy"))) if cons.is_dir() else 0})
    rep["runs"] = runs
    rep["runs_top"] = sorted(({"path": str(p), "bytes": du(p)} for p in root.iterdir()), key=lambda x: x["path"]) \
        if root.exists() else []
    rels = []
    slug = origin_slug()
    try:
        gh = hub(slug)
        page = 1
        while not isinstance(gh, FakeGitHub):
            got = gh._req("GET", f"repos/{slug}/releases?per_page=100&page={page}") or []
            rels += [{"tag": r["tag_name"], "assets": len(r["assets"]),
                      "bytes": sum(a["size"] for a in r["assets"])} for r in got]
            if len(got) < 100:
                break
            page += 1
    except Exception as e:                                           # noqa: BLE001
        rels = [{"error": str(e)[:200]}]
    rep["releases"] = rels
    rep["python"] = sys.version
    rep["pip_freeze"] = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True,
                                       text=True).stdout.splitlines()
    (out / "inventory.json").write_text(json.dumps(rep, indent=1))
    lines = [f"# VM inventory ({rep['made']})", "", "## Disk", "```", rep["df"].strip(), "```", "",
             "## Home folder (largest first)", "", "| Path | GB |", "|---|---|"]
    lines += [f"| {h['path']} | {h['bytes'] / 1e9:.2f} |" for h in rep["home"]]
    lines += ["", "## Run folders on this machine", "",
              "| Run | GB | Generations | Best | Records on GitHub | Same state as GitHub | Constructions |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['run']} | {r['bytes'] / 1e9:.2f} | {r['gens_done']} | {r['best']} | "
              f"{', '.join(r['results_on_github']) or 'none'} | {r['state_same_as_github']} | {r['constructions']} |"
              for r in runs]
    lines += ["", "## The checkout", "", f"- HEAD {rep['git']['head']}, origin/main {rep['git']['origin']}",
              f"- changed tracked files: {len(rep['git']['status'])}", f"- unpushed commits: {len(rep['git']['unpushed'])}",
              "- untracked outside runs/: " + ", ".join(rep["git"]["untracked_outside_runs"][:40]),
              "", "## Releases on GitHub", "", "| Tag | Files | GB |", "|---|---|---|"]
    lines += [f"| {r.get('tag')} | {r.get('assets')} | {r.get('bytes', 0) / 1e9:.2f} |" for r in rels]
    (out / "INVENTORY.md").write_text("\n".join(lines) + "\n")
    say(f"== inventory: {len(runs)} run folders, {len(rep['home'])} entries in {home}; written to {out}")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("archive")
    a.add_argument("--unit", required=True)
    a.add_argument("--src", action="append", default=[])
    a.add_argument("--files-from", default=None)
    a.add_argument("--exclude", action="append", default=[])
    a.add_argument("--repo")
    a.add_argument("--note", default="")
    v = sub.add_parser("verify")
    v.add_argument("--unit", required=True)
    v.add_argument("--repo")
    r = sub.add_parser("restore")
    r.add_argument("--unit", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--repo", default=None)
    q = sub.add_parser("publish-index")
    q.add_argument("--dir", required=True)
    q.add_argument("--repo")
    i = sub.add_parser("inventory")
    i.add_argument("--out", required=True)
    i.add_argument("--home", default=str(Path.home()))
    x = ap.parse_args(argv)
    slug = getattr(x, "repo", None) or (origin_slug() if x.cmd != "restore" else None) \
        or "cybercryptixcoder/helix_evolve"
    if x.cmd == "archive":
        res = archive(x.unit, x.src, slug, x.exclude, x.note, files_from=x.files_from)
        print("RESULT " + json.dumps(res), flush=True)
        return 0 if res["status"] in ("verified", "empty") else 1
    if x.cmd == "verify":
        return 0 if verify(x.unit, slug)["status"] == "verified" else 1
    if x.cmd == "restore":
        return 0 if restore(x.unit, slug, x.out) else 1
    if x.cmd == "publish-index":
        gh = hub(slug)
        rel = gh.release("archive-index", create=True, note="The offload's report: what was on the VM, every archive "
                         "release and its verification (tools/offload.py, docs/OFFLOAD.md).")
        have = gh.assets(rel)
        for name in [n for n in have if "private" in n]:   # the private units' file lists and logs stay off the public repo
            gh.delete(have.pop(name))
        for f in sorted(Path(x.dir).iterdir()):
            if f.is_file() and not f.name.startswith(".") and "private" not in f.name:
                put(gh, rel, have, f, f.name, hashlib.sha256(f.read_bytes()).hexdigest(), f.stat().st_size)
        say(f"== the report is on GitHub: release archive-index ({len(list(Path(x.dir).iterdir()))} files)")
        return 0
    inventory(x.out, x.home)
    return 0


if __name__ == "__main__":
    sys.exit(main())
