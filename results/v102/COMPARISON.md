# v10.2: Helix from Code Zero, with the field's ideas as axes

From Code Zero (R = 2/3), with the field's 15 findings and 38 options on 9 decisions (the deep research, helix10/sota.py) as axes, at most 50,000 steps, the same CPU seconds per program, 3 planned experiments and 3 mutations a generation. Helix v4 (Atlas) from Code Zero without the field's axes: 0.9390 at generation 20, 0.9408 by about generation 50, flat to generation 150 (results/v4cont/atlas-s1, docs/V4_CEILING.md); the long line of Helix runs continuing each other from Code Zero (v4.7, v7, v8, v9: about 800 generations) ended at 0.941442 (docs/VERSIONS.md). For scale: the field's optimisers from nothing reach about 0.90-0.93; the best construction known with n <= 50,000 is AlphaEvolve V2's 0.961021, with n <= 100,000 0.962273842955 (JSAgent), the arena's record 0.963588110582 (n = 1,999,999).

## The climb, by generation (every run has finished 235)

| Generation | Helix v10.2 | Helix v10.2, seed 2 |
|---|---|---|
| 1 | 0.802665035 | 0.842087388 |
| 5 | 0.898159459 | 0.842954069 |
| 10 | 0.898269086 | 0.860071723 |
| 20 | 0.904080512 | 0.862784436 |
| 30 | 0.945939512 | 0.864678463 |
| 40 | 0.946464794 | 0.866112124 |
| 60 | 0.946544967 | 0.904524431 |
| 80 | 0.946547672 | 0.904524431 |
| 100 | 0.946550292 | 0.927286941 |
| 150 | 0.946630536 | 0.940687589 |
| 200 | 0.946769783 | 0.941115345 |
| 235 | 0.947989312 | 0.941115363 |

## The climb, by CPU (44.0 CPU hours on programs so far)

| CPU hours | Helix v10.2 | Helix v10.2, seed 2 |
|---|---|---|
| 4.40 | 0.904080630 | 0.862994360 |
| 11.00 | 0.946537451 | 0.904522743 |
| 21.99 | 0.946550292 | 0.940038865 |
| 32.99 | 0.946630642 | 0.941090510 |
| 43.99 | 0.946777800 | 0.941115363 |

## Cost

| Run | Generations | Programs | CPU hours | Model calls | Tokens | Best |
|---|---|---|---|---|---|---|
| v102-helix | 235 | 1472 | 49.0 | 4331 | 53,490,091 | 0.947989312441 (p1461) |
| v102-helix-s2 | 238 | 1532 | 44.0 | 4211 | 51,225,179 | 0.941115362709 (p1431) |

## Against the published LLM-driven systems

Their values and budgets as they report them (TTT-Discover's Table 2, arXiv:2601.16175: AlphaEvolve, OpenEvolve, best-of-N and TTT-Discover; ThetaEvolve's Table 2, arXiv:2511.23473: its steps of 512 programs; AlphaEvolve V2's construction has 50,000 steps). Each column: the programs the run had evaluated when its best first passed that value (Helix's programs have 150.0 CPU s each).

| System | Model | Its value | Its programs | Its time per program | v102-helix: programs to pass it | v102-helix-s2: programs to pass it |
|---|---|---|---|---|---|---|
| AlphaEvolve (May 2025) | Gemini 2.0 Pro + Flash | 0.8962 | not stated | not stated | 25 (generation 4) | 324 (generation 52) |
| Best-of-25,600 samples | gpt-oss-120b | 0.9344 | 25,600 | 10 min | 151 (generation 24) | 632 (generation 101) |
| OpenEvolve | gpt-oss-120b | 0.9449 | 25,600 | 10 min | 169 (generation 27) | not yet |
| ThetaEvolve, without RL | R1-Distill-Qwen3-8B | 0.9434 | 51,200 | 350 s | 163 (generation 26) | not yet |
| ThetaEvolve, with RL | R1-Distill-Qwen3-8B (trained at test time) | 0.9469 | 33,280 | 350 s | 1,421 (generation 227) | not yet |
| TTT-Discover | gpt-oss-120b (trained at test time) | 0.9591 | 25,600 | 10 min | not yet | not yet |
| AlphaEvolve V2 (Nov 2025; 50,000 steps) | Gemini 2.0 Pro + Flash | 0.9610 | not stated | not stated | not yet | not yet |

Helix's knowledge differs from theirs: its axes are the field's ideas as of October 2026 (the deep research), some published after these systems ran. That is the claim under test: given the literature's axes, Helix searches them as a space.

## Where Helix's progress came from (v102-helix)

