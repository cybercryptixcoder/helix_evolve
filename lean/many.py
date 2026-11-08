"""Several runs in one process, side by side (threads), so that they share the model keys' pacing and their limit on
open calls. Several processes on one key would each pace themselves and together exceed the key's limits.

    python -m lean.many runs.json

runs.json:
    {"runs": [{"name": "asis", "out": "runs/vrp/asis", "problem": "helix_vrp.lean_adapter",
               "params": {"blackbox": "...", "seed_program": "p1010.py", "variant": "as_is"}, "rounds": 1000}, ...]}

Every Config field may be given per run. A run that crashes is logged and retried after a minute (each run resumes
from its last finished generation); the others go on. HELIX_DEADLINE (epoch seconds) stops every run after the
generation in progress.
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
    name = spec.get("name") or spec["out"]
    cfg = Config(**{k: v for k, v in spec.items() if k in KNOWN})
    for attempt in range(1, 6):
        try:
            Run(spec["out"], cfg, log=lambda m: log(f"[{name}] {m}")).go()
            return
        except Exception as exc:                                         # noqa: BLE001
            log(f"[{name}] crashed (attempt {attempt}): {exc}\n{traceback.format_exc()}")
            time.sleep(60)
    log(f"[{name}] gave up after 5 crashes")


def main(argv=None):
    path = (argv or sys.argv[1:])[0]
    specs = json.load(open(path))["runs"]
    lock = threading.Lock()

    def log(m):
        with lock:
            print(time.strftime("%H:%M:%S"), m, flush=True)
    threads = [threading.Thread(target=one, args=(s, log), name=s.get("name", "run")) for s in specs]
    for t in threads:
        t.start()
        time.sleep(5)                       # stagger the seeds' first evaluations
    for t in threads:
        t.join()
    log("all runs finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
