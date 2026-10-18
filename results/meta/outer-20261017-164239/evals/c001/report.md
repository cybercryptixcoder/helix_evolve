# Meta-evaluation: score 27.6

Strategy `/home/ubuntu/helix_evolve_run/meta_runs/outer-20261017-164239/candidates/c001`; 5 generations × 2 repeats; 46.2 min, 631 model calls.

Score = 0.6 × final + 0.4 × AUC, both measured beyond each problem's hidden textbook baseline (0) toward the reference (100).

| Problem | Score | Final, beyond baseline | AUC, beyond baseline | Final test progress (from Code Zero) | 90% by gen | Spread | Crashes |
|---|---|---|---|---|---|---|---|
| binpack1d | -5.2 | -19.1 | 15.6 | -0.2% | 2 | 15.19 | 0 |
| knapsack | 63.1 | 75.2 | 45.1 | 99.3% | 1 | 1.64 | 0 |
| tsp | 43.5 | 40.0 | 48.7 | 97.1% | 1 | 3.98 | 0 |
| scheduling | 9.2 | 0.3 | 22.4 | 98.3% | 1 | 9.52 | 0 |
| coloring (held out) | -6.5 | -15.2 | 6.7 | 55.0% | 3.5 | 7.83 | 0 |
