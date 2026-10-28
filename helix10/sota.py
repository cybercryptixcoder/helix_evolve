"""What the field knows about the second autocorrelation inequality, as of October 28, 2026 (docs/AC2_SOTA.md).

Three parts, each used by v10 (docs/V10_DESIGN.md):
- AXES: the field's design decisions and their options (borrowed axes). They are added to the design map's codebook,
  on an existing decision when the map has one for it (the option is new), else as a new decision. Both run modes get
  them. Exploration is biased towards them: every option is tried as a target before the map's own choices take over.
- FINDINGS: what the field measured, with sources, added to the Atlas as findings of kind "field" (both modes). They
  tell the planner how far each approach has gone, which is the point: the Atlas knows where the known approaches
  saturate.
- IMPORTS: the field's constructions, one per family and approach, verified on download (the warm mode only), and
  PROGRAMS (helix10/programs/): the field's methods rewritten to this problem's interface (the warm mode only).

Every number here was checked against its source; the arena scores were recomputed from the downloaded arrays with
the arena's own verifier (tools/verify_ac2.py agrees to 12 digits).
"""
from __future__ import annotations

ARENA = "https://einsteinarena.com/problems/second-autocorrelation-inequality"
API = "https://einsteinarena.com/api"
CE = "https://github.com/justinkang221/second-autocorrelation-inequality"
CE12 = CE + "/blob/main/experiments/12_hyra_campaign/NOTES.md"
JS = "https://github.com/jmsung/einstein"
TOGETHER = "https://github.com/togethercomputer/EinsteinArena-new-SOTA"
JAECH = "https://github.com/ajaech/autocorrelation_inequality"


def thread(n):
    return f"EinsteinArena thread {n} ({ARENA}, discussions)"


# The record: arena #1 since July 22, 2026. The arena caps n at 2,000,000 and accepts a new #1 only 1e-5 above it.
RECORD = {"score": 0.963588110582029, "agent": "ClaudeExplorer", "date": "2026-07-22", "n": 1_999_999,
          "arena_id": 2416}
ARENA_GATE = 1e-5
ARENA_TARGET = RECORD["score"] + ARENA_GATE          # 0.963598110582...
MAX_N = 2_000_000

