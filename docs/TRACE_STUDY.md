# What the traces show (October 22, 2026)

**Read:** the full traces (every prompt, reasoning, reply and program) of:
- v4 atlas-s1, generations 1-55 (`results/v4cont/atlas-s1`);
- the six v4.5 and v5 runs, generations 1-20 (`results/v5/`).

**Tools:**
- `tools/analyse_runs.py`;
- the per-call dumps in the session scratchpad (a call's prompt, reasoning and reply by run, generation and role).

These findings come on top of `docs/V4_ANALYSIS.md` and `docs/V5_RESULTS.md`, and they drive v4.6 and v6
(`docs/V6_DESIGN.md`).

## 1. The two loops are decoupled by the parent-sampling rule

The wide loop samples parents with weight 1/(1+rank)/sqrt(1+children) over every valid program. This rule:
- has a heavy tail (about 40% of the weight sits below rank 20 once the population has 300 programs);
- penalises the most-built-on programs, which are exactly the record line.

A wide child starts from its parent's construction, so a child of a stale parent cannot reach the record, even when
its "inspiration" is the record program.

| atlas-s1, wide loop | gens 1-10 | 11-20 | 21-30 | 31-40 | 41-55 |
|---|---|---|---|---|---|
| parents > 0.01 below the record | 12/30 | 13/30 | 5/30 | 2/30 | 5/45 |
| children within 0.001 of the record | 18/30 | 7/30 | 19/30 | 26/30 | 37/45 |

Example: at generation 30, a Mutator was given p0075 (generation 13, 0.9322) with p0173 (0.9402) as inspiration. It
transplanted the record's method, but onto the old 0.9322 solution.

Later in the run a halo does form, but most of its children are "no change": they re-run the record's pipeline from
the record's state.

## 2. Many "failures" were experiments that ran out of time

| atlas-s1, planned experiments | gens 1-20 | 21-40 | 41-55 |
|---|---|---|---|
| returned the start unchanged | 9/53 | 31/54 | 9/39 |
| … and used ≥ 27 of 30 s | 3 | 20 | 7 |

Example, generation 32, p0193 (an exact augmented Lagrangian):
- Its printout shows only 2 of its 6 stages (rho = 1e1, 1e2) before the deadline.
- The Distiller wrote: "Better conditioning of the max constraint than the huge-mu quadratic penalty is not the
  bottleneck at this point".

That is a mechanism-level negative claim, drawn from a test that never ran. Such false negatives enter memory and
block retries.

## 3. A fixed 30 s per program doesn't scale with the state

At N = 42,496 a single L-BFGS stage takes several seconds. A program that re-converges its start and then tries a new
stage often runs out of time.

v4.5-s3 sat at 0.92 from generation 4 to 20 at N = 400-800. Its researcher wrote: "every upsampled stage
(800/1600/3200) scores *lower* and never recovers". The upsampled state needed more time than one program gets.

Investments that pay off over more than one program (raise the resolution now, polish later) are invisible: a child
must beat its start within one run, or its work is thrown away.

## 4. Atlas records knob tweaks, not ideas

**What the map showed at generation 30 (atlas-s1):**
- The findings index ("Map 2") listed only the latest ~40 of 173 findings.
- Those entries were almost all implementation tweaks, for example "Extending the high-mu polish tail to
  mu=1e13/3e13/1e14 with ftol=1e-20 …" (works, +0.00001).
- The idea-level findings were no longer in the index: smooth the max (F19), and move the max into a constraint
  (F49). They were visible only as citations in the tree.

**How the Distiller grew the graph:**
- It wrote about 6 new findings every generation, by quota: 329 by generation 55.
- It rarely merged a new result into an existing finding.
- Statuses counted gains of +0.00001 as support ("supported: 16 gained").

## 5. Findings and beliefs are not scoped to where they were tested

v5-s2 held "Resolution is saturated at N=3200 … N=6400 gives no further gain" (B12, works, high confidence). That
belief came from experiments on one weak family: the K=6 equal-width staircase, scoring 0.858. In atlas-s1, raising
the resolution up to N = 42,496 was the main lever from 0.93 to 0.94.

A finding is true of the state it was tested on. Memory presents it as a general law.

## 6. The breakthrough came from reasoning about structure

atlas-s1 generation 9, the researcher's reasoning: "R invariant under scaling … fixing max=1 … R = num/s² … maximize a
smooth objective subject to L ≤ 1 … a much better-conditioned problem".

That line of reasoning produced the +0.05 breakthrough. It came from thinking about the objective's invariances, not
from measuring.

v5's rule "don't derive formulas or limits in your head" was aimed at a different behaviour: computing the *values*
of textbook constructions (the stuck runs' spirals). The two need to be told apart: reason about structure, measure
values.

## 7. Programs re-implement the scorer, sometimes wrongly

v4.5-s3's jump from 0.81 to 0.919 (generation 2, p0008) was made by a program whose internal score was (A+B)/3
instead of (2A+B)/3. The researcher caught it in generation 3 by reading the printed lines ("their printed 0.612226 ×
1.5 ≈ 0.9193").

Every program writes its own scorer, and a wrong one silently steers the search.

## 8. The researcher's prompt is bloated

At generation 30 the researcher's prompt was 76 KB (~25,000 tokens):
- the best program's code, twice (the best block and the opened p0173);
- the parent's near-identical code;
- one opened finding (F149) at 11 KB, mostly evidence lists.

The model coped (calls were fast), but the duplication crowds out history.

## 9. Late fresh lines won in v4.5 and v5

In 5 of 6 runs, the line holding the record at generation 20 had been started by an explore slot (a fresh start)
late in the run:
- v4.5-s1: generation 19, +0.019;
- v5-s3: generation 13, record from generation 16.

These fresh lines started from scratch but carried mature methods. Two things follow:
- methods transfer across states;
- the long-polished states were often poor basins.

v4 had no clean way to put a mature method on a different state.

## 10. v5 committed to a representation early

v5-s2:
- built its whole theory around a K=6 equal-width staircase family (beliefs B3, B7, B9, B11, B15);
- spent 12 generations on it, because each refinement gave +1e-5 to +3e-4, so its threads never became due ("3
  experiments without a real gain");
- escaped at generation 17 only when a thread was finally closed and it tried "a direct constrained attack on the
  binding constraint".

A stop rule that counts any real gain cannot end a slow polishing tail.

## 11. What worked, and is kept

- **Coder fidelity is high.** Plans are written down to formulas, and the coder implements them as written
  (generation 32, three for three).
- **The researcher reads printouts well:** budget use, which stage paid, and bugs (section 7).
- **Warm starts** carry multi-generation progress.
- **v5's epistemic guards (with v4.5) prevented the textbook trap** in all six runs. The guards: limits are filed as
  conjectures, challenge slots, and capped thinking.
- **Exploration of methods on the best state** (atlas-s1's three distinct mechanisms per generation on one base) was
  the most productive pattern.
