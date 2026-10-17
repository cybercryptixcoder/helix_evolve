"""Fast checks for Helix v3 (no model calls). Run: python -m pytest tests/test_helix3.py -q"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helix3 import roles  # noqa: E402
from helix3.ledger import Ledger  # noqa: E402
from helix3.policy import FeatureError, check_source, extract_code, make_priority  # noqa: E402

BEST_FIT = "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"bf\"\"\"\n    return -((bins - item) / capacity).sum(axis=1)\n"
BEST_FIT_X3 = "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"bf cubed, flipped\"\"\"\n    return (((bins - item) / capacity).sum(axis=1)) ** 3\n"
NEW_BIN = "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"new\"\"\"\n    v = np.zeros(len(bins)); v[-1] = 1.0\n    return v\n"
CONST = "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"const\"\"\"\n    return np.ones(len(bins))\n"


def _states(n=80, seed=0):
    rng = np.random.default_rng(seed)
    cap = np.array([100, 100])
    out = []
    for _ in range(n):
        k = rng.integers(2, 9)
        bins = np.vstack([rng.integers(20, 100, size=(k - 1, 2)), cap])
        out.append((rng.integers(1, 20, size=2), bins, cap))
    return out


def _ledger():
    led = Ledger()
    led.set_states(_states(), lambda a: len(a[1]))
    return led


def test_duplicate_up_to_monotone_and_sign():
    led = _ledger()
    a = led.new_feature(name="a", code=BEST_FIT, status="tried")
    b = led.new_feature(name="b", code=BEST_FIT_X3)
    cert = led.certify(b, lambda a_: len(a_[1]))
    assert cert.get("type") == "duplicate" and cert["of"] == a.id


def test_inert_and_distinct():
    led = _ledger()
    led.new_feature(name="a", code=BEST_FIT, status="tried")
    c = led.new_feature(name="c", code=CONST)
    assert led.certify(c, lambda a_: len(a_[1]))["type"] == "inert"
    n = led.new_feature(name="n", code=NEW_BIN)
    assert led.certify(n, lambda a_: len(a_[1])).get("type") is None


def test_span_certificate():
    led = _ledger()
    a = led.new_feature(name="a", code=BEST_FIT, status="kept")
    n = led.new_feature(name="n", code=NEW_BIN, status="kept")
    led.library = [a.id, n.id]
    combo = led.new_feature(name="combo", code=(
        "import numpy as np\n\ndef feature(item, bins, capacity):\n    \"\"\"2*bf + 3*new\"\"\"\n"
        "    v = -2 * ((bins - item) / capacity).sum(axis=1)\n    v[-1] += 3.0\n    return v\n"))
    cert = led.certify(combo, lambda a_: len(a_[1]), against=[])
    assert cert.get("type") == "span"


def test_sandbox_rejects_imports():
    try:
        check_source("import os\n\ndef feature(a):\n    return 0\n")
    except FeatureError:
        return
    raise AssertionError("os import was accepted")


def test_priority_ties_round():
    pr = make_priority([BEST_FIT], [[1.0]], lambda a: len(a[1]))
    s = pr(np.array([5, 5]), np.array([[50, 50], [50, 50], [100, 100]]), np.array([100, 100]))
    assert s[0] == s[1] and int(np.argmax(s)) == 0


def test_extract_and_json():
    assert "def feature" in extract_code("x\n```python\nimport numpy as np\ndef feature(a):\n    return a\n```\nname: x")
    assert roles.extract_json('Sure.\n```json\n{"a": [1, 2,]}\n```')["a"] == [1, 2]


def test_strategy_validates():
    from meta.strategies import validate
    errors, _ = validate(ROOT / "helix3" / "strategy")
    assert not errors, errors


def test_edits_apply(tmp_path):
    from meta.strategies import apply_edits, parse_edits
    text = ('<<<EDIT config.json>>>\n<<<FIND>>>\n"experiments": 4\n<<<REPLACE>>>\n"experiments": 5\n<<<END>>>\n'
            '<<<FILE prompts/coder.md>>>\nNew coder.\n<<<END>>>')
    changed, errors = apply_edits(ROOT / "helix3" / "strategy", tmp_path / "c", parse_edits(text))
    assert not errors and set(changed) == {"config.json", "prompts/coder.md"}
    assert json.loads((tmp_path / "c" / "config.json").read_text())["researcher"]["experiments"] == 5
