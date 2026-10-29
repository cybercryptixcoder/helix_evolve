# Helix v9: the map of hills and the design map

## v102-helix

- Generations 1-9: best 0.666666667 -> 0.898268919 (p0057, track T2); the main track now: T2.
- Exploration levels: level 0: 9 generations.
- Planned experiments by slot: track 12, main 9, build 5, flip 1.

### Records (9)

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

### Hills (7: 2 on the map after its first generation, 5 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H2 | 0.898269 (p0057) | 1 | T2 (build) | 0 | This program optimizes a smooth log-sum-exp surrogate of the sup-norm with an annealed sharpness parameter inside a Dinkelbach loop, rather than directly maximizing the exact ratio. It uses L-BFGS-B with analytic gradien |
| H7 | 0.810165 (p0052) | 8 | T7 (build) | 0 | This program builds a hand-crafted seed of a 10-tooth raised-cosine comb plus a graded ramp of 30 bumps, then grows it by coordinate-wise golden-section tuning of per-run multiplicative factors and additive bumps (doubli |
| H3 | 0.804847 (p0022) | 2 | T3 (flip) | 0 | This program optimizes a Dinkelbach-style surrogate (smooth-max minus λ·num) with L-BFGS-B gradients on a fixed grid, rather than the record's approach of building a tuned small-n construction and carefully upsampling it |
| H4 | 0.803713 (p0035) | 4 | T4 (build) | 0 | This program starts from the given `start` and refines it with local, parameterised moves (run scaling, additive cosine packets, constant-run shifts, bump replacement, and pairwise mass transfer), each tuned by a 1-D gri |
| H5 | 0.801808 (p0031) | 6 | T5 (build) | 0 | This program uses linear interpolation to upsample between fixed ladder sizes (256→4096) rather than repeat-based upsampling, and it anneals the smooth-max exponent p from 4 to 400 within each stage instead of re-anneali |
| H6 | 0.750591 (p0053) | 7 | T6 (build) | 0 | This program builds a hand-crafted spike-plus-decaying-comb seed at n=512 and then doubles resolution in four stages (512→1024→2048→4096), spending only 20% of budget on the first stage and re-annealing beta from 1e4 upw |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 3):

- D1: How the objective is made differentiable for the sup-norm (all: Smooth log-sum-exp (soft-max) surrogate of ||f*f||_inf with an annealed sharpness beta, inside a Dinkelbach/ratio loop)
- D2: How the ratio is handled (all: Dinkelbach-style: fix lambda = current exact R, minimize (surrogate sup) - lambda*(num), update lambda from exact R each round)
- D3: Resolution strategy across the run (all: Fixed geometric ladder of grid sizes (64 up to 2048/4096) with hand-tuned per-stage time shares, upsample by linear interpolation between stages)
- D4: Local optimizer (all: L-BFGS-B with analytic gradients and nonnegativity bounds, restarted in a loop until the time budget expires)
- D5: Parameterization of f (all: Raw nonnegative knot values on a uniform grid, renormalized to sum 1 after each step)
- D6: Initialization (all: Random Gaussian packet mixture (8 bumps with random positions/widths) at the coarsest grid, seeded by a fixed RNG)
- D7: Time allocation (all: Static pre-assigned fraction of the budget per stage, plus a final polish stage at high beta)
- D8: Final high-precision refinement (all: A separate polish pass at the largest grid with much larger beta_max (1e7) and tighter tolerances)

