# e4_core_ac1

The core's setups on the first autocorrelation inequality (minimise C; at most 30,000 steps), where the published LLM systems spread from 1.5100 (best of 25,600) to 1.5029 (TTT-Discover).

Problem `ac1` {'max_n': 30000}; 30 rounds; 20 s of CPU per program; seeds [1, 2, 3]. Arms:

- **floor**: `--planned 0 --mutations 6 --parents best --no-inspiration --no-notes`: the model sees the best program and writes a better one, 6 times a round
- **population**: `--planned 0 --mutations 6 --parents population --no-notes`: mutations from parents sampled by rank, with another strong program for ideas
- **plan**: `--planned 3 --mutations 3 --parents population --no-notes`: a planner without notes, plus mutations (the best setup on 32 circles)
- **plan+notes**: `--planned 3 --mutations 3 --parents population`: a planner with notes, plus mutations
- **planned-only**: `--planned 6 --mutations 0`: the planner with notes, no mutations

## Best value (lower is better) after N programs (mean over seeds; each seed in brackets)

| Arm | 30 | 60 | 90 | 120 | 150 | 180 |
|---|---|---|---|---|---|---|
| floor | 1.5498406 [1.5279468, 1.5809537, 1.5406213] | 1.5404088 [1.5141987, 1.5809036, 1.5261241] | 1.5393193 [1.5133150, 1.5809036, 1.5237392] | 1.5181050 [1.5132097, 1.5173927, 1.5237126] | 1.5178925 [1.5132020, 1.5168107, 1.5236649] | 1.5178694 [1.5131989, 1.5167515, 1.5236577] |
| population | 1.5510518 [1.5312386, 1.5467327, 1.5751842] | 1.5388570 [1.5186613, 1.5227507, 1.5751589] | 1.5197039 [1.5182454, 1.5225492, 1.5183171] | 1.5166545 [1.5108006, 1.5208457, 1.5183171] | 1.5156206 [1.5104008, 1.5206496, 1.5158115] | 1.5153729 [1.5104008, 1.5204308, 1.5152869] |
| plan | 1.5451412 [1.5945999, 1.5261105, 1.5147132] | 1.5393541 [1.5900764, 1.5142842, 1.5137017] | 1.5383874 [1.5899400, 1.5115206, 1.5137017] | 1.5377160 [1.5899310, 1.5095158, 1.5137013] | 1.5377023 [1.5898899, 1.5095158, 1.5137013] | 1.5373005 [1.5887815, 1.5094189, 1.5137013] |
| plan+notes | 1.5294567 [1.5269367, 1.5441878, 1.5172455] | 1.5252282 [1.5245499, 1.5345565, 1.5165783] | 1.5215665 [1.5234876, 1.5250823, 1.5161296] | 1.5211475 [1.5230199, 1.5244333, 1.5159894] | 1.5208681 [1.5227404, 1.5239522, 1.5159119] | 1.5207507 [1.5225429, 1.5237973, 1.5159119] |
| planned-only | 1.5348548 [1.5204008, 1.5454098, 1.5387540] | 1.5236614 [1.5189933, 1.5390441, 1.5129468] | 1.5235749 [1.5189637, 1.5389440, 1.5128169] | 1.5235445 [1.5189623, 1.5389369, 1.5127344] | 1.5235267 [1.5189622, 1.5389347, 1.5126833] | 1.5235131 [1.5189610, 1.5389346, 1.5126439] |

## Per run

| Run | Programs | Best | Failed | Tokens | Records by role | Share of gain by role |
|---|---|---|---|---|---|---|
| floor-s1 | 181 | 1.513198944 | 2 | 707,919 | mutation 53 | mutation 100% |
| floor-s2 | 181 | 1.516751306 | 10 | 697,212 | mutation 55 | mutation 100% |
| floor-s3 | 181 | 1.521721997 | 7 | 819,893 | mutation 53 | mutation 100% |
| population-s1 | 181 | 1.510400806 | 16 | 1,285,875 | mutation 32 | mutation 100% |
| population-s2 | 181 | 1.520430843 | 3 | 1,422,908 | mutation 47 | mutation 100% |
| population-s3 | 181 | 1.515286949 | 3 | 1,299,535 | mutation 27 | mutation 100% |
| plan-s1 | 181 | 1.588781467 | 5 | 1,451,554 | mutation 24, planned 26 | mutation 97%, planned 3% |
| plan-s2 | 181 | 1.509418863 | 15 | 1,289,285 | mutation 12, planned 13 | mutation 91%, planned 9% |
| plan-s3 | 181 | 1.513701307 | 18 | 1,365,947 | mutation 17, planned 17 | mutation 75%, planned 25% |
| plan+notes-s1 | 181 | 1.522540073 | 2 | 2,160,127 | mutation 16, planned 49 | mutation 86%, planned 14% |
| plan+notes-s2 | 181 | 1.523759880 | 5 | 1,547,782 | mutation 24, planned 31 | mutation 92%, planned 8% |
| plan+notes-s3 | 181 | 1.515911871 | 8 | 1,606,273 | mutation 24, planned 27 | mutation 98%, planned 2% |
| planned-only-s1 | 181 | 1.518960972 | 3 | 1,732,252 | planned 65 | planned 100% |
| planned-only-s2 | 181 | 1.538934596 | 2 | 1,524,476 | planned 61 | planned 100% |
| planned-only-s3 | 181 | 1.512643879 | 12 | 1,690,642 | planned 49 | planned 100% |

## Programs each run needed to pass each published value (- : not passed)

| Arm | Best of 25,600 (gpt-oss-120b) (1.51004) | Best human (1.50973) | OpenEvolve (1.50719) | ThetaEvolve (1.50681) | AlphaEvolve (May 2025) (1.5053) | AlphaEvolve V2 (1.50317) | TTT-Discover (gpt-oss-120b) (1.50287) |
|---|---|---|---|---|---|---|---|
| floor | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - |
| population | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - |
| plan | -, 107, - | -, 113, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - |
| plan+notes | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - |
| planned-only | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - | -, -, - |

## Published values (for scale)

- Best of 25,600 (gpt-oss-120b): 1.51004
- Best human: 1.50973
- OpenEvolve: 1.50719
- ThetaEvolve: 1.50681
- AlphaEvolve (May 2025): 1.5053
- AlphaEvolve V2: 1.50317
- TTT-Discover (gpt-oss-120b): 1.50287
