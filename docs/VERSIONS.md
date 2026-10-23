# Helix versions: what each one tried, what worked, what failed

The project's own map. One section per version: the idea, what was built, what the runs showed, and where the
details are. Newest first. Keep it current: every new version, job or finding of consequence gets a line here, with
links to the design, job and results documents.

**The problem most versions are tested on** (since v4) is the second autocorrelation inequality: find a non-negative
step function f that maximises R(f) = ‖f∗f‖₂² / (‖f∗f‖₁ ‖f∗f‖∞) (`helix4/problems/ac2.py`). Every run starts from a
constant function (R = 0.667).

| Reference point | R |
|---|---|
| The textbook construction f = x^(-1/2) (the "0.8825 trap") | 0.8825 |
| AlphaEvolve, May 2025 | 0.8963 |
| Boyer & Li 2025 | 0.9016 |
| Jaech & Joseph 2025 | 0.9414 |
| AlphaEvolve's later result | 0.9610 |
| Best known (2026, warm-started from earlier records) | 0.9626 |

Helix's best is **0.9412296** (v4.7, warm-started from v4's best, generation 181). Before that it was 0.9408 (v4
atlas-s1 by generation 50, which moved only in the 8th decimal place over generations 51–150).

## The two streams

- **The Atlas stream (conservative):** v4 → v4.5 → v4.6 → v4.7. It keeps v4's architecture:
  - a planned deep loop (Researcher and Coders);
  - a memoryless wide loop (the Mutator);
  - the Atlas memory.

  Each version fixes what the previous one's traces showed.
- **The ambitious stream:** v5 (one continuing researcher with a theory and an agenda) and v6 (an agent that decides
  each round how the compute is spent). These are new architectures.

---

## v7: exploration that follows progress (October 23, 2026), job ready

- **Why.** The v4.7 warm run broke the record from a line opened on an alternative construction (generations
  177–181). Rule 1 then closed that line at generation 182, while it was still climbing. Shreyas asked for the
  following (`docs/BRIEF_2026-10-23.md`, task F and the request of 11:28):
  - no closing rules;
  - the main path continues even when flat;
  - exploration rises as progress stalls, and includes reviving earlier approaches on today's state and going back
    to earlier states;
  - whatever picks up gets depth;
  - a broad start.
- **What it does** (`docs/V7_DESIGN.md`).
  - v4's two loops and Atlas, with the tree of attempts restored, plus v4.7's measurement fixes. Every program is on
    a track; nothing is ever closed.
  - From the stall (generations since the last record) and the run's own typical gap between records, 0, 1 or 2 of
    the 3 planned experiments are explorations. The main track always keeps one.
  - An exploration continues a live side track, or opens one: revive, backtrack or bold.
  - A side track is judged against its own best; it gets a follow-up even if it starts worse. One that beats the
    record becomes the main track.
  - The wide loop samples more broadly when stalled.
  - On the VRP, the noise floor is measured at the start.
- **Status.**
  - 18 tests and 2 VRP tests pass, and both jobs ran end to end with a fake model.
  - **The jobs** (`docs/V7_JOB.md`) run side by side on the VM, 100 generations each:
    - the autocorrelation run continues v47-s2 from generation 190;
    - the VRP run starts from atlas-s1/p0292.
- **Code:** `helix7/`. **Risks to watch** are listed at the end of `docs/V7_DESIGN.md`.

## v4.7: the false ceiling removed (October 23, 2026), finished

- **Why.** The 150-generation v4 run climbed for about 40 generations, then polished one construction for 110. The
  analysis (`docs/V4_CEILING.md`) found the ceiling was built by the machinery, not by a lack of ideas:
  - every planned experiment went to the champion and was judged against it after 30 s;
  - 72% of late children handed back their start unchanged, so new ideas were invisible;
  - at generation 140, all 45 findings on the planner's map were failures, many "confirmed saturated";
  - 47 "new bests" added up to +1.4e-9.

  The model (DeepSeek V4.1 Flash, the same model behind the Hermes agent) reads a plateau as a limit: "saturated"
  appears in 15% of the planner's analyses in generations 1–20, and 95% in 101–120.
