# Work log

A running record of the work on Helix since the handoff: what was asked, what was done, what was found, and what was decided. Newest first. HANDOFF.md stays the reference for how the system works; this file is the history of how it is changing.

---

## October 27, 2026 (afternoon): v9 built, tested, and its job ready

- **The request** (09:41): build all of v9, test every part (the replay and the simulators too), fix technical and
  conceptual problems, a viewer for the simulator that also follows live runs of any version, and a test job that
  continues the v8 autocorrelation run from GitHub if that is lossless.
- **Built:** `helix9/` (codebook, annotator, model, drops, race, run, warm start, pack, replay, publishing, report,
  job wrapper, simulator, planted problem, map view), `viz/mapview.html`, `scripts/run_v9_warm.sh`; 41 tests in
  `tests/test_helix9_*.py`; the v7 and v8 tests unchanged and passing.
- **GitHub as the source:** GitHub's copy of v8-s1 lacks the constructions (3 GB), so a continuation from it alone
  would lose every base but the record. The job builds a verified 80 MB pack once on the VM and pushes it; on the VM,
  anything outside the pack comes from the local folder, so nothing is lost; elsewhere it is rebuilt. Every push now
  sends the whole run in gzipped chunks (AETHER.md section 5).
- **Found by testing and fixed:**
  - the warm start's retroactive race made 83 of v8's explorations race at once (the whole continuation would have
    gone to v8's backlog): now the 2 strongest race and the rest wait in a queue, taken in turn with new drops;
  - rebuilding a missing construction from a far ancestor (Code Zero) gave nonsense: now a close ancestor, or the
    program whose output is most like its own, and local folders first;
  - v8's wide loop samples the whole archive, so a GitHub-only continuation would rebuild constructions for most wide
    children: it now samples programs whose construction is at hand;
  - **the race throttled breadth:** in the simulator the first draft opened 11 explorations in 120 generations
    against v8's 57, and was worse than v8 (p = 0.047). Now half the exploration slots open new directions, at most
    3 race, gaining tracks are served first. On 280 fresh worlds v9 beats v8: 88 seeds better, 46 worse (p < 0.001)
    (`docs/V9_SIM.md`).
- **The job** was run end to end with a fake model on the real 3,625-program archive, and through a stop signal, the
  grace running out, `kill -9` with a torn line, a second copy, and restarts.

## October 27, 2026: a model of the search space (v9 proposed, not built)

- **The request** (`docs/BRIEF_2026-10-27.md`): a transcript of a discussion about the map (features as axes, points
  as coordinates, hills, jumping to random points), notes on trust before scale, persistence, RL, an evolutionary
  agent, problem-specific versus general axes, and discovering dimensions while searching. Research widely; thoughts
  first.
- **New measurements** (`docs/SEARCH_SPACE_MODEL.md`, section 2):
  - the Cartographer's 82 scans: 460 wordings, ~98% in 9 recurring axes; 59 different decisions labelled D1;
  - 15 from-scratch runs: best after 20 programs vs final best, Spearman -0.09 (0.50 after 40); the eventual best run
    was 4th lowest of 15 at 20 programs; three of the top four at 20 ended in the 0.8825 trap;
  - v8: restarts paused after a median of 3 experiments; three reached 0.90-0.914 within 12, above where the record's
    run was after 40 programs; flips often changed many decisions; faithful flips landed at record height on other
    shapes;
  - other systems reach 0.947-0.963 on the same problem (ImprovEvolve, GigaEvo, ThetaEvolve, TTT-Discover).
- **Research:** basin hopping, TuRBO, Go-Explore, NK and local optima networks, neutral networks, RegNet's design
  spaces, component-wise algorithm design, Zwicky's box, BOCS, fANOVA, latent-space optimisation, QDAIF, AURORA,
  AutoQD, NEAT, DreamCoder, rising bandits, MCTS-AHD, SMCEvolve, "simple baselines", METR, SEAL, TTT-Discover.
- **Proposed:** v9 = v8 + codebook, annotator, landscape model, drops, a fair race, discovery triggers, ablations;
  a three-stage proof of concept first.

## October 26, 2026 (evening): Aether's guide

- **docs/AETHER.md** (new, general): Aether (the VM agent, formerly called Hermes), the VM's measured specs and budget
  ("disk" = the 48 GB storage, the binding limit), the anatomy of an airtight job, interruptions handled gracefully
  (section 4b: atomic state, a graceful stop that finishes the generation, repair after hard kills, catch-up pushes,
  bounded retries of the job's own run, waiting out a dead model or a full disk), tracing everything, GitHub as the
  medium of exchange (private work stays in private repos: this one is public), Luminal, and the prompt template.

## October 24, 2026 (03:45-05:00): v8, a register of hills

- **The request** (verbatim in `docs/BRIEF_2026-10-24.md`):
  - surgical additions, at least as good as v4 and v7, not a new architecture;
  - reliably discover new hills one after another, and test that each is new;
  - no repeated work.
- **Landed on:**
  - A hill is defined by what the program produces, measured by code: the construction's shape, or the trips of the
    VRP's solutions.
  - Design decisions are where new hills come from.
  - Regions are the hills.
- **Calibration** before choosing the radii (`docs/V8_DESIGN.md`):
  - On the bests of 19 earlier autocorrelation runs: the textbook constructions are within 0.04 of each other,
    v4.7→v7 polishing moved 0.06, and different families are 0.09–0.6 apart.
  - On 12 programs of the v7 VRP run evaluated again on the fake worlds: noise 0.02, climbing steps 0.03–0.08, the
    change of hill 0.20.
  - v7's bold "shared decision" changes of generations 44, 54 and 57 left the output unchanged (0.007, 0.007, 0.000).
- **Built:**
  - `helix8/`: hills, run, prompts, warm, report;
  - small hooks in `helix7/` (the config class and the version as class attributes, a plan-field hook in the
    Atlas);
  - the v7 report now counts records as the runs do (4 on the VRP, not 1).
- **The VRP package:** a trip-set signature in the evaluator (hashes only), `install8`, `--warm-from`, and
  `VERSION=v8 WARM_FROM=` in the job script.
- **Tests:** `tests/test_helix8.py` (12) and 2 VRP tests; the v7 tests still pass.
- **Fake end-to-end runs:**
  - The autocorrelation job continued `results/v7warm/v7-s1`. That folder has no constructions here, so its map has
    one hill; on the VM all constructions exist.
  - A VRP v8 run continued the real v7 archive on the fake worlds. 13 earlier programs were evaluated again for
    signatures. The map begins with 3 hills: T40's (the record), the hill before it (10 of v7's revive and backtrack
    tracks ended there, 9 of them at distance 0.000 or 0.001), and Code Zero's.
  - One v4.7 test failed once, in the full suite run while the VRP test loaded both cores. Alone it passes; its fake
    search depends on CPU time. helix47 is unchanged since 7dfad60.

---

## October 24, 2026 (03:12-04:30): the v7 results, and how to explore the search space

- **The request** (verbatim in `docs/BRIEF_2026-10-24.md`):
  - analyse both v7 runs;
  - reason, concept first, about how to discover new hills rather than climb the current one (what the search space
    is; what machine learning does about local optima; Shreyas's ideas of probing approaches as axes and replaying
    the improvement chain);
  - then say how it would become add-ons to v7. Not built yet.
- **The data:** the autocorrelation run was pushed by its job (`results/v7warm/`). The VRP run came as an archive; the
  first copy was a partial download, and the second was complete.
- **Findings** (`docs/V7_RESULTS.md`):
  - v7 did what it was built to do.
  - Its backtracks were short steps back, not restarts.
  - Restarts from scratch all fell into the model's default basin: on the autocorrelation problem, 19 of 19 at or
    below the textbook 0.8825.
  - Revive gave almost nothing.
  - 68% of autocorrelation children handed back their start unchanged.
  - The one real change of hill (VRP, T40) came from replacing a component every program shared; it started worse
    and climbed after a mutation woke it.
  - VRP programs grew to 132,000 characters.
- **Reasoning** (`docs/SEARCH_SPACE.md`):
  - The search space to reason in is the space of design decisions.
  - Some axes are frozen, and a maximum along the varied axes can be a slope along a frozen one.
  - New options must be judged after a short climb.
  - The probing idea holds with three corrections.
  - The replay idea rebuilds the same hill, so: go sideways instead (keep the chain, change one key decision).
  - Methods that escape local optima change the kind of move and keep solutions per region; restarts work only when
    the starts are really diverse.
  - The concept: a design map, probes that measure hills, regions, directed restarts, spending by knowledge.
  - First step: an offline test of the map on the two archives.

---

## October 23, 2026 (12:36): both v7 jobs started on the VM

- **Autocorrelation:** continues v47-s2 from generation 190 to 290: 289 programs, 278 constructions, 547 findings
  events, 10 v4.7 lines (now side tracks). The best is p0234 (0.941229688).
- **VRP:** Code Zero scores 1.400694. The warm start atlas-s1/p0292 scores 1.644336, the median of 3 evaluations
  (1.644322, 1.644336, 1.644342); that matches its earlier training-world score, 1.6443.
- **The measured noise is 0.0012%, far below the 0.2% assumed earlier**, so the floor is the 0.05% minimum.
  - Gains smaller than that are kept and built on, but they don't count as records or as a side track's own gain.
  - So a slow creep counts as a stall, and the run explores.
  - The minimum was set for the noise level assumed before; whether to lower it for later VRP runs is open.
- **Both stop by Saturday 08:36 (EDT)**, the 20-hour deadline. The VM had about 7.9 GB free, and the load was 2.1 on
  its 2 cores.

---

## October 23, 2026 (11:30-12:30): v7, and its two jobs

- **The request** (11:28) is in `docs/BRIEF_2026-10-23.md`: one new version; no closing rules; exploration that rises
  as progress stalls, including reviving earlier approaches on today's state and backtracking; the main path never
  stops; a broad start. Then both problems warm-started, side by side, for many generations.
- **v7** (`helix7/`, `docs/V7_DESIGN.md`):
  - v4's loops and Atlas, with the tree view back, plus v4.7's measurement fixes;
  - tracks instead of lines, and nothing is closed;
  - the level of exploration (0, 1 or 2 of the 3 planned experiments) comes from the stall against the run's own
    typical gap between records;
  - exploration slots continue live side tracks, or open revive, backtrack or bold ones;
  - side tracks are judged against themselves and get a follow-up even if they start worse;
  - a side track that beats the record becomes the main track;
  - the wide loop broadens when stalled;
  - the VRP's noise floor is measured at the start.
- **Changes made while testing it:**
  - **The main track moves only on a real gain.** A sub-floor polish from a revive experiment was flipping it.
  - **A finding is revived once per record, not once per best program.** Sub-floor polishes changed the best
    program and let the same finding be revived again.
  - **Live tracks are ordered:** first those owed their first follow-up, then by how much of their gap to the record
    their last gain closed. A fresh start from Code Zero gains easily far below the record and would otherwise hold
    a slot.
  - **Breadth guarantee:** at level 2, a new direction opens every other generation.
- **Checks:**
  - 18 tests (`tests/test_helix7.py`); the whole suite passes (107 tests, v7's included), and so do the VRP
    package's 61 tests (2 of them for v7).
  - A fake-model run warm-started from v47-s2 behaves as designed. It runs at level 0 for two generations, then
    level 1 and level 2; revive, backtrack and bold tracks open and pause. The planner's prompt is about 58,000
    characters.
  - Both job scripts ran end to end with a fake model.
- **The jobs** (`docs/V7_JOB.md`):
  - the autocorrelation run continues v47-s2 from generation 190, for 100 generations;
  - the VRP run starts from atlas-s1/p0292, for 100 generations;
  - they run side by side, sharing the 2 evaluation slots.
- **The VRP package** (private, not in this repo) has `install7` and `--version v7`. `--seed-program` takes
  `runs/x/programs.jsonl:p0292`. The job script takes `VERSION=v7` and `SEED_PROGRAM`.

---

## October 23, 2026 (04:10-04:30): the first VRP v4.7 numbers, and rule 2

- **The numbers.** VRP v4.7 was behind v4 at generation 22–26 (1.577 and 1.503, against 1.639 and 1.591). From the
  line log:
  - Rule 1 closed lines too early: run 1's L1 at generation 6, after gaining 0.18% in 4 generations; L2 at generation
    20 after a 4-generation flat spell.
  - The fresh line from Code Zero climbed to the best, 1.577.
  - Both runs were also slower before any line closed.
- **Rule 2.** Patience 8; the record's line keeps a slot while a new line opens beside it, and closes after 16
  generations without a gain. `line_rule` lets runs started under rule 1 keep it, and the prepared warm runs get rule
  2 (they load their code when they start, after a `git pull`).
- **The VRP package** also uses patience 8 now, for future runs. The running VRP job is unchanged.

---

## October 23, 2026 (03:50-04:20): the warm-start job

- **The request.** Shreyas wants v4.7 started from the best of the 150-generation run (0.940795), to see how far it
  can go, before the from-scratch comparison.
- **The tool.** `helix47/warm.py` prepares a v4.7 run folder from an earlier run, in one of two modes:
  - **continue:** generation 151 of the same run (programs, constructions, findings and history kept; line L1 gets 4
    generations under v4.7);
  - **best:** the best program and its construction alone, with a fresh Atlas.
- **The job.** `scripts/run_v47_warm.sh` finds the source run folder on the VM and runs one of each, as v47-s1 and
  v47-s2. They get 40 generations at 60 s per program: compute per attempt is the binding limit above 0.94.
- **What it answers.** Whether the old Atlas helps or hurts.
- **Checks.** A test was added; the job ran end to end with a fake model. On the continued run, the planner's prompt
  is 54,000–63,000 characters, against v4's 311,000. `helix47/compare.py` now counts generations from a warm start.
- **Docs:** `docs/V47_WARM.md`, with the Hermes prompt. The queued from-scratch job is stopped first, so the two don't
  start together.

---

## October 23, 2026 (03:34-04:00): the version map and the plateau question

- **`docs/VERSIONS.md`** is the project's map: every version from v1 to v4.7, what each tried, what worked, what
  failed, and links to its documents. It also covers the applied routing track (no private details) and the open
  research questions.
- **`docs/RESEARCH_PLATEAUS.md`** answers Shreyas's question: do LLM-driven searches grok?
  - It sets out where hidden progress could live: potentiating code changes (the Lenski parallel), the Atlas, and the
    population.
  - It says what "generalisation" would mean here.
  - It plans four experiments on existing data: whether breakouts get likelier the longer a plateau lasts, a code
    replay, a memory replay, and hidden-progress signals.
  - It notes why the answer matters for v4.7's line patience.
- Pointers from the README and CLAUDE.md. A standing rule: keep the map current.
- **Jobs on the VM:** VRP v4.7 (2 runs × 40 generations from Code Zero) started at 01:13. The v4.7-vs-v4 job on the
  autocorrelation problem is queued behind it.

---

## October 23, 2026 (00:21-01:30): v4.7 redesigned around lines

Shreyas pointed out that the first v4.7 was a third loop bolted beside an unchanged main loop: the deep loop still
polished the stalled champion. He was right. The deep loop now works on lines:
- each line is judged against itself;
- code closes stalled lines and opens new ones (alternative → branch → fresh, diverse);
- slots follow progress;
- the planner sees only the active lines, and closed lines by name.

The step slot and the challenger were removed.

- **Real-model check** (lines forced to close quickly): L3, opened from another branch, took the record at
  generation 6.
- **On the VRP:** `run_vrp --version v47` (floors above the VRP's 0.2% evaluation noise), and
  `VERSION=v47 run_vrp_job.sh`.
- **The VRP v4 job was stopped at generation 41–42.** It was flat: s1 1.6436, s2 1.6345.

---

## October 22, 2026 (22:36-00:30): the false ceiling; v4.7 built, tested and packaged

### What was asked
`docs/BRIEF_2026-10-22_V47.md` (verbatim). Is v4 building a false ceiling for itself (the 150-generation atlas-s1
run)? Then build v4.7, a variant of v4 with every fix, meant to be a strict improvement.

### What was found (`docs/V4_CEILING.md`)
- **Programs fall back to their start.** In generations 81-150, 72% of children handed back their start unchanged,
  so a new idea that hadn't beaten the start yet was invisible: it looked like a failure.
- **Every idea is judged against the champion after 30 s.** 16 of 210 late experiments tried a fresh start; the 2
  late children below 0.93 were recorded as failures.
- **The map became a wall of failures.** The Distiller wrote 389 failures and 6 successes in generations 81-150. At
  generation 140, all 45 findings on the map were failures, many "confirmed saturated".
- **Rounding-level gains counted.** 47 "new bests" added up to +1.4e-9.
- **The planner's targets collapsed.** It aimed for +2% at generation 5 and +5e-6 by generation 30, and "saturated"
  rose from 15% to 95% of its analyses. The history-free Mutator stalled at the same time, so the cause is
  structural, not the planner's mood.
- **v4 cut off programs.** Base programs over 12,000 characters were cut off for the coder (67 of 420 late programs).
- **Seeds** only drive the wide loop's parent sampling. The model isn't seeded, so a "good seed" isn't reproducible.

### What was built
`helix47/` (`docs/V47_DESIGN.md`):
- **Always on:**
  - alternative constructions are kept;
  - a 1e-6 noise floor;
  - failures scoped to their construction, and a balanced map;
  - targets instead of confirm-or-refute predictions;
  - no countdown, and the honest room left;
  - up to 1,000,000 steps, 30,000-character bases and 16,000-token replies.
- **Only while stalled:** a step-change slot with twice the budget, and a challenger line that is judged against
  itself and doesn't see the record.

Tests: `tests/test_helix47.py`. The job: `scripts/run_v47_jobs.sh`, with v4.7 and v4 × 3 seeds × 30 generations.
The Hermes prompt is in `docs/V47_JOB.md`.

---

## October 22, 2026 (00:06-01:30): the traces read in depth; v4.6 and v6 built, tested and packaged

### What was asked
`docs/BRIEF_2026-10-22.md` (verbatim). Read every trace in depth: v4 atlas-s1 to generation 55, and v4.5 and v5 to
generation 20. Make the wide loop a halo around the deep loop again. Build two versions:
- a conservative v4 successor that improves it strictly and substantially (v4.6);
- an ambitious agentic one (v6).

Say what is being built before building it, test everything including real end-to-end runs, and package an
overnight job for Hermes with no kill or cron instructions.

### What was found
`docs/TRACE_STUDY.md`, sections 1-11:
- **The loops were decoupled.** The parent-sampling rule decoupled them: 25 of 60 wide parents in generations 1-20
  were more than 0.01 below the record.
- **Failures were often time-outs.** Many "failures" were experiments that ran out of time (20 of 54 in
  generations 21-40), and the Distiller recorded mechanism-level negatives from them.
- **The fixed 30 s didn't scale** with the state.
- **Atlas filled with knob tweaks** by quota.
- **Findings were unscoped.**
- **The breakthrough came from structural reasoning.**
- **Programs re-implemented the scorer**, once wrongly.
- **Prompts were bloated.**
- **Late fresh lines won** in v4.5 and v5.
- **v5's thread stop rule never fired** in a slow polishing tail.

### What was built
`helix6/`, with the design in `docs/V6_DESIGN.md`:
- **The shared engine:**
  - method × state: a program's code runs on any program's construction, or from scratch;
  - the problem's exact scorer as an importable toolkit;
  - an INCONCLUSIVE label (no change after at least 90% of the budget);
  - a planner-controlled time split;
  - plateaus measured by rate of return (a polishing tail).
- **v4.6:**
  - the mutation halo: frontier parents, a stale parent moved onto the record's state, and one donor method
    transplanted onto the record;
  - Atlas around ideas: a table of kinds of change, key findings always on the map, scoped findings, a merge-first
    Distiller with at most 4 new findings and tags;
  - a prompt diet.
- **v6:** an agent spends 6 units of 30 s per round with three actions:
  - experiment;
  - mutate (including transplants);
  - continue (more time for a program, with no new code).

  It keeps a theory (limit claims are forced to low-confidence conjectures) and threads. A thread is due when its
  last 3 actions, over 2 rounds or more, raised the record by less than 3e-4; it is parked after 2 rounds due.
- **The report:** `helix6/report.py`, every version on one page.
- **The job:** `scripts/run_v6_jobs.sh` (v4.6 × 3 and v6 × 3, 30 generations, 8 h deadline, one copy at a time,
  waits for any earlier Helix job, never stops anything). The Hermes prompt is in `docs/V6_JOB.md`.

### Checked
- **Unit tests:** `tests/test_helix6.py`, 15 tests; every older suite still passes (76 in all).
- **A prompt audit for wording from earlier traces.** Three examples were removed: "a higher resolution, a long
  schedule", "a reformulation", and a finding example that named v4's max-as-constraint technique. The first real
  test, one generation old, was discarded.
- **Real end-to-end tests:**
  - v4.6, seed 7 (4 generations): 0.667 → 0.864, halo 12 of 12 near the record, time splits used, 3 inconclusive
    flagged;
  - v6, seed 7 (4 generations): 0.667 → 0.858, all three action kinds used, and a `continue` gave +0.0024;
  - after the fixes: v4.6 seeds 8 and 9 reached 0.881 and 0.8819; v6 seed 8 reached 0.8813, with its threads
    closing with stated outcomes.
- **Fixes from those tests:**
  - plan ids resolve among the programs the planner saw (a race with same-generation wide children);
  - v5's "measure, don't derive" guard restored, plus "your job is to decide what to try, not to solve the
    problem". Before, 3 of 8 v4.6 planner calls hit the 32k thinking cap, deriving the textbook construction in
    their head; after, 0 of 3;
  - a `continue` that finds nothing is CONVERGED, not inconclusive;
  - thread counts sort past round 9, and rewording a thread doesn't reset its count;
  - only 3 opened programs per prompt show their code (prompts had reached 60 KB by generation 4).
- **A fake rehearsal of the whole job:** six runs, the report, the verification; all done.

---

## October 21, 2026 (11:30): v4.5 and v5 results; atlas-s1 to generation 40

`docs/V5_RESULTS.md`.
- **Final scores:** v4.5 0.875 / 0.897 / 0.926; v5 0.872 / 0.872 / 0.934. That is within the v4 spread: no
  difference in score is shown.
- **Behaviour:** no run fell into the 0.8825 attractor. They started slower, and fresh lines took over late (5 of
  6 final best lines). The constructions were shallower (450-4,096 steps), and the runs were still climbing at
  generation 20.
- **Engine fixes:** they worked (fewer wasted children, no spirals, 12 programs saved at the CPU limit). The
  max-as-constraint idea was found again with clean prompts.
- **atlas-s1:** reached 0.940521 at generation 40 (verified). It was flat from g29 to g38; the break came from the
  wide loop on a lower-resolution line.
- **Atlas graph:** fully tracked (an event log). 239 findings, 6 per generation by quota. Only 51 were ever opened,
  and in the plateau retrieval circled on the same four findings.
- **Backup:** the complete v4 data was sent as a file. atlas-s1 is being continued to generation 55.

---

## October 21, 2026 (03:15): two leaks of v4 wording removed from the prompts; the job restarted clean

An audit of every prompt the model sees, asked for by Shreyas (03:11), found wording that came from the v4 traces:
- v5's lookup prompt used "search: penalty continuation" and "search: resolution ladder" as examples. Those are the
  names of atlas-s1's two key techniques; the text was written at 00:49 while v4's traces were being read.
- The stall check's examples of kinds of change ("a constraint or reformulation, more resolution, ...") were picked
  after seeing what worked on this problem.

Both are now neutral ("search: <words>"; no examples of kinds of change). The coder rules' stage examples ("a
schedule, a resolution level") were removed too. The problem statement and the score feedback were already identical
to v4's. The job started at 02:51 was stopped, and the job was restarted from nothing.

---

## October 21, 2026 (02:00-03:00): the finished v4 job analysed from its traces; the lessons built into v4.5 and v5

### What was asked
(02:12, verbatim in `docs/BRIEF_2026-10-21.md`) The v4 job is done: analyse it in depth, from the traces and runs and
not just the scores. Cover how each run progressed, atlas-s1's steady climb, the model's behaviour, failure points
and stalls. Then carry the lessons into v4.5 and v5, and finish the other deliverables.

### Verified
All nine final constructions were re-scored three ways (`tools/verify_ac2.py`).
- atlas-s1 certifies **C2 ≥ 0.9390161** (42,496 steps, exact integer arithmetic on heights rounded below 2^30).
- journal-s1 0.9341847, journal-s2 0.9241822 (exact on the floats themselves), control-s2 0.9135816, atlas-s2
  0.8922728.
- The other four runs are at 0.88244-0.88254.
- Four of nine runs passed AlphaEvolve May 2025 (0.8963). `docs/MILESTONES.md` is updated.

### Found (`docs/V4_ANALYSIS.md`, tables from `tools/analyse_runs.py`)
- **atlas-s1 climbed in three phases:**
  1. free-form search (0.845);
  2. a smoothed max (0.878), then four flat generations;
  3. elimination ("all those smooth the objective; put the max into a constraint"), giving 0.879 → 0.928 in three
     generations, then a resolution ladder through warm starts (N 1,328 → 42,496, each doubling paying about half the
     last) to 0.939.
- **Its weak points:**
  - one base in 19 of 20 generations;
  - a third of planned children with no effect;
  - credit given to the wrong idea when siblings shared code;
  - inherited stages eating the budget;
  - 8 programs killed at the CPU limit late on (all four children of the record in generation 19).
- **The four stuck runs sat at 4 ln 2 / π ≈ 0.88254 (f = x^(-1/2)).** Three of them recalled it in generations 1-2.
  Their planners used 2.5-3.5 times the reasoning tokens of the climbers, deriving integrals in their heads, with 6-9
  cut-offs each.
- **Three runs escaped the attractor:**
  - a constraint on the max (found independently in three runs);
  - a fresh random start;
  - the current method applied to another line (via the wide loop).

### Built (both systems, one engine)
- anytime results (`keep_best`, scored at the CPU limit; `helix5/sandbox.py`);
- stage lines always returned;
- shared gains marked and not counted as evidence;
- an elimination list when stalled, demanding a new kind of change;
- two deepen slots while the line keeps paying (the record rose ≥ 0.001 last generation, or ≥ 0.0001 in each of the
  last two), and they must differ in mechanism.

Four new tests (21 in all). `docs/V5_DESIGN.md` was rewritten: the behavioural problems, their causes, and the
structure that answers each.

### Checked
- All 42 tests pass (v5 21, v4 21).
- A fake rehearsal of `scripts/run_v5_jobs.sh` (2 seeds × both systems, 3 generations) ran end to end, including the
  report and the verification.
- The wait for v4 was tested with stand-ins. The job waited until the stand-in of the v4 job script exited
  (02:07:05), then set its deadline (02:08:06) and ran.
- **Short real test with the new engine** (seed 2, 3 generations):
  - all 36 programs call `keep_best`, and 34 print stage lines;
  - no program reached the CPU limit;
  - v4.5 reached 0.828 and v5 0.882.

  v5 again reached for x^(-1/2) in its first round (an explore slot, 0.881 at once). The structure is built to get
  out of that attractor (threads go due, conjectures are challenged, the elimination list, explore and branch every
  round), not to stop the model from visiting it. Whether it gets out is what the job will show.
- `results/v4/VERIFICATION.md` was written with the job's own verification code and pushed, so the job won't
  repeat it.

---

## October 21, 2026 (night): the AlphaEvolve claim checked; Helix v4.5 and v5 built

### What was asked
`docs/BRIEF_2026-10-21.md` (verbatim). Check the claim "we beat AlphaEvolve's May 2025 result" rigorously; explain
seeds; document model settings and the milestone; build v4.5 (v4 fixed from its traces) and v5 (the researcher);
test; package one overnight job for both.

### The claim (`docs/MILESTONES.md`)
- AlphaEvolve's May 2025 result for this problem is 0.8962 (exactly 0.896279944155), a 50-step function, published in
  DeepMind's `alphaevolve_results` notebook (B.2) with their verification code. Their problem statement and scoring are
  the same as ours: our evaluator reproduces their code on their construction to 12 digits, and exact rational
  arithmetic agrees (`tools/verify_ac2.py`).
- Their set-up for these problems (DeepMind's published prompt): evolve a search program with 1000 s, shown the best
  construction so far; Gemini 2.0 Flash + Pro; generations not published ("a quick experiment"); later AlphaEvolve
  runs reached 0.961. Ours: DeepSeek V4.1 Flash, 30 s per program, ~120 programs per run, 2 ARM cores.
- Fair wording: Helix v4's construction (0.936 mid-run, verification pending) is above AlphaEvolve's first published
  result and Boyer & Li's, below Jaech & Joseph and the best known. Not "beat AlphaEvolve", not "with a dumber model".

### Seeds
Only the wide loop's parent-sampling seed; every run starts from the same constant function. Replicates.

### What the v4 run showed (`docs/V5_DESIGN.md` section 1)
The planner put all 3 experiments on the current best in most generations; stalled runs polished the 1/√x shape
(≈ 0.8825) for many generations; breakouts needed genuinely different methods; programs wasted budget and once
returned a worse construction than they had found; program logs carried a key clue.

### Built (`helix5/`, `tests/test_helix5.py`, `scripts/run_v5_jobs.sh`)
- Shared engine fixes: fresh starts, a stall-triggered escape rule enforced by code, real-gain counting, 8 log lines
  back, unused budget stated, coders told to use the whole budget and return their best.
- v4.5: Atlas + its own recent reasoning with if/then and outcomes + progress check.
- v5: theory / agenda / notebook as versioned event logs changed only by explicit operations; constructed continuity
  from links recorded at write time; lookups with version histories and search; reviews every 5 rounds; interrupts.
- Report: v4, v4.5 and v5 on one page with AlphaEvolve's May 2025 line; verification tables in the job.

### Test findings
- Programs now use 27-28 s of 30 (v4: often 7-13 s). v4.5 plans fresh escapes unprompted.
- v5 round 2 closed an item with its outcome, dropped one, opened one, and looked up the two programs it built on.
- v5 wrote "the true maximum of R is 4 ln2/π ≈ 0.8825" as a belief after reaching the 1/√x shape: a confident
  wrong belief can freeze a researcher with a persistent theory. Guards added (prompt, review, code flag on limit
  claims), on top of the escape rule.
- v5's decision call thought past 24k tokens once; later a v4.5 planning call thought 42k tokens and the client's
  doubled retry made one generation take 8 minutes. Planning calls are now capped (`helix5/llm.py`): a cut-off think
  falls back at once to an answer without thinking.
- Second real test (6 generations each): v5 climbed 0.667 → 0.869 steadily (111-185 s per generation); its
  generation-5 review downgraded its own "a closed form is impossible" belief and added an escape item. v4.5 reached
  0.8647 by generation 2 and stalled there; from generation 4 on it planned fresh-start escapes itself every
  generation (the forced rule never had to fire), with its analysis naming the plateau ("0.8647 is a deep
  attractor: eight optimizer upgrades moved it ≤ 3e-6"). Fresh starts with 30 s reached 0.82-0.85, so an escape
  only pays if the planner keeps building on it for several generations.
- Verified: journal-s2's final construction (4,000 steps) is exactly 0.924182240140321 (C2 ≥ 0.92418224).

---

## October 20, 2026 (evening): Helix v4, program evolution with memory, and the overnight job

### What was asked
The full brief is `docs/BRIEF_2026-10-20.md` (verbatim). In short: evaluate the hypothesis that the plateau comes
from missing continuity between generations; compare (A) appended, managed context with (B) an Avy-inspired
structured memory; evolve programs, not weights; a population, not a champion; a richer evaluator; one good
open-ceiling problem (a benchmark if one fits); test small first; an overnight job of at most 8 hours on the 2-core
OCI VM for the Hermes agent; results for a presentation on October 21.

### Decisions and reasoning (details in `docs/V4_DESIGN.md`)
- **The hypothesis.** Literally inaccurate: the v3 Researcher had a ~15k-character ledger. In spirit right: no
  agent kept its own reasoning, the Coder and Mutator saw no history, the evaluator returned aggregates. The main
  cause of the v3 plateau is the representation (a linear sum of one-step features): on runner, the champion clears
  55% of levels and a simple planner at least 85%. So memory is tested only once whole programs evolve.
- **Helix v4** (`helix4/`): programs `construct(budget_seconds, start)` that improve their parent's construction
  with 30 s of CPU (20 s in the small tests); every program kept in a tree; wide loop (memoryless Mutator, rank-and-novelty parent sampling)
  identical across conditions; deep loop (Researcher at `low`, Coders without thinking) whose view of the past is
  the variable; evaluator feedback computed by code (no LLM in the evaluator).
- **Three conditions**: Control (the standard prompt: best program + top-6 scoreboard); Journal (appended
  chronological journal with the Researcher's own analyses, compacted by an LLM past 24k characters, last 4
  generations verbatim); Atlas (log + tree + findings graph; a Distiller writes findings that must cite program
  ids; code computes each finding's status from measured gains; the Researcher sees a map with the last generation
  in full, opens up to 6 items, then plans).
- **Problem**: the second autocorrelation inequality (best known 0.962643, human best 0.94136, 2010 record 0.88922;
  constant unknown). Exact verifier, cheap on one ARM core, not recallable (zero-shot 0.862 with 7 steps). Circle
  packing rejected (saturated, public code). One problem only.
- **Benchmarks**: ALE-Bench and HeuriGym too heavy for one night on 2 cores; the AlphaEvolve problem set is the de
  facto benchmark for these systems and AC2 is in it.
- **Run plan**: 3 conditions × 3 seeds × 20 generations, all side by side; evaluations capped machine-wide at 2
  at a time (one per core); a 7.5-hour deadline.

### Small tests (real model, this container: 2 cores, like the VM)
- 1 seed × 3 conditions × 3 generations: control 0.8788, Atlas 0.8587, Journal 0.8321 (one seed each: the ranking
  means nothing). Gains per generation are large early (0.667 → ~0.80 in generation 1).
- Atlas works as intended: findings like "seeding p0012-style FFT block hill climbing from p0013's asymmetric profile
  ... raised exact R from 0.796302 to 0.843996 (+0.047694)", linked to earlier findings; in generation 3 the
  Researcher opened F12 (an open question written the generation before) and tested it.
- Model latency: Coders and Mutators 3-5 s, Researcher at `low` 30-70 s; generation time is set by evaluation CPU.
- Fixed: a program returning heights near 1e300 overflowed the scorer (heights are now normalised in `check`); the
  v3 client treated "thought until max_tokens with no answer" as an empty reply and retried with the same budget
  (v4 client lets it double); programs that stopped after a quick probe (prompts now ask to use the whole budget);
  the job's progress ticker leaving a stray process; the job script now runs from a snapshot of itself (editing
  a running bash script broke a test job); the sandbox no longer uses isolated mode (it would miss user-installed
  numpy).
- The full configuration in miniature (9 runs side by side, 3 generations, 20 s per program): 3.5 to 8.5 minutes
  per generation per run; programs used most of their budget (median 18 s of CPU); about 40 MB per run process;
  no API errors with nine runs on four keys. Three Researcher calls thought past the old token room and were
  retried with double (now given 12k answer tokens up front). Best after 3 generations: 0.836-0.882 across the 9
  runs, every run past 0.83.
- Continuity shows up in the plans. Journal, generation 3: "p0013's smoothed max failed, so I will not repeat that",
  then bets on carrying an older, flatter-topped branch (p0008) to higher resolution. Control, the same generation
  in another run, proposes smoothing the max as a fresh idea: it cannot know what has already failed.
- **Overnight settings**: 20 generations, 30 s per program, 3 seeds, 2 evaluation slots: about 3.5-4.5 hours,
  with a 7.5-hour deadline as a backstop (`docs/V4_JOB.md`).

---

## October 20, 2026 (later): is the plateau the optimum? And what would test for discovery

### What was asked

Shreyas suspects leakage: every problem jumps in generation 1 and then flattens, as if the system already knew the answer. The aim of Helix is to make real discoveries, so the tests should show a system still climbing at generation 10. Asked: a non-linear flowchart of the current system ([helix_v3_flow.png](helix_v3_flow.png)); why it flatlines and how to push through; what problems would test for discovery; research on other evolutionary setups. Nothing to be built yet.

### Findings

- **The generation-1 jump is recall, not leakage of the answer.** The agents name the textbook method behind each invented problem in their own replies: MRV for `backtrack` (24 mentions; the Navigator's first approach was "Classic MRV"), Salem-Spencer / 3-AP-free sets for `progression`, Ochiai/Tarantula fault localisation for `repair`, a Tetris well for `stacker`, TSP and orienteering for `forage`, Reversi for `duel`. The invented skins don't hide the structure.
- **The plateau is not the optimum.** `tools/runner_headroom.py` runs a beam search over the runner's own physics. On train the evolved champion scores 55.2% and fails 7 of 18 levels; the planner reaches at least 85.0% (16 of 18 finished; it is itself not optimal). On the held-out test: champion 58.7%, planner 85.6%, every level finished. On levels both finish: 384 ticks against 284. So at least 30 points are left on a problem where the run had flattened.
- **Stacker is not clear.** Quick searches (2-ply, clairvoyant beam, champion-guided beam) did not beat the champion overall (guided beam: 0.90x its points; +20% on `penta`, worse elsewhere). Its 94% is partly the metric: score is 18.6x Code Zero, and gap = 100 x Code Zero / score compresses near 100.
- **Why it flattens:** (1) the champion's shape: a linear sum of one-step features of (state, candidate), then argmax: no lookahead, memory or search, which is exactly what the runner planner uses; (2) one champion line, greedy acceptance: a feature must gain alone on validation at once, so stepping stones die; (3) budget: about 100 features per run; (4) measurement: progress from a random policy front-loads generation 1, and small instance sets (repair: 9) hide later gains in noise.
- **Research** (sources in the conversation): AlphaEvolve mostly evolves *search heuristics* with a time budget as whole programs, Flash + Pro ensemble (about 75% matched, 20% improved on 50+ open math problems); FunSearch ran about a million samples with islands (the cap set n = 8 record came in 4 of 140 runs); ShinkaEvolve: islands, novelty rejection, a bandit over models, 150 samples to a circle-packing record; ALE-Bench: the best agent reached the top 8.6% of AtCoder heuristic contestants by injecting search knowledge (simulated annealing, beam search) plus a best-first search over solutions; Darwin Gödel Machine: removing the archive of stepping stones dropped SWE-bench from 50% to 23%; Zhang et al. (PPSN 2024): simple baselines are competitive and run-to-run variance is large; Tao et al.: AlphaEvolve exploited flawed verifiers.

### Options put to Shreyas (not decided)

Evolve whole policy programs inside a skeleton that can call the simulator (so they can plan and search); keep a population/archive instead of one champion; a discovery suite with external frontiers (open math constructions with best-known records, post-cutoff AtCoder heuristic contests, a league of past champions for games, "make this program faster"); a search-based headroom reference for every problem; a blind-description ablation to measure how much generation 1 owes to recall.

## October 20, 2026: the open-suite job (about 23 hours), and the meta loop dropped

### Decision: the meta loop is scrapped

Shreyas decided to drop meta-evolution entirely: too expensive, too slow and not worth it on the compute available (the one real meta run took 6.8 hours for a single outer generation, overloaded a 2-core VM, and its +10.6 gain was within reach of a 7.6-point repeat noise). `meta/`, `docs/META_V3.md`, `docs/META_LOOP.md` and `scripts/run_meta.sh` stay in the repo as history; nothing builds on them. `scripts/run_open_jobs.sh` still calls `run_meta.sh` for its preflight only (dependency and key checks).

### What the job was

`scripts/run_open_jobs.sh` on the cloud VM, October 18 14:15 → October 19 17:01, one run at a time, one fitting worker. It answers two questions from [OPEN_SUITE.md](OPEN_SUITE.md):

1. **How far does Helix v3 climb when nothing caps it and nothing tells it what good looks like?** Nine invented problems with no reference, no textbook rule and no known optimum, each run once for 12 generations with the default strategy (Researcher thinks at low, a high-effort breakthrough every 5th generation).
2. **Does hidden thinking help?** The same 12 generations on `forage` and `duel` with three more settings: no thinking anywhere (`none`), low without breakthroughs (`low`), Researcher and Navigator always at high (`high`).

Units: progress = share of Code Zero's cost removed (for "bigger is better" problems, `100 − 100 × Code Zero's score / score`). Code Zero here is a **random policy** (candidate order is shuffled), so large early numbers mostly mean "much better than random"; the comparisons that matter are between generations and between runs.

### Results

| Problem | Train | Valid | Test (held-out family) | Best at gen | Gen 1 | Kept / tried | Hours |
|---|---|---|---|---|---|---|---|
| stacker (puzzle game) | 94.4 | 93.6 | **94.2** (prism 95.0) | 10 | 89.9 | 10 / 99 | 1.3 |
| backtrack (solver branching) | 66.1 | 65.2 | 52.3 (hubs 67.4) | 11 | 48.7 | 6 / 96 | 2.5 |
| fairshare (judgement call) | 59.2 | 62.1 | 61.8 (large 63.7) | 6 | 51.9 | 16 / 99 | 1.1 |
| runner (arcade speedrun) | 55.2 | 67.6 | 58.8 (foundry 48.5) | 9 | 23.5 | 8 / 98 | 1.3 |
| thermal (data-hall placement) | 52.8 | 52.0 | 47.3 (mixed 46.3) | 6 | 49.4 | 2 / 100 | 0.5 |
| forage (drone pickup) | 45.4 | 45.8 | 45.9 (drift 44.9) | 10 | 38.5 | 9 / 104 | 0.9 |
| duel (two-player game) | 43.3 | 40.8 | 37.8 (islands 30.5) | 12 | 33.4 | 12 / 105 | 1.9 |
| progression (math construction) | 21.2 | 20.7 | 18.6 (hept 17.5) | 11 | 12.8 | 7 / 107 | 0.8 |
| repair (debugger) | 20.9 | 47.5 | **13.8** (encoding −7.4) | 6 | 9.5 | 3 / 103 | 0.6 |

Thinking ablation (12 generations each, one run per setting):

| Setting | forage test | duel test | duel train | Output tokens (duel) |
|---|---|---|---|---|
| none | 46.5 | 36.9 | 43.2 | 87k |
| low + breakthrough (default) | 45.9 | 37.8 | 43.3 | 192k |
| low | 46.7 | 40.6 | 45.5 | 163k |
| high | 46.4 | 41.1 | 44.9 | 345k |

### What it shows

- **The engine works on problems it has never seen and nothing caps.** All nine improved from a random start with no problem-specific changes, and seven generalise to the held-out family at about the training level or better (stacker, fairshare, forage, thermal, progression, backtrack's `hubs`, runner's train-level test).
- **Most of the gain comes in generation 1.** Generation 1 reaches 85-95% of the final result on stacker, thermal, fairshare and forage. The search loop itself adds the most on runner (+32 points after generation 1, still climbing at 9), backtrack (+17), duel (+10) and progression (+8). Elsewhere it adds 2-7 points.
- **The plateau is the same one as on bin packing.** Fairshare, thermal and forage are flat from generation 5-6; thermal kept 2 of 100 features. The stall response and perturbation generations don't break it here either.
- **repair over-fits.** Train 20.9, valid 47.5, test 13.8, with two test families below Code Zero (geometry −2.6, a *training* family, and the held-out encoding −7.4). The splits have 3 instances per family, so each split is 9 bug sets; the policy fitted those particular bugs. It needs more instances per family before its numbers mean anything.
- **backtrack generalises unevenly**: the held-out `hubs` family scores 67.4, but `scatter` falls from 49 on train to 35 on test, so the policy depends on instance details within a family.
- **Thinking: no effect on forage, maybe 3-4 points on duel.** On forage all four settings land within 0.8 points of each other. On duel, `low` and `high` beat `none` and the default by 3-4 test points, but with one run each and no repeat noise measured, that isn't established. `high` costs about twice the output tokens of `low` for no gain over it. Breakthrough generations never helped (the default was no better than `low` on either problem).
- **Wall time is mostly fitting, not the model.** Agents took 10-15% of the time on duel and backtrack (game and solver simulations dominate) and 25-65% on the light problems. On this VM, faster fitting would shorten runs more than cheaper prompts.

### Next (proposed, not decided)

1. Repeat duel `none` vs `low` 2-3 times each to see whether the 3-4 points are real; if not, run without thinking (half the tokens, same results).
2. Give `repair` more instances per family (3 → 10+) and rerun before reading anything into it.
3. Attack the plateau directly (a population of champions, or restarting from a different library), since every problem shows it.
4. Drop breakthrough generations from the default: they cost tokens and never helped.

## October 17, 2026 (night): Helix v3, the problem suite, the meta loop, the dashboard

### What was asked

Make the system do what it was meant to do, tracing each gap to its cause (prompt, structure or something else); rebuild from the ground up if needed, keeping the structure (a Mutator going wide, a Researcher going deep). Then: a test suite of verifiable problems so the engine is shown to work beyond bin packing; a meta loop that evolves the evolutionary loop with the same kind of loop, swapping the winner into the outer loop; a clean dashboard with sensible units. Run small numbers of generations, read the traces (with subagents), fix, repeat. Commit and push everything in Shreyas's name.

### Decisions

- **A new package, `helix3/`, next to `helix/`** (v2 stays runnable for comparisons). Same two loops; everything around them rebuilt. Why each piece exists: [V3_DESIGN.md](V3_DESIGN.md), section 1 traces each v2 gap to its cause.
- **The approach tree sits above both loops** (the open question in the concept doc): the Navigator decides where they search; the deep loop is how a branch gets explored; the Mutator stays blind to hypotheses but gets parents chosen across the tree.
- **"Exaggerate one aspect" returns as probes that never compete**: mechanical sensitivity probes on every kept feature, and Researcher experiments of kind `probe`, judged by whether their prediction held.
- **Only a checked certificate prunes** (inert, duplicate, span). The Prover agent may propose one; the engine verifies it.
- **Problem-agnostic engine**: every problem is a priority problem (`helix3/problem.py`); bin packing is now one adapter on the read-only evaluator, with identical scores.
- **Units**: gap % (lower is better) and progress % (0 = Code Zero, 100 = reference); gains shown in progress points. No negative scores in the dashboard.
- **Prompts are split** into method (`strategy/prompts/<role>.md`) and domain addenda (`prompts/features/`, `meta/space/`), so the meta loop's winner can drive the outer loop too.
- **Four Luminal keys** in a gitignored `.env`; the client pools them under both rate limits per key.

### Round 1 (v3r1, 2D bin packing, 5 generations): 22.0% train, 22.4% test

One jump in generation 2, then flat; behind v2's run 8 (27.5%). A subagent reviewed the trace against [TRACE_REVIEW.md](TRACE_REVIEW.md). What it found, and what was done:

| Finding | Cause | Fix |
|---|---|---|
| **The champion was knife-edged.** Two near-duplicate kept features (ρ 0.968) with nearly cancelling weights; the policy's within-decision signal fell from 1.13 to 0.15, so a probe at ±0.1 was already two thirds of it. 17 of 23 rejected features did best at the smallest weight | Engine: absolute probe weights and CMA steps; duplicate threshold 0.98 let the twin in | Probe weights are now multiples (±1, ±0.3, ±0.1) of the champion's measured within-decision spread; CMA steps scale with the weights; duplicate threshold 0.95 |
| Generation 5 got empty or cut-off streams (no finish reason) and treated them as answers | Client | Empty or unfinished streams are retried |
| A valid feature was rejected for being named `_f` | Parser | A single function is renamed to `feature`; replies with no code get one more chance |
| The Researcher re-expressed one idea (11 of 16 deep features transform the same leftover); its failed predictions were never shown to it | Prompt and information | It now sees its failed predictions (before → after) and groups of tried features that rank alike, and states a `lesson` per experiment |
| Predictions were "checked" at weights where the policy was broken | Engine | Checked at the trial weights, or not at all when the feature wrecks the policy |
| Every combination the Navigator asked for contained a kept feature and was silently dropped; the same prune request three times; the Prover could never succeed | Engine and information | Kept features are rejected from combinations and the Navigator is told; it sees prune history; the Prover runs only when a feature is close (ρ or R² ≥ 0.9) and span claims are verified numerically |
| A duplicate's inherited gain marked its approach promising | Ledger | Duplicates don't count as evidence |
| Time: Prover 152 s for nothing, sensitivity recomputed unchanged | Engine | Prover gated; sensitivity cached |

Also from round 1, independently: the best two near-misses per generation now get a full trial ("weak but unproven" is retried, not dropped), and searches run on a 12-instance split (records still use all 18).

### Built

- `helix3/`: engine, ledger and certificates, fitter, client, roles, strategy, digest, CLI; `tests/test_helix3.py`.
- `suite/`: the interface docs, `check.py`, `binpack2d.py`; seven more problems in progress.
- `meta/`: `evaluate.py` (meta-evaluator), `outer.py` (the outer loop), `strategies.py`, `space/` (outer-level addenda). Docs: [META_V3.md](META_V3.md).
- `ui/`: the new dashboard (`python -m ui`).
- [TRACE_REVIEW.md](TRACE_REVIEW.md): the checklist each run is reviewed against.

---

## October 17, 2026 (later): a plain walk through run 8

### What was asked

The viewer does too much: everything sits behind a click and it's hard to follow. Shreyas wants to be *taken through* the run instead: what happened each generation, what the agents hypothesised, where each message went, and above all whether the system does what it was designed to do (the intent, not whether the code ran).

### What was done

- [RUN8_WALKTHROUGH.md](RUN8_WALKTHROUGH.md): who each station is (only the Researcher, Coder and Mutator are LLMs), one full cycle from Code Zero through generation 1, each generation in turn, and a table of intent against actual behaviour.
- Two facts confirmed in the code while writing it: the Researcher's `target` (its prediction) is saved and never checked (`evolve.py`, `record_hypotheses`); and an idea rejected by the probe is logged as "refuted" with no number (`evolve.py`, `verdict`).

### Open

- ~~Whether to rebuild the viewer as a guided step-through.~~ Done, kept small on purpose: `viz/walk.py` writes `<run>/walkthrough.html` (32 steps for run 8). Each step shows the stations involved, a plain explanation, automatic intent checks and the result; raw prompts, replies and code are one click away. The factory-floor viewer stays as it was.

---

## October 17, 2026: seeing what the current system actually does

### What was asked

Shreyas wants to turn the solution space (all possible heuristics) into a search space that Helix navigates on purpose: relaxing and pruning branches, trying different axes, orienting itself instead of repeating the same loop. Before changing anything, the first step was to see the current system clearly:

- run 3-5 generations of the current code and look at what the agents actually reason, propose and pass to each other;
- see it laid out visually, as a factory: agents as machines, messages moving between them, every variant and what it was trying, with the exact prompts, replies and code readable, plus a plain-language interpretation of each step;
- build it as a standalone HTML page that can be kept, extended and reused for future runs, not a one-off;
- measure Luminal's rate limit and document it.

### What was done

1. **Luminal rate limits measured** (about 2,500 tiny requests). Two limiters: about 13 requests at the same instant, and a bucket of about 60 requests refilling at about 1 a second. Concurrency and prompt size aren't limited. All thinking levels answer again, `ultra` included. Details: [LUMINAL.md, Rate limits](../LUMINAL.md#rate-limits-measured-october-17-2026).
2. **Run 8**: `results/20261017-014858-full`, the default feature engine, 5 generations from Code Zero, every default setting. About 4 minutes, 46 agent calls; −9.181 → −6.774, 27.5% of the way to optimal on train, 26.2% on the held-out test. Run with `HELIX_TIMING=1` so the probe and trial details are in its console log.
3. **Run viewer** ([viz/](../viz/README.md)): `python -m viz.export <run>` turns any feature-engine run folder into one self-contained HTML page. It replays the run on a factory floor laid out like the two-loop flowchart, with clickable messages, feature cards, per-machine panels, a parts grid, champion diffs and written notes. It also opens run 7 (25 generations). The page for run 8 is `results/20261017-014858-full/viewer.html`.
4. **A written read of run 8**: `results/20261017-014858-full/notes.json`, shown inside the viewer (Notes tab, and next to every call and feature).

Nothing in `helix/`, `evaluator/` or `programs/` was changed.

### What run 8 showed

The full list, with evidence, is in the viewer's Notes tab. The ones that matter most for the search-space work:

- **The deep loop did all the work.** All 4 kept features came from the Researcher; the Mutator's 20 features produced nothing kept (2 were redundant with what was kept).
- **The wide loop isn't wide.** It aims its variants at the champion's own features, so once one feature existed, 7 of its 9 variants over the next three generations were variants of that one feature. It has no memory, and re-proposed a feature it had already tried.
- **Nothing recognises that two ideas are the same.** Three of eight features in generation 1 ranked bins identically; a cosine feature came back a generation later; one Researcher idea came back with its sign flipped. Two features with the same probe scores on the same champion rank bins the same way, so the probe already gives a free fingerprint for "same approach".
- **Most decisions are made one feature at a time.** 30 of 40 features were rejected by the four-weight probe, each judged alone on top of the champion. Features that only help in combination never get a chance (pair trials and revisits are off by default).
- **Credit goes to the formula, not the idea.** The biggest gain (f0013) is argued as "class matching" but measures stranding; another kept feature's formula contradicts its claim and the optimiser flipped its sign. The research log records claims as supported, so the Researcher learns from claims that don't describe what was actually kept.
- **The current deep loop doesn't exaggerate one aspect.** It proposes a new measurement and Fit credits it with the difference it makes. Exaggeration probes were the first design and were dropped after runs 1-2 (HANDOFF §9). The vision as described in conversation ("a variant exaggerating one aspect, to see whether that aspect helps or hurts") is not what the code does today.
- **Little reasoning to see.** Thinking is off (`reasoning_effort: none`), so the only *why* in the whole system is the Researcher's JSON claims and its 100-word analysis.

### What this suggests for the search-space step (for discussion, nothing decided)

These are observations to bring into the design conversation, not choices made:

- An **approach** needs an identity that survives renaming: the probe fingerprint (score change at fixed weights on a fixed champion) is free, and catches renames and sign flips.
- A **ledger of approaches** (tried, how it did, against which champion) would let both loops see what's been done without breaking the air gap's purpose, if the wide loop gets only "this region is explored", not the research reasoning. Whether that keeps the wide loop wide is the open question.
- The search is currently **greedy coordinate ascent** over features. Branching (keeping more than one champion line alive), relaxing (letting a feature in that costs a little now), and revisiting pruned branches are the obvious axes to try, and they map onto mechanisms that partly exist (`--pairs`, `--revisit`, `--combo`).
- **Claim, measurement and fitted sign should agree** before a verdict is written to the log, or the log should record the measurement rather than the claim.

### Decisions

- **Commits** are authored as Shreyas Naik with his GitHub no-reply address, matching the repo's history, with no AI attribution (HANDOFF §11).
- **Which engine to look at:** the default (feature engine), because it's what runs today. The program engine is still there (`--engine programs`) and closer to the original "exaggerate one aspect" concept; the viewer doesn't read its runs yet.
- **The key** stays in `helix/.env` (gitignored); the probe script and screenshots stayed outside the repo.

## Round 3 review (v3r3, binpack2d, October 17)

Progress 0 → 7.9 → 17.8 → 21.0 → 25.7% in 4 generations (generation 5 lost to a shell time limit; later runs are
detached and resumable). Generation time 388 → 561 → 729 → 1234 s.

What the review found (subagent, from the trace):
- **The probe predicts the trial perfectly:** probe > 0 gained in 6 of 6 trials, probe ≤ 0 in 0 of 10. Near-miss
  trials (6) and combinations (3) gained nothing; about 1,100 s of CPU went to them.
- **The duplicate threshold is too tight:** the biggest wins sat at ρ 0.934 and 0.938; 11 of 14 duplicates fell
  between 0.95 and 0.98. Three approaches were pruned on one duplicate each.
- **Bug:** `wide()` gives a variant its parent's node but doesn't add it to the node's feature list, so the tree
  under-counts tries and gains (a02 looked dead; its variant was the best near-miss).
- **Steering away from the winning vein:** variants of kept parents won 2 of 2, other parents 0 of 7; the
  "similar groups" text pushes the Researcher out of the productive family.
- **Researcher memory:** repeats across generations (f044 = f028); a prediction checked at a weight where the
  feature does nothing is recorded as refuted.
- 14 of 21 wide features are named `wide_fXXX` (`extract_name` only reads text after the last code fence).
- Overfitting grows: the train–valid gap went 1.7 → 4.1 → 4.8 points.

To do (next session): probe_margin 0 and near_miss_trials 0; combinations only for pairs with d_valid > 0;
sensitivity [0]; duplicate_rho 0.98 and no pruning on duplicates alone; fix `wide()` node bookkeeping;
extract_name before the fence; 2+ vary slots for kept features by importance; the groups text says refine inside
productive groups; a one-line index of every tried feature for the Researcher; check predictions at an amplified
weight ("inert at fitted weight" instead of "did not hold").

Done this session: checkpoint/resume and the keeper; thinking modes; the fitter's feature-value cache with
instance-affine workers (round 4's generation 1: 70 s against round 3's 388 s); a pipelined generation;
bench/revive streams and a momentum ranking; CVRP (9 problems).

## Round 4, the thinking-mode comparison, generality, robustness (October 17, afternoon)

**Round 4** (binpack2d, 5 generations, Researcher and Navigator without hidden thinking, a max-effort breakthrough at
generation 5): 3.5 → 3.5 → 2.5 → 16.6 → 16.6%. Generations took 70-307 s (round 3: 388-1234 s): the speed work
holds. Quality is worse than round 3 (Researcher at low: 25.7% by generation 4), so the Researcher is back at low.
The breakthrough generation first failed: at max effort the model spent 27.7k of its ~28k output tokens on hidden
reasoning and the answer was cut off after 1k characters (no experiments that generation). Fixed in `helix3/llm.py`:
the output budget grows with effort (max: +80k tokens), and a reply cut off by the limit is retried once with double
room. Rerun, the max generation kept nothing.

**The cloud container is reclaimed** about 10 minutes after the session goes idle, and every process with it
(round 4 died after generation 4; the files survived and it resumed from its checkpoint). Unattended runs in the
cloud need scheduled wake-ups; long runs belong on Shreyas's machine.

**Generality.** TSP, 5 generations: 0 → 96.9 → 96.9 → 97.2 → 97.5 → 97.0% train (Code Zero is index order, a 515%
gap); held-out test 97.2%, a tour gap of about 14% against 25% for the hidden nearest-neighbour baseline. CVRP is
running (generation 1: 89.4%, gap 22.8% against the baseline's 33.6%).

**The first 15-generation run with every fix** (binpack2d, Researcher at low, perturbation every 4th generation,
streams): generation 1 reached 22.6% (valid 20.7%) in 105 s.

**Robust long runs** (Shreyas's 4-hour meta run died in its first second on a missing scipy): scipy is gone from the
run path; `run_meta.sh` has a preflight (dependencies, keys, a one-generation crash test), `DRY=1`, `RESUME=`, and
keeps a Mac awake; the meta loop reuses finished inner runs, resumes unfinished ones, keeps a generation's
candidates across a resume, counts only time spent, and fails fast if the starting strategy's runs all crash;
`scripts/install_keeper.sh` starts the keeper at login. See docs/META_V3.md.

**Also:** round-3 review fixes part 2 (see the commit), perturbation generations, the dashboard showing dead runs as
live (fixed), aborted generations of resumed runs hidden, docs/REQUESTS.md (every request, with status).

## The cloud batch and the 2D bin-packing plateau (October 17, evening)

Shreyas's cloud agent ran `scripts/run_jobs.sh` (all pushed to `results/v3/`). Held-out test progress against each
problem's hidden textbook rule (shown to the human only):

| Problem | Generations | Test | Textbook rule |
|---|---|---|---|
| knapsack | 10 | 99.95% (train and valid 100%: optimal) | 98.2% (value per weight) |
| scheduling | 10 | 99.2% | 98.2% (least-loaded machine) |
| setcover | 10 | 98.5% | 93.3% (cost per new element) |
| tsp | 10 | 97.8% | 95.9% (nearest neighbour) |
| cvrp | 10 | 92.6% | 84.4% (nearest customer that fits) |
| jobshop | 10 | 75.7% | 66.3% (most work remaining) |
| coloring | 10 | 64.8% | 61.1% (DSatur) |
| binpack1d | 10 | 37.6% | 19.3% (Best Fit) |
| binpack2d | 13 (crashed at 14) | 28.8% | 3.1% (Best Fit) |

Every problem beats its textbook rule on unseen instances with no problem-specific changes. 2D bin packing
plateaued: 28.6% at generation 4, flat through 13 (best ever: 34.6%).

**The crash** (generation 14): the Researcher's feature index iterated the ledger while the Mutator added to it.
Fixed (snapshots), and a crashed generation now restores the last checkpoint and is retried.

**The plateau** (subagent review of generations 5-13): 79 features, 1 kept.
1. The probe gate had gone blind: 0 of 12 probe-passing features gained in their trial; it ran on 6 instances
   at coarse weights, and the gated, conditional features that built the 34.6% run died there.
2. Stale results leaked back in: duplicates inherited gains measured against older champions, giving the
   Navigator fake momentum and the Mutator a frozen "+0.666 (redundant)" on its scoreboard every generation.
3. Exploration collapsed: the approaches holding the kept features were benched; the Mutator's two forced
   kept-parent slots produced 15 variants of one feature (7 duplicates); the Navigator opened 22 one-shot approaches.

Fixes (commit "Plateau fixes from the bp2d-25 review"): probe on the full search split with finer weights and two
near-miss trials; no inherited scores, near-copies of features judged under an older champion are re-tested,
duplicates aren't stream evidence, old redundant results leave the scoreboard; approaches holding a kept feature are
never benched, revived approaches get two tries, one forced kept-parent slot; agents are told features may be
conditional. Round 5 (binpack2d, 12 generations) tests them.

**Round 5** (plateau fixes, binpack2d): 5.9 → 24.6 → 27.6 → 28.4 → 28.5 → 28.6 → 28.6% (validation up to 25.1%,
the best yet), then flat; stopped at generation 7. The fixes made the search healthier (gated features got kept,
validation rose) but did not break the plateau. Comparison: the 34.6% run (October 12 engine) also plateaued
(generations 7-12) and broke out at 13-15 with features conditioned on large items and job mixes, growing its
library to 10 features; today's engine stays at 5-6.

Also fixed along the way: thinking calls are bounded (10 minutes, then one retry without thinking; a max-effort
Researcher had run 27+ minutes); breakthrough generations think at high; the keeper resumed runs that had been
stopped on purpose (it now never resumes a stopped or failed run, and `keeper --stop` marks a run stopped before
killing it).

**Round 6** (review-fix round 2): a stall signal (after 2 generations without a keep, agents are told the features
are saturated and where the room is) and searches on the full train split (18 instances). 15 generations. If it
doesn't move past ~29%, the plateau is documented as the current limit (escape condition).

**Leakage ablation** (knapsack, 7 generations, `diagnostics.show_reference: false`: the agents see no statistics
of the reference solution, checked in the prompts): 98.2 → 99.0 → 99.0 → 99.4 → 99.4 → 99.4 → 99.8% train, 99.7%
valid, 99.0% test, against 100% / 100% / 99.95% with the statistics shown (10 generations). Same trajectory, and it
found the same endgame idea (exact residual fit) on its own: the reference statistics are not what drives it.

**Round 6** (stall signal + full-train search, binpack2d, 15 generations): 22.7 → 28.6 (generation 2), flat
through 6, **30.2** at generation 7 (`item_caused_stranding_large`), 29.7 with validation up to 26.3 at 10, then
**35.1% train, 29.3% validation** at generation 14 (`large_both_dim_dead_band`). Held-out test: **−5.910**
(progress 33.7%), against the previous best's −6.001 (October 12 engine, 25 generations), on the same test
instances. The plateau broke the way the October 12 run's did: with features that switch on only for large items.
With one run per configuration I can't say how much the stall signal and the larger search split contributed
versus chance; repeating round 6's configuration (the cloud job list does this) would tell.

## Where this leaves things (end of October 17)

- **Done against the original requests**: the evolver does what was intended (traced and fixed over six review
  rounds); the 9-problem suite, where Helix beats every textbook rule on unseen instances; the meta loop, robust for
  long unattended runs; the dashboard; speed (generations 4-5x faster); thinking modes (bounded, with breakthrough
  generations); the search-space vision (streams, benching and revival, momentum, perturbation, stall response);
  the records beaten on 2D bin packing; leakage checked by ablation.
- **Known limits**: runs plateau after 5-6 generations and break out only occasionally (one breakout in four
  long binpack2d runs); job shop over-fits its training families (86% train, 76% test); perturbation generations
  have never been adopted; generations are bound by the Researcher's thinking time (30-85 s) plus CPU.
- **Next, in order of expected value**: (1) repeated runs of the round-6 configuration to separate the method from
  luck; (2) the meta loop's results (Shreyas's cloud run) and what it changes; (3) a population of champions
  (islands) so a plateau in one doesn't stall the search; (4) drop perturbation generations unless they start
  paying off; (5) held-out families inside validation, against over-fitting to training families.

## The 4-hour meta run (cloud VM, October 17-18) and the open suite, round 2

**Meta run** (`results/meta/outer-20261017-164239`): one outer generation in 6.8 hours on a 2-core VM, which it
overloaded (Shreyas had to reboot it). Four strategies evaluated (4 problems x 2 repeats each): the starting strategy
27.6; "shift one Mutator slot to the Researcher" 38.2 (promoted, and swapped into the outer loop); one candidate
13.3; one with 5 of 8 inner runs timing out. The noise between repeats was about 7.6 points, so +10.6 is suggestive,
not proven. Verdict: not worth more compute on this hardware; paused. The winning idea can be checked directly as an
A/B of two Helix configurations later.

**Open suite round 2** (docs/OPEN_SUITE.md): stacker (puzzle game), runner (arcade game as a speedrun), repair
(evolving a debugger: which patch to try next on a buggy program), progression (a set avoiding an invented equation,
as large as possible). `scripts/run_open_jobs.sh` runs all 9 open problems and then a thinking-mode ablation, gently
by default (one run at a time, one fitting worker, nice/ionice, a small cache, a memory guard).
