"""Load a candidate program, run it on a split, return the contract's result dict."""
import time
import traceback
from pathlib import Path

import numpy as np

from .problem import load_split, run_instance

CONTRACT_VERSION = 1


def _load_priority(program_path):
    source = Path(program_path).read_text()
    namespace = {"__name__": "candidate", "__file__": str(program_path)}
    exec(compile(source, str(program_path), "exec"), namespace)
    priority = namespace.get("priority")
    if not callable(priority):
        raise AttributeError("program defines no function named 'priority'")
    return priority


def _summarise(results):
    families = {}
    for r in results:
        families.setdefault(r["family"], []).append(r)
    summary = {}
    for fam, rs in families.items():
        summary[fam] = {
            "excess_pct": round(100 * float(np.mean([r["excess"] for r in rs])), 4),
            "bins_used": int(sum(r["bins_used"] for r in rs)),
            "lower_bound": int(sum(r["lower_bound"] for r in rs)),
            "fill": [round(float(x), 4) for x in np.mean([r["fill"] for r in rs], axis=0)],
            "instances": len(rs),
        }
    return summary


def evaluate(program_path: str, split: str = "train") -> dict:
    instances = load_split(split)
    start = time.time()
    try:
        # Fresh load per instance, so nothing a program keeps between calls
        # can leak from one instance into the next.
        results = [run_instance(inst, _load_priority(program_path)) for inst in instances]
    except Exception:
        return {
            "contract_version": CONTRACT_VERSION,
            "split": split,
            "valid": False,
            "error": traceback.format_exc(),
            "score": None,
            "excess_pct": None,
            "families": {},
            "runtime_s": round(time.time() - start, 3),
        }
    families = _summarise(results)
    excess_pct = round(float(np.mean([f["excess_pct"] for f in families.values()])), 4)
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
