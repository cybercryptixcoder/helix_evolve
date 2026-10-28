# The second autocorrelation inequality: the state of the art (October 28, 2026)

The research behind v10 (docs/V10_DESIGN.md): every record we could find, the constructions themselves, the methods
behind them, what the field measured and what failed. Its machine-readable form is `helix10/sota.py` (the borrowed
axes, the Atlas's field findings, the imports); the constructions are in `data/field_ac2/` (13 MB, verified).

## The problem and the target

Maximise R(f) = ||f*f||_2^2 / (||f*f||_1 ||f*f||_inf) over non-negative step functions f (R <= 1 by Hoelder). Our
scorer and EinsteinArena's verifier (scipy `oaconvolve`, trapezoid-style quadrature on [0, f*f, 0]) agree to 12
digits on every construction below.

- **The record: 0.963588110582029** (EinsteinArena #1, ClaudeExplorer, July 22, 2026, n = 1,999,999). Not 0.97: no
  listed construction reaches 0.964.
- **The arena's rules:** n up to 2,000,000; a new #1 must beat the current one by 1e-5, so the target is
  **0.963598110582**.
- **The best published (peer-reviewable) bound:** 0.94136 (Jaech & Joseph 2025). AlphaEvolve's first published
  value was 0.8963.
- **Ours:** 0.9414417 (v9-s1, n = 104,992), from Code Zero, above every from-scratch value the field reports
  (0.90-0.93) and above the best published bound.

## Every record, by date

| Value | n | Who | When | How |
| --- | --- | --- | --- | --- |
| 0.88922 | 208 | Matolcsi & Vinuesa | 2010 | step function |
| 0.8963 | 50 | AlphaEvolve | May 2025 | evolutionary code search |
| 0.901564 | 575 | Boyer & Li | 2025 | simulated annealing + gradient |
| 0.94136 | 2,540 | Jaech & Joseph | Aug 2025 | Adam + noise + elitist respawn + upsampling |
| 0.959180 | 50,000 | TTT-Discover | Jan 2026 | test-time reinforcement learning |
| 0.961021 | 50,000 | AlphaEvolve V2 (Georgiev, Gomez-Serrano, Tao, Wagner) | Nov 2025 | evolutionary code search |
| 0.961206 | 100,000 | Together AI | Mar 2026 | projected gradient from AlphaEvolve V2's |
| 0.961986 | 100,000 | ClaudeExplorer | Mar 25, 2026 | iterated Dinkelbach |
| 0.962214 | 100,000 | JSAgent | Mar 31, 2026 | 1.6M construction average-pooled down, then Dinkelbach |
| 0.96258 | 1.6M | ImprovEvolve (not public) | Feb 2026 | LLM-evolved improve/perturb operators + 3 human edits |
| 0.962643 | 400,000 | ClaudeExplorer | Apr 16, 2026 | Dinkelbach, repeated up from 100k, beta to 1e11 |
| 0.962901 | 524,288 | Hyra | Jun 23, 2026 | a new construction (method unpublished) |
| 0.962946 | 1,048,576 | ClaudeExplorer | Jul 17, 2026 | Hyra's repeated twice, polished |
| 0.963433 | 1,999,999 | ClaudeExplorer | Jul 19, 2026 | Hyra's, at the cap, velocity cycles on GPUs |
| 0.963456 | 1,999,999 | MLAI-Yonsei | Jul 21, 2026 | a polish of 0.963433 |
| 0.963546, 0.963565 | 1,999,999 | ClaudeExplorer | Jul 21, 2026 | the same, the support grown to the whole grid |
| **0.963588** | 1,999,999 | ClaudeExplorer | Jul 22, 2026 | the same; the record since |
| 0.962274 | 2,000,000 | SIDON-DevinWright | Oct 26, 2026 | a 100k parent split into 20 sub-cells under a phase kernel |

## The families (from the constructions themselves)

Correlating the downloaded arrays: the arena's top 30 belong to a handful of lineages.

- **Hyra's lattice** (0.9629 at 524k, then 0.9635-0.96359 at 2M): a heavy comb block holding about 29% of the mass
  at one end, an empty band beside it, a graded ramp of bumps; the comb is a fine, coherent lattice (period 2.8e-3 of
  n, coherence 0.86). The record and its four predecessors are polishes of it (MLAI-Yonsei's correlates 0.996 with
  ClaudeExplorer's 0.963433). Found June 2026; nobody knows how.
- **The older comb family** (ClaudeExplorer's 100k/400k/1.6M, CHRONOS's 400k: correlation 0.999 with
  ClaudeExplorer's, JSAgent's 100k): irregular blocks (783 at 100k, 3,133 at 1.6M), the same blueprint mirrored,
  a coarser, less coherent lattice (period 5.4e-3, coherence 0.39). Its ceiling as n grows was about 0.96272.
- **AlphaEvolve V2's** (50k), refined by Together AI to 100k: [small, big, small] triplets at regular spacing.
- **TTT-Discover's** (50k), **Jaech & Joseph's** (2,540: a spike plus a comb), and small-n ones.

## The methods, and what each did

1. **Iterated Dinkelbach** (ClaudeExplorer, threads 126/133; code: github.com/justinkang221/second-autocorrelation-
   inequality, `src/dinkelbach_optimizer.py`). Maximise ||g||^2 - lambda ||g||_1 smoothmax(g), set lambda = R,
   repeat. LogSumExp normalised by max g; beta 1e5 -> 1e9 (later 1e14); L-BFGS on f = w^2; 3-5 rounds per beta.
   +7.8e-4 over the previous best at 100k. Every construction above 0.962 uses it.
2. **Resolution moves.** np.repeat(f, k) and zero-padding leave R exactly unchanged; interpolation destroys a tuned
   construction (-7e-3 to -0.8). Repeating then polishing gains (polish freedom grows with cells per tooth); padding
   to the cap and polishing gave about 10x faster gains per cycle than at 1M and let the construction grow new
   structure into the padding (the July record). Average-pooling a finer construction down to a lower n transplants
   its basin (JSAgent: 1.6M -> 100k beat every native 100k).
3. **Velocity cycles** (ClaudeExplorer's `run_velocity_continue.py`): noise of 1e-8 x max f on every cell, momentum
   0.3 along the last gain, a full Dinkelbach cascade; 100+ cycles of gains in Hyra's basin on GPUs.
4. **Loss anatomy** (experiment 12): with phi = g / max g, 1 - R = sum phi(1 - phi) / sum phi; about 2/3 of it
   lives in level transitions (phi in [0.1, 0.9]), under 5% of the lags; perturbing along the transition loss's
   gradient was the last idea tried.
5. **Exact vertex analysis** (NelsonFrontier, thread 255): at 2M the record is a kinked vertex (its max unique to
   1e-10; 4,000 lags within 1e-8, 322,000 within 1e-7); exact single-coordinate moves gain about 1e-10 each.
6. **Smaller levers:** low-frequency perturbations (the lowest 1-5% Fourier modes; 70% hit rate against 0% for pixel
   noise), packet/run coordinate ascent (+1.5e-5 at 100k, then exhausted), warm self-pruning (set the record on the
   first autocorrelation problem; untried here).

## What the field measured as dead ends

From the leaders' basin: tooth-split re-latticing (-3e-2; polish recovers only to 0.94), fitting f*f to a two-level
target then inverting (collapses to 0.85), region rebalancing, a +-0.05% differential stretch (-1.5e-2), trimming
then duplicating (-1.4e-2), block shifts (0 of 6,000), a 0.1% dilation (-7%), Gerchberg-Saxton/Fienup projections
(0 of 1,370), bulk seeding of new cells (destroys the score), fresh designed envelopes x combs (strand at
0.76-0.80). From scratch: B2/Sidon sets, Paley residues, power-law envelopes, Jaech's cascade extended to 400k: all
cap at 0.90-0.93.

## Measured here (October 28, one ARM-like CPU core, the field's own polish rewritten for it)

- **The record is nearly converged for CPU polishing.** The field's Dinkelbach polish (`helix10/programs/
  dinkelbach_polish.py`) on 0.963588110582: +3.40e-8 in 133 s, then +3.3e-9, +4.2e-10, +3.9e-11, then about
  1.4e-11 a round: **+3.79e-8 after eight rounds of 133 s, and flat.** The arena's 1e-5 is 260 times that. Polishing the record on our VM will not reach it.
- **Our record is equally locked:** the same polish on 0.9414417 gains +7e-9 and stops. Like the field's, our basin
  is a local optimum for this method; borrowing the polish alone moves nothing.
- At n = 2M one evaluation of R with its gradient takes 0.5 s here (0.6-0.8 s expected on the VM's ARM cores), so a
  150 s program gets about 150-250 of them; ClaudeExplorer's cycles used thousands per cycle on GPUs.

## Sources

- EinsteinArena, problem 3: https://einsteinarena.com/problems/second-autocorrelation-inequality (API:
  https://einsteinarena.com/api/solutions/best?problem_id=3; 30 discussion threads, 120 replies, read in full)
- ClaudeExplorer / Justin Kang: https://github.com/justinkang221/second-autocorrelation-inequality (README, skill.md,
  experiments/12_hyra_campaign/NOTES.md and its code)
- JSAgent: https://github.com/jmsung/einstein (knowledge/wiki: problems/3-autocorrelation.md, findings, techniques)
- Together AI: https://github.com/togethercomputer/EinsteinArena-new-SOTA
- Jaech & Joseph: https://github.com/ajaech/autocorrelation_inequality; arXiv:2508.02803
- Boyer & Li, arXiv:2506.16750; Rechnitzer, arXiv:2602.07292; Barnard & Steinerberger, arXiv:1903.08731;
  Matolcsi & Vinuesa, arXiv:1707.07464; Georgiev, Gomez-Serrano, Tao, Wagner, arXiv:2511.02864; Novikov et al.
  (AlphaEvolve), arXiv:2506.13131; Yuksekgonul et al. (TTT-Discover), arXiv:2601.16175; Kravatskiy, Khrulkov,
  Oseledets (ImprovEvolve), arXiv:2602.10233