Helix's record: 0.947989312441 (p1461, n = 50000), on track T2: a new design built from nothing around A13 -> Coarse to fine, upsampling by interpolation betwe….
The track holding the record, over the run: T2 from generation 1.

Explorations built from nothing: 19 (19 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T2 | A13 -> Coarse to fine, upsampling by interpolation betwe… | 1 | 235 | 0.947988852 | running | yes |
| T8 | A11 -> Adam with gradient noise and elitist respawn of t… | 14 | 48 | 0.914143782 | finished |  |
| T19 | A14 -> Regular sparse packets under a smooth raised-cosi… | 204 | 14 | 0.905777786 | running |  |
| T10 | A15 -> A fine, coherent periodic lattice of teeth (perio… | 44 | 51 | 0.876148866 | finished |  |
| T13 | A5 -> Fourier perturbation | 105 | 51 | 0.871745065 | finished |  |
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 48 | 0.866965580 | paused |  |
| T15 | A12 -> Explicit support mask pruning | 122 | 54 | 0.857470732 | finished |  |
| T16 | A4 -> Population evolutionary search | 145 | 41 | 0.853631096 | running |  |
| T7 | A17 -> Small-mass runs of f first | 5 | 51 | 0.844129727 | finished |  |
| T11 | A4 -> Beam search over grids | 97 | 51 | 0.840460626 | finished |  |
| T20 | A4 -> Independent random restarts | 205 | 13 | 0.836384647 | running |  |
| T4 | A9 -> Exact line search on R per block or run of f (no … | 2 | 6 | 0.803713477 | paused |  |
| T5 | A10 -> A softmax- or p-norm-weighted set of the top lags | 3 | 6 | 0.801808313 | paused |  |
| T9 | A12 -> f = w^2 exactly (a cell at zero stays at zero: th… | 18 | 12 | 0.774368749 | paused |  |
| T21 | A28 -> alternate envelope and fine-comb blocks | 223 | 5 | 0.690506197 | running |  |
| T12 | A14 -> One heavy comb block holding about 30% of the mas… | 98 | 3 | - | paused |  |
| T14 | A15 -> Number-theoretic support (Sidon/B2 sets, differen… | 116 | 3 | - | paused |  |
| T17 | A8 -> Fixed repeat count then polish | 194 | 3 | - | paused |  |
| T18 | A15 -> Contiguous blocks with irregular spacing found by… | 200 | 3 | - | paused |  |

The field's options built at least once: 13 of 38; the invariant audit's alternatives: 0 of 27.

## Where Helix's progress came from (v102-helix-s2)

Helix's record: 0.941115362709 (p1431, n = 49949), on track T9: a new design built from nothing around A20 -> Use no regularization.
The track holding the record, over the run: T1 from generation 1, T5 from generation 6, T6 from generation 35, T1 from generation 46, T6 from generation 52, T9 from generation 100.

Explorations built from nothing: 16 (16 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T9 | A20 -> Use no regularization | 53 | 160 | 0.941115345 | running | yes |
| T13 | A20 -> Add an L2 penalty on heights | 104 | 48 | 0.918145126 | finished |  |
| T18 | A57 -> Shift h by half a cell before convolution | 218 | 11 | 0.905891057 | running |  |
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 77 | 0.904628851 | paused | yes |
| T7 | A10 -> A fixed mild smooth max (beta about 100-500 relat… | 7 | 51 | 0.879822914 | finished |  |
| T2 | A11 -> L-BFGS with Anderson acceleration of the Dinkelba… | 1 | 49 | 0.876174678 | finished |  |
| T10 | A10 -> Level-transition lags | 90 | 48 | 0.872669841 | paused |  |
| T11 | A33 -> Min-max plateau-gap surrogate | 101 | 58 | 0.865498772 | finished |  |
| T5 | A16 -> Perturb along the gradient of the transition loss… | 3 | 32 | 0.864890445 | paused | yes |
| T12 | A14 -> Regular small-big-small triplets | 102 | 48 | 0.862511888 | finished |  |
| T4 | A13 -> Average-pool a finer construction down to n, then… | 2 | 48 | 0.859587920 | finished |  |
| T15 | A40 -> Return final iterate | 192 | 20 | 0.850835077 | running |  |
| T16 | A62 -> Search only centered supports with fixed symmetry | 210 | 14 | 0.848316411 | running |  |
| T14 | A42 -> Asymmetric separated support islands | 186 | 26 | 0.814709154 | running |  |
| T8 | A19 -> Force even symmetry h[i]=h[N-1-i] | 39 | 6 | 0.723887489 | paused |  |
| T17 | A61 -> Minimize -log R | 212 | 3 | - | paused |  |

The field's options built at least once: 6 of 38; the invariant audit's alternatives: 0 of 75.
