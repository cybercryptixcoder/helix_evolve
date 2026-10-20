# Helix v4: program evolution with memory

October 20, 2026. Built from Shreyas's brief of that evening (`docs/BRIEF_2026-10-20.md`, verbatim request in its
section 3). Code: `helix4/`. Tests: `tests/test_helix4.py`. Overnight job: `scripts/run_v4_jobs.sh` and
`docs/V4_JOB.md`.

## 1. The question

Helix v3 plateaus. Shreyas's hypothesis: every agent call is a fresh instance with only "static" context (the
champion's feature names and weights), so there is no continuity from one generation to the next, and that is why
runs flatline. He proposed two fixes to compare: (A) append the earlier context, managed by chunking or compaction;
(B) a structured memory inspired by Avy (an immutable log, facts pointing at it, a graph of related facts, retrieval by
walking the graph): a graph or tree of attempts with what worked, what failed and why, that the model can jump
around in. Progress records must be informative ("branch C changed X, gained N because Y"), and the evaluator should
say more than a number.

## 2. What the evidence says about the hypothesis

- **Literally, v3 was not memoryless.** The v3 Researcher received about 14.8k characters per call: the champion's
  feature descriptions, weights and importance, diagnostics, sensitivity, a ledger of past experiments with their
  probe curves, trial deltas and whether each prediction came true, an index of everything tried, and the wide
  loop's finds with code.
- **In spirit, it is right.** (1) Nobody kept their own reasoning: the Researcher never saw why it had planned what
  it planned. (2) The Coder (1.7k characters) and the Mutator saw no history at all. (3) The evaluator returned
  aggregates, never what changed in the behaviour.
- **But the main cause of the plateau was the representation.** v3's champion is a weighted sum of one-step
  features followed by an argmax: it cannot express lookahead, memory or search. Measured on the runner problem:
  the champion clears 55% of levels; a simple planner clears at least 85% (`tools/runner_headroom.py`). No memory
  can lift a representation past its ceiling. The first generation's jumps came from the model recalling textbook
  heuristics, not from leaked answers.
- **Conclusion.** Memory can only be tested fairly once whole programs evolve. So v4 does three things at once:
  programs instead of weights, a population instead of one champion, and a controlled comparison of memory.

## 3. What v4 is

**Programs.** A candidate is a Python module with `construct(budget_seconds, start)` that returns a construction. It
starts from its parent's construction (`start`) and gets `budget` seconds of CPU (30 in the overnight job) to improve it, as in
AlphaEvolve's set-up for this kind of problem. Progress therefore compounds down a lineage: a child that improves its
parent's construction by +0.004 builds on everything above it.

**A population.** Every program ever written is kept (`programs.jsonl`, append-only) in a tree (each points at its
base). The wide loop samples parents by rank, weighted `1/(1+rank)/sqrt(1+children)`, which favours strong programs
that haven't been built on much. The Researcher may choose any program as a base.

**Two loops per generation.**
- *Wide* (identical in every condition): 3 parents sampled; the **Mutator** (no thinking, no memory) writes an
  improved version of each, with one other strong program as inspiration.
- *Deep*: the **Researcher** (thinking `low`, the best setting from the v3 ablation) sees the past through the
  condition's memory and plans 3 experiments, each with a base, hypothesis, change, prediction and what it builds
  on; a **Coder** (no thinking) implements each. A low-thinking code call took 6.4 minutes in a probe, so thinking
  is spent only on planning.

**The evaluator** (`helix4/evaluate.py`, `helix4/problems/ac2.py`). Each program runs in its own process (one thread,
low priority, CPU, memory and wall-clock limits). The result is checked and scored exactly, and described by code:
the score and its change against the start, N, how much of f*f's top is within 0.1% / 1% / 5% of its maximum (the
quantity this problem rewards), where the peak sits, the two norm terms in a scale-free form, CPU used, and the
program's last printed lines or its error and traceback. **No LLM in the evaluator**: its comments would be guesses
presented as measurements. Interpretation happens where it can be checked (the Distiller, below). The published
records are never shown to any agent.

**Machine-wide evaluation slots.** Evaluations are the only CPU-heavy work. They go through file-lock slots
(`HELIX4_EVAL_SLOTS`, default 2 = one per core) shared by every run on the machine, and none starts with less than
600 MB free. So any number of runs can share the machine without exceeding its two cores.

## 4. The three conditions (the only thing that differs)

Same models, budgets, evaluator and wide loop. Only what the Researcher sees of the past changes.