### The design map (22 decisions, 55 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A14: What is the macro shape (the envelope) of f across its domain | One heavy comb block holding about 30% o; A tall spike plus a comb of smaller peak; A smooth arcsine-like density, 1/sqrt(1 ; A parametric series sum_j a_j (1 - 4x^2); Regular sparse packets under a smooth ra | 100% of 2 (kappa 1.00) | 33% |
| A11: Which local optimiser solves the inner problem | L-BFGS on the smooth surrogate, many ite; L-BFGS with Anderson acceleration of the; Adam with gradient noise and elitist res; Simulated annealing or random search on ; gradient ascent with momentum and adapti ... | 100% of 3 (kappa 1.00) | 20% |
| A12: How is f >= 0 enforced | f = w^2 exactly (a cell at zero stays at; Clip or project to f >= 0 after each ste; An explicit support mask pruned on purpo; none imposed; f is unconstrained and sca; fix //f//_1 or //f//_2 to a constant to  ... | 100% of 3 (kappa 1.00) | 17% |
| A1: How is a candidate solution represented? | a dense real-valued array of samples on ; a parametric analytic form (e.g. Gaussia; a sparse / low-degree representation (e.; Raw nonnegative knot values on a uniform; Low-dimensional basis: spline/B-spline c ... | 100% of 3 (kappa 1.00) | 7% |
| A9: How is the ratio R optimised: the objective the optimiser actually works on | Dinkelbach: maximise //f*f//_2^2 - lambd; Gradient steps on R itself (or log R) wi; Active-set minimax: the tied maxima of f; Exact line search on R per block or run ; Alternating projection: push f*f towards ... | 100% of 3 (kappa 1.00) | 4% |
| A18: How is the objective (the convolution and its norms) computed numerically? | compute f*f by direct convolution on the; evaluate the ratio analytically for a pa; use FFT-based convolution with careful n | 100% of 3 (kappa 1.00) | 4% |
| A2: How is the first solution built? | constant ones (or the externally supplie; random smooth function (e.g. low-frequen; a hand-designed bump/indicator-like shap; Random Gaussian packet mixture (8 bumps ; Deterministic analytic seeds: single bum ... | 100% of 3 (kappa 1.00) | - |
| A3: What quantity does the search optimise while it runs? | maximise R = //f*f//_2^2/(//f//_1^2 * // | 100% of 3 (kappa 1.00) | - |
| A4: Which moves or update steps change a solution? | no search at all: return the provided st; local gradient-free search (coordinate/p; population-based evolutionary search ove | 100% of 3 (kappa 1.00) | - |
| A5: How does the search accept worse solutions or escape a local optimum? | accept slightly worse with small probabi; no acceptance of worse; restart on stall | 100% of 3 (kappa 1.00) | - |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | Fixed geometric ladder of grid sizes (64; Single fixed high resolution from the st; Adaptive resolution: refine grid only wh | 67% of 3 (kappa 0.00) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A8: How is the time budget split between phases? | ignores budget_seconds entirely; run iterative optimization until budget_; allocate budget to a coarse-to-fine mult; Static pre-assigned fraction of the budg; Adaptive budget: allocate time proportio ... | 67% of 3 (kappa 0.40) | - |
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact maximum (a subgradient at the arg ; LogSumExp smooth max normalised by max(f; A fixed mild smooth max (beta about 100-; A softmax- or p-norm-weighted set of the; Smooth log-sum-exp (soft-max) surrogate  ... | 100% of 3 (kappa 1.00) | - |
| A13: How is the number of steps n chosen and changed | Exact k-fold repeat np.repeat(f, k) (R u; Zero-pad to the step limit and polish th; Average-pool a finer construction down t; Coarse to fine, upsampling by interpolat | 100% of 3 (kappa 1.00) | - |
| A15: What is the fine structure of f (the comb of teeth or blocks) | A fine, coherent periodic lattice of tee; Contiguous blocks with irregular spacing; A coarser parent with each cell split in; Number-theoretic support (Sidon/B2 sets,; Regular [small, big, small] triplets | 50% of 2 (kappa 0.00) | - |
| A16: Once converged, how does the program try to leave the local optimum | Small noise (about 1e-8 x max f), then a; Perturb along the gradient of the transi; Perturb only the lowest 1-5% Fourier mod; Structural surgery on blocks (shift, sca; Exact single-coordinate moves on the tie ... | 0% of 3 (kappa -0.29) | - |
| A17: Which part of f*f does the program's step aim at | The level transitions of f*f (lags with ; Only the tied maxima (the active set of ; Small-mass runs of f first | 67% of 3 (kappa 0.00) | - |
| A19: What domain and boundary treatment is used for the convolution? | finite interval with zero-padding implie; periodic (circular) convolution on a tor; explicit zero extension with a chosen su | 100% of 3 (kappa 1.00) | - |
| A20: What symmetry or shape assumptions are imposed on f? | general unconstrained shape, no symmetry; enforce even symmetry (f(x)=f(-x)); enforce a unimodal or compactly supporte | 100% of 3 (kappa 1.00) | - |
| A21: Is there a separate final high-precision polish pass (larger beta, tighter tolerances, or  | A separate polish pass at the largest gr; No separate polish; keep one beta schedu; Post-hoc exact-knot local search (coordi | 100% of 3 (kappa 1.00) | - |
| A22: Does the program use a coarse-to-fine geometric ladder of grid sizes with linear interpola | coarse-to-fine ladder with interpolation | 50% of 2 (kappa 0.00) | - |

### Explorations chosen from the map (6: 5 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A13 -> Coarse to fine, upsampling by  | 0/1 | 9 | 0.898269 | running | founder H2 |
| T3 | flip | 1 | A18 -> a new option, unlike the liste | 1/1 | 5 | 0.804847 | running at 3 | founder H3 |
| T4 | build | 2 | A9 -> Exact line search on R per blo | 1/1 | 4 | 0.803713 | running at 3 | founder H4 |
| T5 | build | 3 | A10 -> A softmax- or p-norm-weighted  | 0/1 | 3 | 0.801808 | running at 3 | founder H5 |
| T6 | build | 4 | A14 -> A tall spike plus a comb of sm | 1/1 | 3 | 0.750591 | running at 3 | founder H6 |
| T7 | build | 5 | A17 -> Small-mass runs of f first | 1/1 | 2 | 0.810165 | running | founder H7 |

## v102-helix-s2

- Generations 1-10: best 0.666666667 -> 0.860071723 (p0061, track T5); the main track now: T5.
- Exploration levels: level 0: 10 generations.
- Planned experiments by slot: track 14, main 10, build 5, flip 1.

### Records (7)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 1 | 0.842087388 | p0002 | wide | mutation | T1 |
| 4 | 0.842209958 | p0022 | wide | mutation | T1 |
| 5 | 0.842954069 | p0030 | deep | main | T1 |
| 6 | 0.849786988 | p0037 | deep | track | T5 |
| 7 | 0.857120371 | p0044 | deep | main | T5 |
| 8 | 0.857510119 | p0052 | deep | main | T5 |
| 10 | 0.860071723 | p0061 | deep | main | T5 |

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

### Hills (6: 2 on the map after its first generation, 4 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H4 | 0.860072 (p0061) | 6 | T5 (build) | 0 | This program optimises the full autocorrelation ratio directly via Dinkelbach iterations on a square-root variable with a soft-max surrogate for the infinity norm, rather than isolating the level-transition loss and pert |
| H2 | 0.842964 (p0038) | 1 | T1 (seed) | 0 | The new program uses a multi-resolution approach: it starts from a resampled grid and applies block-multiplicative perturbations, edge-preserving smoothing, and global noise, rather than the record's single-resolution co |
| H5 | 0.799558 (p0058) | 9 | T6 (build) | 0 | This program seeds a hand-built spike-plus-decaying-comb shape and refines it with a Dinkelbach-style ascent that maximizes num − λ·l1·linf via random contiguous-block scaling, rather than starting from the record's symm |
| H3 | 0.795939 (p0060) | 2 | T2 (build) | 3 | This program optimises a smooth soft-max surrogate of the sup-norm (log-sum-exp with increasing sharpness β) via L-BFGS on a squared-parameterisation w↦w², rather than hill-climbing heights directly. It adds Anderson ext |
| H6 | 0.784764 (p0057) | 9 | T7 (build) | 0 | This program optimises a smooth soft-max surrogate of the sup-norm (exponential penalty with β annealed 500→2000→8000) via Dinkelbach iterations on a squared-weight parametrisation, rather than perturbing along a transit |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 3):

- D1: representation of the function f (all: a nonnegative height vector on a fixed uniform grid, convolved with itself)
- D2: objective handling of the sup-norm in the denominator (all: compute ||f*f||_inf exactly as the max of the discrete autocorrelation and divide)
- D3: search paradigm (all: local improvement (coordinate/block hill climb or L-BFGS) from a deterministic or seeded start)
- D4: starting point (all: a smooth analytic bump (sine-power) or the upsampled previous best)
- D5: normalisation / scale of f (all: keep f nonnegative and let the ratio be scale-invariant, never renormalising explicitly)
- D6: grid resolution strategy (all: fixed resolution chosen up front (optionally one doubling), tuned by hand)
- D7: time/effort allocation (all: a fixed step-size schedule or fixed iteration count with a CPU-deadline guard)
- D8: handling of the convolution cost (all: recompute or incrementally update the full discrete autocorrelation each trial)

### The design map (21 decisions, 61 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A4: Which moves or update steps change a solution? | L-BFGS-B steps on w=sqrt(f); multiplicative coordinate descent on h; projected gradient ascent with adaptive ; projected gradient ascent on h | 50% of 6 (kappa 0.38) | 45% |
| A5: How does the search accept worse solutions or escape a local optimum? | anneal beta and keep best R; random multiplicative restarts and coord; random kicks on stalled gradient ascent | 50% of 6 (kappa 0.28) | 28% |
| A11: Which local optimiser solves the inner problem | L-BFGS on the smooth surrogate, many ite; L-BFGS with Anderson acceleration of the; Adam with gradient noise and elitist res; Simulated annealing or random search on ; none — a single hand-picked closed-form  ... | 67% of 6 (kappa 0.56) | 7% |
| A17: Which part of f*f does the program's step aim at | The level transitions of f*f (lags with ; Only the tied maxima (the active set of ; Small-mass runs of f first | 80% of 5 (kappa 0.58) | 4% |
| A12: How is f >= 0 enforced | f = w^2 exactly (a cell at zero stays at; Clip or project to f >= 0 after each ste; An explicit support mask pruned on purpo | 100% of 6 (kappa 1.00) | 2% |
| A1: How is a candidate solution represented? | a fixed-length dense real vector of leng; a piecewise-constant function on a nonun; a parametric family (e.g. Gaussian mixtu; variable-length dense vector with resamp; a nonnegative height vector on a fixed u ... | 100% of 6 (kappa 1.00) | - |
| A2: How is the first solution built? | return start unchanged if given, else a ; use start as a seed and locally perturb/; ignore start and always construct from s; a smooth analytic bump (sine-power) or t; random multi-start over many random init ... | 67% of 6 (kappa 0.20) | - |
| A3: What quantity does the search optimise while it runs? | Dinkelbach surrogate A - lambda*L1*LSE | 75% of 4 (kappa 0.00) | - |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | fixed resolution chosen up front (option; continuously refine resolution as a func; optimise at coarse resolution then inter | 100% of 5 (kappa 1.00) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A8: How is the time budget split between phases? | ignored entirely; no time-aware search o; allocate budget across a coarse-to-fine ; use budget for a stochastic optimizer (s; a fixed step-size schedule or fixed iter; adaptive step sizes from a line search o ... | 67% of 6 (kappa 0.45) | - |
| A9: How is the ratio R optimised: the objective the optimiser actually works on | Dinkelbach: maximise //f*f//_2^2 - lambd; Gradient steps on R itself (or log R) wi; Active-set minimax: the tied maxima of f; Exact line search on R per block or run ; Alternating projection: push f*f towards ... | 100% of 6 (kappa 1.00) | - |
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact maximum (a subgradient at the arg ; LogSumExp smooth max normalised by max(f; A fixed mild smooth max (beta about 100-; A softmax- or p-norm-weighted set of the; compute //f*f//_inf exactly as the max o ... | 83% of 6 (kappa 0.78) | - |
| A13: How is the number of steps n chosen and changed | Exact k-fold repeat np.repeat(f, k) (R u; Zero-pad to the step limit and polish th; Average-pool a finer construction down t; Coarse to fine, upsampling by interpolat | 83% of 6 (kappa 0.75) | - |
| A14: What is the macro shape (the envelope) of f across its domain | One heavy comb block holding about 30% o; A tall spike plus a comb of smaller peak; A smooth arcsine-like density, 1/sqrt(1 ; A parametric series sum_j a_j (1 - 4x^2); Regular sparse packets under a smooth ra ... | 100% of 5 (kappa 1.00) | - |
| A15: What is the fine structure of f (the comb of teeth or blocks) | A fine, coherent periodic lattice of tee; Contiguous blocks with irregular spacing; A coarser parent with each cell split in; Number-theoretic support (Sidon/B2 sets,; Regular [small, big, small] triplets | 100% of 5 (kappa 1.00) | - |
| A16: Once converged, how does the program try to leave the local optimum | Small noise (about 1e-8 x max f), then a; Perturb along the gradient of the transi; Perturb only the lowest 1-5% Fourier mod; Structural surgery on blocks (shift, sca; Exact single-coordinate moves on the tie ... | 50% of 6 (kappa 0.36) | - |
| A18: What support and boundary treatment does f use (full support vs compact support with paddi | full support over all 50 entries, no exp; compact support with zero padding and tu; periodic vs. zero-padded convolution bou | 83% of 6 (kappa 0.60) | - |
| A19: How is the scale/normalization of f handled (implicit fixed scale, normalize to unit L2/L1 | implicitly fixed scale (constant 1), no ; normalize f to unit L2 or unit L1 before; search over scale as an explicit free pa; keep f nonnegative and let the ratio be ; fix //f//_1 = 1 or //f//_2 = 1 each step ... | 100% of 6 (kappa 1.00) | - |
| A20: How is the autocorrelation f*f computed and updated during search (full recompute, increme | recompute or incrementally update the fu; use FFT-based convolution with analytic ; exploit sparsity/structure (e.g. only up | 100% of 5 (kappa 1.00) | - |
| A21: Every program so far: Whether the breakpoint geometry of the step function is a degree of  | as every program so far: Whether the bre; Let cell boundaries be free continuous v; Optimise a global sub-cell offset/phase ; Keep equal-width cells fixed from the in | 100% of 1 (kappa 1.00) | - |

### Explorations chosen from the map (6: 5 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A11 -> L-BFGS with Anderson accelerat | 1/1 | 6 | 0.795939 | running at 6 | founder H3 |
| T3 | flip | 1 | A9 -> Alternating projection: push f | 1/1 | 3 | 0.723900 | paused at 6 | on H3 |
| T4 | build | 2 | A13 -> Average-pool a finer construct | 1/1 | 4 | 0.776348 | running at 3 | top H3 |
| T5 | build | 3 | A16 -> Perturb along the gradient of  | 0/1 | 6 | 0.860072 | running | founder H4 |
| T6 | build | 4 | A14 -> A tall spike plus a comb of sm | 1/1 | 3 | 0.799558 | running at 3 | founder H5 |
| T7 | build | 7 | A10 -> A fixed mild smooth max (beta  | 0/1 | 2 | 0.784764 | running | founder H6 |
