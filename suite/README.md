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
| `jobshop` | pick the next operation to dispatch | ready operations | best-known schedule |
| `cvrp` | pick the vehicle's next stop | unvisited customers that fit + back to the depot | best-known routes |

## Open suite

No reference, no floor, no ceiling (`docs/OPEN_SUITE.md`): `open_ceiling = True`, gap = 100 x cost / Code Zero's cost on the instance (Code Zero = 100 exactly), candidates reshuffled at every decision with the instance's seed.

| Problem | Decision | Candidates | Cost |
|---|---|---|---|
| `forage` | the drone's next target | visible items + the charger | value lost (decayed or never collected) + a penalty per battery run-out |
| `thermal` | place an arriving or waiting job in a heating data hall | servers with room (none: the queue, automatically) | minutes lost to heat slowdown and queueing |
| `fairshare` | staff the next shift position | eligible volunteers + leave uncovered | 5 x uncovered + unmet preferences + unfairness (parts reported separately) |
| `backtrack` | the variable a fixed depth-first solver branches on next (invented "tide pools" puzzle) | unassigned variables | search nodes until the first solution, summed over a ladder of 3 puzzles (~30/55/85 variables), each capped at 15 x size; Code Zero costs cached in `suite/data/backtrack_cz.json` (`python -m suite.backtrack --cz`) |
| `duel` | the cell to claim in an invented territory game ("spore") | legal claims | 100 x the opponents' share of points over 24 seeded games against a pool of 4 scripted opponents; Code Zero costs cached in `suite/data/duel_cz.json` (`python -m suite.duel --cz`) |

## Rules for a problem (what keeps comparisons honest)

- **Deterministic instances** from fixed seeds, for `train`, `valid` and `test` (different seeds). `test` may add families listed in `held_out_families` that train never shows.
- **Fast:** Code Zero on the whole train split in well under a second. A search evaluates thousands of policies.
- **Neutral candidate order.** The order of candidates decides Code Zero, so it must not encode a good heuristic (arrival order, index order).
- **No hints.** The description says what the problem is and how it's scored, never which heuristics are known to work.
- **gap %** per instance: how far above the reference (minimisation: `100 * (cost / ref - 1)`; maximisation: `100 * (1 - value / ref)`). `floor(family)` is the best gap reachable (0 when the reference is the optimum).
- **Diagnostics:** a few named metrics of a solution (`diagnose`), with a one-line note each (`metric_notes`), and the same metrics for the reference solution when there is one (`reference_metrics`). The Researcher reads them and names them in its predictions, which the engine checks.
- **Expensive references are cached** in `suite/data/<name>_refs.json`, rebuilt with `python -m suite.<name> --refs`.
