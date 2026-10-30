# v10.2: Helix from Code Zero, with the field's ideas as axes

From Code Zero (R = 2/3), with the field's 15 findings and 38 options on 9 decisions (the deep research, helix10/sota.py) as axes, at most 50,000 steps, the same CPU seconds per program, 3 planned experiments and 3 mutations a generation. Helix v4 (Atlas) from Code Zero without the field's axes: 0.9390 at generation 20, 0.9408 by about generation 50, flat to generation 150 (results/v4cont/atlas-s1, docs/V4_CEILING.md); the long line of Helix runs continuing each other from Code Zero (v4.7, v7, v8, v9: about 800 generations) ended at 0.941442 (docs/VERSIONS.md). For scale: the field's optimisers from nothing reach about 0.90-0.93; the best construction known with n <= 50,000 is AlphaEvolve V2's 0.961021, with n <= 100,000 0.962273842955 (JSAgent), the arena's record 0.963588110582 (n = 1,999,999).

## The climb, by generation (every run has finished 94)

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
| 94 | 0.946550167 | 0.904622210 |

## The climb, by CPU (17.3 CPU hours on programs so far)

| CPU hours | Helix v10.2 | Helix v10.2, seed 2 |
|---|---|---|
| 1.73 | 0.898266870 | 0.860074252 |
| 4.34 | 0.904080630 | 0.862994360 |
| 8.67 | 0.946464794 | 0.866112124 |
| 13.01 | 0.946544967 | 0.904524431 |
| 17.34 | 0.946547672 | 0.904628851 |

## Cost

| Run | Generations | Programs | CPU hours | Model calls | Tokens | Best |
|---|---|---|---|---|---|---|
| v102-helix | 94 | 586 | 20.4 | 1713 | 20,620,257 | 0.946550167262 (p0583) |
| v102-helix-s2 | 97 | 608 | 17.3 | 1719 | 19,415,383 | 0.904628851053 (p0605) |

## Against the published LLM-driven systems

Their values and budgets as they report them (TTT-Discover's Table 2, arXiv:2601.16175: AlphaEvolve, OpenEvolve, best-of-N and TTT-Discover; ThetaEvolve's Table 2, arXiv:2511.23473: its steps of 512 programs; AlphaEvolve V2's construction has 50,000 steps). Each column: the programs the run had evaluated when its best first passed that value (Helix's programs have 150.0 CPU s each).

| System | Model | Its value | Its programs | Its time per program | v102-helix: programs to pass it | v102-helix-s2: programs to pass it |
|---|---|---|---|---|---|---|
| AlphaEvolve (May 2025) | Gemini 2.0 Pro + Flash | 0.8962 | not stated | not stated | 25 (generation 4) | 324 (generation 52) |
| Best-of-25,600 samples | gpt-oss-120b | 0.9344 | 25,600 | 10 min | 151 (generation 24) | not yet |
| OpenEvolve | gpt-oss-120b | 0.9449 | 25,600 | 10 min | 169 (generation 27) | not yet |
| ThetaEvolve, without RL | R1-Distill-Qwen3-8B | 0.9434 | 51,200 | 350 s | 163 (generation 26) | not yet |
| ThetaEvolve, with RL | R1-Distill-Qwen3-8B (trained at test time) | 0.9469 | 33,280 | 350 s | not yet | not yet |
| TTT-Discover | gpt-oss-120b (trained at test time) | 0.9591 | 25,600 | 10 min | not yet | not yet |
| AlphaEvolve V2 (Nov 2025; 50,000 steps) | Gemini 2.0 Pro + Flash | 0.9610 | not stated | not stated | not yet | not yet |

Helix's knowledge differs from theirs: its axes are the field's ideas as of October 2026 (the deep research), some published after these systems ran. That is the claim under test: given the literature's axes, Helix searches them as a space.

## Where Helix's progress came from (v102-helix)

Helix's record: 0.946550167264 (p0589, n = 50000), on track T2: a new design built from nothing around A13 -> Coarse to fine, upsampling by interpolation betwe….
The track holding the record, over the run: T2 from generation 1.

Explorations built from nothing: 8 (8 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T2 | A13 -> Coarse to fine, upsampling by interpolation betwe… | 1 | 94 | 0.946549778 | running | yes |
| T8 | A11 -> Adam with gradient noise and elitist respawn of t… | 14 | 38 | 0.913712442 | running |  |
| T10 | A15 -> A fine, coherent periodic lattice of teeth (perio… | 44 | 26 | 0.876128741 | running |  |
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 47 | 0.866965580 | running |  |
| T7 | A17 -> Small-mass runs of f first | 5 | 46 | 0.844122370 | running |  |
| T4 | A9 -> Exact line search on R per block or run of f (no … | 2 | 6 | 0.803713477 | paused |  |
| T5 | A10 -> A softmax- or p-norm-weighted set of the top lags | 3 | 6 | 0.801808313 | paused |  |
| T9 | A12 -> f = w^2 exactly (a cell at zero stays at zero: th… | 18 | 12 | 0.774368749 | paused |  |

The field's options built at least once: 8 of 38; the invariant audit's alternatives: 0 of 3.

## Where Helix's progress came from (v102-helix-s2)

Helix's record: 0.904628851053 (p0605, n = 50000), on track T6: a new design built from nothing around A14 -> A tall spike plus a comb of smaller peaks.
The track holding the record, over the run: T1 from generation 1, T5 from generation 6, T6 from generation 35, T1 from generation 46, T6 from generation 52.

Explorations built from nothing: 8 (8 around an option of the field, 0 new designs from the map). Their climbs:

| Track | Built around | Opened | Experiments | Best | Race | Held the record |
|---|---|---|---|---|---|---|
| T6 | A14 -> A tall spike plus a comb of smaller peaks | 4 | 74 | 0.904628851 | running | yes |
| T7 | A10 -> A fixed mild smooth max (beta about 100-500 relat… | 7 | 46 | 0.879781781 | running |  |
| T9 | A20 -> Use no regularization | 53 | 20 | 0.876905871 | running |  |
| T2 | A11 -> L-BFGS with Anderson acceleration of the Dinkelba… | 1 | 49 | 0.876174678 | finished |  |
| T5 | A16 -> Perturb along the gradient of the transition loss… | 3 | 32 | 0.864890445 | paused | yes |
| T4 | A13 -> Average-pool a finer construction down to n, then… | 2 | 46 | 0.859587920 | running |  |
| T10 | A10 -> Level-transition lags | 90 | 3 | 0.848639442 | running |  |
| T8 | A19 -> Force even symmetry h[i]=h[N-1-i] | 39 | 6 | 0.723887489 | paused |  |

The field's options built at least once: 6 of 38; the invariant audit's alternatives: 0 of 21.
