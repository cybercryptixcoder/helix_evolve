# e5a_base32

Does the base setup (plan: planner + mutations from a population, no notes) beat the plainest loop (floor) and mutations alone (population)? Experiment 2's setups again, 8 seeds in all, with the exact circle check from the start. This half: seeds [1, 2, 3, 4], on the VM; e5a and e5b are read together.

Problem `circles` {'n': 32}; 15 rounds; 10 s of CPU per program; seeds [1, 2, 3, 4]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: v4's mutation loop alone: parents sampled by rank, another strong program for ideas
- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: v4's two loops without memory (v4's 'control')

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 |
|---|---|---|---|
| floor | 2.9228190 [2.9183878, 2.9272501] | (1 of 2 seeds so far) | (1 of 2 seeds so far) |
| population | 2.9033762 [2.9324576, 2.8742948] | (1 of 2 seeds so far) | (1 of 2 seeds so far) |
| plan | (1 of 2 seeds so far) | (1 of 2 seeds so far) | (1 of 2 seeds so far) |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s1 | 91 | 2.931108889 | 0 | 515,701 | mutation 19 | mutation 100% |
| floor-s2 (running) | 49 | 2.927250146 | 3 | 313,607 | mutation 11 | mutation 100% |
| population-s1 | 91 | 2.933449712 | 4 | 624,911 | mutation 16 | mutation 100% |
| population-s2 (running) | 38 | 2.917225422 | 1 | 243,786 | mutation 13 | mutation 100% |
| plan-s1 | 91 | 2.939572768 | 8 | 928,631 | mutation 5, planned 10 | mutation 49%, planned 51% |
| plan-s2 (running) | 14 | 2.939572768 | 1 | 69,256 | mutation 3, planned 1 | mutation 100%, planned 0% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (2.93794) | within 1e-9 of the best known (2.939572771205, Packomania) (2.939572770205) |
|---|---|---|
| floor | -, - | -, - |
| population | -, - | -, - |
| plan | 20, 10 | -, - |

## Published values (for scale)

- AlphaEvolve: 2.93794
- within 1e-9 of the best known (2.939572771205, Packomania): 2.939572770205
