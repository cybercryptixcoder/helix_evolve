# Helix v9: the map of hills and the design map

## v102-helix

- Generations 1-28: best 0.666666667 -> 0.945870416 (p0175, track T2); the main track now: T2.
- Exploration levels: level 0: 25 generations, level 1: 3 generations.
- Planned experiments by slot: track 48, main 28, build 7, flip 1.

### Records (22)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 1 | 0.802665035 | p0003 | deep | build | T2 |
| 2 | 0.852896164 | p0013 | deep | main | T2 |
| 3 | 0.853568835 | p0017 | wide | mutation | T2 |
| 4 | 0.897662945 | p0021 | deep | main | T2 |
| 5 | 0.898159459 | p0027 | deep | main | T2 |
| 6 | 0.898257458 | p0036 | deep | main | T2 |
| 7 | 0.898265412 | p0039 | wide | mutation | T2 |
| 8 | 0.898266870 | p0051 | deep | main | T2 |
| 9 | 0.898268919 | p0057 | deep | main | T2 |
| 11 | 0.902680221 | p0066 | wide | mutation | T2 |
| 12 | 0.903340524 | p0076 | deep | main | T2 |
| 13 | 0.904041397 | p0081 | deep | main | T2 |
| 14 | 0.904072817 | p0085 | deep | main | T2 |
| 17 | 0.904078401 | p0107 | deep | main | T2 |
| 18 | 0.904080512 | p0110 | deep | main | T2 |
| 22 | 0.932126682 | p0135 | deep | main | T2 |
| 23 | 0.933073443 | p0142 | deep | main | T2 |
| 24 | 0.937953178 | p0146 | wide | mutation | T2 |
| 25 | 0.938047870 | p0156 | deep | main | T2 |
| 26 | 0.944645586 | p0161 | wide | mutation | T2 |
| 27 | 0.945662592 | p0164 | wide | mutation | T2 |
| 28 | 0.945870416 | p0175 | deep | main | T2 |

### Side tracks opened (0)


### Generation by generation

| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |
|---|---|---|---|---|---|---|---|
| 1 | 0.802665035 | yes | 0 / 3 | 0 | main, build, flip | 0.802665 | the map begins with 1 known hills: H1 (0.666667, reached 0 more times); T2 took the record (0.802665): it is now the main track, and T1 a side track; T2 opened (a new design built from nothing around A13 -> Coarse to fine, upsampling by interpolation betwe…); T3 opened (a flip of A18 -> a new option on p0001); new hill H2, found by T2 (build): 0.802665, distance 0.324 from the nearest known hill (H1) |
| 2 | 0.852896164 | yes | 0 / 3 | 0 | main, track:T3, build | 0.784460 | T4 opened (a new design built from nothing around A9 -> Exact line search on R per block or run of f (no …); new hill H3, found by T3 (flip): 0.784460, distance 0.204 from the nearest known hill (H1) |
| 3 | 0.853568835 | yes | 0 / 1 | 0 | main, track:T3, build | 0.792974 | T3 gained (0.784460 -> 0.800507); T5 opened (a new design built from nothing around A10 -> A softmax- or p-norm-weighted set of the top lags); T3 goes on to the next rung (6 experiments): still rising (best 0.800507 at 3 experiments) |
| 4 | 0.897662945 | yes | 0 / 1 | 0 | main, track:T4, build | 0.794089 | T3 gained (0.800507 -> 0.804847); T4 gained (0.782305 -> 0.794089); T6 opened (a new design built from nothing around A14 -> A tall spike plus a comb of smaller peaks); new hill H4, found by T4 (build): 0.794089, distance 0.220 from the nearest known hill (H1) |
| 5 | 0.898159459 | yes | 0 / 1 | 0 | main, track:T3, build | 0.804847 | T4 gained (0.794089 -> 0.803704); T5 gained (0.752599 -> 0.801808); T7 opened (a new design built from nothing around A17 -> Small-mass runs of f first) |
| 6 | 0.898257458 | yes | 0 / 1 | 0 | main, track:T5, track:T4 | 0.803713 | T4 gained (0.803704 -> 0.803713); T4 goes on to the next rung (6 experiments): still rising (best 0.803713 at 3 experiments); new hill H5, found by T5 (build): 0.801808, distance 0.219 from the nearest known hill (H1) |
| 7 | 0.898265412 | yes | 0 / 1 | 0 | main, track:T6, track:T3 | 0.804847 | new hill H6, found by T6 (build): 0.746445, distance 0.298 from the nearest known hill (H3) |
| 8 | 0.898266870 | yes | 0 / 1 | 0 | main, track:T7, track:T4 | 0.803713 | new hill H7, found by T7 (build): 0.780639, distance 0.130 from the nearest known hill (H5) |
| 9 | 0.898268919 | yes | 0 / 1 | 0 | main, track:T6, track:T5 | 0.801808 | T6 gained (0.746445 -> 0.750591); T7 gained (0.780639 -> 0.810165); T5 goes on to the next rung (6 experiments): still rising (best 0.801808 at 3 experiments); T6 goes on to the next rung (6 experiments): still rising (best 0.750591 at 3 experiments) |
| 10 | 0.898269086 |  | 0 / 1 | 0 | main, track:T7, track:T3 | 0.810214 | T6 gained (0.750591 -> 0.750624); T7 gained (0.810165 -> 0.824044); T3 paused by the race at 6 experiments: stopped rising at 6 experiments (best 0.804847); T7 goes on to the next rung (6 experiments): still rising (best 0.824044 at 3 experiments) |
| 11 | 0.902680221 | yes | 1 / 1 | 0 | main, track:T6, track:T4 | 0.803713 | T6 gained (0.750624 -> 0.795417); T7 gained (0.824044 -> 0.825294) |
| 12 | 0.903340524 | yes | 0 / 1 | 0 | main, track:T7, track:T5 | 0.825650 | T7 gained (0.825294 -> 0.825650) |
| 13 | 0.904041397 | yes | 0 / 1 | 0 | main, track:T6, track:T4 | 0.812464 | T6 gained (0.795417 -> 0.812464); T4 paused by the race at 6 experiments: stopped rising at 6 experiments (best 0.803713) |
| 14 | 0.904072817 | yes | 0 / 1 | 0 | main, track:T7, build | 0.825655 | T7 gained (0.825650 -> 0.826414); T8 opened (a new design built from nothing around A11 -> Adam with gradient noise and elitist respawn of t…) |
| 15 | 0.904072817 |  | 0 / 1 | 0 | main, track:T6, track:T5 | 0.812464 | T1 gained (0.793300 -> 0.795273); T8 gained (0.745231 -> 0.745301); T6 goes on to the next rung (12 experiments): still rising (best 0.812464 at 6 experiments) |
| 16 | 0.904072817 |  | 1 / 1 | 0 | main, track:T7, track:T8 | 0.767747 | T8 gained (0.745301 -> 0.767747); T7 goes on to the next rung (12 experiments): still rising (best 0.826414 at 6 experiments); new hill H8, found by T8 (build): 0.767747, distance 0.138 from the nearest known hill (H4) |
| 17 | 0.904078401 | yes | 2 / 1 | 1 | main, track:T8, track:T5 | 0.801808 | T8 gained (0.767747 -> 0.767806); T5 paused by the race at 6 experiments: stopped rising at 6 experiments (best 0.801808, below the cohort's 50% quantile); T8 goes on to the next rung (6 experiments): still rising (best 0.767806 at 3 experiments) |
| 18 | 0.904080512 | yes | 0 / 1 | 0 | main, track:T8, build | 0.767806 | T7 gained (0.826414 -> 0.834774); T8 gained (0.767806 -> 0.770539); T9 opened (a new design built from nothing around A12 -> f = w^2 exactly (a cell at zero stays at zero: th…) |
| 19 | 0.904080512 |  | 0 / 1 | 0 | main, track:T7, track:T6 | 0.836400 | T6 gained (0.812464 -> 0.812517); T7 gained (0.834774 -> 0.836400); T8 gained (0.770539 -> 0.776184) |
| 20 | 0.904080512 |  | 1 / 1 | 0 | main, track:T8, track:T9 | 0.797606 | T6 gained (0.812517 -> 0.812549); T8 gained (0.776184 -> 0.797606); new hill H9, found by T9 (build): 0.723440, distance 0.164 from the nearest known hill (H4) |
| 21 | 0.904080630 |  | 2 / 1 | 1 | main, track:T6, track:T7 | 0.836406 | T6 gained (0.812549 -> 0.812570); T7 gained (0.836400 -> 0.836406) |
| 22 | 0.932126682 | yes | 3 / 1 | 1 | main, track:T8, track:T9 | 0.797606 | T9 gained (0.723440 -> 0.726037); T8 goes on to the next rung (12 experiments): still rising (best 0.797606 at 6 experiments); T9 goes on to the next rung (6 experiments): still rising (best 0.726037 at 3 experiments) |
| 23 | 0.933073443 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.812591 | T1 gained (0.795273 -> 0.795300); T6 gained (0.812570 -> 0.812591); T9 gained (0.726037 -> 0.762543) |
| 24 | 0.937953178 | yes | 0 / 1 | 0 | main, track:T9, track:T8 | 0.797606 | T6 gained (0.812591 -> 0.812621); T9 gained (0.762543 -> 0.762553) |
| 25 | 0.938047870 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.836412 | T6 gained (0.812621 -> 0.812646); T7 gained (0.836406 -> 0.836412); T9 gained (0.762553 -> 0.762754) |
| 26 | 0.944645586 | yes | 0 / 1 | 0 | main, track:T9, track:T8 | 0.913606 | T1 gained (0.795300 -> 0.795302); T8 gained (0.797606 -> 0.913606); T9 gained (0.762754 -> 0.774357) |
| 27 | 0.945662592 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.836412 | T7 gained (0.836412 -> 0.836443); T9 gained (0.774357 -> 0.774363) |
| 28 | 0.945870416 | yes | 0 / 1 | 0 | main, track:T8, track:T9 | 0.913606 | T9 goes on to the next rung (12 experiments): still rising (best 0.774363 at 6 experiments) |

### Hills (9: 2 on the map after its first generation, 7 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H2 | 0.945870 (p0175) | 1 | T2 (build) | 0 | This program optimizes a smooth log-sum-exp surrogate of the sup-norm with an annealed sharpness parameter inside a Dinkelbach loop, rather than directly maximizing the exact ratio. It uses L-BFGS-B with analytic gradien |
| H8 | 0.913606 (p0162) | 16 | T8 (build) | 0 | This program abandons the record's high-resolution climb entirely, instead starting from the given start and running a prune-refine-upsample loop that repeatedly zeroes the smallest fraction of cells and re-optimises ins |
| H7 | 0.836443 (p0167) | 8 | T7 (build) | 0 | This program builds a hand-crafted seed of a 10-tooth raised-cosine comb plus a graded ramp of 30 bumps, then grows it by coordinate-wise golden-section tuning of per-run multiplicative factors and additive bumps (doubli |
| H6 | 0.812646 (p0155) | 7 | T6 (build) | 0 | This program builds a hand-crafted spike-plus-decaying-comb seed at n=512 and then doubles resolution in four stages (512→1024→2048→4096), spending only 20% of budget on the first stage and re-annealing beta from 1e4 upw |
| H3 | 0.804847 (p0022) | 2 | T3 (flip) | 0 | This program optimizes a Dinkelbach-style surrogate (smooth-max minus λ·num) with L-BFGS-B gradients on a fixed grid, rather than the record's approach of building a tuned small-n construction and carefully upsampling it |
| H4 | 0.803713 (p0035) | 4 | T4 (build) | 0 | This program starts from the given `start` and refines it with local, parameterised moves (run scaling, additive cosine packets, constant-run shifts, bump replacement, and pairwise mass transfer), each tuned by a 1-D gri |
| H5 | 0.801808 (p0031) | 6 | T5 (build) | 0 | This program uses linear interpolation to upsample between fixed ladder sizes (256→4096) rather than repeat-based upsampling, and it anneals the smooth-max exponent p from 4 to 400 within each stage instead of re-anneali |
| H9 | 0.774363 (p0166) | 20 | T9 (build) | 0 | This program abandons the record's multi-resolution pipeline (refine at 4096/8192/32768 then pool down) and instead works directly at a single fixed resolution (N=1024), starting from the constant-ones seed rather than a |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 21):

- D1: Search space / representation of f (all: Nonnegative real-valued array f on a uniform grid, optimized directly in f-space (or w=sqrt(f) in one case), with positivity enforced by clipping/projection)
- D2: Objective surrogate for the sup-norm (all: Smooth log-sum-exp / p-norm / soft-max surrogate of ||f*f||_inf with an annealed sharpness parameter (beta or p) inside a Dinkelbach or ratio loop)
- D3: Optimizer core (all: Gradient-based local ascent (L-BFGS-B, PGD with momentum, or Adam) using analytic gradients of the smoothed objective)
- D4: Resolution strategy (all: Multi-resolution ladder that upsamples (repeat or linear interpolation) from a coarse grid to a fine grid, or refines at a fixed high resolution then pools down)
- D5: Seed / initialization (all: Start from the provided `start` (or a random Gaussian-packet / hand-crafted comb fallback) and locally refine it)
- D6: Time allocation (all: Fixed hand-tuned fractions of the CPU budget across stages (main polish, kicks, native control, ladder stages), decided before running)
- D7: Escape mechanism from local optima (all: Small low-frequency Fourier-mode perturbation ('kick') followed by re-polishing, or Gaussian noise / smoothing blends, with a fixed small amplitude)
- D8: Normalization / constraint handling (all: Fix ||f||_1 = 1 by renormalizing after every step (mass-preserving projection), treating the ratio as scale-invariant)

### The design map (24 decisions, 170 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A18: How is the objective (the convolution and its norms) computed numerically? | compute f*f by direct convolution on the; evaluate the ratio analytically for a pa; use FFT-based convolution with careful n | 100% of 16 (kappa 1.00) | 28% |
| A12: How is f >= 0 enforced | f = w^2 exactly (a cell at zero stays at; Clip or project to f >= 0 after each ste; An explicit support mask pruned on purpo; none imposed; f is unconstrained and sca; fix //f//_1 or //f//_2 to a constant to  ... | 100% of 16 (kappa 1.00) | 20% |
| A9: How is the ratio R optimised: the objective the optimiser actually works on | Dinkelbach: maximise //f*f//_2^2 - lambd; Gradient steps on R itself (or log R) wi; Active-set minimax: the tied maxima of f; Exact line search on R per block or run ; Alternating projection: push f*f towards ... | 100% of 16 (kappa 1.00) | 15% |
| A11: Which local optimiser solves the inner problem | L-BFGS quasi-Newton ascent; Adam stochastic ascent with restarts; Simulated annealing / random search; Momentum gradient ascent with line searc; Projected gradient / FISTA ... | 100% of 16 (kappa 1.00) | 10% |
| A16: Once converged, how does the program try to leave the local optimum | Small noise (about 1e-8 x max f), then a; Perturb along the gradient of the transi; Perturb only the lowest 1-5% Fourier mod; Structural surgery on blocks (shift, sca; Exact single-coordinate moves on the tie ... | 75% of 16 (kappa 0.59) | 4% |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | Fixed geometric ladder of grid sizes (64; Single fixed high resolution from the st; Adaptive resolution: refine grid only wh; A fixed ladder of power-of-two sizes wit; Stay at one native resolution the whole  ... | 81% of 16 (kappa 0.74) | 4% |
| A1: How is a candidate solution represented? | a dense real-valued array of samples on ; a parametric analytic form (e.g. Gaussia; a sparse / low-degree representation (e.; Raw nonnegative knot values on a uniform; Low-dimensional basis: spline/B-spline c ... | 88% of 16 (kappa 0.75) | - |
| A2: How is the first solution built? | constant ones (or the externally supplie; random smooth function (e.g. low-frequen; a hand-designed bump/indicator-like shap; Random Gaussian packet mixture (8 bumps ; Deterministic analytic seeds: single bum ... | 75% of 16 (kappa 0.67) | - |
| A3: What quantity does the search optimise while it runs? | maximise R = //f*f//_2^2/(//f//_1^2 * // | 100% of 16 (kappa 1.00) | - |
| A4: Which moves or update steps change a solution? | no search at all: return the provided st; local gradient-free search (coordinate/p; population-based evolutionary search ove | 100% of 16 (kappa 1.00) | - |
| A5: How does the search accept worse solutions or escape a local optimum? | accept slightly worse with small probabi; no acceptance of worse; restart on stall | 100% of 16 (kappa 1.00) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A8: How is the time budget split between phases? | ignores budget_seconds entirely; run iterative optimization until budget_; allocate budget to a coarse-to-fine mult; Static pre-assigned fraction of the budg; Adaptive budget: allocate time proportio ... | 81% of 16 (kappa 0.74) | - |
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact maximum (a subgradient at the arg ; LogSumExp smooth max normalised by max(f; A fixed mild smooth max (beta about 100-; A softmax- or p-norm-weighted set of the; Smooth log-sum-exp (soft-max) surrogate  ... | 100% of 16 (kappa 1.00) | - |
| A13: How is the number of steps n chosen and changed | Exact k-fold repeat np.repeat(f, k) (R u; Zero-pad to the step limit and polish th; Average-pool a finer construction down t; Coarse to fine, upsampling by interpolat; native length, no zero-padding | 88% of 16 (kappa 0.80) | - |
| A14: What is the macro shape (the envelope) of f across its domain | One heavy comb block holding about 30% o; A tall spike plus a comb of smaller peak; A smooth arcsine-like density, 1/sqrt(1 ; A parametric series sum_j a_j (1 - 4x^2); Regular sparse packets under a smooth ra | 69% of 13 (kappa 0.44) | - |
| A15: What is the fine structure of f (the comb of teeth or blocks) | A fine, coherent periodic lattice of tee; Contiguous blocks with irregular spacing; A coarser parent with each cell split in; Number-theoretic support (Sidon/B2 sets,; Regular [small, big, small] triplets | 69% of 13 (kappa -0.11) | - |
| A17: Which part of f*f does the program's step aim at | The level transitions of f*f (lags with ; Only the tied maxima (the active set of ; Small-mass runs of f first; plateau structure via mass transfer | 69% of 16 (kappa -0.11) | - |
| A19: What domain and boundary treatment is used for the convolution? | finite interval with zero-padding implie; periodic (circular) convolution on a tor; explicit zero extension with a chosen su | 94% of 16 (kappa 0.00) | - |
| A20: What symmetry or shape assumptions are imposed on f? | general unconstrained shape, no symmetry; enforce even symmetry (f(x)=f(-x)); enforce a unimodal or compactly supporte | 100% of 16 (kappa 1.00) | - |
| A21: Is there a separate final high-precision polish pass (larger beta, tighter tolerances, or  | A separate polish pass at the largest gr; No separate polish; keep one beta schedu; Post-hoc exact-knot local search (coordi | 94% of 16 (kappa 0.89) | - |
| A22: Does the program use a coarse-to-fine geometric ladder of grid sizes with linear interpola | coarse-to-fine ladder with interpolation; no ladder; resample start to fixed high  | 93% of 15 (kappa 0.85) | - |
| A23: How is the resolution of the returned final answer chosen (native, truncated, pooled, or b | Evaluate a handful of candidate resoluti; Return the native high-resolution field ; Choose the output resolution by a valida | 83% of 6 (kappa 0.67) | - |
| A24: How is the scale/normalization of f fixed (e.g. //f//_1=1 renormalization, //f*f//_inf=1,  | Fix //f//_1 = 1 by renormalizing after e; Fix //f*f//_inf = 1 and let mass float, ; Fix //f//_2 = 1 and optimize the full th | 100% of 1 (kappa 1.00) | - |

### Explorations chosen from the map (8: 7 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A13 -> Coarse to fine, upsampling by  | 1/1 | 28 | 0.945870 | running | founder H2 |
| T3 | flip | 1 | A18 -> a new option, unlike the liste | 1/1 | 6 | 0.804847 | paused at 6 | founder H3 |
| T4 | build | 2 | A9 -> Exact line search on R per blo | 1/1 | 6 | 0.803713 | paused at 6 | founder H4 |
| T5 | build | 3 | A10 -> A softmax- or p-norm-weighted  | 1/1 | 6 | 0.801808 | paused at 6 | founder H5 |
| T6 | build | 4 | A14 -> A tall spike plus a comb of sm | 1/1 | 11 | 0.812646 | running at 6 | founder H6 |
| T7 | build | 5 | A17 -> Small-mass runs of f first | 1/1 | 11 | 0.836443 | running at 6 | founder H7 |
| T8 | build | 14 | A11 -> Adam stochastic ascent with re | 1/1 | 9 | 0.913606 | running at 6 | founder H8 |
| T9 | build | 18 | A12 -> f = w^2 exactly (a cell at zer | 1/1 | 6 | 0.774363 | running at 6 | founder H9 |

## v102-helix-s2

- Generations 1-33: best 0.666666667 -> 0.864865098 (p0205, track T5); the main track now: T5.
- Exploration levels: level 0: 30 generations, level 1: 2 generations, level 2: 1 generations.
- Planned experiments by slot: track 60, main 33, build 5, flip 1.

### Records (26)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 1 | 0.842087388 | p0002 | wide | mutation | T1 |
| 4 | 0.842209958 | p0022 | wide | mutation | T1 |
| 5 | 0.842954069 | p0030 | deep | main | T1 |
| 6 | 0.849786988 | p0037 | deep | track | T5 |
| 7 | 0.857120371 | p0044 | deep | main | T5 |
| 8 | 0.857510119 | p0052 | deep | main | T5 |
| 10 | 0.860071723 | p0061 | deep | main | T5 |
| 11 | 0.860074252 | p0068 | deep | main | T5 |
| 12 | 0.862073247 | p0074 | deep | main | T5 |
| 13 | 0.862558110 | p0083 | deep | main | T5 |
| 14 | 0.862564420 | p0087 | deep | main | T5 |
| 19 | 0.862783505 | p0119 | wide | mutation | T5 |
| 20 | 0.862784436 | p0125 | deep | main | T5 |
| 21 | 0.862804903 | p0134 | deep | main | T5 |
| 22 | 0.862806074 | p0140 | deep | main | T5 |
| 23 | 0.862994360 | p0145 | deep | main | T5 |
| 24 | 0.863198432 | p0150 | deep | main | T5 |
| 25 | 0.863465596 | p0157 | deep | main | T5 |
| 26 | 0.863548361 | p0161 | deep | main | T5 |
| 27 | 0.863552810 | p0167 | deep | main | T5 |
| 28 | 0.863772390 | p0171 | wide | mutation | T5 |
| 29 | 0.864140809 | p0182 | deep | main | T5 |
| 30 | 0.864678463 | p0184 | deep | main | T5 |
| 31 | 0.864726552 | p0194 | deep | main | T5 |
| 32 | 0.864831942 | p0199 | deep | main | T5 |
| 33 | 0.864865098 | p0205 | deep | main | T5 |

### Side tracks opened (0)


### Generation by generation

| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |
|---|---|---|---|---|---|---|---|
| 1 | 0.842087388 | yes | 0 / 3 | 0 | main, build, flip | 0.707550 | the map begins with 1 known hills: H1 (0.666667, reached 0 more times); T2 opened (a new design built from nothing around A11 -> L-BFGS with Anderson acceleration of the Dinkelba…); T3 opened (a flip of A9 -> Alternating projection: push f*f towards a two-le… on p0001); new hill H2, found by T1 (seed): 0.842087, distance 0.211 from the nearest known hill (H1) |
| 2 | 0.842087492 |  | 0 / 3 | 0 | main, track:T2, build | 0.725267 | T3 gained (0.707550 -> 0.723766); T4 opened (a new design built from nothing around A13 -> Average-pool a finer construction down to n, then…); new hill H3, found by T2 (build): 0.723731, distance 0.211 from the nearest known hill (H1) |
| 3 | 0.842087492 |  | 1 / 3 | 0 | main, track:T3, build | 0.723734 | T4 gained (0.725267 -> 0.727261); T5 opened (a new design built from nothing around A16 -> Perturb along the gradient of the transition loss…); T4 landed on H3 (distance 0.030); T4 is now the top of H3 (0.727261); T3 landed on H3 (distance 0.039); T5 landed on H3 (distance 0.030) |
| 4 | 0.842209958 | yes | 2 / 3 | 0 | main, track:T2, build | 0.723734 | T2 gained (0.723731 -> 0.723734); T3 gained (0.723766 -> 0.723862); T6 opened (a new design built from nothing around A14 -> A tall spike plus a comb of smaller peaks); T2 goes on to the next rung (6 experiments): still rising (best 0.723734 at 3 experiments) |
| 5 | 0.842954069 | yes | 0 / 2 | 0 | main, track:T4, track:T3 | 0.727317 | T2 gained (0.723734 -> 0.723887); T3 gained (0.723862 -> 0.723900); T4 gained (0.727261 -> 0.731157); T3 goes on to the next rung (6 experiments): still rising (best 0.723900 at 3 experiments); T3 stops racing: after 3 experiments it sits on H3 below that hill's top (a copy of a known design) |
| 6 | 0.849786988 | yes | 0 / 1 | 0 | main, track:T5, track:T2 | 0.849787 | T4 gained (0.731157 -> 0.738594); T5 gained (0.723734 -> 0.849787); T5 took the record (0.849787): it is now the main track, and T1 a side track; new hill H4, found by T5 (build): 0.849787, distance 0.243 from the nearest known hill (H3) |
| 7 | 0.857120371 | yes | 0 / 1 | 0 | main, track:T6, build | 0.723263 | T4 gained (0.738594 -> 0.749784); T7 opened (a new design built from nothing around A10 -> A fixed mild smooth max (beta about 100-500 relat…) |
| 8 | 0.857510119 | yes | 0 / 1 | 0 | main, track:T4, track:T2 | 0.767465 | T2 gained (0.723887 -> 0.788655); T4 gained (0.749784 -> 0.767465); T4 goes on to the next rung (6 experiments): still rising (best 0.767465 at 3 experiments) |
| 9 | 0.857510119 |  | 0 / 1 | 0 | main, track:T7, track:T6 | 0.799558 | T7 gained (0.723263 -> 0.784764); T6 goes on to the next rung (6 experiments): still rising (best 0.799558 at 3 experiments); new hill H5, found by T6 (build): 0.799558, distance 0.127 from the nearest known hill (H2); new hill H6, found by T7 (build): 0.784764, distance 0.090 from the nearest known hill (H5) |
| 10 | 0.860071723 | yes | 1 / 1 | 0 | main, track:T2, track:T4 | 0.795939 | T2 gained (0.788655 -> 0.795939); T4 gained (0.767465 -> 0.776348); T2 goes on to the next rung (12 experiments): still rising (best 0.795939 at 6 experiments) |
| 11 | 0.860074252 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.845793 | T6 gained (0.799558 -> 0.803224); T7 gained (0.784764 -> 0.845793); T7 goes on to the next rung (6 experiments): still rising (best 0.845793 at 3 experiments) |
| 12 | 0.862073247 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.795939 | T4 gained (0.776348 -> 0.777272); T6 gained (0.803224 -> 0.806957) |
| 13 | 0.862558110 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.836686 | T6 gained (0.806957 -> 0.836686); T7 gained (0.845793 -> 0.847552) |
| 14 | 0.862564420 | yes | 0 / 1 | 0 | main, track:T4, track:T2 | 0.806552 | T2 gained (0.795939 -> 0.796177); T4 gained (0.777272 -> 0.806552); T4 goes on to the next rung (12 experiments): still rising (best 0.806552 at 6 experiments) |
| 15 | 0.862564420 |  | 0 / 1 | 0 | main, track:T6, track:T7 | 0.847552 | T2 gained (0.796177 -> 0.796180); T7 gained (0.847552 -> 0.849000); T6 goes on to the next rung (12 experiments): still rising (best 0.836686 at 6 experiments) |
| 16 | 0.862564666 |  | 1 / 1 | 0 | main, track:T2, track:T4 | 0.811150 | T2 gained (0.796180 -> 0.811150); T4 gained (0.806552 -> 0.808850); T6 gained (0.836686 -> 0.843123) |
| 17 | 0.862564666 |  | 2 / 1 | 1 | main, track:T6, track:T7 | 0.849000 | T4 gained (0.808850 -> 0.809019); T6 gained (0.843123 -> 0.844825); T7 gained (0.849000 -> 0.851370); T7 goes on to the next rung (12 experiments): still rising (best 0.851370 at 6 experiments) |
| 18 | 0.862564666 |  | 3 / 1 | 1 | main, track:T2, track:T4 | 0.846634 | T2 gained (0.811150 -> 0.846634); T4 gained (0.809019 -> 0.809786); T6 gained (0.844825 -> 0.844938) |
| 19 | 0.862783505 | yes | 4 / 1 | 2 | main, track:T6, track:T7 | 0.851437 | T2 gained (0.846634 -> 0.847345); T7 gained (0.851370 -> 0.851523) |
| 20 | 0.862784436 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.847346 | T4 gained (0.809786 -> 0.809863); T6 gained (0.844938 -> 0.846812); T7 gained (0.851523 -> 0.851724); T2 goes on to the next rung (24 experiments): still rising (best 0.847345 at 12 experiments) |
| 21 | 0.862804903 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.851724 | T2 gained (0.847345 -> 0.847919); T4 gained (0.809863 -> 0.810004) |
| 22 | 0.862806074 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.847920 | T2 gained (0.847919 -> 0.847920); T4 gained (0.810004 -> 0.810259); T6 gained (0.846812 -> 0.848463); T7 gained (0.851724 -> 0.852624) |
| 23 | 0.862994360 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.852914 | T2 gained (0.847920 -> 0.847921); T4 gained (0.810259 -> 0.810276); T6 gained (0.848463 -> 0.848806); T7 gained (0.852624 -> 0.852914) |
| 24 | 0.863198432 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.847922 | T1 gained (0.842964 -> 0.842966); T6 gained (0.848806 -> 0.848827) |
| 25 | 0.863465596 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.848857 | T2 gained (0.847921 -> 0.847922); T6 gained (0.848827 -> 0.848857) |
| 26 | 0.863548361 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.857688 | T1 gained (0.842966 -> 0.842967); T2 gained (0.847922 -> 0.857688); T4 gained (0.810276 -> 0.810383); T6 gained (0.848857 -> 0.848858); T4 goes on to the next rung (24 experiments): still rising (best 0.810383 at 12 experiments) |
| 27 | 0.863552810 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.853069 | T4 gained (0.810383 -> 0.810430); T6 gained (0.848858 -> 0.849670); T7 gained (0.852914 -> 0.853315); T6 goes on to the next rung (24 experiments): still rising (best 0.849670 at 12 experiments) |
| 28 | 0.863772390 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.858370 | T1 gained (0.842967 -> 0.843012); T2 gained (0.857688 -> 0.858370); T4 gained (0.810430 -> 0.810709) |
| 29 | 0.864140809 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.853378 | T2 gained (0.858370 -> 0.858632); T6 gained (0.849670 -> 0.849928); T7 gained (0.853315 -> 0.853378); T7 goes on to the next rung (24 experiments): still rising (best 0.853378 at 12 experiments); T6 landed on H6 (distance 0.057); T6 climbed from H5 into H6 |
| 30 | 0.864678463 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.858963 | T2 gained (0.858632 -> 0.858963); T6 gained (0.849928 -> 0.850611); new hill H7, found by T6 (build): 0.850611, distance 0.076 from the nearest known hill (H6) |
| 31 | 0.864726552 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.859720 | T6 gained (0.850611 -> 0.859720); T7 gained (0.853378 -> 0.853542) |
| 32 | 0.864831942 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.859158 | T2 gained (0.858963 -> 0.859158); T4 gained (0.810709 -> 0.813788); T6 gained (0.859720 -> 0.859887) |
| 33 | 0.864865098 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.859889 | T1 gained (0.843012 -> 0.844047); T2 gained (0.859158 -> 0.859177); T6 gained (0.859887 -> 0.859889); T7 gained (0.853542 -> 0.853588) |

### Hills (7: 2 on the map after its first generation, 5 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H4 | 0.864865 (p0205) | 6 | T5 (build) | 0 | This program optimises the full autocorrelation ratio directly via Dinkelbach iterations on a square-root variable with a soft-max surrogate for the infinity norm, rather than isolating the level-transition loss and pert |
| H7 | 0.859889 (p0207) | 30 | T6 (build) | 0 | This program runs its structural surgery at multiple low resolutions (1500 and 3000) rather than a single n_low=2500 round, and it polishes the surgery result with L-BFGS-B every 4 accepts instead of validating only at l |
| H3 | 0.859177 (p0204) | 2 | T2 (build) | 3 | This program optimises a smooth soft-max surrogate of the sup-norm (log-sum-exp with increasing sharpness β) via L-BFGS on a squared-parameterisation w↦w², rather than hill-climbing heights directly. It adds Anderson ext |
| H6 | 0.853588 (p0208) | 9 | T7 (build) | 1 | This program optimises a smooth soft-max surrogate of the sup-norm (exponential penalty with β annealed 500→2000→8000) via Dinkelbach iterations on a squared-weight parametrisation, rather than perturbing along a transit |
| H5 | 0.849670 (p0170) | 9 | T6 (build) | 0 | This program seeds a hand-built spike-plus-decaying-comb shape and refines it with a Dinkelbach-style ascent that maximizes num − λ·l1·linf via random contiguous-block scaling, rather than starting from the record's symm |
| H2 | 0.844047 (p0206) | 1 | T1 (seed) | 0 | The new program uses a multi-resolution approach: it starts from a resampled grid and applies block-multiplicative perturbations, edge-preserving smoothing, and global noise, rather than the record's single-resolution co |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 17):

- D1: objective being optimised (all: the exact ratio R = ||f*f||_2^2 / (||f*f||_1 ||f*f||_inf) (or a soft-max surrogate of it, annealed to the exact ratio))
- D2: search space / parametrisation of f (all: nonnegative real heights on a fixed uniform grid, with the grid resolution fixed (n=4000/8000/50000) and f constrained to be nonnegative)
- D3: how the sup-norm (Linf of f*f) is handled (all: treat the argmax of f*f as a single point (exact gradient with indicator at argmax) or a soft-max surrogate annealed to sharpness)
- D4: starting point (all: a smooth analytic seed (sine-power bump, or the record's symmetric construction, or a hand-built spike-plus-comb) then local ascent)
- D5: local optimiser used for polishing (all: gradient-based (L-BFGS-B or projected gradient / Dinkelbach) on heights or sqrt-heights)
- D6: structural move set (all: contiguous-run operations: scale/zero bottom-percentile runs, transfer mass between runs, warp windows, block scaling)
- D7: time / budget allocation (all: a single CPU-time deadline with a fixed phase split (e.g. ~95s phase A then move loop until deadline-10s), one process)
- D8: acceptance criterion for moves (all: strict improvement of R (accept only if r_new > cur_R + tiny epsilon), i.e. monotone hill climbing)

### The design map (14 decisions, 195 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact max subgradient; Annealed LogSumExp smooth max; Fixed mild smooth max; Top-lag softmax/p-norm weighting; Exact discrete autocorrelation max ... | 68% of 22 (kappa 0.55) | 45% |
| A14: What is the macro shape (the envelope) of f across its domain | Heavy comb block plus ramp; Spike plus smaller comb peaks; Smooth arcsine density; Parametric series sum of bumps; Sparse packets under smooth envelope ... | 86% of 21 (kappa 0.64) | 24% |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | fixed resolution chosen up front (option; continuously refine resolution as a func; optimise at coarse resolution then inter; ignored entirely; no time-aware search o; allocate budget across a coarse-to-fine  ... | 77% of 22 (kappa 0.70) | 7% |
| A5: How does the search accept worse solutions or escape a local optimum? | Anneal beta, keep best; Random kicks on stalled ascent; Strict monotone hill climbing; Simulated annealing / tabu; Population diversity/novelty acceptance ... | 73% of 22 (kappa 0.61) | 7% |
| A4: Which moves or update steps change a solution? | Projected gradient ascent; Contiguous-run structural edits; Scattered single-cell mutations; Global parametric transforms; L-BFGS on smooth surrogate ... | 77% of 22 (kappa 0.60) | 6% |
| A13: How is the number of steps n chosen and changed | Exact k-fold repeat np.repeat(f, k) (R u; Zero-pad to the step limit and polish th; Average-pool a finer construction down t; Coarse to fine, upsampling by interpolat; as every program so far: Whether the bre ... | 82% of 22 (kappa 0.71) | 4% |
| A1: How is a candidate solution represented? | Adaptive grid piecewise-constant; Low-dimensional parametric family; Variable-length vector with resampling; Signed or complex irregular function; Nonnegative heights on fixed uniform gri ... | 73% of 22 (kappa 0.59) | - |
| A2: How is the first solution built? | return start unchanged if given, else a ; use start as a seed and locally perturb/; ignore start and always construct from s; a smooth analytic bump (sine-power) or t; random multi-start over many random init ... | 50% of 22 (kappa 0.31) | - |
| A3: What quantity does the search optimise while it runs? | Dinkelbach surrogate with lambda update; Exact ratio gradient ascent; Active-set minimax dual weights; Exact line search on ratio; Alternating projection to two-level targ ... | 91% of 22 (kappa 0.84) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A12: How is f >= 0 enforced | f = w^2 exactly (a cell at zero stays at; Clip or project to f >= 0 after each ste; An explicit support mask pruned on purpo; as every program so far: Support topolog; Force one contiguous positive block ... | 100% of 22 (kappa 1.00) | - |
| A19: How is the scale/normalization of f handled (implicit fixed scale, normalize to unit L2/L1 | implicitly fixed scale (constant 1), no ; normalize f to unit L2 or unit L1 before; search over scale as an explicit free pa; keep f nonnegative and let the ratio be ; fix //f//_1 = 1 or //f//_2 = 1 each step ... | 100% of 22 (kappa 1.00) | - |
| A20: How is the autocorrelation f*f computed and updated during search (full recompute, increme | recompute or incrementally update the fu; use FFT-based convolution with analytic ; exploit sparsity/structure (e.g. only up; as every program so far: No smoothness, ; Add a small total-variation penalty ... | 95% of 21 (kappa 0.90) | - |
| A22: Every program so far: Optimising programs keep and return the best-R array seen, not the f | as every program so far: Optimising prog; Return the final iterate; Return the best of the last k iterates; Return an average of top candidates; the best-R array seen ... | 90% of 10 (kappa 0.80) | - |

### Explorations chosen from the map (6: 5 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A11 -> L-BFGS with Anderson accelerat | 1/1 | 18 | 0.859177 | running at 12 | founder H3 |
| T3 | flip | 1 | A9 -> Alternating projection: push f | 1/1 | 3 | 0.723900 | paused at 6 | on H3 |
| T4 | build | 2 | A13 -> Average-pool a finer construct | 1/1 | 15 | 0.813788 | running at 12 | top H3 |
| T5 | build | 3 | A16 -> Perturb along the gradient of  | 1/1 | 28 | 0.864865 | running | founder H4 |
| T6 | build | 4 | A14 -> Spike plus smaller comb peaks | 1/1 | 15 | 0.859889 | running at 12 | founder H7 |
| T7 | build | 7 | A10 -> Fixed mild smooth max | 1/1 | 14 | 0.853588 | running at 12 | founder H6 |
