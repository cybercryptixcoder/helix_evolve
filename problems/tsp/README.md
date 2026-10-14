# Second problem: greedy travelling-salesman tours

Proves the loop is problem-agnostic: **no loop code is packing-specific**, so the same
`helix/` search runs a completely different problem by swapping the problem side through the
CONTRACT.md interfaces only. Nothing in `helix/` mentions tours, cities or distances; nothing
here mentions bins, jobs or capacities.

## The contract points this problem plugs into

| Interface | Value for this problem |
|---|---|
| Evaluator process | `python -m problems.tsp.cli --program ... --split ... --out ...` (via `HELIX_EVALUATOR_CMD`) |
| Prompts (role files + problem statement) | `problems/tsp/prompts/` (via `HELIX_PROMPTS_DIR`) |
| Family floors for the Researcher message | `problems.tsp.bounds` (via `HELIX_BOUNDS_MODULE`; returns no floors) |
| Seed program | `--seed-program problems/tsp/seed.py` |

## Run it

```bash
cd /home/ubuntu/helix_evolve
HELIX_PROMPTS_DIR=$PWD/problems/tsp/prompts \
HELIX_EVALUATOR_CMD="$PWD/.venv/bin/python -m problems.tsp.cli" \
HELIX_BOUNDS_MODULE=problems.tsp.bounds \
.venv/bin/python -m helix.run --engine programs --seed-program problems/tsp/seed.py \
  --generations 8 --mode full --no-publish
```

## Scoring

Tour length ÷ lower bound − 1, averaged per family, as %; `score = −mean excess`. Lower bound:
half the sum over cities of each city's two nearest-neighbour distances (no tour can beat it).

## Baselines

`problems/tsp/baselines/` — nearest, farthest, input_order. Run one:

```bash
.venv/bin/python -m problems.tsp.cli --program problems/tsp/baselines/nearest.py --split test --out /tmp/r.json
```