- **What it does.** The deep loop works on lines: lineages each judged against their own previous generations.
  - Code closes a line that stops gaining and opens new ones: from a kept alternative construction, another branch,
    or a fresh start.
  - Slots follow progress.
  - The planner sees the active lines and the closed ones by name only, and is never asked whether a construction is
    saturated.
  - Also: programs can hand back alternative constructions; a noise floor on gains; findings balanced and scoped to
    their line; plans aim at targets; no countdown; up to 1,000,000 steps; long programs shown whole.
- **The first draft** (a step-change slot plus a challenger line, only while stalled) was replaced the same night.
  Shreyas pointed out that it bolted a third loop beside an unchanged main loop.
- **Status.**
  - A short real-model check worked: a new line took the record at generation 6.
  - **First VRP run (from Code Zero): behind v4 at generation 22–26** (1.577 and 1.503, against 1.639 and 1.591).
    - Rule 1 closed lines too early (after 4 generations at under 0.2%), including the record's line.
    - Both runs were also slower in generations 1–5, before any line closed.
    - Fixed with rule 2 (patience 8; the record's line keeps a slot while a new line opens beside it). See
      `docs/V47_DESIGN.md`, last section.
  - **The warm-start job** (`docs/V47_WARM.md`, results in `results/v47warm/`). Two v4.7 runs started from the
    0.940795 construction, 40 generations at 60 s per program. Both ran under rule 1: the `git pull` with rule 2
    came after they started.
    - **v47-s2** (the best program alone, a fresh Atlas) set the record, **0.9412296**. The record came from line L7,
      opened at generation 176 from an alternative construction, rising every generation from 177 to 181. Rule 1
      closed L7 at generation 182.
    - **v47-s1** (the whole old Atlas) didn't move from 0.940795.
  - **VRP from Code Zero:** v4.7's best scored 1.6420 on the held-out worlds, against v4's 1.6961.
    Whether that gap is noise is an open question (task B of `docs/BRIEF_2026-10-23.md`).
  - v4.7 against v4 from scratch (`docs/V47_JOB.md`) has not been run; v7 came first.
- **Docs:** `docs/V47_DESIGN.md`, `docs/V4_CEILING.md`, `docs/BRIEF_2026-10-22_V47.md`. **Code:** `helix47/`.
- **Risk to watch.** Closing a line after 4 generations without a real gain might end a line just before a late
  breakthrough (see `docs/RESEARCH_PLATEAUS.md`).

## v4.6 and v6 (October 22, 2026), stopped: worse than v4.5 and v5

- **v4.6:**
  - experiments name a method and the state it runs on;
  - the planner splits the CPU among its experiments;
  - the wide loop is a "halo" around the record;
  - time-outs are INCONCLUSIVE, not failures.
- **v6:** an agent with actions and a budget, threads, a theory.
- **What happened** (`docs/V6_POSTMORTEM.md`): no breakouts in 8–12 generations.
  - The fixes concentrated effort on the record and removed the scatter that every earlier breakout had come from.
  - The state (N) grew without bound.
  - Stages accreted.
  - Ideas were judged on converged states.
- **Lesson carried into v4.7:** keep several lines alive by construction, each with its own record and time to
  mature, and measure lines by their own rate of return.
- **Docs:** `docs/V6_DESIGN.md`, `docs/V6_JOB.md`, `docs/V6_POSTMORTEM.md`, `docs/BRIEF_2026-10-22.md`.
  **Code:** `helix6/`.

## v4.5 and v5 (October 21, 2026), finished: within chance of v4, structurally different

- **v4.5:** v4's Atlas with a portfolio of slot roles (deepen, branch, explore from scratch), and real gains counted
  from 1e-5.
- **v5:** one continuing researcher with a theory, an agenda and a notebook.
- **What happened** (`docs/V5_RESULTS.md`), 3 seeds × 20 generations:
  - the medians were within chance of v4's;
  - no new run fell into the 0.8825 trap;
  - fresh lines took over late in 5 of 6 runs;
  - four of six runs were still climbing at generation 20.

  Breadth cost early depth. The max-as-constraint idea was rediscovered with no hint.
- **Docs:** `docs/V5_DESIGN.md`, `docs/V5_JOB.md`, `docs/V5_RESULTS.md`, `docs/BRIEF_2026-10-21.md`.
  **Code:** `helix5/`.

## v4 (October 20, 2026), the baseline: program evolution with memory

- **What it is.** The agents evolve whole programs, `construct(budget, start)`, warm-started from their parent's
  construction. There were three memory conditions:
  - control: an AlphaEvolve-style scoreboard;
  - journal: appended context, compacted;
  - Atlas: an immutable log, a tree of attempts, and a findings graph whose statuses are computed from measured
    results.
- **What happened** (`docs/V4_ANALYSIS.md`, `docs/MILESTONES.md`):
  - Atlas seed 1 reached 0.9390 in 20 generations, above AlphaEvolve's May 2025 result, verified three ways;
  - four of nine runs passed 0.8963, and four ended in the 0.8825 trap.
- **Continued:** generations 20 → 55 → 150 (`results/v4cont/atlas-s1`) climbed to 0.9408 by about generation 50, then
  stopped moving (`docs/V4_CEILING.md`).
- **Docs:** `docs/V4_DESIGN.md`, `docs/V4_JOB.md`, `docs/BRIEF_2026-10-20.md`, `docs/TRACE_STUDY.md`.
  **Code:** `helix4/`.

## v3 (October 17–18, 2026): features, a ledger, the open suite

- **What it is.** Agents propose features (measurements in a decision), an optimiser fits their weights, and a ledger
  records the experiments.
- **What happened:**
  - Run on a 9-problem suite, then on an open suite of invented problems with no reference.
  - It reached records on several problems, then plateaued.
  - The plateau prompted the continuity hypothesis that v4 tested.
  - A meta-loop (Helix evolving its own strategy) was built and then scrapped as too expensive.
- **Docs:** `docs/V3_DESIGN.md`, `docs/OPEN_SUITE.md`, `docs/META_V3.md`.

## v1 and v2 (October 11–14, 2026): the hackathon engines

- **v1 (programs):** agents wrote whole priority functions for online 2-D vector bin packing.
- **v2 (features):** agents proposed what to measure, and an optimiser set the weights. It came from v1's lesson that
  LLMs did coordinate search on numbers.
- **Docs:** `HANDOFF.md` §6–7.

---

## Applied track: a private routing problem (October 22–23, 2026)

A heterogeneous-fleet vehicle routing problem with hard constraints, run through a private plug-in. Neither the
plug-in nor any data is in this repo; the runs use synthetic data in the real formats. What it taught the main line:

- **Code-length cut-offs are a hidden ceiling.** Programs grew to 50,000 characters, the coder was shown them cut off,
  and children broke. The same bug existed in v4 at 12,000 characters, and v4.7 fixes it.
- **Plateaus there broke from old, weaker branches**, not from the champion, one more reason for lines.
- **Under a fixed time limit, speed is quality.** The biggest gains came from making the search cheaper per move.
- **Status.** v4 ran for 49 generations, beating the current method by about 20% on held-out worlds (atlas-s1/p0292:
  1.6961, against 1.3865 for the best current method). v4.7 from Code Zero reached 1.6420. The v7 job starts from
  p0292 for 100 generations (`docs/V7_JOB.md`).

---

## Open research questions

- **Do LLM-driven searches grok?** Long plateaus followed by sudden climbs: luck, or hidden progress? Planned
  experiment: `docs/RESEARCH_PLATEAUS.md`. Checked against the literature on October 23: replay experiments for
  potentiation exist for classical genetic programming, but no study was found for LLM-guided search or LLM memory.
- **How much do seeds matter?** The seed only drives parent sampling, and the model isn't seeded, so the spread
  between runs (0.882–0.939 at generation 20) is the model's own randomness. Results need several runs
  (`docs/V4_CEILING.md`, "Seeds").
- **How much does the system prompt matter?** The evidence so far says the structure and the context matter more than
  the wording. A proposed ablation is in `docs/V4_CEILING.md`.
