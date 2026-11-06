# e5a_base32

Does the base setup (plan: planner + mutations from a population, no notes) beat the plainest loop (floor) and mutations alone (population)? Experiment 2's setups again, 8 seeds in all, with the exact circle check from the start. This half: seeds [1, 2, 3, 4], on the VM; e5a and e5b are read together.

Problem `circles` {'n': 32}; 15 rounds; 10 s of CPU per program; seeds [1, 2, 3, 4]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: v4's mutation loop alone: parents sampled by rank, another strong program for ideas
- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: v4's two loops without memory (v4's 'control')

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 |
|---|---|---|---|
| floor | 2.9233765 [2.9183878, 2.9272501, 2.9349663, 2.9129019] | 2.9286999 [2.9233665, 2.9272501, 2.9349663, 2.9292167] | 2.9306435 [2.9311089, 2.9272501, 2.9349663, 2.9292487] |
| population | 2.9152654 [2.9324576, 2.8742948, 2.9228948, 2.9314146] | 2.9297605 [2.9334497, 2.9217198, 2.9324579, 2.9314146] | 2.9305417 [2.9334497, 2.9228088, 2.9344937, 2.9314146] |
| plan | 2.9356229 [2.9391002, 2.9395728, 2.9242461, 2.9395727] | 2.9366135 [2.9395728, 2.9395728, 2.9277356, 2.9395728] | 2.9395728 [2.9395728, 2.9395728, 2.9395728, 2.9395728] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s1 | 91 | 2.931108889 | 0 | 515,701 | mutation 19 | mutation 100% |
| floor-s2 | 91 | 2.927250146 | 3 | 612,451 | mutation 12 | mutation 100% |
| floor-s3 | 91 | 2.934966263 | 1 | 448,538 | mutation 20 | mutation 100% |
| floor-s4 | 91 | 2.929248662 | 14 | 437,736 | mutation 18 | mutation 100% |
| population-s1 | 91 | 2.933449712 | 4 | 624,911 | mutation 16 | mutation 100% |
| population-s2 | 91 | 2.922808763 | 2 | 656,823 | mutation 23 | mutation 100% |
| population-s3 | 91 | 2.934493727 | 0 | 614,104 | mutation 15 | mutation 100% |
| population-s4 | 91 | 2.931414584 | 4 | 662,297 | mutation 13 | mutation 100% |
| plan-s1 | 91 | 2.939572768 | 8 | 928,631 | mutation 5, planned 10 | mutation 49%, planned 51% |
| plan-s2 | 91 | 2.939572768 | 4 | 669,349 | mutation 3, planned 3 | mutation 100%, planned 0% |
| plan-s3 | 91 | 2.939572768 | 9 | 934,052 | planned 8, mutation 7 | planned 99%, mutation 1% |
| plan-s4 | 91 | 2.939572771 | 1 | 892,265 | mutation 8, planned 6 | mutation 93%, planned 7% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (2.93794) | within 1e-9 of the best known (2.939572771205, Packomania) (2.939572770205) |
|---|---|---|
| floor | -, -, -, - | -, -, -, - |
| population | -, -, -, - | -, -, -, - |
| plan | 20, 10, 65, 10 | -, -, -, 43 |

## Published values (for scale)

- AlphaEvolve: 2.93794
- within 1e-9 of the best known (2.939572771205, Packomania): 2.939572770205