1. **Control: the standard prompt of evolution systems.** The problem, the best program (code, result, lineage) and
   a scoreboard of the 6 strongest programs. No history, no notes of its own. This is what AlphaEvolve-style systems
   show their models, so the question becomes: does memory beat the standard prompt?
2. **Journal: idea A, appended context.** The control view plus a chronological journal appended every generation:
   the Researcher's own analysis, each experiment (hypothesis, change, prediction, score, change in score, key
   feedback, the coder's summary) and the wide loop's mutations. When the journal passes 24,000 characters, an LLM
   compacts everything older than the last 4 generations into a running summary of at most 4,000 characters (what
   was tried, what worked with ids and gains, what failed and why, open questions); the recent part stays verbatim.
3. **Atlas: idea B, structured memory, adapted from Avy.**
   - *Layer 1, the log:* every program, plan and result, immutable (`programs.jsonl`, `plans.jsonl`).
   - *Layer 2, the tree of attempts:* who built on whom and what each change did.
   - *Layer 3, the findings graph* (`findings.jsonl`): after each generation a **Distiller** (no thinking) writes
     findings, short claims of kind works / fails / mechanism / question, each of which **must cite the programs that
     are its evidence**, and attaches new evidence to old findings. Findings are linked by type: refines,
     contradicts, requires, combines-with, explains. Code validates everything: unknown program ids and links to
     unknown findings are dropped. **The status of a finding (supported / mixed / refuted, and the best measured
     gain) is computed by code from its evidence's measured results**, never taken from the model: Shreyas's
     "informative progress", with the numbers guaranteed.
   - *Navigation in two steps:* the Researcher first sees a map: the pruned tree (the 12 strongest programs and the
     last generation, with their ancestors, each line with score, gain, intent and the findings citing it), the
     findings index, and **the last generation in full**. It opens up to 6 items (a program: plan, diff, code,
     result, children, findings citing it; a finding: its evidence and linked findings), then plans.

### Why this design (and what from Avy carries over)

- **Agent-steered retrieval over context dumping.** In Avy's own bench, giving the model more recalled context made
  answers worse (caps of 24 and 50 recalled items scored below 12), while letting the model steer exploration
  (open, follow, search, keep) scored best (86%). So Atlas lets the Researcher choose what to open.
- **The recent window.** Avy's weakness was message-to-message continuity: retrieval worked, but the thread of the
  last exchange got lost. Here the equivalent is the last generation, so Atlas always shows it verbatim, next to the
  long-term structure.
