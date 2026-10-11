"""Put a run's real numbers into the demo slides.

    python demo/update_data.py helix/runs/<run-folder>

Reads the run's generations, programs and (if present) held-out check, then rewrites the
RUN block in demo/index.html. Run it again whenever the run has moved on.
"""
import json
import re
import sys
from pathlib import Path

PAGE = Path(__file__).resolve().parent / "index.html"


def read_jsonl(path):
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def main():
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit("usage: python demo/update_data.py helix/runs/<run-folder>")
    run = Path(sys.argv[1])
    gens = sorted(read_jsonl(run / "generations.jsonl"), key=lambda g: g["generation"])
    programs = read_jsonl(run / "programs.jsonl")
    seed = next((p["score"] for p in programs if p.get("branch") == "seed" and p.get("score") is not None), None)
    if not gens or seed is None:
        sys.exit(f"{run} has no finished generation yet")

    heldout = None
    held_path = run / "heldout.json"
    if held_path.exists():
        rows = json.loads(held_path.read_text())
        heldout = next((r.get("test_score") for r in rows if str(r.get("label", "")).startswith("Evolved best")), None)

    data = {
        "sample": False,
        "run": run.name,
        "start": seed,
        "best": [g["best_score"] for g in gens],
        "minutes": round(sum(g.get("seconds") or 0 for g in gens) / 60),
        "programs": len(programs),
        "llmCalls": (gens[-1].get("llm") or {}).get("calls"),
        "heldout": heldout,
    }
    html = PAGE.read_text()
    new, n = re.subn(r"const RUN = .*?;\n", "const RUN = " + json.dumps(data) + ";\n", html, count=1)
    if n != 1:
        sys.exit("couldn't find the RUN block in demo/index.html")
    PAGE.write_text(new)

    gain = 100 * (data["best"][-1] - seed) / -seed
    print(f"{run.name}: {len(gens) - 1} generations, {len(programs)} programs, {data['minutes']} min, "
          f"{gain:.1f}% fewer wasted servers" + (f", held-out score {heldout}" if heldout is not None else ""))


if __name__ == "__main__":
    main()
