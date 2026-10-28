"""A v10 run made robust for an unattended job (as helix9/job.py: graceful stop, torn-line repair, health waits for
disk and model, the deadline), around helix10.run.Run.

    python -m helix10.job --out runs/v10/v10-warm --gens 920
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from helix9.job import EXIT_ERROR, EXIT_STOPPED, install_signals, repair_jsonl, robust


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the run folder (resumes if state.json is there)")
    ap.add_argument("--gens", type=int, default=None, help="the generation to stop at")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=float, default=150.0, help="CPU seconds per program (a new run only)")
    ap.add_argument("--fake", action="store_true", help="no model calls (a fake model)")
    a = ap.parse_args(argv)
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)   # noqa: E731
    install_signals(log)
    from helix4.llm import FakeLLM
    from helix10.run import Config, Run, fake_answer
    fixed = repair_jsonl(a.out) if Path(a.out).is_dir() else []
    if fixed:
        log(f"repaired {', '.join(fixed)} (cut off mid-line by a hard stop)")
    R = robust(Run)
    llm = None
    if a.fake:
        delay = float(os.environ.get("FAKE_DELAY", "0") or 0)
        llm = FakeLLM(lambda role, s, u: "OK" if role == "health" else fake_answer(role, s, u), delay=delay)
    try:
        run = R(a.out, Config(seed=a.seed, gens=a.gens or 20, budget=a.budget), llm=llm, gens=a.gens, log=log)
        summary = run.go()
    except SystemExit:
        raise
    except Exception:                                              # noqa: BLE001
        import traceback
        log("the run crashed:\n" + traceback.format_exc())
        return EXIT_ERROR
    return EXIT_STOPPED if summary.get("stopped_by") == "stop" else 0


if __name__ == "__main__":
    sys.exit(main())