# ---------------------------------------------------------------------------------------------- the borrowed axes
# Each: a decision (its question), the options the field uses, and `attach`: names of decisions an existing map may
# already have for it (the options are then added there). An option's note is shown to the annotator and the planner.
AXES = [
    {"key": "objective", "question": "How is the ratio R optimised: the objective the optimiser actually works on",
     "attach": ["Objective parametrisation / domain in which the ratio is optimised"],
     "options": [
         ("Dinkelbach: maximise ||f*f||_2^2 - lambda*||f*f||_1*smoothmax(f*f), then lambda = R, repeated",
          "iterated Dinkelbach (fractional programming); behind every construction above 0.962 (" + thread(133) + ")"),
         ("Gradient steps on R itself (or log R) with a smooth max",
          "the direct route: vanishing gradients on the flat top (" + thread(133) + ")"),
         ("Active-set minimax: the tied maxima of f*f as constraints with dual weights (LP, SLSQP, persistent dual)",
          "KKT view of the plateau (" + thread(43) + "; " + CE + " experiments/12, gpu_pd_optimizer)"),
         ("Exact line search on R per block or run of f (no gradient)",
          "packet/run-coordinate ascent: +1.5e-5 at 100k, then exhausted (" + thread(92) + ")"),
         ("Alternating projection: push f*f towards a two-level target, then project back to f >= 0",
          "Gerchberg-Saxton/Fienup; no gain in 1,370 trials on the leaders (" + thread(212) + ")"),
     ]},
    {"key": "max", "question": "How is the maximum of f*f (the L-infinity norm) handled in the optimised objective",
     "attach": [],
     "options": [
         ("Exact maximum (a subgradient at the arg max)", "kinked: smooth methods stall at the vertex (" + thread(255) + ")"),
         ("LogSumExp smooth max normalised by max(f*f), beta annealed upward (1e5 to 1e9 and beyond, up to 1e14)",
          "the leaders' choice; the normalisation keeps high beta stable (" + thread(133) + "; " + CE12 + ")"),
         ("A fixed mild smooth max (beta about 100-500 relative to the max)",
          "Adam-friendly; too smooth to resolve the 1e-7 ties at the top (" + thread(133) + ", CHRONOS)"),
         ("A softmax- or p-norm-weighted set of the top lags", "a smooth relative of the active set"),
     ]},
    {"key": "optimiser", "question": "Which local optimiser solves the inner problem",
     "attach": ["Core local optimiser"],
     "options": [
         ("L-BFGS on the smooth surrogate, many iterations per Dinkelbach round",
          "the leaders' inner solver, 3-5 rounds per beta (" + thread(133) + ")"),
         ("L-BFGS with Anderson acceleration of the Dinkelbach iterates",
          "used in the July 2026 polish of the record's basin (" + CE12 + ")"),
         ("Adam with gradient noise and elitist respawn of the worst candidates",
          "Jaech & Joseph 2025 (published 0.94136; their released function has 2,540 steps; " + JAECH + ")"),
         ("Simulated annealing or random search on f", "Boyer & Li 2025 (0.901564, arXiv:2506.16750)"),
     ]},
    {"key": "positivity", "question": "How is f >= 0 enforced",
     "attach": ["How are the array values parametrized to enforce positivity and handle dynamic range"],
     "options": [
         ("f = w^2 exactly (a cell at zero stays at zero: the support is locked)",
          "the leaders' choice; the optimiser can't revive a dead cell (" + CE + ")"),
         ("Clip or project to f >= 0 after each step", "lets cells die and revive"),
         ("An explicit support mask pruned on purpose (zero the smallest cells, re-optimise, repeat)",
          "warm self-pruning: set the record on the first autocorrelation problem (" + JS + ", wiki techniques)"),
     ]},
    {"key": "resolution", "question": "How is the number of steps n chosen and changed",
     "attach": ["Resolution / grid size strategy"],
     "options": [
         ("Exact k-fold repeat np.repeat(f, k) (R unchanged), then polish at the finer grid",
          "score-preserving to 1e-16; polish freedom grows with cells per tooth (" + thread(212) + "; " + CE12 + ")"),
         ("Zero-pad to the size cap (2,000,000) and polish there, letting structure grow into the padding",
          "the single biggest lever of the July record: about 10x faster gains per cycle (" + CE12 + ")"),
         ("Average-pool a finer construction down to n, then polish (a basin transplant)",
          "JSAgent: 1.6M pooled to 100k gave 0.96221, above any native 100k (" + thread(180) + ")"),
         ("Coarse to fine, upsampling by interpolation between stages",
          "works from small n (Jaech & Joseph); interpolating a tuned construction destroys it (" + thread(211) + ")"),
     ]},
    {"key": "envelope", "question": "What is the macro shape (the envelope) of f across its domain",
     "attach": [],
     "options": [
         ("One heavy comb block holding about 30% of the mass at one end, an empty gap beside it, a graded ramp of bumps",
          "the blueprint of the best constructions, found independently twice (" + thread(254) + ")"),
         ("A tall spike plus a comb of smaller peaks", "Jaech & Joseph 2025's continuous extremiser (" + CE + ")"),
         ("A smooth arcsine-like density, 1/sqrt(1 - 4x^2) on [-1/2, 1/2]",
          "Barnard & Steinerberger: its autoconvolution is flat in the limit (arXiv:1903.08731)"),
         ("A parametric series sum_j a_j (1 - 4x^2)^(j - 1/2) (about 100 terms)",
          "Rechnitzer 2026's Bessel-type ansatz (arXiv:2602.07292)"),
         ("Regular sparse packets under a smooth raised-cosine envelope", "from scratch, caps at 0.903 (" + thread(103) + ")"),
     ]},
    {"key": "comb", "question": "What is the fine structure of f (the comb of teeth or blocks)",
     "attach": [],
     "options": [
         ("A fine, coherent periodic lattice of teeth (period about 0.3% of the domain)",
          "Hyra's innovation: half the relative period and twice the coherence of the older family (" + thread(254) + ")"),
         ("Contiguous blocks with irregular spacing found by optimisation (hundreds to thousands of blocks)",
          "the older family: 783 blocks at 100k, 3,133 at 1.6M (" + thread(133) + ")"),
         ("A coarser parent with each cell split into about 20 sub-cells under a phase kernel",
          "NIGHTFALL: a 100k parent to 2M, 0.962274 (" + thread(287) + ")"),
         ("Number-theoretic support (Sidon/B2 sets, difference sets, quadratic residues)",
          "caps at about 0.903 from scratch (" + thread(127) + ")"),
         ("Regular [small, big, small] triplets", "the 50k constructions of March 2026 (" + thread(59) + ")"),
     ]},
    {"key": "escape", "question": "Once converged, how does the program try to leave the local optimum",
     "attach": [],
     "options": [
         ("Small noise (about 1e-8 x max f), then a full re-polish, with momentum along the last improving step",
          "velocity cycles: sustained gains for 100+ cycles in the record's basin (" + CE12 + ")"),
         ("Perturb along the gradient of the transition loss (lags where f*f crosses between its levels), re-polish",
          "aims at where 2/3 of the loss lives (" + CE12 + ")"),
         ("Perturb only the lowest 1-5% Fourier modes of f, then re-polish",
          "about 70% of such moves improved, against about 0% for pixel noise (" + thread(180) + ")"),
         ("Structural surgery on blocks (shift, scale, split, merge, remove), then re-polish",
          "useful early; on the leaders, 6,000 block shifts gained nothing (" + thread(212) + ")"),
         ("Exact single-coordinate moves on the tied plateau (incremental update of f*f, no FFT)",
          "harvests about 1e-10 per move at the vertex (" + thread(255) + ")"),
     ]},
    {"key": "target", "question": "Which part of f*f does the program's step aim at",
     "attach": ["Where is polishing effort concentrated: full array, peak-centred windows, or windows around"],
     "options": [
         ("The level transitions of f*f (lags with f*f/max between 0.1 and 0.9)",
          "about 2/3 of 1 - R lives there, in under 5% of the lags; crossings are 8-11 cells wide (" + CE12 + ")"),
         ("Only the tied maxima (the active set of the L-infinity norm)", "the vertex's constraints (" + thread(255) + ")"),
         ("Small-mass runs of f first", "packet ascent's order (" + thread(92) + ")"),
     ]},
]

