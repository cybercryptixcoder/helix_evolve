# v10.2: Helix from Code Zero, with the field's ideas as axes

From Code Zero (R = 2/3), with the field's 15 findings and 38 options on 9 decisions (the deep research, helix10/sota.py) as axes, at most 50,000 steps, the same CPU seconds per program, 3 planned experiments and 3 mutations a generation. Helix v4 (Atlas) from Code Zero without the field's axes: 0.9390 at generation 20, 0.9408 by about generation 50, flat to generation 150 (results/v4cont/atlas-s1, docs/V4_CEILING.md); the long line of Helix runs continuing each other from Code Zero (v4.7, v7, v8, v9: about 800 generations) ended at 0.941442 (docs/VERSIONS.md). For scale: the field's optimisers from nothing reach about 0.90-0.93; the best construction known with n <= 50,000 is AlphaEvolve V2's 0.961021, with n <= 100,000 0.962273842955 (JSAgent), the arena's record 0.963588110582 (n = 1,999,999).

## The climb, by generation (every run has finished 344)

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
| 250 | 0.947991608 | 0.941115363 |
| 300 | 0.948046250 | 0.941136077 |
| 344 | 0.948559779 | 0.941242888 |

## The climb, by CPU (67.3 CPU hours on programs so far)

| CPU hours | Helix v10.2 | Helix v10.2, seed 2 |
|---|---|---|
| 6.73 | 0.946064548 | 0.864868956 |
| 16.83 | 0.946547668 | 0.904622210 |
| 33.67 | 0.946630994 | 0.941110839 |
| 50.50 | 0.947990398 | 0.941115363 |
| 67.34 | 0.948079957 | 0.941242888 |

## Cost

| Run | Generations | Programs | CPU hours | Model calls | Tokens | Best |
|---|---|---|---|---|---|---|
| v102-helix | 344 | 2180 | 71.9 | 6343 | 79,218,867 | 0.948559779360 (p2179) |
| v102-helix-s2 | 347 | 2230 | 67.3 | 6197 | 77,461,385 | 0.941242888016 (p2186) |

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

Helix's record: 0.948582161162 (p2186, n = 50000), on track T2: a new design built from nothing around A13 -> Coarse to fine, upsampling by interpolation betwe….
The track holding the record, over the run: T2 from generation 1.

