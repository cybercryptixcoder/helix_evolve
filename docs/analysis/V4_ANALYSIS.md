# The v4 overnight job, analysed from its traces (October 21, 2026)

Data: `results/v4/` (9 runs: Atlas, Journal, Control × seeds 1-3; 20 generations each; 120 programs and about 180
model calls per run). Every number below comes from `history.jsonl`, `plans.jsonl`, `programs.jsonl`,
`findings.jsonl` and `trace.jsonl.gz` (every prompt, reply and reasoning trace). The tables can be re-run with
`python tools/analyse_runs.py results/v4` (one run in detail: `python tools/analyse_runs.py results/v4 atlas-s1`).

## 1. In short

- **The best construction certifies C2 ≥ 0.9390161** (atlas-s1, 42,496 steps, checked in exact integer arithmetic).
  Four runs passed AlphaEvolve's May 2025 result (0.8963); four ended at 0.8825.
- **atlas-s1's climb had three phases, not one smooth rise:**
  1. Free-form search took it to 0.845 (generations 1-3).
  2. A smoothed objective gave 0.878 (generation 4), then it stood still for four generations (5-8).
  3. A reformulation broke out (generations 9-11, to 0.928), and a resolution ladder carried it up steadily to the
     end (12-20, 0.929 → 0.939).

  It was still rising at generation 20, by less each time: each doubling of resolution paid about half the one
  before.