# ---------------------------------------------------------------------------------------------- the field's findings
FINDINGS = [
    ("The records. Arena #1: 0.963588110582 (ClaudeExplorer, July 22, 2026, n = 1,999,999). The arena allows up to "
     "2,000,000 steps and lists a new #1 only 1e-5 above the current one (0.963598). Before it: 0.963565, 0.963546, "
     "0.963456, 0.963433 (July 2026), all on one family.", ARENA),
    ("How the best score grew with n: 0.96221 (100k), 0.96264 (400k), 0.96290 (524k, Hyra), 0.96295 (1.05M), "
     "0.96343 then 0.96359 (2M). Good constructions are tuned to their own n: interpolating one to another n loses "
     "7e-3 to 0.8; an exact k-fold repeat np.repeat(f, k) and zero-padding leave R unchanged.",
     thread(255) + "; " + thread(211) + "; " + thread(212)),
    ("Iterated Dinkelbach (maximise ||g||_2^2 - lambda*||g||_1*LSEmax(g), lambda = R after each round), LogSumExp "
     "normalised by max g with beta annealed 1e5 -> 1e9 (later 1e14), L-BFGS on f = w^2: the method behind every "
     "construction above 0.962; +7.8e-4 over the previous best at 100k.", thread(133) + "; " + CE),
    ("From random or designed starts, the field's from-scratch constructions cap at about 0.90-0.93 (sparse packets "
     "0.903; Adam cascade to 400k 0.901; CPU Dinkelbach at n = 2,000 0.930). Every construction above 0.96 descends "
     "from a seed that already had the right irregular block structure.",
     thread(127) + "; " + JS + " (findings/dead-end-p3-jaech-cascade-extended.md)"),
    ("The best constructions share one blueprint: a heavy comb block holding about 29% of the mass at one end, an "
     "empty band beside it, a graded ramp of bumps over the rest (mirroring f leaves R unchanged). Hyra's comb is a "
     "fine coherent lattice: period 2.8e-3 of n, coherence 0.86, against 5.4e-3 and 0.39 for the older family.",
     thread(254)),
    ("Near the optimum f*f is two-level (41% of lags within 1% of the max). With phi = g/max g, 1 - R = "
     "sum phi(1 - phi) / sum phi: about 2/3 of the loss lives in the level transitions (phi in [0.1, 0.9]), under 5% "
     "of the lags. Crossings are 8-11 cells wide at best, but a tail of wide ramps carries most of the transition loss; "
     "narrowing them to that floor would be worth about +0.019 (their estimate).", CE12),
    ("The record (0.963588 at 2M) is a kinked vertex: its max is unique to 1e-10; about 4,000 lags lie within 1e-8 "
     "of it and 322,000 within 1e-7. Every smooth direction lowers R; exact single-coordinate moves still gain about "
     "1e-10 each. The Dinkelbach polish on one CPU core gains +3.4e-8 in 133 s, +3.8e-8 in 18 minutes, then nothing.",
     thread(255) + "; measured here, October 28 (docs/AC2_SOTA.md)"),
    ("Polishing at the size cap: zero-padding to 2M then polishing gained about 7e-6 per cycle against 6e-7 at 1M, "
     "and the construction grew new structure into the padding; velocity cycles (noise 1e-8 x max f, momentum 0.3, "
     "full cascade to beta 1e14) kept gaining for 100+ cycles. This took 0.96290 to 0.96359 on GPUs.", CE12),
    ("Measured dead ends from the leaders' basin: tooth-split re-latticing (-3e-2), fitting f*f to a two-level target "
     "then inverting (collapses to 0.85), region rebalancing, a +-0.05% differential stretch (-1.5e-2), trimming then "
     "duplicating, block shifts (0 of 6,000), a 0.1% dilation (-7%), Gerchberg-Saxton projections (0 of 1,370).",
     CE12 + "; " + thread(212)),
    ("Average-pooling a high-resolution construction down to a lower n, then polishing, transplants its basin "
     "(1.6M pooled to 100k: 0.96221, above the native 100k optimum 0.96199); pooling from the July 2M family down "
     "failed (0.93).", thread(180)),
    ("Perturbing only the lowest 1-5% Fourier modes of f before re-polishing improved about 70% of the time, against "
     "about 0% for random pixel noise (100k, the older family).", thread(180)),
    ("Published bounds: Matolcsi & Vinuesa 0.88922; Boyer & Li 0.901564 (simulated annealing + gradient, 575 steps); "
     "AlphaEvolve 0.8963 (50 steps, May 2025); Jaech & Joseph 0.94136 (Adam + noise + elitist respawn + upsampling, "
     "2,540 steps; extremiser looks like a spike plus a comb).", CE + " (README, literature)"),
    ("Agent systems: AlphaEvolve V2 0.961021 (50,000 steps, Nov 2025); TTT-Discover 0.959180 (test-time RL, 50,000); "
     "Together AI 0.961206 (projected gradient from AlphaEvolve V2's); ImprovEvolve 0.9512 with LLM-evolved "
     "improve/perturb operators, 0.96258 after 3 human edits (coarse-to-fine to 1.6M, no clipping, longer L-BFGS).",
     TOGETHER + "; arXiv:2602.10233"),
    ("Theory: R <= 1 (Hoelder); the arcsine density 1/sqrt(1 - 4x^2) has flat autoconvolution in the limit "
     "(Barnard & Steinerberger); for a related problem the optimum has f*f*f constant on the support of f, and a "
     "Bessel-type series sum a_j (1 - 4x^2)^(j - 1/2) fits it with about 100 terms (Rechnitzer 2026).",
     "arXiv:1903.08731; arXiv:2602.07292"),
]

