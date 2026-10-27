# The replay: is the design map real? (v8-s1)

Stage 0 of the proof of concept (`helix9/replay.py`, `docs/V9_DESIGN.md`). No programs were run.

## Verdicts

- Reliability: 12 of 13 measured decisions read with at least 80% agreement (pass)
- The model's knowledge: predicted vs actual change from base to child, rank correlation +0.158 over 120 later programs (permutation p = 0.042; on the 106 that moved a decision: +0.185, p = 0.033) (pass)
- The level: the model's predicted score vs the later programs' actual scores, rank correlation +0.060 (permutation p = 0.253); their parents' scores alone: +0.996
- The codebook: 13 decisions from 425 distinct names the Cartographer gave; 458 programs read, 119 of them twice.

## The decisions, how reliably they are read, and what the model says about them

| Decision | Read twice | Agreement | Kappa | Importance |
|---|---|---|---|---|
| A31: How is the iterate rescaled/normalized after each step (rescale by 1/sqrt(max f*f), no res | 119 | 97% | 0.87 | 15% |
| A2: Representation of the unknown function f | 119 | 92% | 0.70 | 2% |
| A1: Objective parametrisation / domain in which the ratio is optimised | 118 | 75% | 0.49 | 0% |
| A5: Resolution / grid size strategy | 118 | 85% | 0.78 | 0% |
| A8: Peak-window polishing | 118 | 95% | 0.78 | 0% |
| A3: Handling of zero entries / support | 118 | 87% | 0.77 | 0% |
| A4: Core local optimiser | 118 | 95% | 0.71 | 0% |
| A6: Global exploration mechanism | 119 | 85% | 0.78 | 0% |
| A36: Is the autoconvolution computed as a black-box FFT/convolution, or is its quadratic/Gram/T | 118 | 84% | 0.23 | 0% |
| A7: Time / budget allocation | 118 | 87% | 0.40 | 0% |
| A13: symmetry / structure of the candidate | 119 | 97% | 0.49 | 0% |
| A30: How is the shift/symmetry of the f*f peak position handled (implicit shift invariance, exp | 119 | 98% | 0.66 | 0% |
| A37: How is the final answer selected from the candidates found (single best-R array, ensemble/ | 119 | 100% | 1.00 | 0% |

## Options and their estimated effects (the whole archive)

- **A31: How is the iterate rescaled/normalized after each step (rescale by 1/sqrt(max f*f), no rescaling, or fix ||f||_1=1)?**
  - Rescale by 1/sqrt(max) each step: 395 programs, effect +0.056693 ± 0.017071
  - Analytic scale or block parameterization: 1 programs, effect +0.002998 ± 0.025352
  - Fix max/inf-norm to 1: 6 programs, effect -0.011464 ± 0.019221
  - Fix L1 mass to 1: 9 programs, effect -0.016208 ± 0.018202
  - No rescale, free scale: 47 programs, effect -0.032019 ± 0.016529
- **A2: Representation of the unknown function f**
  - Low-dimensional parametric family: 22 programs, effect +0.040132 ± 0.013625
  - Cumulative/quantile/moving-mesh: 1 programs, effect +0.004807 ± 0.020051
  - Reparameterized or block heights: 29 programs, effect -0.004118 ± 0.012976
  - Dense grid heights: 401 programs, effect -0.004318 ± 0.012246
  - Discrete/sparse/multiscale structure: 4 programs, effect -0.022356 ± 0.016828
- **A1: Objective parametrisation / domain in which the ratio is optimised**
  - Minimax/Dinkelbach/alternating reformulation: 18 programs, effect +0.004869 ± 0.006438
  - Exact max subgradient/bundle: 6 programs, effect +0.004171 ± 0.007148
  - Constrained/penalty/augmented-Lagrangian solver: 6 programs, effect +0.001859 ± 0.007187
  - Different functional/flatness/global proxy: 86 programs, effect -0.001330 ± 0.005451
  - Softmax/p-norm surrogate of max: 341 programs, effect -0.007888 ± 0.005252
- **A5: Resolution / grid size strategy**
  - Fixed single resolution: 166 programs, effect +0.003093 ± 0.003940
  - Multigrid V-cycle: 3 programs, effect +0.000865 ± 0.005605
  - Adaptive mesh refinement: 3 programs, effect +0.000386 ± 0.005609
  - Resampling / lift-fold polish: 44 programs, effect +0.000073 ± 0.004543
  - Free N / multi-resolution search: 94 programs, effect -0.000323 ± 0.004104
  - Coarse-to-fine homotopy ladder: 147 programs, effect -0.003175 ± 0.003994
- **A8: Peak-window polishing**
  - Contiguous peak window polish: 392 programs, effect +0.003123 ± 0.005226
  - Multi-window near-max polish: 10 programs, effect +0.001762 ± 0.006201
  - Full-array uniform polish: 55 programs, effect -0.003581 ± 0.005463
- **A3: Handling of zero entries / support**
  - Prune/revive heuristic sweeps: 27 programs, effect +0.001811 ± 0.007388
  - Dense nonnegative vector, implicit sparsity: 267 programs, effect +0.001769 ± 0.007370
  - Explicit combinatorial support search: 1 programs, effect -0.000673 ± 0.007480
  - Frozen sparse support, active cells only: 162 programs, effect -0.001318 ± 0.007376
- **A4: Core local optimiser**
  - Second-order trust-region / Newton-CG: 7 programs, effect +0.004676 ± 0.006808
  - L-BFGS-B with analytic gradients: 424 programs, effect +0.002936 ± 0.005723
  - Stochastic gradient / Adam minibatch: 1 programs, effect -0.000430 ± 0.007308
  - Derivative-free / stochastic global search: 6 programs, effect -0.002263 ± 0.006953
  - Surrogate scalarisation with L-BFGS-B: 19 programs, effect -0.003402 ± 0.006324
- **A6: Global exploration mechanism**
  - Exact-R Gauss-Newton plateau attack: 57 programs, effect +0.001994 ± 0.007559
  - Discrete structural support edits: 18 programs, effect +0.001369 ± 0.007613
  - Single-trajectory local descent: 231 programs, effect +0.000937 ± 0.007603
  - Basin-hopping / simulated annealing: 26 programs, effect -0.000103 ± 0.007562
  - Random multi-start from seeds: 115 programs, effect -0.001016 ± 0.007558
  - Population/evolutionary/CMA-ES search: 11 programs, effect -0.003180 ± 0.007654
- **A36: Is the autoconvolution computed as a black-box FFT/convolution, or is its quadratic/Gram/Toeplitz or Fourier-diagonal structure exploited explicitly in the solv**
  - Exact convolution with analytic backprop: 434 programs, effect +0.002497 ± 0.006233
  - Fourier-domain diagonalization: 1 programs, effect +0.000701 ± 0.007030
  - Black-box FFT/convolution with autodiff: 22 programs, effect -0.001796 ± 0.006317
- **A7: Time / budget allocation**
  - Adaptive bandit budget reallocation: 4 programs, effect +0.002119 ± 0.006489
  - Stagnation-triggered restarts, no fixed phases: 24 programs, effect +0.001371 ± 0.005784
  - Many short restarts, keep best: 1 programs, effect -0.000135 ± 0.006716
  - Single fixed deadline, sequential phases: 428 programs, effect -0.002078 ± 0.005548

Interacting decisions: A3 x A6