- **What made it climb:**
  1. It never adopted the textbook construction.
  2. It worked through its plateau by elimination: it listed what had failed, grouped the failures ("all of these
     smooth the objective"), and tried the opposite kind of change.
  3. It read its programs' printouts to find where the budget went.
  4. It warm-started a resolution ladder across generations.
- **Where it struggled:**
  - The four-generation plateau.
  - Three experiment slots on the same base in 19 of 20 generations.
  - A third of its planned children had no effect.
  - Gains were credited to the wrong idea when siblings shared code.
  - Inherited stages ate the budget before new ones ran.
  - Late on, 8 programs were killed at the CPU limit, including all four children of the record in generation 19.
- **The four stuck runs fell into one attractor: 0.88254 = 4 ln 2 / π, the value of the classical f(x) = x^(-1/2).**
  Three of them reached for that construction from memory in generations 1-2. They then polished it for 15-19
  generations, and their planners thought 2.5-3.5 times longer than the climbers', deriving integrals in their
  heads.
- **Three runs that reached the attractor got out.** Each used one of three moves:
  - turned the non-smooth max into a constraint;
  - started over with the current method;
  - applied the current method to an older, different line.

  These are the deepen-with-a-new-mechanism, explore and branch roles that v4.5 and v5 now guarantee every
  generation.
- **The changes this analysis adds to v4.5 and v5 (section 7):**
  - programs keep their best construction at the CPU limit;
  - stage lines show where the budget goes;
  - gains shared by siblings are not counted as evidence;
  - a stalled planner must try a kind of change not yet tried;
  - a line that keeps paying keeps two deepen slots.

## 2. Final results, verified

Re-scored three ways with `tools/verify_ac2.py`: our evaluator, DeepMind's verification formula, and exact
arithmetic. All agree.

| Run | N | Final R (exact) | Passed 0.8963 (AlphaEvolve, May 2025)? |
|---|---|---|---|
| atlas-s1 | 42,496 | **0.939016147** | yes, at generation 10 |
| journal-s1 | 6,000 | 0.934184690 | yes, at generation 12 |
| journal-s2 | 4,000 | 0.924182240 | yes, at generation 9 |
| control-s2 | 25,600 | 0.913581645 | yes, at generation 13 |
| atlas-s2 | 544 | 0.892272819 | no (0.8923) |
| journal-s3 | 200,000 | 0.882541740 | no |
| control-s1 | 160,000 | 0.882531730 | no |
| control-s3 | 4,096 | 0.882489096 | no |
| atlas-s3 | 20,000 | 0.882442130 | no |

How the exact value was computed:
- **N ≤ 12,000:** exact rationals of the float heights themselves.
- **Larger N:** the heights rounded to integers below 2^30, with an exactly checked integer convolution. The rounded
  step function is itself a valid construction, so its exact value is a certified lower bound.

**By condition (mean of three seeds):** Journal 0.9136, Atlas 0.9046, Control 0.8929. Atlas has the best single
run; Journal has the best mean. With three seeds and this spread (each condition has a run at 0.8825), the
conditions are not separated. The honest statement: memory (Atlas or Journal) produced 3 of the 4 runs that passed
0.8963, and the no-memory control produced 1.

**Trajectories (best so far):**

| run | g1 | g5 | g10 | g15 | g20 |
|---|---|---|---|---|---|
| atlas-s1 | .8370 | .8781 | .9076 | .9375 | **.9390** |
| journal-s1 | .8327 | .8820 | .8956 | .8987 | .9342 |
| journal-s2 | .8494 | .8789 | .9217 | .9239 | .9242 |
| control-s2 | .8148 | .8724 | .8823 | .9048 | .9136 |
| atlas-s2 | .8578 | .8835 | .8912 | .8923 | .8923 |
| atlas-s3 | .8648 | .8819 | .8820 | .8824 | .8824 |
| control-s1 | .8824 | .8825 | .8825 | .8825 | .8825 |
| control-s3 | .8446 | .8649 | .8820 | .8825 | .8825 |
| journal-s3 | .8333 | .8809 | .8825 | .8825 | .8825 |

## 3. atlas-s1, generation by generation

| Gens | Best | What happened |
|---|---|---|
| 1-3 | 0.667 → 0.845 | The planner's opening: "the clear first target is to flatten f*f". It tested three families (two-level, two blocks, free-form coordinate search). Free-form stochastic search won (0.837 at N = 400, then 0.845 at N = 48 with coordinate descent). |
| 4 | 0.878 | Its diagnosis: "single-coordinate exact maximization has converged… the non-smooth max in R creates a rugged landscape". Its bet: replace max L by a smooth p-norm and raise p gradually (+0.033). This planning call thought for 379 s, the longest of the run. |
| 5-8 | 0.878 (stuck) | 12 planned children, at most +2e-5 each. It tested, one by one: a convergence-driven p schedule, structural moves inside the smooth phase, spiky analytic seeds, softmax and top-k-mean surrogates, block moves, Metropolis annealing, and doubling the resolution (46 → 88 → 176). Each was recorded as a refuted finding (F19, F31, F33, F42, F44, F45). |
| 9 | 0.879 | **Elimination:** "The 0.878093 plateau is robust to every surrogate that replaced max L (p-norm F19, softmax F33, top-k mean F44) and to exact-R annealing (F45). All those smooth the *objective*. Untried: keep the objective smooth … and put the non-smooth max into a *constraint* max L ≤ 1, solved by a quadratic-penalty continuation." That gave +0.00095. |
| 10 | 0.908 | "Push the penalty route harder": a denser μ schedule (+0.0286), from a program that used only 7.3 s of its 30. |
| 11 | 0.928 | "The obvious untapped lever is budget… or higher resolution": doubling and tripling N under the penalty (+0.0206). |
| 12-13 | 0.929 → 0.932 | Its own correction: "Three structurally different routes all landed on exactly 0.928987 at N = 996, and p0072's planned push to N ~ 4000-16000 never actually happened: pass1/pass2 consumed the budget". The way out came from the wide loop (p0075: interpolated upsampling of a sibling line, +0.0087). |
| 14-20 | 0.936 → 0.939 | A resolution ladder carried across generations by the warm start: N = 1,328 → 2,656 → 5,312 → 10,624 → 21,248 → 42,496. Each step was its own experiment (PCHIP seeding instead of repeat, FFT convolution, trimming the μ schedule). Gains per doubling: +0.0038, +0.0015, +0.0005, +0.0003, +0.0002, then +0.0005 from a stiffer penalty at fixed N. |

### What worked

1. **It let the data choose the shape.** The final construction is jagged: 62% zeros, largest height 43 times the
   mean. It is unlike any smooth textbook profile. When x^(-1/2) came up (generation 5) it was one hypothesis
   among several and was never adopted.
2. **Elimination with the findings graph.** On the plateau, each generation tested three distinct mechanisms and
   recorded the failures as refuted findings. In generation 9 the planner grouped the failures by kind and chose
   the complement. That one move was worth +0.05 within three generations. The graph made this possible: the
   failures were stated, with evidence, in one place.
3. **Diagnosis from the programs' own output.** Examples from the plans:
   - "consumed only 7.3 s of 30 s because its second pass exits on the first non-improving schedule";
   - "p0102's own printout shows the real gain came from the up2-PCHIP doubling, not from its smoothing seeds".

   Most of its later bets were budget and pipeline fixes read off printouts.
4. **Three mechanistically different bets per generation**, even on one base. Narrow in where it built, wide in
   what it tried.
5. **Continuity in the construction itself.** The warm start let a resolution ladder span seven generations: each
   child started from its parent's N and doubled it.
6. **Short, grounded planning.** Its plans averaged 5,470 reasoning tokens (the stuck runs: 15,000-20,000), with 1
   length cut-off in 21 planning calls.

### Where it struggled

1. **A four-generation plateau** (5-8): 12 planned children, none gained more than 2.3e-5. The escape came only once
   the elimination argument was made.
2. **Narrowing.** All three planned experiments were on the same base in 19 of 20 generations. Diversity came only
   from the wide loop. 25 of its 60 programs were on parents more than 0.01 below the record, mostly wasted, but
   it produced 6 records, including the 0.932 breakout of generation 13.
3. **Children with no effect.** 20 of 60 planned children returned exactly their start: the new idea did worse
   than the start, so the start came back. 12 planned children had exactly the same score as a sibling.
4. **Credit given to the wrong idea.** In generation 12, three different experiments on p0064 all scored
   0.928987 (+0.00074). The gain came from code they shared, yet each hypothesis was recorded as supported. The
   planner caught this one generation later, by noticing the identical scores.
5. **Inherited stages ate the budget.** Programs grew from about 3,300 to about 8,400 characters. A 17-19-stage
   μ schedule inherited from earlier generations ran first, so new stages often never ran:
   - generation 13: none of the three experiments changed the score;
   - generation 16: the ladder stopped after one doubling.
6. **The CPU limit at high N.** 8 programs were killed at the 47 s limit (1.25 × 30 + 10), all in generations
   15-20, when N was 5,000-42,000:
   - generation 19 lost all four children of the record, so the main line made no progress that generation;
   - the records themselves overshot the 30 s budget (p0105 used 36 s, p0120 45 s).

   A killed program scored nothing, even if it had already improved on its start.
7. **Context growth.** The planner's prompt grew from 4,000 to 74,500 characters.

## 4. The attractor at 0.8825, and how three runs escaped it

The value the stuck runs converge to, 0.88254 at N = 200,000, is 4 ln 2 / π: the ratio of the classical
f(x) = x^(-1/2), whose autoconvolution is flat on half its support. It is a deep local optimum, and the model knows
it.

**Who got stuck, and why:**

| Run | Reached for x^(-1/2) | Then | Planner reasoning per plan | Length cut-offs |
|---|---|---|---|---|
| control-s1 | generation 1 (0.8824 at once) | 19 generations within 0.0001 | 17,254 tokens | 9 |
| atlas-s3 | generation 2 ("the classic near-extremal choice is f(x) ∝ x^(-1/2)") | 18 generations of 1e-6 to 1e-4 gains | 14,848 | 6 |
| journal-s3 | generation 1 (plan) / 5 (code), "Abel's construction" | its last 13 generations at 0.8825 | 20,291 | 9 |
| control-s3 | not by name; reached 0.8825 by polishing | its last 9 generations at 0.8825 | 8,428 | 0 |
| *the climbers* | atlas-s1, journal-s1, journal-s2, control-s2 | | 5,470-7,556 | 0-1 |

**The stuck planners spiral.** In their longest plans, marker words were frequent:
- journal-s3, 37,128 tokens: "Actually" 50 times, "Wait" 41 times, "integral" 31 times;
- control-s1, cut off at 48,000 tokens: "integral" 95 times;
- atlas-s3, 27,807 tokens: "pi" 150 times.

They derive integrals by Parseval, Abel's construction and discretisation conventions in their heads. The
derivations are often wrong: atlas-s3 concluded in generation 20 that the continuous x^(-1/2) value is "~0.879",
which is below what it had already measured (0.8824). In two of the runs about half the planned children had no
effect at all (control-s1 35 of 60, journal-s3 29 of 60).

**The escapes.** Every run except atlas-s1 spent time around 0.882. Four never left; atlas-s2 crept past it to
0.892; three got out with a clear move:

| Run | Escape | Move |
|---|---|---|
| journal-s1 g9 | 0.8822 → 0.8923 | "a direct hinge penalty on knots above the current maximum optimizes the true constrained problem": the same reformulation atlas-s1 found (deepen, with a new kind of change) |
| journal-s1 g18 | 0.8988 → 0.9299 | a wide child took a different line (p0087) and applied the p-norm continuation to it (branch) |
| journal-s2 g9 | 0.8821 → 0.9142 | "the current basin may be a strong local optimum; a fresh random smooth seed could enter a different basin" (explore) |
| control-s2 g13 | 0.8823 → 0.9029 | a wide child on an old line (p0011, at 0.80) with FFT and N = 25,600: +0.10 from a parent far below the record (branch) |

Three independent runs found that the non-smooth max is the obstacle and that turning it into a constraint is the
way through:
- atlas-s1 (generation 9);
- journal-s1 (generation 9);
- control-s2, which planned it in generation 13, the same generation its record came from the wide loop.

This is the problem's real structure, found from scratch three times.

## 5. Failure points across the job

| | atlas-s1 | atlas-s2 | atlas-s3 | control-s1 | control-s2 | control-s3 | journal-s1 | journal-s2 | journal-s3 |
|---|---|---|---|---|---|---|---|---|---|
| failed programs (of 120) | 12 | 7 | 7 | 4 | 4 | 9 | 4 | 4 | 9 |
| killed at the CPU limit | 8 | 0 | 5 | 2 | 1 | 8 | 0 | 3 | 7 |
| planned children with no effect (of 60) | 20 | 10 | 4 | 35 | 7 | 26 | 13 | 16 | 29 |
| identical siblings (planned) | 12 | 6 | 11 | 23 | 12 | 21 | 10 | 21 | 29 |
| gens with all 3 planned on one base | 19 | 8 | 13 | 11 | 14 | 12 | 18 | 16 | 13 |
| records from the wide loop | 6 | 6 | 9 | 7 | 4 | 7 | 8 | 4 | 1 |
| planner seconds, mean / max | 60 / 379 | 74 / 518 | 159 / 482 | 187 / 612 | 69 / 173 | 83 / 174 | 61 / 137 | 60 / 241 | 253 / 531 |

**Model calls were reliable:**
- 1,079 of 1,080 coder and mutator replies came back complete;
- 26 of the 27 length cut-offs were planning calls, and 24 of the 27 were in the three stuck runs;
- there was 1 syntax error in 1,080 programs.

## 6. What this says about the design

- **Depth was not the problem; the kind of change was.** atlas-s1 was the narrowest run (one base in 19 of 20
  generations) and the best. It was narrow in where it built and wide in what it tried. The stuck runs were stuck
  because every experiment was the same kind of change (polishing one construction), not because they lacked
  bases.
- **Diversity of base still mattered at the critical moments.** Two of the four escapes came from the wide loop
  building on another line, and one from a fresh start. So the portfolio (deepen / branch / explore) is supported.
  It must not starve depth while a line is paying, which is what the steady-climb rule below is for.
- **Memory helped where it held evidence about failures.** The elimination in atlas-s1 depended on refuted
  findings being stated with their evidence.
- **The textbook answer is the trap.** The model's prior knowledge put three runs on x^(-1/2) at once. v5's rule
  that limit claims are conjectures, held at low confidence until they survive challenges, and its "measure,
  don't derive" rule are aimed exactly at this. The traces show the spiral they prevent.

## 7. What changes in v4.5 and v5 (both get the same engine, so they stay comparable)

| v4 evidence | Change | Where |
|---|---|---|
| 8 programs killed at the CPU limit in atlas-s1 (a whole generation lost in g19); records overshooting the budget | **Anytime results**: programs call `keep_best(h)` whenever the best improves; at the limit the runner stops the program and scores what it kept | `helix5/sandbox.py`, CODE_RULES |
| Inherited stages ate the budget (g12-g16); the planner had to infer it from free-form printouts | **Stage lines**: one line per stage ("stage name: before -> after, s"), always shown back first, however long the log | `helix5/sandbox.py`, `helix5/evaluate.py`, CODE_RULES |
| g12: three different experiments scored exactly 0.928987 and each was counted as support | **Shared gains**: siblings on one base that land on the same score are marked ("the gain came from code they share"); v4.5's findings and v5's beliefs don't count them as evidence | `Run.mark_shared`, `outcome()` in `v45.py` and `v5.py` |
| atlas-s1's plateau broke when the planner grouped what had failed and tried the complement | **Elimination, built in**: after 2 generations without a rise, the progress check lists every planned experiment since the last rise with its result, and asks for at least one kind of change none of them made | `Run.tried_since_rise`, `Run.progress_block` |
| atlas-s1's steady climb (g12-g20) came from deepening, at +0.0002 to +0.004 per generation, mostly below the hot-streak threshold | **A line that keeps paying keeps depth**: two deepen slots when the record rose by ≥ 0.001 last generation, or by ≥ 0.0001 in each of the last two | `Run._compute_roles` |
| Its two-to-three bets on one base were different mechanisms | **Two deepen slots must test different mechanisms** | PORTFOLIO prompt |

**Kept as they are:**
- warm starts, which carried the resolution ladder;
- the wide loop, which produced 52 records and two of the escapes;
- the findings graph in v4.5 (Atlas's strength);
- the v5 structure already built: falsifiable beliefs and conjectures, threads with stop rules, the portfolio, the
  capped planning call, "measure, don't derive".

## 8. What this does not show

- That one memory condition beats another: three seeds each, and every condition has one run stuck at 0.8825.
- How far atlas-s1's line could go. Its last lever paid about half as much at each doubling. Resolution alone was
  closing on about 0.9392, and the stiffer-penalty lever was still adding 0.0005 per generation.
- That the changes above will help. They target failures seen in these traces. The overnight job (v4.5 × 3, v5 × 3,
  same budget, same problem) is the test.