# ---------------------------------------------------------------------------------------------- the field's constructions
# One per family and approach (the warm mode's imports). `arena_id`: the solution id on EinsteinArena
# (GET {API}/solutions/best?problem_id=3); `url`: elsewhere. Scores as recomputed here.
IMPORTS = [
    {"key": "arena-2416", "arena_id": 2416, "who": "ClaudeExplorer", "date": "2026-07-22", "score": 0.963588110582029,
     "n": 1_999_999, "family": "Hyra's lattice, polished at the cap",
     "how": "Hyra's 524k construction repeated, zero-padded to the cap and polished with Dinkelbach velocity cycles "
            "(GPU); the arena record"},
    {"key": "arena-2413", "arena_id": 2413, "who": "MLAI-Yonsei", "date": "2026-07-21", "score": 0.963455719992,
     "n": 1_999_999, "family": "Hyra's lattice, polished at the cap",
     "how": "a polish of ClaudeExplorer's 0.963433 (support 438k-1.57M of the grid)"},
    {"key": "arena-2408", "arena_id": 2408, "who": "ClaudeExplorer", "date": "2026-07-17", "score": 0.962946026672,
     "n": 1_048_576, "family": "Hyra's lattice, repeated twice",
     "how": "Hyra's 524k construction repeated twice, then Dinkelbach + Anderson polish"},
    {"key": "arena-2361", "arena_id": 2361, "who": "Hyra", "date": "2026-06-23", "score": 0.962901101096,
     "n": 524_288, "family": "Hyra's lattice",
     "how": "a new construction (method unpublished): finer, coherent comb lattice; heavy block + gap + ramp"},
    {"key": "arena-1801", "arena_id": 1801, "who": "ClaudeExplorer", "date": "2026-04-16", "score": 0.962643318762,
     "n": 400_000, "family": "the older comb family",
     "how": "iterated Dinkelbach + L-BFGS, repeated from 100k and polished with beta up to 1e11"},
    {"key": "arena-2641", "arena_id": 2641, "who": "SIDON-DevinWright", "date": "2026-10-26", "score": 0.962273865103,
     "n": 2_000_000, "family": "sub-cell phase kernel",
     "how": "JSAgent's 100k parent polished, each cell split into 20 sub-cells under a positive phase kernel"},
    {"key": "arena-993", "arena_id": 993, "who": "JSAgent", "date": "2026-03-31", "score": 0.962213536591,
     "n": 100_000, "family": "the older comb family, pooled down",
     "how": "ClaudeExplorer's 1.6M construction average-pooled to 100k, then Dinkelbach (cross-resolution transfer)"},
    {"key": "arena-613", "arena_id": 613, "who": "ClaudeExplorer", "date": "2026-03-25", "score": 0.961985772687,
     "n": 100_000, "family": "the older comb family",
     "how": "iterated Dinkelbach at 100k (the first Dinkelbach record)"},
    {"key": "arena-11", "arena_id": 11, "who": "Together-AI", "date": "2026-03-19", "score": 0.961205542269,
     "n": 100_000, "family": "AlphaEvolve V2's, refined",
     "how": "projected gradient ascent from AlphaEvolve V2's 50,000-step construction"},
    {"key": "arena-3", "arena_id": 3, "who": "AlphaEvolve", "date": "2026-03-19", "score": 0.961021077784,
     "n": 50_000, "family": "AlphaEvolve V2",
     "how": "AlphaEvolve V2 (Georgiev, Gomez-Serrano, Tao, Wagner, arXiv:2511.02864)"},
    {"key": "arena-8", "arena_id": 8, "who": "TTT-Discover", "date": "2026-03-19", "score": 0.959179771148,
     "n": 50_000, "family": "TTT-Discover",
     "how": "test-time reinforcement learning on the problem (Yuksekgonul et al., arXiv:2601.16175)"},
    {"key": "arena-2303", "arena_id": 2303, "who": "KiroScientist", "date": "2026-05-06", "score": 0.950466507939,
     "n": 50_000, "family": "resampled",
     "how": "resampling experiments between resolutions (thread 211)"},
    {"key": "jaech-joseph-2025", "url": JAECH + "/raw/main/function.py", "who": "Jaech & Joseph", "date": "2025-08",
     "score": 0.9413628950, "n": 2_540, "family": "spike plus comb (published)",
     "how": "Adam with gradient noise, elitist respawn and upsampling (arXiv:2508.02803); the best published bound"},
    {"key": "arena-2636", "arena_id": 2636, "who": "ASTRADEX-DevinWright", "date": "2026-10-21",
     "score": 0.908566104138, "n": 4_096, "family": "small n", "how": "a 4,096-step construction"},
]
