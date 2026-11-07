# e7b_memory32

Experiment 7 on 32 circles: does the best program's path beat no memory?

Problem `circles` {'n': 32}; 15 rounds; 10 s of CPU per program; seeds [5, 6, 7, 8]. Arms:

- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: the base setup, no memory; experiment 5's plan runs (seeds 5-8)
- **plan+path**: `--planned 3 --mutations 3 --parents population --no-notes --path`: the same, and the planner sees the best program's path

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 |
|---|---|---|---|
| plan | 2.9332847 [2.9280828, 2.9395725, 2.9331614, 2.9323221] | 2.9377600 [2.9395724, 2.9395728, 2.9395728, 2.9323221] | 2.9395728 [2.9395728, 2.9395728, 2.9395728, 2.9395728] |
| plan+path | 2.9252620 [2.8823297, 2.9395728, 2.9395728, 2.9395728] | 2.9395728 [2.9395727, 2.9395728, 2.9395728, 2.9395728] | 2.9395728 [2.9395728, 2.9395728, 2.9395728, 2.9395728] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| plan-s5 | 91 | 2.939572768 | 2 | 972,101 | mutation 11, planned 9 | mutation 100%, planned 0% |
| plan-s6 | 91 | 2.939572771 | 3 | 679,209 | mutation 5, planned 8 | mutation 88%, planned 12% |
| plan-s7 | 91 | 2.939572771 | 1 | 734,367 | mutation 8, planned 7 | mutation 87%, planned 13% |
| plan-s8 | 91 | 2.939572768 | 6 | 816,125 | mutation 7, planned 4 | mutation 100%, planned 0% |
| plan+path-s5 | 91 | 2.939572771 | 5 | 951,207 | mutation 5, planned 9 | mutation 99%, planned 1% |
| plan+path-s6 | 91 | 2.939572771 | 5 | 875,368 | mutation 4, planned 6 | mutation 99%, planned 1% |
| plan+path-s7 | 91 | 2.939572771 | 5 | 989,870 | mutation 8, planned 9 | mutation 88%, planned 12% |
| plan+path-s8 | 91 | 2.939572771 | 2 | 947,354 | mutation 5, planned 6 | mutation 94%, planned 6% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | AlphaEvolve (2.93794) | within 1e-9 of the best known (2.939572771205, Packomania) (2.939572770205) |
|---|---|---|
| plan | 58, 15, 39, 68 | -, 47, 54, - |
| plan+path | 58, 17, 14, 18 | 85, 17, 19, 34 |

## Published values (for scale)

- AlphaEvolve: 2.93794
- within 1e-9 of the best known (2.939572771205, Packomania): 2.939572770205
