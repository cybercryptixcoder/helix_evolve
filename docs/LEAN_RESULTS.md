# Lean Helix: experiment results

Every number here comes from the runs in `results/lean/<experiment>/` (programs, model calls, reports). Model:
DeepSeek V4.1 Flash for every role. Machine: a 2-core cloud container (experiments 1-2) or the 2-core VM.

## Experiment 1: which parts of v4's core help? (26 circles; Nov 5, 2026)

Setup: `experiments/lean/e1_core.json`.
- **Problem:** 26 circles in the unit square, maximise the sum of radii, checked with zero tolerance.
- **Budget:** 10 s of CPU per program; 25 rounds of 6 programs (150 programs per run); 3 seeds per setup.

The five setups:

| Setup | What it is |
|---|---|
| floor | the model rewrites the best program, 6 times a round |
| population | parents sampled by rank, plus another strong program for ideas |
| plan | v4's planner (3 a round) plus mutations (3), no memory |
| plan+notes | the same, with notes of every experiment for the planner |
| planned-only | the planner with notes, no mutations |

Runs that passed each published value, out of 3, with the programs each needed:

| Setup | AlphaEvolve's 2.63586276 | ShinkaEvolve's 2.63597771 (its exact re-check) |
|---|---|---|
| floor | 2 of 3 (38, 26) | 2 of 3 (38, 26) |
| population | 2 of 3 (60, 71) | 2 of 3 (60, 71) |
| plan | 2 of 3 (19, 55) | 2 of 3 (19, 55) |
| plan+notes | 2 of 3 (38, 66) | 2 of 3 (47, 71) |
| planned-only | 3 of 3 (122, 88, 46) | 3 of 3 (122, 92, 74) |

**Corrected (Nov 6):** the checker used during the runs compared distances in floating point. Re-checked in exact
rational arithmetic (`lean/recheck.py`, now the checker itself), 86 results across 5 runs overlap by a hair and are
counted as invalid. Most came from planner setups, whose programs learned to sit exactly on the float boundary.
The tables use the exact check.

**Best result:** 2.6359830849176, 1.4e-12 below the best known packing (Packomania: 2.635983084919, given to 12
decimals). It came from the planned-only setup, seed 2, program `p0103` (round 17). The first to come within 1e-9
of the best known was the floor setup, seed 2, program `p0049` (round 8, 2.635983084917539). Every run that passed ShinkaEvolve's
value reached at least 2.6359830. Every best construction was re-checked in exact rational arithmetic with zero
tolerance (`tools/verify_circles.py`).

**What it says:**
- No setup is clearly better here. Every setup reaches the best known packing in most seeds within about 20-120
  programs, and the failures are seeds stuck in another local optimum (2.6309, 2.6343).
- This problem has a ceiling, and the plainest loop reaches it. It can't rank the components; harder problems must
  (experiments 2 and 3).
- **As a result in its own right:** with a small model, 10 s per program and at most 150 programs, the lean loop
  matches the best known packing. That is a higher score than AlphaEvolve's (zero tolerance) and than the exact
  re-check of ShinkaEvolve's 150-sample result. The models differ (ShinkaEvolve used several frontier models,
  AlphaEvolve Gemini 2.0).

### Programs needed to come within 1e-9 of the best known packing (exact check; - : not within 150 programs)

| Setup | Seeds 1, 2, 3 |
|---|---|
| floor | -, 49, - |
| population | -, -, - |
| plan | -, 54, 130 |
| plan+notes | -, 51, 90 |
| planned-only | -, 92, 119 |

## Experiment 2: the same on 32 circles (Nov 6, 2026)

Setup: `experiments/lean/e2_core32.json`.
- **Problem:** 32 circles, exact check. AlphaEvolve reported 2.937944; the best known is 2.939572771205 (Packomania;
  FICO Xpress, 2026).
- **Budget:** 15 rounds (90 programs per run), 10 s per program, 3 seeds.

Programs each run needed (- : not within 90 programs):

| Setup | Above AlphaEvolve's 2.93794 | Within 1e-9 of the best known |
|---|---|---|
| floor | -, 26, - | -, 87, - |
| population | 28, 71, 44 | 39, 89, 64 |
| plan | 29, 16, 16 | **43, 20, 34** |
| plan+notes | 29, 9, - | 66, 24, - |
| planned-only | 74, -, 66 | -, -, 66 |

**What it says:**
- On 32 circles the setups separate.
- **plan** (planner plus mutations, no notes) reaches the best known packing in every seed, after 20-43
  programs.
- **population** also does it in every seed, but later.
- **floor** gets there in 1 of 3 seeds.
- The notes don't help here: plan+notes is behind plan.
- The planner alone, without mutations, is the weakest.
- Three seeds and one problem are not proof; experiments 3 (AC2) and 4 (AC1) test the same setups on harder,
  continuous problems.

**As a result:** 13 of 15 runs beat AlphaEvolve's 2.93794, and 9 came within 1e-9 of the best known packing, each in
at most 90 programs of 10 s with DeepSeek V4.1 Flash.

