# v10.2: Helix from Code Zero, with the field's ideas as axes

From Code Zero (R = 2/3), with the field's 15 findings and 38 options on 9 decisions (the deep research, helix10/sota.py) as axes, at most 50,000 steps, the same CPU seconds per program, 3 planned experiments and 3 mutations a generation. Helix v4 (Atlas) from Code Zero without the field's axes: 0.9390 at generation 20, 0.9408 by about generation 50, flat to generation 150 (results/v4cont/atlas-s1, docs/V4_CEILING.md); the long line of Helix runs continuing each other from Code Zero (v4.7, v7, v8, v9: about 800 generations) ended at 0.941442 (docs/VERSIONS.md). For scale: the field's optimisers from nothing reach about 0.90-0.93; the best construction known with n <= 50,000 is AlphaEvolve V2's 0.961021, with n <= 100,000 0.962273842955 (JSAgent), the arena's record 0.963588110582 (n = 1,999,999).

## The climb, by generation (every run has finished 12)

| Generation | Helix v10.2 | Helix v10.2, seed 2 |
|---|---|---|
| 1 | 0.802665035 | 0.842087388 |
| 5 | 0.898159459 | 0.842954069 |
| 10 | 0.898269086 | 0.860071723 |
| 12 | 0.903340524 | 0.862073247 |

## The climb, by CPU (2.3 CPU hours on programs so far)

| CPU hours | Helix v10.2 | Helix v10.2, seed 2 |
|---|---|---|
| 0.23 | 0.802665035 | 0.842087388 |
| 0.59 | 0.852896164 | 0.842209958 |
| 1.17 | 0.898159459 | 0.857120371 |
| 1.76 | 0.898266870 | 0.860074252 |
| 2.35 | 0.902680221 | 0.862564420 |

## Cost

| Run | Generations | Programs | CPU hours | Model calls | Tokens | Best |
|---|---|---|---|---|---|---|
| v102-helix | 12 | 76 | 2.5 | 216 | 1,742,720 | 0.903340523588 (p0076) |
| v102-helix-s2 | 14 | 89 | 2.3 | 245 | 2,037,565 | 0.862564420343 (p0087) |

## Against the published LLM-driven systems

Their values and budgets as they report them (TTT-Discover's Table 2, arXiv:2601.16175: AlphaEvolve, OpenEvolve, best-of-N and TTT-Discover; ThetaEvolve's Table 2, arXiv:2511.23473: its steps of 512 programs; AlphaEvolve V2's construction has 50,000 steps). Each column: the programs the run had evaluated when its best first passed that value (Helix's programs have 150.0 CPU s each).

| System | Model | Its value | Its programs | Its time per program | v102-helix: programs to pass it | v102-helix-s2: programs to pass it |
|---|---|---|---|---|---|---|
| AlphaEvolve (May 2025) | Gemini 2.0 Pro + Flash | 0.8962 | not stated | not stated | 25 (generation 4) | not yet |
| Best-of-25,600 samples | gpt-oss-120b | 0.9344 | 25,600 | 10 min | not yet | not yet |
| OpenEvolve | gpt-oss-120b | 0.9449 | 25,600 | 10 min | not yet | not yet |
| ThetaEvolve, without RL | R1-Distill-Qwen3-8B | 0.9434 | 51,200 | 350 s | not yet | not yet |
| ThetaEvolve, with RL | R1-Distill-Qwen3-8B (trained at test time) | 0.9469 | 33,280 | 350 s | not yet | not yet |
| TTT-Discover | gpt-oss-120b (trained at test time) | 0.9591 | 25,600 | 10 min | not yet | not yet |
| AlphaEvolve V2 (Nov 2025; 50,000 steps) | Gemini 2.0 Pro + Flash | 0.9610 | not stated | not stated | not yet | not yet |

Helix's knowledge differs from theirs: its axes are the field's ideas as of October 2026 (the deep research), some published after these systems ran. That is the claim under test: given the literature's axes, Helix searches them as a space.

## Where Helix's progress came from (v102-helix)

Helix's record: 0.903340523588 (p0076, n = 16384), on track T2: a new design built from nothing around A13 -> Coarse to fine, upsampling by interpolation betwe….
The track holding the record, over the run: T2 from generation 1.

Explorations built from nothing: 5 (5 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T2 | A13 -> Coarse to fine, upsampling by interpolation betwe… | 1 | 12 | 0.903340524 | running | yes |
| T7 | A17 -> Small-mass runs of f first | 5 | 4 | 0.825649716 | running |  |
| T4 | A9 -> Exact line search on R per block or run of f (no … | 2 | 5 | 0.803713477 | running |  |
| T5 | A10 -> A softmax- or p-norm-weighted set of the top lags | 3 | 4 | 0.801808313 | running |  |
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 4 | 0.795417405 | running |  |

The field's options built at least once: 5 of 38.

## Where Helix's progress came from (v102-helix-s2)

Helix's record: 0.862564420343 (p0087, n = 32000), on track T5: a new design built from nothing around A16 -> Perturb along the gradient of the transition loss….
The track holding the record, over the run: T1 from generation 1, T5 from generation 6.

Explorations built from nothing: 5 (5 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T5 | A16 -> Perturb along the gradient of the transition loss… | 3 | 10 | 0.862564420 | running | yes |
| T7 | A10 -> A fixed mild smooth max (beta about 100-500 relat… | 7 | 4 | 0.847552075 | running |  |
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 5 | 0.836685899 | running |  |
| T4 | A13 -> Average-pool a finer construction down to n, then… | 2 | 6 | 0.806552274 | running |  |
| T2 | A11 -> L-BFGS with Anderson acceleration of the Dinkelba… | 1 | 8 | 0.796176702 | running |  |

The field's options built at least once: 6 of 38; the invariant audit's alternatives: 0 of 3.
