# Meta-evaluation: score 13.3

Strategy `/home/ubuntu/helix_evolve_run/meta_runs/outer-20261017-164239/candidates/c004`; 5 generations × 2 repeats; 67.5 min, 633 model calls.

Score = 0.6 × final + 0.4 × AUC, both measured beyond each problem's hidden textbook baseline (0) toward the reference (100).

| Problem | Score | Final, beyond baseline | AUC, beyond baseline | Final test progress (from Code Zero) | 90% by gen | Spread | Crashes |
|---|---|---|---|---|---|---|---|
| binpack1d | -11.6 | -27.5 | 12.3 | -7.2% | 1.5 | 18.84 | 0 |
| knapsack | 18.3 | 9.3 | 31.7 | 97.4% | 1 | 25.58 | 0 |
| tsp | 46.9 | 48.3 | 44.8 | 97.5% | 1 | 2.29 | 0 |
| scheduling | -0.6 | -9.8 | 13.2 | 98.1% | 1 | 7.21 | 0 |
| coloring (held out) | -1.2 | -5.8 | 5.6 | 58.7% | 4 | 12.03 | 0 |
