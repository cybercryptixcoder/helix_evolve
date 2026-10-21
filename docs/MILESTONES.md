# Milestones

## October 20-21, 2026: Helix v4 passes AlphaEvolve's first published result on the second autocorrelation inequality

### What happened
The v4 overnight job (`results/v4/`, `docs/V4_DESIGN.md`) ran 9 runs (3 memory conditions × 3 seeds) on the second
autocorrelation inequality, each starting from a constant function (0.667). Mid-run (October 21, 00:31; final numbers
and verification to be added when the job finishes):

| Run | Generation | Best |
|---|---|---|
| atlas-s1 | 14 | **0.93601** |
| journal-s2 | 16 | 0.92394 |
| control-s2 | 15 | 0.90477 |
| journal-s1 | 11 | 0.89599 |
| atlas-s2 | 14 | 0.89226 |
| atlas-s3, control-s1, control-s3, journal-s3 | 10-15 | 0.8824-0.8825 |

Four runs passed AlphaEvolve's May 2025 bound (0.8962); five passed the 2010 record (0.88922).

### The claim, and how far it holds

**What can be said:** *On the identical problem, scored with DeepMind's own verification formula, Helix v4 found a
construction certifying C2 ≥ 0.936: above AlphaEvolve's first published result for this problem (0.8962, May 2025)
and above the human-optimised construction of Boyer & Li (0.9016, 2025); below Jaech & Joseph (0.9414, 2025) and the
best known value (0.9626, 2026), which includes AlphaEvolve's own later result (0.961).*

**Why it holds (same problem, same scoring):**
- The problem: the smallest C2 with ‖f*f‖₂² ≤ C2 ‖f*f‖₁ ‖f*f‖∞ for all non-negative f; any non-negative f gives a
  lower bound. DeepMind's statement (`google-deepmind/alphaevolve_results`, `mathematical_results.ipynb`, section B.2)
  and ours (`helix4/problems/ac2.py`) are the same; both restrict to step functions with equal-width steps; the ratio
  doesn't depend on the interval or the scale.
- The scoring: DeepMind's verification cell integrates the piecewise-linear f*f exactly (the h/3 (y1² + y1y2 + y2²)
  rule). Ours is the same formula. On DeepMind's own 50-step construction our evaluator gives **0.896279944155**,
  identical to their code to 12 digits, and exact rational arithmetic agrees (`tools/verify_ac2.py
  --alphaevolve-may-2025`; Boyer & Li independently report 0.89628 for it).
- Every one of our constructions is checked the same three ways (`tools/verify_ac2.py`; the next job writes
  `results/v4/VERIFICATION.md` automatically). A lower bound is a fact about the construction, not about how it was
  found: if the exact value of our step function is 0.936, then C2 ≥ 0.936, whoever or whatever produced it.

**The set-ups, side by side:**

| | AlphaEvolve, May 2025 | Helix v4, October 2026 |
|---|---|---|
| Model | Gemini 2.0 Flash + Gemini 2.0 Pro (ensemble) | DeepSeek V4.1 Flash (via Luminal); planner thinks at "low", everything else no thinking |
| What evolves | a search heuristic program with a time budget, shown the best construction so far | the same: `construct(budget_seconds, start)`, warm-started from its parent's construction |
| Time per program | 1000 s (their published prompt for these problems) | 30 s of CPU |
| Start | "a simple or a random construction" | a constant function (0.667) |
| Generations / samples | not published for this problem; called "a quick experiment" (Georgiev, Gómez-Serrano, Tao, Wagner 2025) | 20 generations × 6 programs ≈ 120 programs per run; 9 runs |
| Hardware | Google's (not published) | one 2-core ARM cloud VM shared by all 9 runs |
| Result | 0.8962 (50 steps); later, with more time, 0.961 (50,000 steps) | 0.936 (mid-run; verification pending) |

**What should not be said:**
- "Helix beat AlphaEvolve." AlphaEvolve's later runs reached 0.961 on this very problem; the May 2025 number came
  from a quick experiment. The fair statement compares against a published result, not against the system.
- "With a dumber model." DeepSeek V4.1 Flash (2026) is newer than Gemini 2.0 (early 2025); there is no evidence it
  is weaker.
- Ignoring contamination. Our model was trained after the 0.94 (August 2025) and 0.96 (November 2025) papers, so it
  may know their *techniques* (gradient methods, smoothing the max, resolution ladders). It did not recall a
  construction: zero-shot it scored 0.862 with a 7-step function, and the run logs show the score built up step by
  step, with the breakthroughs coming after the planner diagnosed its own plateau. Several runs settled first on the
  1/√x construction (≈ 0.8825), which is classical.

**What it does show:** a cheap, fast model in an evolutionary loop with memory, on one small machine overnight,
produces certified constructions that were state of the art in mid-2025, starting from a constant function.

### Sources
- DeepMind, AlphaEvolve results notebook: https://github.com/google-deepmind/alphaevolve_results (section B.2)
- DeepMind, problem repository and prompts: https://github.com/google-deepmind/alphaevolve_repository_of_problems
  (`experiments/autocorrelation_problems`)
- AlphaEvolve paper (models, set-up): https://arxiv.org/abs/2506.13131
- Georgiev, Gómez-Serrano, Tao, Wagner, Mathematical exploration and discovery at scale: https://arxiv.org/abs/2511.02864
- Boyer & Li, An improved example for an autoconvolution inequality: https://arxiv.org/abs/2506.16750
- Jaech & Joseph, Further improvements to the lower bound for an autoconvolution inequality: https://arxiv.org/abs/2508.02803
