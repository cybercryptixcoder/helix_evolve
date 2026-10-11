"""Score one candidate program with the evaluator, in its own process (CONTRACT.md, Level 2).

The loop never imports evaluator code. It writes the candidate to a file, runs
`python -m evaluator --program ... --split ... --out ...`, and reads the JSON back.
A crash, a hang or unreadable output becomes an invalid result instead of
stopping the run.

Try it on its own:  python -m helix.sandbox programs/code_zero.py
"""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_VERSION = 1
ERROR_LINES = 20


def evaluator_command():
    """`python -m evaluator` by default; HELIX_EVALUATOR_CMD overrides it (for testing)."""
    custom = os.environ.get("HELIX_EVALUATOR_CMD")
    return shlex.split(custom) if custom else [sys.executable, "-m", "evaluator"]


def _invalid(split, error, started):
    return {
        "contract_version": CONTRACT_VERSION,
        "split": split,
        "valid": False,
        "error": error,
        "score": None,
        "excess_pct": None,
        "families": {},
        "runtime_s": round(time.time() - started, 3),
    }


def evaluate_file(program_path, split="train", timeout=60.0):
    """Run the evaluator on a program file and return the contract's result dict."""
    program_path = Path(program_path).resolve()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}  # don't touch the evaluator's tracked files
    started = time.time()

    # The result goes to a throwaway temp folder, never next to the program.
    with tempfile.TemporaryDirectory(prefix="helix-eval-") as tmp:
        out = Path(tmp) / "result.json"
        cmd = evaluator_command() + ["--program", str(program_path), "--split", split, "--out", str(out)]
        try:
            proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return _invalid(split, f"timeout: evaluation took longer than {timeout:.0f}s", started)

        if not out.exists():
            tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-ERROR_LINES:])
            return _invalid(split, f"evaluator crashed (exit code {proc.returncode}):\n{tail}", started)
        try:
            result = json.loads(out.read_text())
        except json.JSONDecodeError as err:
            return _invalid(split, f"evaluator wrote unreadable JSON: {err}", started)

    if result.get("valid") and not isinstance(result.get("score"), (int, float)):
        return _invalid(split, "evaluator said valid but returned no numeric score", started)
    return result


def evaluate_code(code, path, split="train", timeout=60.0):
    """Write candidate code to `path`, then score it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)
    return evaluate_file(path, split, timeout)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m helix.sandbox PROGRAM.py [split]")
    res = evaluate_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "train")
    print(json.dumps(res, indent=2))
