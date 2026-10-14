"""python -m problems.tsp.cli --program PATH --split train --out RESULT.json"""
import argparse
import json
from pathlib import Path

from .evaluate import evaluate


def main():
    parser = argparse.ArgumentParser(prog="python -m problems.tsp.cli",
                                     description="Score a candidate TSP tour program.")
    parser.add_argument("--program", required=True, help="path to a .py file defining pick(city, cities, visited, dist)")
    parser.add_argument("--split", default="train", choices=["train", "test", "quick"])
    parser.add_argument("--out", required=True, help="where to write the result JSON")
    args = parser.parse_args()

    result = evaluate(args.program, args.split)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
