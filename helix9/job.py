"""A v9 run made airtight for a job on the VM (docs/AETHER.md, section 4b; docs/V9_JOB.md).

    python -m helix9.job --out runs/v9warm/v9-s1 --gens 800            # resumes; exits 0 (done or deadline),
                                                                        # 75 (stopped by a signal), 4 (an error)
    python -m helix9.job --out /tmp/x --gens 3 --fake --budget 2        # a test, no model calls

Around helix9.run.Run:
- **a graceful stop:** the first SIGTERM, SIGINT or SIGHUP finishes the generation in progress (up to STOP_GRACE_S,
  default 300 s), saves, and exits with 75; a second signal (not the same one arriving twice within 10 s), or the
  grace running out, exits at once (the generation in progress is redone on resume);
- **a repair step at start:** JSONL files cut off mid-line by a hard stop are trimmed back to their last whole line
  (the run then drops the unfinished generation's programs, as every Helix run does on resume);
- **health checks before every generation:** while the disk has less than MIN_DISK_MB (800) free, or the model doesn't
  answer a one-word call, the run waits (1, 2, 4 ... up to 30 minutes between checks) instead of burning generations;
- the deadline (HELIX4_DEADLINE, epoch seconds) stops it after the generation in progress, with exit 0.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import threading
import time
from pathlib import Path

STOP = threading.Event()
STOP_INFO = {"t": None, "signal": None}
EXIT_STOPPED, EXIT_ERROR = 75, 4


def repair_jsonl(folder):
    """Trims JSONL files cut off mid-line by a hard stop back to their last whole line. Returns the files fixed."""
    fixed = []
    for f in Path(folder).glob("*.jsonl"):
        raw = f.read_bytes()
        if not raw:
            continue
        lines = raw.split(b"\n")
        keep = len(lines)
        while keep > 0:
            last = lines[keep - 1].strip()
            if not last:
                keep -= 1
                continue
            try:
                json.loads(last)
                break
            except ValueError:
                keep -= 1
        good = b"\n".join(lines[:keep]).rstrip(b"\n")
        good = good + b"\n" if good else b""
        if good != raw:
            tmp = f.with_suffix(".jsonl.tmp")
            tmp.write_bytes(good)
            os.replace(tmp, f)
            fixed.append(f.name)
    return fixed


def robust(Base):
    class Robust(Base):
        def healthy(self, gen):
            """Waits while the disk is nearly full or the model can't be reached. False if a stop was asked."""
            waited = 0
            while not STOP.is_set():
                free_mb = shutil.disk_usage(self.dir).free // (1 << 20)
                problem = None
                if free_mb < int(os.environ.get("MIN_DISK_MB", "800")):
                    problem = f"only {free_mb} MB of disk free"
                else:
                    try:
                        self.llm.chat("health", "You answer in one word.", "Say OK.", max_tokens=20, effort="none",
                                      meta={"gen": gen}, tries=3)
                    except Exception as exc:              # noqa: BLE001
                        problem = f"the model can't be reached ({type(exc).__name__}: {str(exc)[:120]})"
                if problem is None:
                    if waited:
                        self.log(f"[{self.name}] resuming generation {gen} after waiting {waited // 60} min")
                    return True
                pause = min(1800, 60 * 2 ** min(5, waited // 600))
                self.log(f"[{self.name}] waiting before generation {gen}: {problem}; checking again in {pause // 60} min")
                STOP.wait(pause)
                waited += pause
            return False

        def go(self):
            t0 = time.time()
            if self.gen_done < 0:
                self.seed()
            deadline = float(os.environ.get("HELIX4_DEADLINE", "0") or 0)
            stopped_by = None
            for gen in range(self.gen_done + 1, self.cfg.gens + 1):
                if STOP.is_set():
                    stopped_by = "stop"
                    break
                if deadline and time.time() > deadline:
                    self.log(f"[{self.name}] the job's deadline has passed: stopping after generation {self.gen_done}")
                    stopped_by = "deadline"
                    break
                if not self.healthy(gen):
                    stopped_by = "stop"
                    break
                self.generation(gen)
            if stopped_by == "stop":
                self.log(f"[{self.name}] stopped cleanly after generation {self.gen_done} (signal "
                         f"{STOP_INFO['signal']}); running again resumes from generation {self.gen_done + 1}")
            summary = self.finish(time.time() - t0, stopped_at=self.gen_done if stopped_by else None)
            summary["stopped_by"] = stopped_by
            (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
            return summary
    Robust.__name__ = f"Robust{Base.__name__}"
    return Robust


def install_signals(log):
    grace = float(os.environ.get("STOP_GRACE_S", "300"))

    def handler(signum, frame):
        name = signal.Signals(signum).name
        if STOP.is_set():
            if time.time() - (STOP_INFO["t"] or 0) < 10:
                return                  # the same request arriving twice (the job forwards it; a shutdown sends it too)
            log(f"second stop signal ({name}): stopping now; the generation in progress is dropped and redone on resume")
            os._exit(EXIT_STOPPED)
        STOP_INFO.update(t=time.time(), signal=name)
        STOP.set()
        log(f"stop requested ({name}): finishing the generation in progress (up to {grace:.0f} s), then stopping")

        def watchdog():
            time.sleep(grace)
            log(f"the generation in progress didn't finish within {grace:.0f} s: stopping now; it is redone on resume")
            os._exit(EXIT_STOPPED)
        threading.Thread(target=watchdog, daemon=True).start()

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, handler)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the run folder (resumes if state.json is there)")
    ap.add_argument("--gens", type=int, default=None, help="the generation to stop at")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=float, default=60.0, help="CPU seconds per program (a new run only)")
    ap.add_argument("--fake", action="store_true", help="no model calls (a fake model)")
    a = ap.parse_args(argv)
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)   # noqa: E731
    install_signals(log)
    from helix4.llm import FakeLLM
    from helix9.run import Config, Run, fake_answer
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
