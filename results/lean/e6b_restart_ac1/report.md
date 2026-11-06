# e6b_restart_ac1

Do restarts help? Experiments 1-4 showed that which region a run ends in matters more than how well it climbs. On the past runs, the best of 3 short runs beat one long run on AC1 and 32 circles, but not on AC2, where late jumps matter. A restart when a line stalls might get both.

Problem `ac1` {'max_n': 30000}; 30 rounds; 20 s of CPU per program; seeds [1, 2, 3, 4, 5]. Arms:

- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: the base setup; seeds 1-3 are e4_core_ac1's plan runs (the same code for this problem)
- **plan+restart**: `--planned 3 --mutations 3 --parents population --no-notes --restart 5`: the same, and a new line from Code Zero after 5 rounds without a gain of 1e-5 (relative)

## Best value (lower is better) after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 | 120 | 150 | 180 |
|---|---|---|---|---|---|---|
| plan | 1.5442613 [1.5945999, 1.5261105, 1.5147132, 1.5193678, 1.5665152] | 1.5304644 [1.5900764, 1.5142842, 1.5137017, 1.5135562, 1.5207033] | 1.5289470 [1.5899400, 1.5115206, 1.5137017, 1.5131400, 1.5164329] | 1.5285339 [1.5899310, 1.5095158, 1.5137013, 1.5130974, 1.5164238] | 1.5285022 [1.5898899, 1.5095158, 1.5137013, 1.5130953, 1.5163085] | 1.5282382 [1.5887815, 1.5094189, 1.5137013, 1.5130945, 1.5161947] |
| plan+restart | 1.5348212 [1.5106257, 1.5108030, 1.6198137, 1.5147345, 1.5181293] | 1.5263267 [1.5089401, 1.5106798, 1.5824509, 1.5142139, 1.5153490] | 1.5195798 [1.5088583, 1.5101006, 1.5498338, 1.5137967, 1.5153094] | 1.5132752 [1.5088466, 1.5101006, 1.5184516, 1.5136680, 1.5153092] | 1.5127403 [1.5088466, 1.5101006, 1.5157868, 1.5136580, 1.5153092] | 1.5125382 [1.5088466, 1.5101006, 1.5157868, 1.5136580, 1.5142989] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| plan-s1 | 181 | 1.588781467 | 5 | 1,451,554 | mutation 24, planned 26 | mutation 97%, planned 3% |
| plan-s2 | 181 | 1.509418863 | 15 | 1,289,285 | mutation 12, planned 13 | mutation 91%, planned 9% |
| plan-s3 | 181 | 1.513701307 | 18 | 1,365,947 | mutation 17, planned 17 | mutation 75%, planned 25% |
| plan-s4 | 181 | 1.513094513 | 6 | 1,505,976 | mutation 20, planned 25 | mutation 70%, planned 30% |
| plan-s5 | 181 | 1.516194714 | 6 | 1,235,413 | mutation 12, planned 19 | mutation 76%, planned 24% |
| plan+restart-s1 | 182 | 1.508846626 | 9 | 1,132,221 | mutation 11, planned 7 | mutation 63%, planned 37% |
| plan+restart-s2 | 182 | 1.510100650 | 16 | 1,444,015 | mutation 12, planned 18 | mutation 79%, planned 21% |
| plan+restart-s3 | 182 | 1.515786831 | 7 | 1,512,188 | mutation 16, planned 16 | mutation 84%, planned 16% |
| plan+restart-s4 | 182 | 1.513658031 | 28 | 1,375,652 | mutation 5, planned 20 | mutation 66%, planned 34% |
| plan+restart-s5 | 182 | 1.514298899 | 4 | 1,096,248 | mutation 17, planned 12 | mutation 79%, planned 21% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | Best of 25,600 (gpt-oss-120b) (1.51004) | Best human (1.50973) | OpenEvolve (1.50719) | ThetaEvolve (1.50681) | AlphaEvolve (May 2025) (1.5053) | AlphaEvolve V2 (1.50317) | TTT-Discover (gpt-oss-120b) (1.50287) |
|---|---|---|---|---|---|---|---|
| plan | -, 107, -, -, - | -, 113, -, -, - | -, -, -, -, - | -, -, -, -, - | -, -, -, -, - | -, -, -, -, - | -, -, -, -, - |
| plan+restart | 49, -, -, -, - | 49, -, -, -, - | -, -, -, -, - | -, -, -, -, - | -, -, -, -, - | -, -, -, -, - | -, -, -, -, - |

## Published values (for scale)

- Best of 25,600 (gpt-oss-120b): 1.51004
- Best human: 1.50973
- OpenEvolve: 1.50719
- ThetaEvolve: 1.50681
- AlphaEvolve (May 2025): 1.5053
- AlphaEvolve V2: 1.50317
- TTT-Discover (gpt-oss-120b): 1.50287
