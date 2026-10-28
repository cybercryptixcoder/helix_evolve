"""The field's methods as programs for this problem's interface (`construct(budget_seconds, start)`, one CPU core).

- dinkelbach_polish: ClaudeExplorer's iterated Dinkelbach (LogSumExp max, beta cascade, L-BFGS on f = w^2);
- velocity_cycles: the July 2026 record's polish: small noise, a full re-polish, momentum along the last gain;
- resolution_transfer: the exact resolution moves (k-fold repeat, zero-pad to the cap) and then the polish.

Each is self-contained (the polisher's code is shared and copied into each program when it is loaded), so the coder
sees and edits one whole program. Used by helix10/warm.py in the warm mode only.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ("dinkelbach_polish", "velocity_cycles", "resolution_transfer")


def core():
    """The polisher (everything in dinkelbach_polish.py before its construct)."""
    text = (HERE / "dinkelbach_polish.py").read_text()
    return text.split("\ndef construct(")[0].rstrip() + "\n"


def _split_doc(text):
    """(the module docstring, the rest)."""
    end = text.index('"""', 3) + 3
    return text[:end], text[end:]


def load(name):
    if name == "dinkelbach_polish":
        return (HERE / "dinkelbach_polish.py").read_text()
    doc, tail = _split_doc((HERE / f"{name}.py").read_text())
    _, polisher = _split_doc(core())
    return f"{doc}\n{polisher.strip()}\n\n\n{tail.strip()}\n"
