"""Keep runs alive across interruptions.

    python -m helix3.keeper              # resume every unfinished run whose process is gone, then exit
    python -m helix3.keeper --watch 300  # keep checking every 5 minutes
    python -m helix3.keeper --list       # show runs and whether they are alive
    python -m helix3.keeper --stop runs/<problem>/<run>   # stop a run for good (the keeper won't resume it)

A run writes an atomic checkpoint after every generation (checkpoint.json) and its pid in status.json. A run is
*dead* when its status says running but the pid is gone (a crash, a reboot, a closed session). The keeper restarts
it with `python -m helix3.run --resume <folder>`, detached from the terminal, logging to <folder>/resume.log; the
run continues from its last finished generation. Meta-loop runs (meta_runs/outer-*) are resumed the same way,
through scripts/run_meta.sh when they were started with it (so their results are still published at the end).
A run stopped on purpose (status stopped or failed) is left alone. Only one keeper runs at a time.

scripts/install_keeper.sh starts the keeper at login (macOS LaunchAgent, Linux crontab), so runs resume by
themselves after a restart.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def inner_runs():
    for d in sorted((ROOT / "runs").glob("*/*")):
        if (d / "checkpoint.json").exists():
            yield d


def state(d):
    try:
        st = json.loads((d / "status.json").read_text())
    except (OSError, ValueError):
        st = {}
    try:
        ck = json.loads((d / "checkpoint.json").read_text())
    except (OSError, ValueError):
        ck = {}
    done = st.get("state") == "finished" or (ck.get("target") and ck.get("gen", 0) >= ck["target"])
    return {"dir": d, "gen": ck.get("gen"), "target": ck.get("target"), "pid": st.get("pid"),
            "alive": alive(st.get("pid")), "finished": bool(done)}


def detach(cmd, log, env=None):
    with open(log, "a") as fh:
        fh.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} keeper: {' '.join(cmd)}\n")
    return subprocess.Popen(cmd, cwd=ROOT, stdout=open(log, "a"), stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True,
                            env={**os.environ, **(env or {})})


def sweep(verbose=True):
    restarted = []
    for d in inner_runs():
        s = state(d)
        if s["finished"] or s["alive"]:
            continue
        detach([sys.executable, "-m", "helix3.run", "--resume", str(d)], d / "resume.log")
        restarted.append(str(d))
    for d in sorted((ROOT / "meta_runs").glob("outer-*")):
        try:
            st = json.loads((d / "status.json").read_text())
        except (OSError, ValueError):
            continue
        if st.get("state") == "running" and not alive(st.get("pid")):
            if (d / "launch.env").exists():              # started by scripts/run_meta.sh: resume through it
                detach(["bash", str(ROOT / "scripts" / "run_meta.sh")], d / "resume.log",
                       env={"RESUME": str(d), "PYTHON": sys.executable})
            else:
                detach([sys.executable, "-m", "meta.outer", "--resume", str(d)], d / "resume.log")
            restarted.append(str(d))
    if verbose:
        print(f"{time.strftime('%H:%M:%S')} keeper: " + (f"resumed {len(restarted)}: " + ", ".join(restarted)
                                                          if restarted else "nothing to resume"), flush=True)
    return restarted


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--watch", type=int, default=0, help="keep checking every N seconds")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--stop", default=None, help="a run folder to stop for good: marked stopped first, then killed")
    a = ap.parse_args(argv)
    if a.stop:
        d = Path(a.stop).resolve()
        st = json.loads((d / "status.json").read_text())
        st["state"] = "stopped"                       # first, so a keeper sweep can't resume it in between
        (d / "status.json").write_text(json.dumps(st))
        if alive(st.get("pid")):
            os.killpg(os.getpgid(int(st["pid"])), 15) if os.getpgid(int(st["pid"])) != os.getpgid(0) else os.kill(int(st["pid"]), 15)
        print(f"stopped {d}")
        return
    if a.list:
        for d in inner_runs():
            s = state(d)
            tag = "finished" if s["finished"] else ("running" if s["alive"] else "DEAD (resumable)")
            print(f"{d.relative_to(ROOT)}: generation {s['gen']} of {s['target']} - {tag}")
        return
    lock = open(ROOT / "runs" / ".keeper.lock" if (ROOT / "runs").exists() else ROOT / ".keeper.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another keeper is already running: nothing to do", flush=True)
        return
    sweep()
    while a.watch:
        time.sleep(a.watch)
        sweep()


if __name__ == "__main__":
    main()
