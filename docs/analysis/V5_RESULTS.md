# v4.5 and v5 results, and atlas-s1 to generation 40 (October 21, 2026)

Data: `results/v5/` (v4.5 and v5, 3 seeds each, 20 generations) and `results/v4cont/atlas-s1/` (v4's best run
resumed from generation 20 to 40). Tables: `python tools/analyse_runs.py results/v5`. The constructions were
verified three ways (`results/v5/VERIFICATION.md`; the generation-40 construction was checked separately).

## 1. Scores

| | seed 1 | seed 2 | seed 3 | median | mean | above 0.8963 |
|---|---|---|---|---|---|---|
| v4 Atlas | 0.9390 | 0.8923 | 0.8824 | 0.8923 | 0.9046 | 1 of 3 |
| v4 Journal | 0.9342 | 0.9242 | 0.8825 | 0.9242 | 0.9136 | 2 of 3 |
| v4 Control | 0.8825 | 0.9136 | 0.8825 | 0.8825 | 0.8929 | 1 of 3 |
| **v4.5** | 0.8751 | 0.8971 | 0.9264 | 0.8971 | 0.8995 | 2 of 3 |
| **v5** | 0.8723 | 0.8718 | 0.9337 | 0.8723 | 0.8926 | 1 of 3 |

**Median best by generation:**

| | g1 | g5 | g10 | g15 | g20 |
|---|---|---|---|---|---|
| v4 Atlas | .858 | .882 | .891 | .892 | .892 |
| v4 Journal | .833 | .881 | .896 | .899 | .924 |
| v4 Control | .845 | .872 | .882 | .883 | .883 |
| v4.5 | .812 | .873 | .876 | .893 | .897 |
| v5 | .840 | .858 | .858 | .859 | .872 |

**atlas-s1 continued:** 0.939016 at generation 20, then 0.940245 at g29, flat until g38, then 0.940521 at g40. The
generation-40 construction is exact at **C2 ≥ 0.9405210** (N = 42,496, integer arithmetic).

## 2. Chance or structure?

**On final scores, this is within chance.**
- With 3 seeds each, the five conditions overlap completely.
- Every condition has a run above 0.92 and a run below 0.89.
- v4.5's median (0.897) is above v4 Atlas's and Control's; v5's (0.872) is the lowest.

Nothing here shows that v4.5 or v5 is worse or better than v4 at reaching a high score.

**On how the runs behave, the differences are structural.** They follow directly from the design:

1. **No new run fell into the textbook attractor.**
   - Four of nine v4 runs ended at 4 ln 2 / π ≈ 0.8825 (f = x^(-1/2)); none of the six new runs did.
   - The new runs' low plateaus are other basins, below that value. v5-s2 sat on a "block staircase" family at 0.858
     for twelve generations; v4.5-s1 sat at 0.852-0.856.
   - So the new runs swapped the one deep, well-known trap for shallower, run-specific ones, and they started
     slower.
2. **Fresh lines take over late.** In 5 of 6 runs the final best line was started by an explore slot (a fresh
   start that used the methods of its base as a template):
   - v4.5-s1's line from generation 19 took the record at g20 (+0.019);
   - v4.5-s2's line took over at g13;
   - v5-s1's at g19;
   - v5-s3's at g16 (+0.017 at g19).

   A fresh line has to rebuild resolution from scratch. The final constructions have 450-4,096 steps, against
   atlas-s1's 42,496. Each new line is younger and shallower at generation 20.
3. **They were still climbing at the end.** Four of six runs set records of more than 0.001 in generations 19-20
   (v4.5-s1 +0.019, v5-s3 +0.017 then +0.004, v5-s1 +0.0075, v5-s2 +0.0043). Most v4 runs had flattened by then.
   Breadth costs depth early and keeps options open late, which is what the portfolio was designed to trade.
   Twenty generations was too short to see the payoff, if there is one.
4. **The engine fixes worked as intended:**
   - planned children with no effect fell from 4-35 per run (v4) to 2-21;
   - identical siblings fell from 6-29 to 0-4;
   - `keep_best` saved 12 programs that hit the CPU limit (8 in v5-s2, 4 in v4.5-s1);
   - length cut-offs fell from 27 to 1;
   - planner thinking per plan stayed at 5,300-9,000 tokens in every run, so there were no spirals.

   Shared-gain marks never fired: siblings no longer landed on identical gains.
