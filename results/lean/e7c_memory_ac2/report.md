# e7c_memory_ac2

Experiment 7 on AC2: does the best program's path beat no memory?

Problem `ac2` {'max_n': 50000}; 30 rounds; 30 s of CPU per program; seeds [1, 2, 3, 4, 5]. Arms:

- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: the base setup, no memory; seeds 1-3 are experiment 3's plan runs
- **plan+path**: `--planned 3 --mutations 3 --parents population --no-notes --path`: the same, and the planner sees the best program's path

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 | 120 | 150 | 180 |
|---|---|---|---|---|---|---|
| plan | 0.8729457 [0.8481534, 0.8885207, 0.8821630] | 0.8778393 [0.8532208, 0.8981204, 0.8821765] | 0.8780278 [0.8533816, 0.8985229, 0.8821789] | 0.8780519 [0.8534226, 0.8985483, 0.8821849] | 0.8781746 [0.8534230, 0.8985610, 0.8825398] | 0.8877051 [0.8820146, 0.8985610, 0.8825398] |
| plan+path | 0.8702697 [0.8236741, 0.8825398, 0.9045952] | 0.8963519 [0.8988234, 0.8825398, 0.9076925] | 0.9003334 [0.9106662, 0.8825398, 0.9077941] | (2 of 3 seeds so far) | (1 of 3 seeds so far) | - |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| plan-s1 | 181 | 0.882014551 | 4 | 1,502,805 | mutation 23, planned 32 | mutation 78%, planned 22% |
| plan-s2 | 181 | 0.898561004 | 7 | 1,444,735 | mutation 21, planned 23 | mutation 61%, planned 39% |
| plan-s3 | 181 | 0.882539783 | 11 | 1,696,232 | mutation 16, planned 22 | mutation 64%, planned 36% |
| plan+path-s1 (running) | 142 | 0.913910763 | 10 | 1,173,864 | mutation 16, planned 24 | mutation 71%, planned 29% |
| plan+path-s2 (running) | 103 | 0.882539783 | 8 | 690,602 | planned 3, mutation 5 | planned 93%, mutation 7% |
| plan+path-s3 (running) | 162 | 0.909812220 | 16 | 1,386,812 | mutation 13, planned 17 | mutation 58%, planned 42% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (May 2025) (0.8962) | OpenEvolve (TTT-Discover Table 2) (0.9449) | ThetaEvolve with RL (0.9469) |
|---|---|---|---|
| plan | -, 44, - | -, -, - | -, -, - |
| plan+path | 57, -, 14 | -, -, - | -, -, - |

## Published values (for scale)

- AlphaEvolve (May 2025): 0.8962
- OpenEvolve (TTT-Discover Table 2): 0.9449
- ThetaEvolve with RL: 0.9469
