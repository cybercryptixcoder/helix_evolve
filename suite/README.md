# The problem suite

Verifiable problems for Helix v3. Every problem is a **priority problem**: a solution is built one decision at a time; at each decision a policy scores the candidates and the highest score wins (ties: the first candidate). The policy Helix evolves is a weighted sum of features `feature(...)` written by agents. **Code Zero** scores every candidate 0, so it always takes the first candidate: that is 0% progress.

The interface is `helix3/problem.py`; `suite/binpack2d.py` is the worked example. Check a problem with:

```bash
python -m suite.check <name>      # determinism, speed, Code Zero, example features, diagnostics
python -m suite.check --all
```

| Problem | Decision | Candidates | Reference (100%) |
|---|---|---|---|
| `binpack2d` | place an arriving 2D job | open bins it fits + a new bin | optimal packings (train) |
| `binpack1d` | place an arriving item | open bins it fits + a new bin | L1 lower bound |
| `knapsack` | pick the next item to add | items that still fit | DP optimum |
| `setcover` | pick the next set | sets that cover something new | ILP optimum |
| `tsp` | pick the next city | unvisited cities | best-known tour |
| `scheduling` | assign an arriving job | machines | lower bound |
| `coloring` | pick the next vertex to colour | uncoloured vertices | best known |
| `jobshop` | pick the next operation to dispatch | ready operations | lower bound |

## Rules for a problem (what keeps comparisons honest)

- **Deterministic instances** from fixed seeds, for `train`, `valid` and `test` (different seeds). `test` may add families listed in `held_out_families` that train never shows.
- **Fast:** Code Zero on the whole train split in well under a second. A search evaluates thousands of policies.
- **Neutral candidate order.** The order of candidates decides Code Zero, so it must not encode a good heuristic (arrival order, index order).
- **No hints.** The description says what the problem is and how it's scored, never which heuristics are known to work.
- **gap %** per instance: how far above the reference (minimisation: `100 * (cost / ref - 1)`; maximisation: `100 * (1 - value / ref)`). `floor(family)` is the best gap reachable (0 when the reference is the optimum).
- **Diagnostics:** a few named metrics of a solution (`diagnose`), with a one-line note each (`metric_notes`), and the same metrics for the reference solution when there is one (`reference_metrics`). The Researcher reads them and names them in its predictions, which the engine checks.
- **Expensive references are cached** in `suite/data/<name>_refs.json`, rebuilt with `python -m suite.<name> --refs`.
