# e7c_memory_ac2

Experiment 7 on AC2: does the best program's path beat no memory?

Problem `ac2` {'max_n': 50000}; 30 rounds; 30 s of CPU per program; seeds [1, 2, 3, 4, 5]. Arms:

- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: the base setup, no memory; seeds 1-3 are experiment 3's plan runs
- **plan+path**: `--planned 3 --mutations 3 --parents population --no-notes --path`: the same, and the planner sees the best program's path

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 | 120 | 150 | 180 |
|---|---|---|---|---|---|---|
| plan | 0.8721569 [0.8481534, 0.8885207, 0.8821630, 0.8474112, 0.8945362] | (4 of 5 seeds so far) | (4 of 5 seeds so far) | (4 of 5 seeds so far) | (3 of 5 seeds so far) | (3 of 5 seeds so far) |
| plan+path | 0.8759309 [0.8236741, 0.8825398, 0.9045952, 0.8929143] | 0.8975474 [0.8988234, 0.8825398, 0.9076925, 0.9011336] | 0.9005345 [0.9106662, 0.8825398, 0.9077941, 0.9011378] | (3 of 4 seeds so far) | (3 of 4 seeds so far) | (3 of 4 seeds so far) |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| plan-s1 | 181 | 0.882014551 | 4 | 1,502,805 | mutation 23, planned 32 | mutation 78%, planned 22% |
| plan-s2 | 181 | 0.898561004 | 7 | 1,444,735 | mutation 21, planned 23 | mutation 61%, planned 39% |
| plan-s3 | 181 | 0.882539783 | 11 | 1,696,232 | mutation 16, planned 22 | mutation 64%, planned 36% |
| plan-s4 (running) | 147 | 0.929509851 | 4 | 1,440,307 | mutation 15, planned 26 | mutation 81%, planned 19% |
| plan-s5 (running) | 58 | 0.894536176 | 1 | 419,868 | mutation 2, planned 6 | mutation 76%, planned 24% |
| plan+path-s1 | 181 | 0.914014913 | 10 | 1,571,816 | mutation 21, planned 31 | mutation 71%, planned 29% |
| plan+path-s2 | 181 | 0.882539783 | 10 | 1,300,954 | planned 3, mutation 6 | planned 93%, mutation 7% |
| plan+path-s3 | 181 | 0.909830431 | 18 | 1,561,894 | mutation 17, planned 19 | mutation 58%, planned 42% |
| plan+path-s4 (running) | 107 | 0.901137832 | 10 | 669,827 | mutation 5, planned 15 | mutation 85%, planned 15% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (May 2025) (0.8962) | OpenEvolve (TTT-Discover Table 2) (0.9449) | ThetaEvolve with RL (0.9469) |
|---|---|---|---|
| plan | -, 44, -, 51, - | -, -, -, -, - | -, -, -, -, - |
| plan+path | 57, -, 14, 45 | -, -, -, - | -, -, -, - |

## Published values (for scale)

- AlphaEvolve (May 2025): 0.8962
- OpenEvolve (TTT-Discover Table 2): 0.9449
- ThetaEvolve with RL: 0.9469
