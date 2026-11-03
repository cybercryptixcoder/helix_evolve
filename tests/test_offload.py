"""tools/offload.py with GitHub replaced by a folder: exact restore, resume, change detection, the secret scan."""
import gzip
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

TOOL = Path(__file__).resolve().parent.parent / "tools" / "offload.py"


def run(args, cwd, env):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=cwd, env=env, capture_output=True, text=True)


def setup(tmp_path):
    co = tmp_path / "co"
    d = co / "runs" / "v9" / "r1"
    (d / "constructions").mkdir(parents=True)
    (d / "empty").mkdir()
    for i in range(12):
        np.save(d / "constructions" / f"p{i:04d}.npy", np.random.default_rng(i).random(20000))
    (d / "state.json").write_text('{"gens_done": 3}')
    with gzip.open(d / "trace.jsonl.gz", "wt") as f:
        f.write("a call\n" * 500)
    os.symlink("constructions/p0001.npy", d / "best.npy")
    (co / ".env").write_text("LUMINAL_API_KEYS=sk-aaaaaaaaaaaaaaaa1111,sk-bbbbbbbbbbbbbbbb2222\n")
    subprocess.run(["git", "init", "-q"], cwd=co, check=True)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/x/y.git"], cwd=co, check=True)
    env = dict(os.environ, OFFLOAD_FAKE_DIR=str(tmp_path / "gh"), OFFLOAD_PART_MB="0.5",
               OFFLOAD_TMP=str(co / "runs" / ".offload_tmp"))
    return co, env


def test_roundtrip_resume_change_and_scan(tmp_path):
    co, env = setup(tmp_path)
    r = run(["archive", "--unit", "runs-v9", "--src", "runs/v9"], co, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert '"status": "verified"' in r.stdout
    out = tmp_path / "restored"
    r = run(["restore", "--unit", "runs-v9", "--out", str(out), "--repo", "x/y"], co, env)
    assert r.returncode == 0 and "every file matches" in r.stdout
    assert subprocess.run(["diff", "-r", "--no-dereference", str(co / "runs" / "v9"), str(out / "v9")]).returncode == 0
    assert os.readlink(out / "v9" / "r1" / "best.npy") == "constructions/p0001.npy"
    # a rerun sends nothing new
    r = run(["archive", "--unit", "runs-v9", "--src", "runs/v9"], co, env)
    assert "uploaded" not in r.stdout.replace('"status": "verified"', "")
    # a same-size change is caught
    a = np.load(co / "runs/v9/r1/constructions/p0011.npy")
    a[0] += 1
    np.save(co / "runs/v9/r1/constructions/p0011.npy", a)
    r = run(["archive", "--unit", "runs-v9", "--src", "runs/v9"], co, env)
    assert "uploaded" in r.stdout
    out2 = tmp_path / "restored2"
    assert run(["restore", "--unit", "runs-v9", "--out", str(out2), "--repo", "x/y"], co, env).returncode == 0
    assert np.load(out2 / "v9/r1/constructions/p0011.npy")[0] == a[0]
    # a key inside a gzip file blocks the unit
    leak = co / "runs" / "leak"
    leak.mkdir()
    with gzip.open(leak / "t.jsonl.gz", "wt") as f:
        f.write("key sk-bbbbbbbbbbbbbbbb2222\n")
    r = run(["archive", "--unit", "runs-leak", "--src", "runs/leak"], co, env)
    assert r.returncode == 1 and "blocked" in r.stdout
    assert not (tmp_path / "gh" / "x__y" / "archive-runs-leak").exists()
