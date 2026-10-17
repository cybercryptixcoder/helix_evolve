"""Checks for the run viewer's exporter (viz/export.py).

Run:  python tests/test_viz_export.py     (plain asserts, no test framework needed)

Uses the published 5-generation run in results/, so it needs no model and no fitting.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from viz import export as X

RUN = os.path.join(ROOT, "results", "20261017-014858-full")


def test_clock_times_land_inside_their_generation():
    t = X.build_trace(RUN)
    gens = {g["gen"]: g for g in t["generations"]}
    for c in t["calls"]:
        g = gens[c["gen"]]
        assert c["end"] is not None, c["id"]
        # the call log keeps whole seconds only, so allow a little slack either side
        assert g["started"] - 2 <= c["end"] <= g["finished"] + 2, (c["id"], c["end"], g["started"], g["finished"])


def test_every_feature_is_linked_to_its_calls_and_verdict():
    t = X.build_trace(RUN)
    calls = {c["id"]: c for c in t["calls"]}
    kept = {fid for g in t["generations"] for fid in g["accepted"]}
    for f in t["features"]:
        assert f["calls"], f["id"]
        assert all(calls[c]["feature"] == f["id"] for c in f["calls"])
        assert (f["verdict"] == "kept") == (f["id"] in kept), f["id"]
        if f["branch"] == "deep":
            assert any(i["feature"] == f["id"] for i in t["ideas"]), f["id"]


def test_probe_lines_are_read_from_the_console():
    probes, timing, by_gen = X.parse_console(
        "── generation 2: deep + wide\n"
        "      [mag] f0013 +0.4:+1.828 -0.4:-1.349 +0.1:+1.828 -0.1:-1.349\n"
        "   [tim] f0013 probe 1.2s free 3.1s refit 4.4s valid 1.1s total 9.9s\n"
        "   [tim] f0014 probe 0.9s (rejected)\n"
        "   f0013 deep class_match_residual         train +1.828  valid +1.513\n")
    assert probes["f0013"][1] == {"w": -0.4, "delta": -1.349}
    assert timing["f0013"]["total"] == 9.9 and timing["f0014"]["rejected"]
    assert by_gen[2] == ["── generation 2: deep + wide", "   f0013 deep class_match_residual         train +1.828  valid +1.513"]


def test_page_embeds_the_trace_safely():
    t = X.build_trace(RUN)
    t["calls"][0]["reply"] = "a reply that mentions </script> in passing"
    page = X.to_html(t)
    assert X.PLACEHOLDER not in page
    start = page.index("const EMBEDDED_TRACE = ") + len("const EMBEDDED_TRACE = ")
    end = page.index(";\n</script>", start)
    blob = page[start:end]
    assert "</script>" not in blob
    assert json.loads(blob.replace("<\\/", "</"))["run"]["id"] == "20261017-014858-full"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