- **"The model proposes, code disposes"** (Avy's principle): the Distiller proposes findings; code checks every
  citation and computes every status.
- **What doesn't carry over.** Avy's problem is conversation; this one is progress-tracking with exact, measurable
  outcomes. That makes it easier: every finding can be checked against numbers, and the tree is given by the
  lineage, not inferred.
- **The literature agrees on direction, warns on noise.** Memory-guided tree search with a two-level memory reports
  +7.3 points; removing the Darwin Gödel Machine's archive dropped it from 50% to 23%; but at small budgets
  different memory types tie, and run-to-run variance in LLM evolution is large. Hence three seeds per condition, and
  a report of the spread, not a single curve.

## 5. The problem: the second autocorrelation inequality

Find a non-negative step function f (heights h, N equal steps, N ≤ 200,000) maximising
R(f) = ‖f*f‖₂² / (‖f*f‖₁ · ‖f*f‖∞). R ≤ 1 always; every construction is a proven lower bound for the constant
C₂ = sup R. For a step function, f*f is piecewise linear, so R is computed exactly from its knots (Boyer et al.).

| Reference | R |
|---|---|
| Constant function (Code Zero) | 0.666667 |
| Matolcsi & Vinuesa 2010 | 0.88922 |
| Boyer et al. 2025 (human) | 0.901564 |
| Jaech & Joseph 2025 (human, published) | 0.94136 |
| AlphaEvolve V2 (2025) | 0.9610 |
| ImprovEvolve+E (2026) | 0.96258 |
| EinsteinArena best (2026) | 0.962643 |

Why this problem, against the criteria from October 20: an **open ceiling** (the constant is unknown); an **external,
moving frontier** that separates good search from bad (AI systems score anywhere from 0.88 to 0.963); an **exact,
cheap verifier** with no hidden test set; **not recallable**: a zero-shot call to our model scored 0.862 with a
7-step function; and **not maxed out in generation 1** (0.79 to 0.82 after one generation in tests). It runs in
seconds on one ARM core. Circle packing (n = 26) was rejected: saturated at 2.635983 and the winning code is public.
One problem is enough: generality was shown by the v3 suites, and a second problem here would not tell us anything
different. (The "first 128 digits of an autoconvolution inequality" paper, arXiv 2602.07292, is about a different
constant, the L² one; this one is still open.)

**Benchmarks considered.** ALE-Bench (AtCoder heuristic contests) and HeuriGym need hours of compute per task; the
AlphaEvolve problem set (ported by OpenEvolve, CodeEvolve and others) is the de facto benchmark for these systems, and
this problem is in it. The "test suite" here is the problem with its verifier, its tests (exact formula against brute
force, FFT against direct convolution, invalid inputs, scale invariance, the sandbox killing runaway programs) and
the frontier table.

## 6. "Cheaper samples"

FunSearch drew about a million program samples, AlphaEvolve thousands; v4 gets 6 per generation per run. Each sample
costs a model call plus CPU to evaluate it. With Luminal, a call without thinking takes 3 to 5 s and a Researcher
call at `low` 30 to 70 s, so time per generation is set by evaluation CPU, not by the model. So: thinking only where
it pays (planning), fast coders and mutators, and a fixed 30 s of CPU per program (20 s in the small tests). In this kind of search, more cheap
samples beat fewer expensive ones.

## 7. What we measure

Per run, per generation (`history.jsonl`): best score; best deep child and best wide child; how many deep and wide
children gained over their start; failures; duplicates; whether the plan parsed; how many experiments cite earlier
programs or findings; Researcher prompt size and time; memory statistics (journal size and compactions; number of
findings, supported, refuted, links). At the end (`summary.json`): best score and its full lineage. The report
(`python -m helix4.report runs/v4 results/v4`) shows best score by generation for each condition (each seed and the
median), against the published records; per-condition gain rates and which loop set each record; the best
construction and its autoconvolution; the chain of changes that built the best program; Atlas's top findings.

The comparison that matters: **the deep loop's gain rate and record share, by condition**, since the wide loop is
identical everywhere; and the **final best per seed**.

## 8. Honest expectations

- All three conditions will write real optimisers and climb well past 0.85 (tests: 0.83 to 0.88 after 3
  generations).
- Differences between memory conditions may be within seed noise at 20 generations. Atlas should show more
  explicit building on earlier results (cited findings, tested open questions); whether that turns into higher
  scores is the experiment.
- Passing the 2010 record (0.88922) is likely; reaching the published human best (0.94136) is a stretch; AlphaEvolve's
  0.9610 is unlikely on two cores in one night.
- Atlas costs two extra model calls per generation (navigation, distilling) and the journal an occasional compaction:
  memory costs compute. Both are cheap next to evaluation.

## 9. Files

| File | What |
|---|---|
| `helix4/run.py` | one run: the loop, roles, checkpoint/resume, deadline, fake model for tests |
| `helix4/memory.py` | the three conditions (Control, Journal, Atlas) |
| `helix4/prompts.py` | every prompt and reply parser |
| `helix4/archive.py` | the population: programs, tree, parent sampling, duplicates, truncation for resume |
| `helix4/evaluate.py` | run, check, score and describe a program; machine-wide evaluation slots |
| `helix4/sandbox.py` | the program runner (process, limits) |
| `helix4/problems/ac2.py` | the problem: verifier, description, Code Zero, feedback, frontier (human-only) |
| `helix4/llm.py` | the Luminal client (v3's, with the empty-reply fix) and the fake model |
| `helix4/report.py` | the presentation page |
| `scripts/run_v4_jobs.sh` | the overnight job |
| `docs/V4_JOB.md` | how to run it, and the prompt for the Hermes agent |

## Sources

- AlphaEvolve: https://arxiv.org/abs/2506.13131
- FunSearch: https://www.nature.com/articles/s41586-023-06924-6
- ShinkaEvolve: https://arxiv.org/abs/2509.19349
- ALE-Bench: https://arxiv.org/abs/2506.09050
- HeuriGym: https://arxiv.org/abs/2506.07972
- Darwin Gödel Machine: https://arxiv.org/abs/2505.22954
- Memory-guided tree search: https://arxiv.org/abs/2605.17539
- EinsteinArena: https://arxiv.org/abs/2606.10402
- Jaech & Joseph, 0.94136: https://arxiv.org/abs/2508.02803
- Boyer et al., exact evaluation for step functions: https://arxiv.org/abs/2506.16750
- ThetaEvolve: https://arxiv.org/abs/2511.23473
- Avy's memory design: https://github.com/cybercryptixcoder/Avy (MEMORY.md, CONCEPT.md)