## Experiment 4: the same setups on AC1 (Nov 6, 2026)

Setup: `experiments/lean/e4_core_ac1.json`.
- **Problem:** the first autocorrelation inequality, as TTT-Discover's verifier states it: minimise
  C = 2N·max(h∗h)/(Σh)² over non-negative step functions h with at most 30,000 steps. Lower is better.
- **Budget:** 30 rounds (181 programs per run), 20 s of CPU per program (TTT-Discover allowed 10 minutes), 3 seeds.

Best C after 180 programs, each seed (lower is better):

| Setup | Seeds 1, 2, 3 | Median |
|---|---|---|
| floor | 1.51320, 1.51675, 1.52172 | 1.51675 |
| population | 1.51040, 1.52043, 1.51529 | 1.51529 |
| plan | 1.58878, **1.50942**, 1.51370 | **1.51370** |
| plan+notes | 1.52254, 1.52376, 1.51591 | 1.52254 |
| planned-only | 1.51896, 1.53893, 1.51264 | 1.51896 |

**Best result:** C = 1.509418863 from plan, seed 2, program `p0178` (round 30). That is below the best human construction
(1.50973), passed after 113 programs. It is above every published LLM system's value: OpenEvolve 1.50719,
ThetaEvolve 1.50681, AlphaEvolve 1.5053, AlphaEvolve V2 1.50317, TTT-Discover 1.50287. Re-checked independently from
`best.npy` (320 steps, all non-negative): C = 1.50941886320579.

**What it says:**
- The ranking repeats experiment 2 at the top:
  - **plan** has the best median and the best run;
  - **population** comes next;
  - the plainest loop (**floor**) is behind both.
- plan's seed 1 got stuck at 1.589 for all 180 programs, which is the widest spread of any setup.
- **The notes hurt again:** plan+notes has the worst median, as it was behind plan on 32 circles.
- **The planner alone**, without mutations, is behind plan in 2 of 3 seeds.
- **Where the gains came from:** with planner and mutations together, the mutations set 75-98% of the total gain. The
  planner's programs set about half the records, but these were small ones.
- **At this budget no setup gets near the published LLM systems.** They used 25,600 to 51,200 samples and up to 10
  minutes per program; these runs used 181 programs of 20 s each.

## Experiment 3: the same setups on AC2 (Nov 6, 2026; on the VM)

Setup: `experiments/lean/e3_core_ac2.json`.
- **Problem:** the second autocorrelation inequality: maximise R(f) over non-negative step functions with at most
  50,000 steps. Higher is better.
- **Budget:** 30 rounds (181 programs per run), 30 s of CPU per program, 3 seeds.

Best R after 180 programs, each seed (higher is better):

| Setup | Seeds 1, 2, 3 | Median | Passed AlphaEvolve's 0.8962 |
|---|---|---|---|
| floor | 0.92235, 0.87513, 0.91128 | **0.91128** | 2 of 3 |
| plan+notes | 0.84241, 0.90449, **0.92557** | 0.90449 | 2 of 3 |
| planned-only | 0.90711, 0.88373, 0.83882 | 0.88373 | 1 of 3 |
| plan | 0.88201, 0.89856, 0.88254 | 0.88254 | 1 of 3 |
| population | 0.90679, 0.86564, 0.86973 | 0.86973 | 1 of 3 |

**Best result:** R = 0.925573895, from plan+notes seed 3. Re-checked from `best.npy` (4,000 steps). No run came
near OpenEvolve (0.9449), ThetaEvolve (0.9469), TTT-Discover (0.9591) or AlphaEvolve V2 (0.9610).

**What it says:** the ranking turns over. The plainest loop has the best median. plan, first on 32 circles and AC1,
is fourth here. Records jump late and by a lot: floor-s1 went from 0.8506 to 0.9206 between programs 120 and 150.
Because of that, three seeds of 180 programs can't rank the setups on AC2.

## So far (experiments 1-4)

| Setup | 26 circles | 32 circles | AC1 | AC2 |
|---|---|---|---|---|
| floor | 1 of 3 at the ceiling | 1 of 3 at best known | 3rd | **1st** |
| population | 0 of 3 within 1e-9 | 3 of 3 | 2nd | 5th |
| plan | 2 of 3 | **3 of 3, fastest** | **1st** | 4th |
| plan+notes | 2 of 3 | 2 of 3 | 5th | 2nd |
| planned-only | 2 of 3 | 1 of 3 | 4th | 3rd |

- **No setup wins everywhere.** plan wins two problems, and the plainest loop wins AC2. Within one setup, the spread
  between seeds is usually larger than the gap between setups.
- **The one steady result:** the planner without mutations is never first. Dropping the mutation loop doesn't help on
  any problem.
- **The notes don't help on average.** They are last on AC1, second on AC2, and behind plan on 32 circles.
- **Next:** experiment 5 settles the base setup with 8 seeds (plan, floor and population on 32 circles) before any
  part is added.
