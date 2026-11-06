# e2_core32

Experiment 1 again on a harder instance: 32 circles, where AlphaEvolve (2.93794) stopped short of the best known (2.93957, FICO Xpress 2026). (Cut from 40 to 15 rounds on Nov 5: two setups reached the best known packing within 7 rounds; this problem also has a ceiling within reach.)

Problem `circles` {'n': 32}; 15 rounds; 10 s of CPU per program; seeds [1, 2, 3]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: v4's mutation loop alone: parents sampled by rank, another strong program for ideas
- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: v4's two loops without memory (v4's 'control')
- **plan+notes**: `--planned 3 --mutations 3 --parents population`: v4's two loops with plain notes of every experiment for the planner
- **planned-only**: `--planned 6 --mutations 0`: the planner with notes, no mutation loop

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 |
|---|---|---|---|
| floor | 2.8831880 [2.9125616, 2.9395696, 2.7974329] | 2.8929743 [2.9286290, 2.9395727, 2.8107213] | 2.8952151 [2.9353198, 2.9395728, 2.8107529] |
| population | 2.9043704 [2.9395728, 2.8369051, 2.9366332] | 2.9353722 [2.9395728, 2.9269710, 2.9395728] | 2.9395728 [2.9395728, 2.9395728, 2.9395728] |
| plan | 2.9395728 [2.9395728, 2.9395728, 2.9395728] | 2.9395728 [2.9395728, 2.9395728, 2.9395728] | 2.9395728 [2.9395728, 2.9395728, 2.9395728] |
| plan+notes | 2.9226786 [2.9395727, 2.9395728, 2.8888903] | 2.9269158 [2.9395728, 2.9395728, 2.9016018] | 2.9290624 [2.9395728, 2.9395728, 2.9080418] |
| planned-only | 2.9289454 [2.9335927, 2.9272501, 2.9259934] | 2.9309521 [2.9335927, 2.9272501, 2.9320135] | 2.9381563 [2.9395727, 2.9353233, 2.9395728] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s1 | 91 | 2.935319796 | 5 | 428,098 | mutation 19 | mutation 100% |
| floor-s2 | 91 | 2.939572771 | 5 | 341,448 | mutation 23 | mutation 100% |
| floor-s3 | 91 | 2.810752881 | 1 | 474,875 | mutation 32 | mutation 100% |
| population-s1 | 91 | 2.939572770 | 8 | 831,830 | mutation 11 | mutation 100% |
| population-s2 | 91 | 2.939572771 | 15 | 688,295 | mutation 11 | mutation 100% |
| population-s3 | 91 | 2.939572771 | 4 | 808,034 | mutation 11 | mutation 100% |
| plan-s1 | 91 | 2.939572771 | 6 | 877,179 | mutation 3, planned 8 | mutation 98%, planned 2% |
| plan-s2 | 91 | 2.939572771 | 2 | 798,331 | mutation 7, planned 7 | mutation 89%, planned 11% |
| plan-s3 | 91 | 2.939572771 | 3 | 816,907 | mutation 9, planned 2 | mutation 100%, planned 0% |
| plan+notes-s1 | 91 | 2.939572771 | 12 | 747,953 | mutation 7, planned 10 | mutation 98%, planned 2% |
| plan+notes-s2 | 91 | 2.939572771 | 10 | 1,083,005 | mutation 6, planned 9 | mutation 89%, planned 11% |
| plan+notes-s3 | 91 | 2.909496554 | 11 | 1,011,262 | mutation 7, planned 11 | mutation 97%, planned 3% |
| planned-only-s1 | 91 | 2.939572707 | 5 | 733,167 | planned 17 | planned 100% |
| planned-only-s2 | 91 | 2.935323348 | 23 | 794,942 | planned 13 | planned 100% |
| planned-only-s3 | 91 | 2.939572771 | 5 | 705,076 | planned 17 | planned 100% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (2.93794) | within 1e-9 of the best known (2.939572771205, Packomania) (2.939572770205) |
|---|---|---|
| floor | -, 26, - | -, 87, - |
| population | 28, 71, 44 | 39, 89, 64 |
| plan | 29, 16, 16 | 43, 20, 34 |
| plan+notes | 29, 9, - | 66, 24, - |
| planned-only | 74, -, 66 | -, -, 66 |

## Published values (for scale)

- AlphaEvolve: 2.93794
- within 1e-9 of the best known (2.939572771205, Packomania): 2.939572770205
