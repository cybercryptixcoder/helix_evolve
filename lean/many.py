"""Several runs in one process, side by side (threads), so that they share the model keys' pacing and their limit on
open calls. Several processes on one key would each pace themselves and together exceed the key's limits.

    python -m lean.many runs.json

runs.json:
    {"runs": [{"name": "asis", "out": "runs/vrp/asis", "problem": "helix_vrp.lean_adapter",
               "params": {"blackbox": "...", "seed_program": "p1010.py", "variant": "as_is"}, "rounds": 1000}, ...]}

Every Config field may be given per run. The file is read again every minute: a run added to it later is started
then, in the same process (so a long job can take on new runs without stopping the ones going). A run that crashes
is logged and retried after a minute (each run resumes from its last finished generation); the others go on.
HELIX_DEADLINE (epoch seconds) stops every run after the generation in progress. The process ends when every run
has ended and none has been added for a minute.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from dataclasses import fields

from lean.loop import Config, Run

KNOWN = {f.name for f in fields(Config)}


def one(spec, log):
    name = spec["name"]
    cfg = Config(**{k: v for k, v in spec.items() if k in KNOWN})
    for attempt in range(1, 6):
        try:
            Run(spec["out"], cfg, log=lambda m: log(f"[{name}] {m}")).go()
            return
        except Exception as exc:                                         # noqa: BLE001
            log(f"[{name}] crashed (attempt {attempt}): {exc}\n{traceback.format_exc()}")
            time.sleep(60)
    log(f"[{name}] gave up after 5 crashes")


def read(path, log):
    try:
        specs = json.load(open(path))["runs"]
        for s in specs:
            s.setdefault("name", s["out"])
        return specs
    except Exception as exc:                                             # noqa: BLE001  (a half-written file)
        log(f"could not read {path}: {exc}")
        return None


def main(argv=None):
    path = (argv or sys.argv[1:])[0]
    lock = threading.Lock()

    def log(m):
        with lock:
            print(time.strftime("%H:%M:%S"), m, flush=True)
    threads = {}
    while True:
        for s in read(path, log) or []:
            if s["name"] not in threads:
                log(f"starting {s['name']}")
                threads[s["name"]] = threading.Thread(target=one, args=(s, log), name=s["name"], daemon=True)
                threads[s["name"]].start()
                time.sleep(5)               # stagger the runs' first evaluations
        if threads and not any(t.is_alive() for t in threads.values()):
            time.sleep(60)
            if all(s["name"] in threads for s in read(path, log) or []):
                break
        else:
            time.sleep(60)
    log("all runs finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
