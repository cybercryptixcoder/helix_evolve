"""Load a candidate program, run it on a split, return the contract's result dict."""
import builtins
import contextlib
import os
import time
import traceback
from pathlib import Path

import numpy as np

from .problem import load_split, run_instance

CONTRACT_VERSION = 1
ALLOWED_IMPORTS = {"numpy", "math"}
BLOCKED_BUILTINS = {"open", "exec", "eval", "compile", "input", "breakpoint"}
ERROR_LINES = 20


def _guarded_import(name, *args, **kwargs):
    if name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"programs may only import numpy and math, not {name!r}")
    return builtins.__import__(name, *args, **kwargs)


_SAFE_BUILTINS = {k: v for k, v in vars(builtins).items() if k not in BLOCKED_BUILTINS}
_SAFE_BUILTINS["__import__"] = _guarded_import


def _load_priority(program_path):
    source = Path(program_path).read_text()
    namespace = {"__name__": "candidate", "__file__": str(program_path), "__builtins__": _SAFE_BUILTINS}
    exec(compile(source, str(program_path), "exec"), namespace)
    priority = namespace.get("priority")
    if not callable(priority):
        raise AttributeError("program defines no function named 'priority'")
    return priority


def _mean(values):
    return sum(values) / len(values)


def _summarise(results):
    # Plain Python on purpose: by now the program's code has run, and it could
    # have changed numpy functions such as np.mean.
    families = {}
    for r in results:
        families.setdefault(r["family"], []).append(r)
    summary = {}
    for fam, rs in families.items():
        summary[fam] = {
            "excess_pct": round(100 * _mean([float(r["excess"]) for r in rs]), 4),
            "bins_used": int(sum(r["bins_used"] for r in rs)),
            "lower_bound": int(sum(r["lower_bound"] for r in rs)),
            "fill": [round(_mean([float(r["fill"][d]) for r in rs]), 4) for d in range(2)],
            "instances": len(rs),
        }
    return summary


def evaluate(program_path: str, split: str = "train") -> dict:
    instances = load_split(split)
    start = time.time()
    try:
        # Programs may print; their output is discarded. Fresh load per
        # instance, so nothing a program keeps between calls can leak from
        # one instance into the next.
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            results = [run_instance(inst, _load_priority(program_path)) for inst in instances]
    except (Exception, SystemExit):
        error = traceback.format_exc().rstrip().splitlines()
        return {
            "contract_version": CONTRACT_VERSION,
            "split": split,
            "valid": False,
            "error": "\n".join(error[-ERROR_LINES:]),
            "score": None,
            "excess_pct": None,
            "families": {},
            "runtime_s": round(time.time() - start, 3),
        }
    families = _summarise(results)
    excess_pct = round(_mean([f["excess_pct"] for f in families.values()]), 4)
    return {
        "contract_version": CONTRACT_VERSION,
        "split": split,
        "valid": True,
        "error": None,
        "score": -excess_pct,
        "excess_pct": excess_pct,
        "families": families,
        "runtime_s": round(time.time() - start, 3),
    }
