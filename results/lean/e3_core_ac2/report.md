# e3_core_ac2

Experiment 1 on the hard problem: the second autocorrelation inequality (at most 50,000 steps), where Helix's earlier versions plateaued at 0.9414 and v10.2 reached 0.9486 with the field's ideas.

Problem `ac2` {'max_n': 50000}; 30 rounds; 30 s of CPU per program; seeds [1, 2, 3]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: mutations from parents sampled by rank, with another strong program for ideas
- **plan+notes**: `--planned 3 --mutations 3 --parents population`: a planner with notes, plus mutations
- **planned-only**: `--planned 6 --mutations 0`: the planner with notes, no mutations

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 |
|---|---|---|
| floor | 0.8493206 [0.8493206] | 0.8504512 [0.8504512] |
| population | 0.8552881 [0.8552881] | 0.8664758 [0.8664758] |
| plan+notes | 0.8342909 [0.8342909] | - |
| planned-only | - | - |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s1 (running) | 62 | 0.850460888 | 4 | 245,177 | mutation 25 | mutation 100% |
| population-s1 (running) | 61 | 0.866475822 | 5 | 408,096 | mutation 13 | mutation 100% |
| plan+notes-s1 (running) | 52 | 0.839676870 | 2 | 360,566 | mutation 6, planned 7 | mutation 72%, planned 28% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (May 2025) (0.8962) | OpenEvolve (TTT-Discover Table 2) (0.9449) | ThetaEvolve with RL (0.9469) |
|---|---|---|---|
| floor | - | - | - |
| population | - | - | - |
| plan+notes | - | - | - |
| planned-only |  |  |  |

## Published values (for scale)

- AlphaEvolve (May 2025): 0.8962
- OpenEvolve (TTT-Discover Table 2): 0.9449
- ThetaEvolve with RL: 0.9469
