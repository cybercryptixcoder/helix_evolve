# e5b_base32

Does the base setup (plan: planner + mutations from a population, no notes) beat the plainest loop (floor) and mutations alone (population)? Experiment 2's setups again, 8 seeds in all, with the exact circle check from the start. This half: seeds [5, 6, 7, 8], on the cloud session; e5a and e5b are read together.

Problem `circles` {'n': 32}; 15 rounds; 10 s of CPU per program; seeds [5, 6, 7, 8]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: v4's mutation loop alone: parents sampled by rank, another strong program for ideas
- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: v4's two loops without memory (v4's 'control')

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 |
|---|---|---|---|
| floor | 2.9271281 [2.9333525, 2.9084070, 2.9335914, 2.9331614] | 2.9297462 [2.9334500, 2.9187804, 2.9335928, 2.9331614] | 2.9373162 [2.9395728, 2.9395728, 2.9335928, 2.9365263] |
| population | 2.8922168 [2.9147415, 2.9209233, 2.8178242, 2.9153781] | 2.9265753 [2.9294517, 2.9395728, 2.9173764, 2.9199002] | 2.9373994 [2.9308793, 2.9395728, 2.9395727, 2.9395728] |
| plan | 2.9332847 [2.9280828, 2.9395725, 2.9331614, 2.9323221] | 2.9377600 [2.9395724, 2.9395728, 2.9395728, 2.9323221] | 2.9395728 [2.9395728, 2.9395728, 2.9395728, 2.9395728] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s5 | 91 | 2.939572771 | 4 | 572,801 | mutation 22 | mutation 100% |
| floor-s6 | 91 | 2.939572771 | 1 | 395,056 | mutation 16 | mutation 100% |
| floor-s7 | 91 | 2.933592795 | 9 | 435,090 | mutation 18 | mutation 100% |
| floor-s8 | 91 | 2.936526264 | 3 | 482,858 | mutation 18 | mutation 100% |
| population-s5 | 91 | 2.930879253 | 5 | 775,229 | mutation 13 | mutation 100% |
| population-s6 | 91 | 2.939572768 | 12 | 665,305 | mutation 5 | mutation 100% |
| population-s7 | 91 | 2.939572742 | 2 | 661,841 | mutation 21 | mutation 100% |
| population-s8 | 91 | 2.939572768 | 4 | 735,071 | mutation 16 | mutation 100% |
| plan-s5 | 91 | 2.939572768 | 2 | 972,101 | mutation 11, planned 9 | mutation 100%, planned 0% |
| plan-s6 | 91 | 2.939572771 | 3 | 679,209 | mutation 5, planned 8 | mutation 88%, planned 12% |
| plan-s7 | 91 | 2.939572771 | 1 | 734,367 | mutation 8, planned 7 | mutation 87%, planned 13% |
| plan-s8 | 91 | 2.939572768 | 6 | 816,125 | mutation 7, planned 4 | mutation 100%, planned 0% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (2.93794) | within 1e-9 of the best known (2.939572771205, Packomania) (2.939572770205) |
|---|---|---|
| floor | 82, 74, -, - | 82, 80, -, - |
| population | -, 38, 86, 68 | -, -, -, - |
| plan | 58, 15, 39, 68 | -, 47, 54, - |

## Published values (for scale)

- AlphaEvolve: 2.93794
- within 1e-9 of the best known (2.939572771205, Packomania): 2.939572770205
