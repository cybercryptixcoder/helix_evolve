"""Load a candidate program, run it on a split, return the contract's result dict (TSP).

Same safety discipline as the packing evaluator: guarded imports (numpy/math only), blocked
builtins, output discarded, a fresh load per instance, and every failure turns into an invalid
result instead of stopping the run.
"""
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
FUNC_NAME = "pick"


def _guarded_import(name, *args, **kwargs):
    if name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"programs may only import numpy and math, not {name!r}")
    return builtins.__import__(name, *args, **kwargs)


_SAFE_BUILTINS = {k: v for k, v in vars(builtins).items() if k not in BLOCKED_BUILTINS}
_SAFE_BUILTINS["__import__"] = _guarded_import

_seed_global_rng = np.random.seed
_real_default_rng = np.random.default_rng


def _seeded_default_rng(seed=None, *args, **kwargs):
    return _real_default_rng(0 if seed is None else seed, *args, **kwargs)


def _load_pick(program_path):
    source = Path(program_path).read_text(encoding="utf-8")
    namespace = {"__name__": "candidate", "__file__": str(program_path), "__builtins__": _SAFE_BUILTINS}
    exec(compile(source, str(program_path), "exec"), namespace)
    pick = namespace.get(FUNC_NAME)
    if not callable(pick):
        raise AttributeError(f"program defines no function named {FUNC_NAME!r}")
    return pick


def _mean(values):
    return sum(values) / len(values)


def _summarise(results):
    families = {}
    for r in results:
        families.setdefault(r["family"], []).append(r)
    summary = {}
    for fam, rs in families.items():
        summary[fam] = {
            "excess_pct": round(100 * _mean([float(r["excess"]) for r in rs]), 4),
            "tour_length": int(round(sum(r["length"] for r in rs))),
            "lower_bound": int(round(sum(r["lower_bound"] for r in rs))),
            "instances": len(rs),
        }
    return summary


def evaluate(program_path: str, split: str = "train") -> dict:
    instances = load_split(split)
    start = time.time()
    np.random.default_rng = _seeded_default_rng
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            results = []
            for inst in instances:
                _seed_global_rng(0)
                results.append(run_instance(inst, _load_pick(program_path)))
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
    finally:
        np.random.default_rng = _real_default_rng
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
