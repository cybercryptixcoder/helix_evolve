"""Regression tests for agent-reply extraction hygiene (see HANDOFF §15).

Run:  python tests/test_extraction.py     (plain asserts, no test framework needed)

The bug these cover: one Mutator reply put its `name:` line inside the python fence; the stored
code then carried a bare module-level annotation, which executes as NameError in the evaluator
(no future-import) while the fitter (helix/fit.py has `from __future__ import annotations`) never
noticed. Composed champions silently failed official scoring.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helix import features as FT
from helix import roles


REPLY_WITH_NAME_INSIDE = (
    "```python\n"
    "import numpy as np\n\n\n"
    "def feature(item, bins, capacity):\n"
    '    """A bin whose leftover is balanced."""\n'
    "    r = (bins - item) / capacity\n"
    "    return -(np.abs(r[:, 0] - r[:, 1]).sum())\n\n"
    "name: small_job_balanced_residual\n"
    "```\n"
)


def test_extract_code_strips_metadata_line():
    code = roles.extract_code(REPLY_WITH_NAME_INSIDE, "feature", flexible=True)
    assert code is not None
    assert "name:" not in code, code
    assert "def feature" in code


def test_extract_feature_name_finds_inside_fence():
    assert roles.extract_feature_name(REPLY_WITH_NAME_INSIDE, "default_x") == "small_job_balanced_residual"


def test_extract_feature_name_prefers_outside():
    reply = "```python\ndef feature(item, bins, capacity):\n    return 0.0\n```\nname: outside_name\n"
    assert roles.extract_feature_name(reply, "default_x") == "outside_name"


def test_prepare_skips_bare_annotation():
    bad = ("import numpy as np\n\n\n"
           "def feature(item, bins, capacity):\n    return -(item.sum())\n\n"
           "_f0011_name: small_job_balanced_residual\n")
    imports, body = FT.prepare(bad, "f0011")
    assert "small_job_balanced_residual" not in body
    ns = {}
    exec("import numpy as np\nimport math\n" + body, ns)          # must execute cleanly
    assert callable(ns["_f0011"])


def test_prepare_still_accepts_valued_annotations():
    src = ("import numpy as np\n\n\n"
           "SCALE: float = 2.0\n\n\n"
           "def feature(item, bins, capacity):\n    return -(item.sum()) * SCALE\n")
    imports, body = FT.prepare(src, "f0012")
    assert "SCALE" in body
    ns = {}
    exec("import numpy as np\nimport math\n" + body, ns)
    assert callable(ns["_f0012"])


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print("all good" if not failures else f"{failures} failure(s)")
    sys.exit(1 if failures else 0)
