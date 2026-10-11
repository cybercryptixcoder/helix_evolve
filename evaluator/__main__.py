"""python -m evaluator --program PATH --split train --out RESULT.json"""
import argparse
import json
from pathlib import Path

from .evaluate import evaluate
from .problem import SPLITS


def main():
    parser = argparse.ArgumentParser(prog="python -m evaluator", description="Score a candidate packing program.")
    parser.add_argument("--program", required=True, help="path to a .py file defining priority(item, bins, capacity)")
    parser.add_argument("--split", default="train", choices=list(SPLITS))
    parser.add_argument("--out", required=True, help="where to write the result JSON")
    args = parser.parse_args()

    result = evaluate(args.program, args.split)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
