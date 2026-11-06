# e3_core_ac2

Experiment 1 on the hard problem: the second autocorrelation inequality (at most 50,000 steps), where Helix's earlier versions plateaued at 0.9414 and v10.2 reached 0.9486 with the field's ideas.

Problem `ac2` {'max_n': 50000}; 30 rounds; 30 s of CPU per program; seeds [1, 2, 3]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: mutations from parents sampled by rank, with another strong program for ideas
- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: a planner without notes, plus mutations (the best setup on 32 circles)
- **plan+notes**: `--planned 3 --mutations 3 --parents population`: a planner with notes, plus mutations
- **planned-only**: `--planned 6 --mutations 0`: the planner with notes, no mutations

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 | 120 | 150 | 180 |
|---|---|---|---|---|---|---|
| floor | 0.8562031 [0.8493206, 0.8741074, 0.8451812] | 0.8569363 [0.8504512, 0.8750322, 0.8453255] | 0.8603433 [0.8505192, 0.8751068, 0.8554041] | 0.8655160 [0.8505907, 0.8751216, 0.8708356] | 0.8905954 [0.9206187, 0.8751218, 0.8760456] | 0.9021604 [0.9221986, 0.8751273, 0.9091554] |
| population | 0.8578876 [0.8552881, 0.8588648, 0.8595101] | 0.8640497 [0.8664758, 0.8645169, 0.8611563] | 0.8674057 [0.8725828, 0.8649034, 0.8647310] | 0.8698141 [0.8755774, 0.8654622, 0.8684028] | 0.8711880 [0.8788215, 0.8656068, 0.8691359] | 0.8807183 [0.9067884, 0.8656385, 0.8697279] |
| plan | 0.8729457 [0.8481534, 0.8885207, 0.8821630] | 0.8778393 [0.8532208, 0.8981204, 0.8821765] | (2 of 3 seeds so far) | - | - | - |
| plan+notes | 0.8645138 [0.8342909, 0.8823168, 0.8769338] | 0.8681062 [0.8398487, 0.8824528, 0.8820172] | 0.8755184 [0.8405528, 0.9039850, 0.8820173] | 0.8760264 [0.8415719, 0.9043089, 0.8821985] | 0.8864724 [0.8418962, 0.9044831, 0.9130379] | 0.8908275 [0.8424146, 0.9044938, 0.9255739] |
| planned-only | 0.8378496 [0.8461662, 0.8610315, 0.8063512] | 0.8499339 [0.8605171, 0.8804423, 0.8088423] | 0.8728476 [0.8964158, 0.8835804, 0.8385466] | 0.8730292 [0.8965464, 0.8837287, 0.8388126] | 0.8730313 [0.8965491, 0.8837287, 0.8388160] | 0.8765502 [0.9071054, 0.8837287, 0.8388166] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s1 | 181 | 0.922349711 | 4 | 933,851 | mutation 72 | mutation 100% |
| floor-s2 | 181 | 0.875127261 | 6 | 947,743 | mutation 69 | mutation 100% |
| floor-s3 | 181 | 0.911277415 | 17 | 873,227 | mutation 60 | mutation 100% |
| population-s1 | 181 | 0.906788434 | 7 | 1,416,824 | mutation 37 | mutation 100% |
| population-s2 | 181 | 0.865638543 | 3 | 1,329,609 | mutation 38 | mutation 100% |
| population-s3 | 181 | 0.869727924 | 3 | 1,282,441 | mutation 37 | mutation 100% |
| plan-s1 (running) | 104 | 0.853407452 | 2 | 776,422 | mutation 14, planned 18 | mutation 90%, planned 10% |
| plan-s2 (running) | 100 | 0.898545397 | 2 | 603,371 | mutation 16, planned 13 | mutation 61%, planned 39% |
| plan-s3 (running) | 89 | 0.882178887 | 6 | 715,081 | mutation 11, planned 15 | mutation 64%, planned 36% |
| plan+notes-s1 | 181 | 0.842414641 | 5 | 2,063,142 | mutation 19, planned 33 | mutation 71%, planned 29% |
| plan+notes-s2 | 181 | 0.904493821 | 5 | 1,673,120 | mutation 26, planned 18 | mutation 96%, planned 4% |
| plan+notes-s3 | 181 | 0.925573895 | 3 | 1,731,515 | mutation 15, planned 25 | mutation 49%, planned 51% |
| planned-only-s1 | 181 | 0.907105404 | 14 | 1,427,979 | planned 46 | planned 100% |
| planned-only-s2 | 181 | 0.883728731 | 5 | 1,446,212 | planned 46 | planned 100% |
| planned-only-s3 | 181 | 0.838816586 | 8 | 2,706,662 | planned 56 | planned 100% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (May 2025) (0.8962) | OpenEvolve (TTT-Discover Table 2) (0.9449) | ThetaEvolve with RL (0.9469) |
|---|---|---|---|
| floor | 128, -, 164 | -, -, - | -, -, - |
| population | 166, -, - | -, -, - | -, -, - |
| plan | -, 44, - | -, -, - | -, -, - |
| plan+notes | -, 76, 125 | -, -, - | -, -, - |
| planned-only | 88, -, - | -, -, - | -, -, - |

## Published values (for scale)

- AlphaEvolve (May 2025): 0.8962
- OpenEvolve (TTT-Discover Table 2): 0.9449
- ThetaEvolve with RL: 0.9469
