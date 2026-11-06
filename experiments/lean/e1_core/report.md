# e1_core

Which parts of v4's core help? From the plainest loop (mutate the best program) upward: a population, a planner, notes for the planner; and is the mutation loop needed next to the planner? (Cut from 40 to 25 rounds on Nov 5: the plainest loop reached the known optimum by round 11, so later rounds tell nothing.)

Problem `circles` {'n': 26}; 25 rounds; 10 s of CPU per program; seeds [1, 2, 3]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: v4's mutation loop alone: parents sampled by rank, another strong program for ideas
- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: v4's two loops without memory (v4's 'control')
- **plan+notes**: `--planned 3 --mutations 3 --parents population`: v4's two loops with plain notes of every experiment for the planner
- **planned-only**: `--planned 6 --mutations 0`: the planner with notes, no mutation loop

## Best score after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 120 |
|---|---|---|---|
| floor | 2.630452 [2.6244, 2.6360, 2.6310] | 2.634313 [2.6360, 2.6360, 2.6310] | 2.634313 [2.6360, 2.6360, 2.6310] |
| population | 2.612500 [2.5753, 2.6317, 2.6304] | 2.625226 [2.6078, 2.6360, 2.6319] | 2.628594 [2.6138, 2.6360, 2.6360] |
| plan | 2.630864 [2.6299, 2.6360, 2.6267] | 2.633945 [2.6299, 2.6360, 2.6360] | 2.634232 [2.6307, 2.6360, 2.6360] |
| plan+notes | 2.628064 [2.6343, 2.6343, 2.6156] | 2.633854 [2.6343, 2.6360, 2.6313] | 2.635420 [2.6343, 2.6360, 2.6360] |
| planned-only | 2.631583 [2.6306, 2.6343, 2.6299] | 2.633700 [2.6308, 2.6343, 2.6360] | 2.635000 [2.6330, 2.6360, 2.6360] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s1 | 151 | 2.635983067 | 7 | 705,351 | mutation 17 | mutation 100% |
| floor-s2 | 151 | 2.635983085 | 5 | 1,034,873 | mutation 18 | mutation 100% |
| floor-s3 | 151 | 2.630972267 | 0 | 824,959 | mutation 24 | mutation 100% |
| population-s1 | 151 | 2.629242877 | 3 | 1,550,874 | mutation 25 | mutation 100% |
| population-s2 | 151 | 2.635983082 | 4 | 1,654,234 | mutation 20 | mutation 100% |
| population-s3 | 151 | 2.635982821 | 2 | 1,325,508 | mutation 12 | mutation 100% |
| plan-s1 | 151 | 2.630729705 | 9 | 1,476,200 | mutation 13, planned 11 | mutation 82%, planned 18% |
| plan-s2 | 151 | 2.635983085 | 44 | 1,579,441 | mutation 2, planned 11 | mutation 87%, planned 13% |
| plan-s3 | 151 | 2.635983085 | 1 | 1,646,445 | mutation 12, planned 10 | mutation 88%, planned 12% |
| plan+notes-s1 | 151 | 2.634292402 | 9 | 1,733,680 | mutation 8, planned 8 | mutation 96%, planned 4% |
| plan+notes-s2 | 151 | 2.635983085 | 5 | 1,630,348 | mutation 9, planned 6 | mutation 99%, planned 1% |
| plan+notes-s3 | 151 | 2.635983085 | 3 | 1,845,190 | mutation 14, planned 15 | mutation 99%, planned 1% |
| planned-only-s1 | 151 | 2.635983059 | 10 | 1,504,692 | planned 16 | planned 100% |
| planned-only-s2 | 151 | 2.635983085 | 5 | 1,270,656 | planned 19 | planned 100% |
| planned-only-s3 | 151 | 2.635983085 | 6 | 1,580,771 | planned 21 | planned 100% |

## Published values (for scale)

- AlphaEvolve (zero tolerance): 2.63586276
- ShinkaEvolve (exact re-check): 2.63597770931127
