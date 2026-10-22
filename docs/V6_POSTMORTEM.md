# Why v4.6 and v6 stalled (October 22, 2026)

**The runs:** 6 runs (v4.6 and v6, three seeds each), stopped by Shreyas at 03:20 after 8-12 generations.

**The data pushed** (`results/v6/`): `history.jsonl`, `plans.jsonl` (every plan and analysis), `findings.jsonl`,
`meta.jsonl`, `threads.jsonl` and `theory.jsonl`. The full model traces are only on the VM (`runs/v6/*/trace.jsonl`);
unfinished runs push a light copy without them.

## The scores, at matched generations

| Version | gen 3 | gen 5 | gen 8 |
|---|---|---|---|
| v4 Atlas | 0.845 / 0.878 / 0.882 | 0.878 / 0.884 / 0.882 | 0.878 / 0.888 / 0.882 |
| v4.5 | 0.852 / 0.849 / **0.921** | 0.852 / 0.873 / **0.923** | 0.853 / 0.875 / **0.925** |
| v5 | 0.837 / 0.858 / 0.843 | 0.840 / 0.858 / **0.905** | 0.841 / 0.858 / **0.908** |
| v4.6 | 0.857 / 0.867 / 0.8825 | 0.858 / 0.878 / 0.8825 | 0.858 / 0.882 / (stopped) |
| v6 | 0.879 / 0.847 / 0.852 | 0.879 / 0.864 / 0.868 | 0.879 / 0.865 / 0.874 |

**Typical runs: no worse.** The median run of v4.6 and v6 is no worse than v4.5's or v5's.

**Breakouts: none.** No run broke out. Every earlier version had one by now:
- v4.5-s3 reached 0.92 at generation 2;
- v5-s3 reached 0.905 at generation 5;
- v4 atlas-s1 reached 0.908 at generation 10.

**Stalls:** every new run sat flat in one basin from about generation 4:
- v6-s1 was frozen at 0.8792 for 7 rounds;
- v4.6-s3 was frozen at 0.8825 for 5 generations;
- v4.6-s1 rose by about 2e-5 to 6e-5 per generation.

## What the breakouts had in common

| Breakout | What changed | N |
|---|---|---|
| v4.5-s3, gen 2 (0.81 → 0.919) | a climber with a coarse-to-fine ladder (its internal scorer was mis-coded: a different objective) | 200-400 |
| v5-s3, gens 4-5 (0.84 → 0.873 → 0.905) | max replaced by an annealed softmax, analytic gradients | 100-200 |
| v4 atlas-s1, gen 10 (0.879 → 0.908) | "remove the Phase A/B/C/D blocks entirely and spend the whole budget on the penalty route" | 88-332 |
| v4 atlas-s1, gen 11 (→ 0.928) | the same route on a 2-3× upsample | ~1,000 |

Two things are common to all three:
- **Each changed what the optimiser optimises**: a surrogate, a penalty or a constraint.
- **Each ran on a small construction, with the whole budget given to that one idea.**

## What the new runs did instead

### 1. Every experiment ran on the record's construction

In v4.6, every deep experiment from generation 2 on ran on the best construction, in all three seeds:
- v4.6-s1 had 0 fresh starts after generation 1;
- v4.6-s2 had 0;
- v4.6-s3 had 3.

The wide loop, my "halo" fix, put all 3 mutations on the frontier or transplanted onto the record's state. So
everything a run did each generation worked on one construction.

v6 did the same by choice. 9 of its 10-12 rounds per run put all 6 units on the latest best (`state` = the record).

In v4 the "erratic" wide loop was the only thing that kept other lines alive: it sampled stale parents. atlas-s1's
generation-39 break came from the wide loop on a lower-resolution line. v4.5 had forced explore and challenge slots.
v4.6 removed both, v6 had neither, and the runs became monocultures.

### 2. The construction's size ran away, and every later program inherited it

The largest N in each run's plans, by generation:

| Run | N by generation |
|---|---|
| v4.6-s3 | 50,000 at gen 1, then 200,000 from gen 3 to the end |
| v6-s1 | 12,800 → 200,000 → 100,000 |
| v6-s2 | 12,800-51,200 |
| v4.6-s1 | 800 → 4,800 → 12,000 |

