# Meta-evaluation: score 29.4

Strategy `/home/ubuntu/helix_evolve_run/meta_runs/outer-20261017-164239/candidates/c002`; 5 generations × 2 repeats; 120.2 min, 525 model calls.

Score = 0.6 × final + 0.4 × AUC, both measured beyond each problem's hidden textbook baseline (0) toward the reference (100).

| Problem | Score | Final, beyond baseline | AUC, beyond baseline | Final test progress (from Code Zero) | 90% by gen | Spread | Crashes |
|---|---|---|---|---|---|---|---|
| binpack1d | 2.9 | 13.7 | 25.7 | 22.2% | 1.5 | 2.92 | 1 |
| knapsack | 66.0 | 68.3 | 62.4 | 99.1% | 1 | 8.51 | 0 |
| tsp | 48.7 | 51.0 | 45.3 | 97.7% | 1 | 1.22 | 0 |
| scheduling | 0.0 | 98.9 | 98.5 | 98.9% | 1 | 0.0 | 2 |
| coloring (held out) | 0.0 | 41.6 | 40.0 | 41.6% | 0.5 | 0.0 | 2 |

## Crashes

- binpack1d r1: `timed out after 3600s`
- scheduling r0: `timed out after 3600s`
- scheduling r1: `timed out after 3600s`
- coloring r0: `timed out after 3600s`
- coloring r1: `timed out after 3600s`
