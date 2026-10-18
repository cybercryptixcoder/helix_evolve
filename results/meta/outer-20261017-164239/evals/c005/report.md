# Meta-evaluation: score 38.2

Strategy `/home/ubuntu/helix_evolve_run/meta_runs/outer-20261017-164239/candidates/c005`; 5 generations × 2 repeats; 59.0 min, 628 model calls.

Score = 0.6 × final + 0.4 × AUC, both measured beyond each problem's hidden textbook baseline (0) toward the reference (100).

| Problem | Score | Final, beyond baseline | AUC, beyond baseline | Final test progress (from Code Zero) | 90% by gen | Spread | Crashes |
|---|---|---|---|---|---|---|---|
| binpack1d | 18.2 | 19.6 | 16.0 | 32.4% | 3.5 | 1.46 | 0 |
| knapsack | 70.9 | 83.0 | 52.8 | 99.5% | 1 | 1.84 | 0 |
| tsp | 43.3 | 45.9 | 39.4 | 97.4% | 1 | 0.54 | 0 |
| scheduling | 20.5 | 28.9 | 8.0 | 98.8% | 1 | 10.38 | 0 |
| coloring (held out) | -0.1 | -14.7 | 21.7 | 55.2% | 1.5 | 5.85 | 0 |