The breakouts happened at N = 36-400. Because experiments default to the record's state, once one program
upsampled, every later experiment started from the huge array. At N = 200,000 a 30-90 s program can evaluate the
score a few hundred times, so most ideas returned their start unchanged:
- v4.6-s3, generations 4-7: 11 of 12 deep experiments were INCONCLUSIVE or zero;
- its own analysis: "every local move … returns the start literally unchanged".

The engine has nothing that pushes back. A state never gets smaller, and "method × state" made the record's state the
default for everything.

### 3. Programs accrete stages, and new ideas starve

The default base is the record's program, so every new experiment is the record's whole pipeline plus a new stage.
The runs say so themselves:
- **v6-s1, round 11:** "every program built on p0015 spends 50-80 s in the inherited pnorm/escape stages, which never
  help, and starves whatever is new."
- **v6-s1, round 10:** "p0019's two-lobe stage got only 2.7 s before the unchanged escape loop consumed 72 s."
- **v4.6-s1, generation 6:** "p0031 wasted 19 s at N=400."

atlas-s1's breakthrough was the opposite move: delete the old stages and give the new route the whole budget.

### 4. Ideas were judged in the worst place, and closed fast

A method tested by polishing a converged local optimum of the exact score, at high N, inherits that optimum. So it
returns about +0 whether or not the idea is good. The runs then filed it as dead:
- v4.6-s1 F16: "surrogate objectives are dead ends", tested on the N = 400 record;
- v6-s1 T8: "plateau-aware p-norm continuation added no real gain", on the record at N = 100,000.

The softmax/p-norm surrogate was the v5-s3 breakout. Here it was tested only as polish on a converged state.

Fresh lines got one or two shots against a heavily polished record, were declared inferior and were dropped:
- v6-s1 T9 and T11: "p0014's basin is genuinely inferior" after 2 rounds, 0.026 below;
- v6-s2 T6: "deprioritize it".

In v4.5/v5 the late fresh lines that won needed many generations.

My stop rule made this worse. Threads are due when they creep, so the agent closed lines quickly and opened new ones,
which again ran on the record's state. It relabelled kinds of change to satisfy "change the kind of move", for
example "different method on the best construction" and "giving an inconclusive idea the time it needs", while the
experiment shape stayed the same.

### 5. A limit belief came back

v4.6-s3, generations 4-7: "the binomial is a genuine stationary point … the real ceiling is the continuous x^-1/2
value". v6's theory guard forces such claims to low-confidence conjectures. v4.6 has no such guard in its findings or
analysis, and the progress block's tail note only fired late (it needs 3 generations of total rise < 3e-4).

## The conceptual mistake

I fixed what looked wrong in v4's chart (an erratic wide loop, scattered parents, "failures" that were time-outs) by
concentrating effort on the record. But in this search the scatter was doing work. Diversity of states, and small
states, is where every breakout came from.

v4.6 and v6 removed that diversity: the halo removed it, method × state defaulting to the record removed it, and the
missing explore slots removed it. They also let the state grow without bound, and the stop rule closed lines before
they could mature. The result is a fast collapse into whatever basin generation 1-3 found, then polishing.

## What follows (for the next design; nothing built yet)

- **Keep several lines alive by construction.** Not a halo only around the record: a few independent lines (islands),
  each with its own record, budget and time to mature, with the wide loop working around each line's own best.
- **Test new methods where they can show their value.** Use a small state (downsampled), or the state's line from
  earlier, or from scratch with several generations of protection. Never only as polish on the converged record.
- **Bound the state.** Cap N relative to the budget, or test downsampling as a first-class move, so one upsample
  can't tax every later program.
- **Prune the pipeline.** Let an experiment start from the method alone (the record's construction, but a program
  with only the new route), the move that produced v4's breakthrough.
- **Slow down verdicts.** No "inferior / dead end" from one or two runs on a converged state. Measure lines by rate of
  return over several generations, not a single comparison with the record.