5. **The max-as-constraint idea was found again, with no hint in any prompt:**
   - v4.5-s3 in generation 4 (its jump to 0.919 in generation 2 came from another idea first);
   - v5-s2 in generation 17 ("a direct constrained attack on the binding constraint … a hinge penalty"), after
     which it climbed every generation.

   This is the clean check on the leak that was removed at 03:15: the model reaches this idea by itself.
6. **v5's research structure ran as designed, but slowly.**
   - Threads were closed (17-19 per run) and parked (5-7). Beliefs were challenged 9-17 times per run; most held,
     4-5 failed in two runs.
   - Ceiling claims were filed as conjectures, held at low confidence, and kept open. Example: v5-s2 at
     generation 5, "the block-staircase family is near a true ceiling … headroom above 0.858 is small".
   - What v5 still did was spend a long time on one family before closing it. The stop rule counts only
     experiments without a real gain, and the staircase kept producing gains of +1e-5 to +3e-4, so its thread was
     never due.

**The honest verdict:**
- Neither system is shown better or worse on score.
- Both fixed the failure modes they targeted (the attractor, wasted children, spirals, lost programs).
- Both start slower and are shallower at generation 20, because breadth is guaranteed every round and new lines
  keep restarting.
- The likely structural issue is that depth is lost when the record moves to a new line, because the new line has
  to rebuild its resolution.

## 3. atlas-s1 from generation 20 to 40, and its graph

**Is Atlas's knowledge graph tracked?** Yes, completely.
- `findings.jsonl` is an append-only event log: every finding with its generation, kind, claim, evidence programs
  and links, plus every later evidence addition.
- `plans.jsonl` records what the navigator opened each generation and why.

So the graph can be replayed at any generation.

**How it grew:**
- 239 findings over 40 generations, with exactly 6 new ones every generation: the Distiller fills a quota, so
  growth is steady whatever happens in the search.
- 151 are "fails", 76 "works", 7 questions, 5 mechanisms.
- There were 293 evidence additions and about 13 links per generation.

**How retrieval behaved:**
- The navigator opened 4-6 items per generation: the best program, its parent, and 3-4 findings, almost always 1-4
  generations old.
- Only 51 of the 239 findings were ever opened. Occasionally it reached back: F49, the constraint finding, at age
  11 in g20; F157 at age 13 in g40.
- In the late plateau (g29-g38) it reopened the same few findings almost every generation (F149, F157, F169,
  F171). That is the retrieval side of circling: the map kept pointing back at the record that had been there all
  along.

**What the planner did:**
- Generations 21-28: a stiff penalty tail at fixed N moved the record by +0.0012. In g21 three identical gains
  appeared again (+0.000423 each); v4 has no shared-gain check, by design.
- Generations 29-38: a hard attractor at 0.940245. The planner's own words: "20+ structurally different escapes …
  all return the start unchanged". 18 children in g32-g34 returned exactly their start. It diagnosed the plateau
  correctly every generation, and kept all three planned experiments on the one base.
- Generations 38-40: the escape came from the wide loop. A child on a lower-resolution side line (N = 10,624)
  gained +0.00166. The planner then picked up that route: "escaping the frozen-argmax saddle by block-averaging to
  N = 10,624, moving with the softmax-direct ladder there, and ZOH-doubling back". That gave +0.0002 and +0.00005.

**Meaningful progress or circling?** Both, in turn:
- Real progress up to generation 28.
- Ten generations of well-documented circling.
- A break that came from breadth (the wide loop and another line), not from the graph.

The graph worked as a memory of what failed. It was the reason the planner could say "20+ escapes all fail". But
retrieval never surfaced an old idea that changed direction. The break came from a different line, which is the
case for guaranteed branch slots. The finding about v4.5 and v5 is that those slots also need protected depth.

## 4. What this suggests for the next version (not built)

- **Keep the gains of the portfolio, without making new lines rebuild their resolution.** A branch or explore line
  could inherit the resolution and pipeline of the best line rather than starting at a few hundred steps.
- **Due on lack of real progress, not lack of any gain.** A thread or line should become due after k experiments
  that together add less than about 1e-3, not only after experiments with no gain at all.
- **Run longer.** Both new systems were still rising at generation 20. Continuing them, as with atlas-s1, would
  show whether breadth pays off later.