Explorations built from nothing: 24 (24 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T2 | A13 -> Coarse to fine, upsampling by interpolation betwe… | 1 | 342 | 0.948559779 | running | yes |
| T19 | A14 -> Regular sparse packets under a smooth raised-cosi… | 204 | 48 | 0.917006435 | finished |  |
| T8 | A11 -> Adam with gradient noise and elitist respawn of t… | 14 | 48 | 0.914143782 | finished |  |
| T24 | A64 -> Optimize a continuous sub-cell shift parameter | 304 | 22 | 0.908468841 | running |  |
| T10 | A15 -> A fine, coherent periodic lattice of teeth (perio… | 44 | 51 | 0.876148866 | finished |  |
| T13 | A5 -> Fourier perturbation | 105 | 51 | 0.871745065 | finished |  |
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 48 | 0.866965580 | paused |  |
| T15 | A12 -> Explicit support mask pruning | 122 | 55 | 0.857470732 | finished |  |
| T20 | A4 -> Independent random restarts | 205 | 48 | 0.854908817 | finished |  |
| T16 | A4 -> Population evolutionary search | 145 | 48 | 0.853632976 | finished |  |
| T26 | A45 -> Finite differences on heights | 321 | 12 | 0.849573539 | running |  |
| T7 | A17 -> Small-mass runs of f first | 5 | 51 | 0.844129727 | finished |  |
| T11 | A4 -> Beam search over grids | 97 | 51 | 0.840460626 | finished |  |
| T23 | A45 -> Derivative-free local search | 255 | 43 | 0.823907076 | running |  |
| T21 | A28 -> alternate envelope and fine-comb blocks | 223 | 49 | 0.817116003 | finished |  |
| T25 | A72 -> Penalty or barrier on max | 308 | 19 | 0.807577515 | running |  |
| T4 | A9 -> Exact line search on R per block or run of f (no … | 2 | 6 | 0.803713477 | paused |  |
| T5 | A10 -> A softmax- or p-norm-weighted set of the top lags | 3 | 6 | 0.801808313 | paused |  |
| T9 | A12 -> f = w^2 exactly (a cell at zero stays at zero: th… | 18 | 12 | 0.774368749 | paused |  |
| T12 | A14 -> One heavy comb block holding about 30% of the mas… | 98 | 3 | - | paused |  |
| T14 | A15 -> Number-theoretic support (Sidon/B2 sets, differen… | 116 | 3 | - | paused |  |
| T17 | A8 -> Fixed repeat count then polish | 194 | 3 | - | paused |  |
| T18 | A15 -> Contiguous blocks with irregular spacing found by… | 200 | 3 | - | paused |  |
| T22 | A50 -> Solve a bilevel problem with an inner max-locatio… | 250 | 3 | - | paused |  |

The field's options built at least once: 13 of 38; the invariant audit's alternatives: 0 of 57.

## Where Helix's progress came from (v102-helix-s2)

Helix's record: 0.941242888016 (p2186, n = 50000), on track T9: a new design built from nothing around A20 -> Use no regularization.
The track holding the record, over the run: T1 from generation 1, T5 from generation 6, T6 from generation 35, T1 from generation 46, T6 from generation 52, T9 from generation 100.

Explorations built from nothing: 21 (21 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T9 | A20 -> Use no regularization | 53 | 268 | 0.941242506 | running | yes |
| T13 | A20 -> Add an L2 penalty on heights | 104 | 48 | 0.918145126 | finished |  |
| T20 | A67 -> Second-order Newton/trust-region/SLSQP | 300 | 19 | 0.916665091 | running |  |
| T18 | A57 -> Shift h by half a cell before convolution | 218 | 61 | 0.909230611 | finished |  |
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 77 | 0.904628851 | paused | yes |
| T7 | A10 -> A fixed mild smooth max (beta about 100-500 relat… | 7 | 51 | 0.879822914 | finished |  |
| T16 | A62 -> Search only centered supports with fixed symmetry | 210 | 50 | 0.879371090 | finished |  |
| T2 | A11 -> L-BFGS with Anderson acceleration of the Dinkelba… | 1 | 49 | 0.876174678 | finished |  |
| T22 | A36 -> L1 mass / scale / L-infinity variants | 315 | 13 | 0.875032544 | running |  |
| T10 | A10 -> Level-transition lags | 90 | 48 | 0.872669841 | paused |  |
| T23 | A4 -> Random search / simulated annealing | 316 | 12 | 0.867153513 | running |  |
| T11 | A33 -> Min-max plateau-gap surrogate | 101 | 58 | 0.865498772 | finished |  |
| T5 | A16 -> Perturb along the gradient of the transition loss… | 3 | 32 | 0.864890445 | paused | yes |
| T12 | A14 -> Regular small-big-small triplets | 102 | 48 | 0.862511888 | finished |  |
| T4 | A13 -> Average-pool a finer construction down to n, then… | 2 | 48 | 0.859587920 | finished |  |
| T15 | A40 -> Return final iterate | 192 | 48 | 0.850848262 | finished |  |
| T19 | A68 -> Many independent random restarts | 280 | 32 | 0.849792929 | running |  |
| T14 | A42 -> Asymmetric separated support islands | 186 | 49 | 0.815359268 | finished |  |
| T8 | A19 -> Force even symmetry h[i]=h[N-1-i] | 39 | 6 | 0.723887489 | paused |  |
| T21 | A68 -> Simulated annealing temperature schedule | 303 | 6 | 0.650785522 | paused |  |
| T17 | A61 -> Minimize -log R | 212 | 3 | - | paused |  |

The field's options built at least once: 6 of 38; the invariant audit's alternatives: 0 of 111.
