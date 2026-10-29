# Helix v9: the map of hills and the design map

## v102-helix

- Generations 1-3: best 0.666666667 -> 0.853568835 (p0017, track T2); the main track now: T2.
- Exploration levels: level 0: 3 generations.
- Planned experiments by slot: main 3, build 3, track 2, flip 1.

### Records (3)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 1 | 0.802665035 | p0003 | deep | build | T2 |
| 2 | 0.852896164 | p0013 | deep | main | T2 |
| 3 | 0.853568835 | p0017 | wide | mutation | T2 |

### Side tracks opened (0)


### Generation by generation

| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |
|---|---|---|---|---|---|---|---|
| 1 | 0.802665035 | yes | 0 / 3 | 0 | main, build, flip | 0.802665 | the map begins with 1 known hills: H1 (0.666667, reached 0 more times); T2 took the record (0.802665): it is now the main track, and T1 a side track; T2 opened (a new design built from nothing around A13 -> Coarse to fine, upsampling by interpolation betwe…); T3 opened (a flip of A18 -> a new option on p0001); new hill H2, found by T2 (build): 0.802665, distance 0.324 from the nearest known hill (H1) |
| 2 | 0.852896164 | yes | 0 / 3 | 0 | main, track:T3, build | 0.784460 | T4 opened (a new design built from nothing around A9 -> Exact line search on R per block or run of f (no …); new hill H3, found by T3 (flip): 0.784460, distance 0.204 from the nearest known hill (H1) |
| 3 | 0.853568835 | yes | 0 / 1 | 0 | main, track:T3, build | 0.792974 | T3 gained (0.784460 -> 0.800507); T5 opened (a new design built from nothing around A10 -> A softmax- or p-norm-weighted set of the top lags); T3 goes on to the next rung (6 experiments): still rising (best 0.800507 at 3 experiments) |

### Hills (3: 2 on the map after its first generation, 1 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H2 | 0.853569 (p0017) | 1 | T2 (build) | 0 | This program optimizes a smooth log-sum-exp surrogate of the sup-norm with an annealed sharpness parameter inside a Dinkelbach loop, rather than directly maximizing the exact ratio. It uses L-BFGS-B with analytic gradien |
| H3 | 0.800507 (p0014) | 2 | T3 (flip) | 0 | This program optimizes a Dinkelbach-style surrogate (smooth-max minus λ·num) with L-BFGS-B gradients on a fixed grid, rather than the record's approach of building a tuned small-n construction and carefully upsampling it |
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

### The design map (21 decisions, 18 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A12: How is f >= 0 enforced | f = w^2 exactly (a cell at zero stays at; Clip or project to f >= 0 after each ste; An explicit support mask pruned on purpo; none imposed; f is unconstrained and sca; fix //f//_1 or //f//_2 to a constant to  ... | 100% of 1 (kappa 1.00) | 55% |
| A19: What domain and boundary treatment is used for the convolution? | finite interval with zero-padding implie; periodic (circular) convolution on a tor; explicit zero extension with a chosen su | 100% of 1 (kappa 1.00) | 9% |
| A18: How is the objective (the convolution and its norms) computed numerically? | compute f*f by direct convolution on the; evaluate the ratio analytically for a pa; use FFT-based convolution with careful n | 100% of 1 (kappa 1.00) | 5% |
| A11: Which local optimiser solves the inner problem | L-BFGS on the smooth surrogate, many ite; L-BFGS with Anderson acceleration of the; Adam with gradient noise and elitist res; Simulated annealing or random search on ; gradient ascent with momentum and adapti ... | 100% of 1 (kappa 1.00) | 2% |
| A2: How is the first solution built? | constant ones (or the externally supplie; random smooth function (e.g. low-frequen; a hand-designed bump/indicator-like shap; Random Gaussian packet mixture (8 bumps ; Deterministic analytic seeds: single bum ... | 100% of 1 (kappa 1.00) | 2% |
| A1: How is a candidate solution represented? | a dense real-valued array of samples on ; a parametric analytic form (e.g. Gaussia; a sparse / low-degree representation (e.; Raw nonnegative knot values on a uniform; Low-dimensional basis: spline/B-spline c ... | 100% of 1 (kappa 1.00) | - |
| A3: What quantity does the search optimise while it runs? | maximise R = //f*f//_2^2/(//f//_1^2 * // | 100% of 1 (kappa 1.00) | - |
| A4: Which moves or update steps change a solution? | no search at all: return the provided st; local gradient-free search (coordinate/p; population-based evolutionary search ove | 100% of 1 (kappa 1.00) | - |
| A5: How does the search accept worse solutions or escape a local optimum? | accept slightly worse with small probabi; no acceptance of worse; restart on stall | 100% of 1 (kappa 1.00) | - |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | Fixed geometric ladder of grid sizes (64; Single fixed high resolution from the st; Adaptive resolution: refine grid only wh | 100% of 1 (kappa 1.00) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A8: How is the time budget split between phases? | ignores budget_seconds entirely; run iterative optimization until budget_; allocate budget to a coarse-to-fine mult; Static pre-assigned fraction of the budg; Adaptive budget: allocate time proportio ... | 100% of 1 (kappa 1.00) | - |
| A9: How is the ratio R optimised: the objective the optimiser actually works on | Dinkelbach: maximise //f*f//_2^2 - lambd; Gradient steps on R itself (or log R) wi; Active-set minimax: the tied maxima of f; Exact line search on R per block or run ; Alternating projection: push f*f towards ... | 100% of 1 (kappa 1.00) | - |
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact maximum (a subgradient at the arg ; LogSumExp smooth max normalised by max(f; A fixed mild smooth max (beta about 100-; A softmax- or p-norm-weighted set of the; Smooth log-sum-exp (soft-max) surrogate  ... | 100% of 1 (kappa 1.00) | - |
| A13: How is the number of steps n chosen and changed | Exact k-fold repeat np.repeat(f, k) (R u; Zero-pad to the step limit and polish th; Average-pool a finer construction down t; Coarse to fine, upsampling by interpolat | 100% of 1 (kappa 1.00) | - |
| A14: What is the macro shape (the envelope) of f across its domain | One heavy comb block holding about 30% o; A tall spike plus a comb of smaller peak; A smooth arcsine-like density, 1/sqrt(1 ; A parametric series sum_j a_j (1 - 4x^2); Regular sparse packets under a smooth ra | 100% of 1 (kappa 1.00) | - |
| A15: What is the fine structure of f (the comb of teeth or blocks) | A fine, coherent periodic lattice of tee; Contiguous blocks with irregular spacing; A coarser parent with each cell split in; Number-theoretic support (Sidon/B2 sets,; Regular [small, big, small] triplets | 100% of 1 (kappa 1.00) | - |
| A16: Once converged, how does the program try to leave the local optimum | Small noise (about 1e-8 x max f), then a; Perturb along the gradient of the transi; Perturb only the lowest 1-5% Fourier mod; Structural surgery on blocks (shift, sca; Exact single-coordinate moves on the tie | 0% of 1 (kappa 0.00) | - |
| A17: Which part of f*f does the program's step aim at | The level transitions of f*f (lags with ; Only the tied maxima (the active set of ; Small-mass runs of f first | 100% of 1 (kappa 1.00) | - |
| A20: What symmetry or shape assumptions are imposed on f? | general unconstrained shape, no symmetry; enforce even symmetry (f(x)=f(-x)); enforce a unimodal or compactly supporte | 100% of 1 (kappa 1.00) | - |
| A21: Is there a separate final high-precision polish pass (larger beta, tighter tolerances, or  | A separate polish pass at the largest gr; No separate polish; keep one beta schedu; Post-hoc exact-knot local search (coordi | 100% of 1 (kappa 1.00) | - |

### Explorations chosen from the map (4: 3 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A13 -> Coarse to fine, upsampling by  | 0/1 | 3 | 0.853569 | running | founder H2 |
| T3 | flip | 1 | A18 -> a new option, unlike the liste | 1/1 | 3 | 0.800507 | running at 3 | founder H3 |
| T4 | build | 2 | A9 -> Exact line search on R per blo | 1/1 | 1 | 0.782305 | running | candidate  |
| T5 | build | 3 | A10 -> A softmax- or p-norm-weighted  | 1/1 | 1 | 0.752599 | running | candidate  |

## v102-helix-s2

- Generations 1-4: best 0.666666667 -> 0.842209958 (p0022, track T1); the main track now: T1.
- Exploration levels: level 0: 4 generations.
- Planned experiments by slot: main 4, build 4, track 3, flip 1.

### Records (2)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 1 | 0.842087388 | p0002 | wide | mutation | T1 |
| 4 | 0.842209958 | p0022 | wide | mutation | T1 |

### Side tracks opened (0)


### Generation by generation

| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |
|---|---|---|---|---|---|---|---|
| 1 | 0.842087388 | yes | 0 / 3 | 0 | main, build, flip | 0.707550 | the map begins with 1 known hills: H1 (0.666667, reached 0 more times); T2 opened (a new design built from nothing around A11 -> L-BFGS with Anderson acceleration of the Dinkelba…); T3 opened (a flip of A9 -> Alternating projection: push f*f towards a two-le… on p0001); new hill H2, found by T1 (seed): 0.842087, distance 0.211 from the nearest known hill (H1) |
| 2 | 0.842087492 |  | 0 / 3 | 0 | main, track:T2, build | 0.725267 | T3 gained (0.707550 -> 0.723766); T4 opened (a new design built from nothing around A13 -> Average-pool a finer construction down to n, then…); new hill H3, found by T2 (build): 0.723731, distance 0.211 from the nearest known hill (H1) |
| 3 | 0.842087492 |  | 1 / 3 | 0 | main, track:T3, build | 0.723734 | T4 gained (0.725267 -> 0.727261); T5 opened (a new design built from nothing around A16 -> Perturb along the gradient of the transition loss…); T4 landed on H3 (distance 0.030); T4 is now the top of H3 (0.727261); T3 landed on H3 (distance 0.039); T5 landed on H3 (distance 0.030) |
| 4 | 0.842209958 | yes | 2 / 3 | 0 | main, track:T2, build | 0.723734 | T2 gained (0.723731 -> 0.723734); T3 gained (0.723766 -> 0.723862); T6 opened (a new design built from nothing around A14 -> A tall spike plus a comb of smaller peaks); T2 goes on to the next rung (6 experiments): still rising (best 0.723734 at 3 experiments) |

### Hills (3: 2 on the map after its first generation, 1 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H2 | 0.842210 (p0022) | 1 | T1 (seed) | 0 | The new program uses a multi-resolution approach: it starts from a resampled grid and applies block-multiplicative perturbations, edge-preserving smoothing, and global noise, rather than the record's single-resolution co |
| H3 | 0.727261 (p0019) | 2 | T2 (build) | 3 | This program optimises a smooth soft-max surrogate of the sup-norm (log-sum-exp with increasing sharpness β) via L-BFGS on a squared-parameterisation w↦w², rather than hill-climbing heights directly. It adds Anderson ext |
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

### The design map (20 decisions, 23 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A1: How is a candidate solution represented? | a fixed-length dense real vector of leng; a piecewise-constant function on a nonun; a parametric family (e.g. Gaussian mixtu; variable-length dense vector with resamp; a nonnegative height vector on a fixed u ... | 100% of 3 (kappa 1.00) | 20% |
| A14: What is the macro shape (the envelope) of f across its domain | One heavy comb block holding about 30% o; A tall spike plus a comb of smaller peak; A smooth arcsine-like density, 1/sqrt(1 ; A parametric series sum_j a_j (1 - 4x^2); Regular sparse packets under a smooth ra ... | 100% of 2 (kappa 1.00) | 17% |
| A4: Which moves or update steps change a solution? | L-BFGS-B steps on w=sqrt(f); multiplicative coordinate descent on h; projected gradient ascent with adaptive ; projected gradient ascent on h | 33% of 3 (kappa 0.25) | 14% |
| A12: How is f >= 0 enforced | f = w^2 exactly (a cell at zero stays at; Clip or project to f >= 0 after each ste; An explicit support mask pruned on purpo | 100% of 3 (kappa 1.00) | 11% |
| A11: Which local optimiser solves the inner problem | L-BFGS on the smooth surrogate, many ite; L-BFGS with Anderson acceleration of the; Adam with gradient noise and elitist res; Simulated annealing or random search on ; none — a single hand-picked closed-form  ... | 67% of 3 (kappa 0.57) | 10% |
| A9: How is the ratio R optimised: the objective the optimiser actually works on | Dinkelbach: maximise //f*f//_2^2 - lambd; Gradient steps on R itself (or log R) wi; Active-set minimax: the tied maxima of f; Exact line search on R per block or run ; Alternating projection: push f*f towards ... | 100% of 3 (kappa 1.00) | 8% |
| A2: How is the first solution built? | return start unchanged if given, else a ; use start as a seed and locally perturb/; ignore start and always construct from s; a smooth analytic bump (sine-power) or t; random multi-start over many random init ... | 33% of 3 (kappa 0.00) | - |
| A3: What quantity does the search optimise while it runs? | Dinkelbach surrogate A - lambda*L1*LSE | 100% of 2 (kappa 1.00) | - |
| A5: How does the search accept worse solutions or escape a local optimum? | anneal beta and keep best R; random multiplicative restarts and coord; random kicks on stalled gradient ascent | 67% of 3 (kappa 0.40) | - |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | fixed resolution chosen up front (option; continuously refine resolution as a func; optimise at coarse resolution then inter | 100% of 2 (kappa 1.00) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A8: How is the time budget split between phases? | ignored entirely; no time-aware search o; allocate budget across a coarse-to-fine ; use budget for a stochastic optimizer (s; a fixed step-size schedule or fixed iter; adaptive step sizes from a line search o ... | 67% of 3 (kappa 0.40) | - |
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact maximum (a subgradient at the arg ; LogSumExp smooth max normalised by max(f; A fixed mild smooth max (beta about 100-; A softmax- or p-norm-weighted set of the; compute //f*f//_inf exactly as the max o ... | 100% of 3 (kappa 1.00) | - |
| A13: How is the number of steps n chosen and changed | Exact k-fold repeat np.repeat(f, k) (R u; Zero-pad to the step limit and polish th; Average-pool a finer construction down t; Coarse to fine, upsampling by interpolat | 67% of 3 (kappa 0.40) | - |
| A15: What is the fine structure of f (the comb of teeth or blocks) | A fine, coherent periodic lattice of tee; Contiguous blocks with irregular spacing; A coarser parent with each cell split in; Number-theoretic support (Sidon/B2 sets,; Regular [small, big, small] triplets | 100% of 2 (kappa 1.00) | - |
| A16: Once converged, how does the program try to leave the local optimum | Small noise (about 1e-8 x max f), then a; Perturb along the gradient of the transi; Perturb only the lowest 1-5% Fourier mod; Structural surgery on blocks (shift, sca; Exact single-coordinate moves on the tie ... | 67% of 3 (kappa 0.57) | - |
| A17: Which part of f*f does the program's step aim at | The level transitions of f*f (lags with ; Only the tied maxima (the active set of ; Small-mass runs of f first | 100% of 2 (kappa 1.00) | - |
| A18: What support and boundary treatment does f use (full support vs compact support with paddi | full support over all 50 entries, no exp; compact support with zero padding and tu; periodic vs. zero-padded convolution bou | 67% of 3 (kappa 0.00) | - |
| A19: How is the scale/normalization of f handled (implicit fixed scale, normalize to unit L2/L1 | implicitly fixed scale (constant 1), no ; normalize f to unit L2 or unit L1 before; search over scale as an explicit free pa; keep f nonnegative and let the ratio be ; fix //f//_1 = 1 or //f//_2 = 1 each step ... | 100% of 3 (kappa 1.00) | - |
| A20: How is the autocorrelation f*f computed and updated during search (full recompute, increme | recompute or incrementally update the fu; use FFT-based convolution with analytic ; exploit sparsity/structure (e.g. only up | 100% of 2 (kappa 1.00) | - |

### Explorations chosen from the map (5: 4 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A11 -> L-BFGS with Anderson accelerat | 1/1 | 3 | 0.723734 | running at 3 | founder H3 |
| T3 | flip | 1 | A9 -> Alternating projection: push f | 1/1 | 2 | 0.723862 | running | on H3 |
| T4 | build | 2 | A13 -> Average-pool a finer construct | 1/1 | 1 | 0.727261 | running | top H3 |
| T5 | build | 3 | A16 -> Perturb along the gradient of  | 1/1 | 1 | 0.723734 | running | on H3 |
| T6 | build | 4 | A14 -> A tall spike plus a comb of sm | 1/1 | 1 | - | running | -  |
