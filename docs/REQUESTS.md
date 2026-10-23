# What Shreyas has asked for

The running record of every request, so nothing is lost across context compactions or session resets. Each line has a status: **done**, **doing**, **todo**, or **standing** (a rule that applies all the time). New requests are appended to the log at the bottom, with the date, as they arrive (including mid-run ones), and the lists above are updated to match.

Last reviewed: 2026-10-17, from the full message history Shreyas pasted in.

## Standing rules

- **standing**: Commit and push regularly to GitHub, in Shreyas's name (`Shreyas Naik <119774329+cybercryptixcoder@users.noreply.github.com>`), with no AI attribution in commits.
- **standing**: Keep documenting everything (worklog, design docs, this file). Since 2026-10-23: keep `docs/VERSIONS.md` current as the project's map (what each version tries, what worked, what failed), so every exploration is tracked on GitHub.
- **standing**: Keep going until every workstream is truly done; don't end a turn just because a plan or update was sent. Use sleeps, monitors or scheduled wake-ups to keep working while runs go. A pause is not a wrap-up: wrap up only when the work is really finished, never prematurely with subpar results.
- **standing**: Send progress updates when a workstream makes decent progress (not only at completion), in parallel with the work, in terms of the original requests rather than internal run jargon. Say what worked, by how much, and whether records were beaten.
- **standing**: Every background run has guards: progress saved automatically, interruptions handled, runs pick up where they left off. Check background work after any interruption, say what was affected and whether it was recoverable.
- **standing**: Check the context level now and then; pause systematically before being cut off, and before a known session end, start a long interruption-proof run in the background to check on later.
- **standing**: Never leak evaluator internals or solutions (references, optimal values) to the agents. No warm starts (a warm start only counts if the gain on top of it is very significant).
- **standing**: UI/UX is a priority: pretty, uncluttered, user-friendly, interactive, only necessary data, correct units, no negative scores.
- **standing**: Use subagents to read traces, to save context.
- **standing**: My own runs are small (one problem, 5 generations, at most 10-15). Big suite runs and meta runs are Shreyas's to run.
- **standing**: Use the several Luminal keys in parallel, respecting the rate limits (keys live in `.env`, never committed).
- **standing**: Keep this record: append every new request, including mid-run ones.
- **standing** (2026-10-22): Prompts for job agents (Hermes) never tell the agent to stop, kill or restart processes, and never to create cron jobs, wake-ups or check-ins for itself: the agent starts the job, checks the start once and reports; Shreyas checks in himself. (An agent's own restart cron once killed a running job every 12 minutes.)
- **standing** (2026-10-21): Prompts must not carry problem-specific solution hints: no wording, examples or kinds of change taken from what worked in earlier traces. Audit every new prompt for it before a job.

## 1. Understand the existing system (session start)

- **done**: Walk through run 8's trace in plain language: each generation, the hypotheses, whether there is a separate hypothesis step, the lifetime of one cycle, which models looked at what, what reasoning was done, and whether it did what was *intended*. (`docs/RUN8_WALKTHROUGH.md`)
- **done**: Read the repo enough to work on it.
- **done**: Make the viewer less cluttered (a guided walkthrough page instead of everything-behind-a-click). (`viz/walk.py`)

## 2. Make the evolver do what was intended

- **done**: For each intent the system missed, trace the cause (system prompt, structure, other) and fix it, or rebuild from the ground up keeping the structure: a Researcher going deep, a Mutator going wide, Coders. Enforce intent without limiting the agents. (`docs/V3_DESIGN.md`, `helix3/`)
- **done**: Iterate: run small runs, review traces (subagents), fix, repeat. Six rounds on binpack2d plus the cloud batch; see docs/WORKLOG.md. Further rounds: see "Next" there.
- **done**: Beat records (binpack2d: 27.5% at 5 generations, 34.6% best): round 6 reached 35.1% train, held-out test −5.91 against −6.00, in 15 generations.

## 3. Test suite (generality, no flukes, no leaks)

- **done**: Many verifiable problems: binpack2d, binpack1d, knapsack, set cover, TSP, online scheduling, graph colouring, job shop, CVRP (vehicle routing, added on request). Held-out families, hidden baselines, references never shown to agents. (`suite/`)
- **done**: Generality runs on all 9 problems (cloud batch): every one beats its textbook rule on unseen instances. TSP: 97% from Code Zero in 5 generations; test tour gap ~14% against 25% for the hidden nearest-neighbour baseline.
- **done**: Everything plugged in for Shreyas to run big suite runs himself.

## 4. Meta-evolution (code by me, runs by Shreyas) — scrapped 2026-10-20

- **dropped**: Shreyas scrapped meta-evolution (too expensive and slow for the compute available). The code stays as history; nothing builds on it.

- **done**: An evolutionary loop that evolves the evolutionary loop, using the same kind of LLM search. The best strategy is swapped into the outer loop and the process continues. (`meta/`)
- **done**: The evaluator runs the suite and measures the degree of improvement, speed, generations to improve, flatlining.
- **done**: The outer loop reads the inner runs' traces.
- **done**: An LLM supervisor that keeps it running, fixes crashes, hot-swaps.
- **done**: Make long meta runs robust: resume after any interruption (including a machine restart), preflight checks, fail loudly and early (the first 4-hour run died in its first second on a missing package). See docs/META_V3.md, "Long runs that survive interruptions".

## 5. Dashboard

- **done**: A new dashboard: pretty, uncluttered, interactive, necessary data only, correct units, no negative scores. (`ui/`)
- **done**: Send images of the UI.

## 6. Vision: the search space

- **done**: Explore approaches as a search space; prune only with a certificate.
- **done**: Bench a stream that isn't doing well, keep using the rest, bring benched streams back with a probability.
- **done**: A direction of fastest improvement (approaches ranked by recent gains, with the chain of kept steps; the Navigator pushes the leader).
- **done**: Avoid repetition (novelty fingerprints, an index of everything tried).
- **done**: Aggressive improvement with occasional perturbations (perturbation generations: random-restart weight fits).
- **todo**: Judge these in runs and refine.

## 7. Speed

- **doing**: Shorter generations through engineering only, without hurting quality; target under a minute, ideally under 30 s. Done so far: feature-value cache, instance-affine workers, pipelined fitting (388-1234 s → 70-307 s per generation on 2 cores).

## 8. Thinking modes

- **done**: Effort per role (none, low, medium, high, max), always-on or every Nth generation ("breakthrough"); a thinking model is not asked to write out its reasoning; output budgets grow with effort.
- **done**: Thinking ablation on forage and duel (open suite, 12 generations): no effect on forage; low/high ~3-4 points over none on duel (one run each, unconfirmed); breakthroughs never helped. See WORKLOG, October 20.
- **done (earlier)**: Compare modes in runs. Round 3 (Researcher at low): 25.7% by generation 4. Round 4 (none, max breakthrough at generation 5): 16.6% after 5; the max generation first failed (reasoning ate the token budget; fixed), then kept nothing. Default is back to low.

## 9. Robustness of runs on Shreyas's machine

- **done**: Runs pick up where they left off after any interruption, including turning the PC off (`scripts/install_keeper.sh`: the keeper starts at login and resumes them); a preflight and fail-fast guards so a 4-hour run doesn't fail silently; every state file atomic; the Mac kept awake during meta runs. Nothing can run while the computer is off.
- **todo**: Shreyas: `git pull`, `scripts/install_keeper.sh` once, then `DRY=1 scripts/run_meta.sh` to check, then the real run.

## Log of requests

- 2026-10-17 (session start): walkthrough of run 8; cleaner viewer; commit in Shreyas's name.
- 2026-10-17: the marathon (sections 2-5, 7), the Luminal keys.
- 2026-10-17: after an interruption: check background work, report what was affected; give a plan in terms of the original requests.
- 2026-10-17: don't stop; guards and interruption handling on every background run; CVRP; no leaks or warm starts; UI images; the vision (section 6); speed (section 7); thinking modes (section 8); context checks; a long background run before a session ends.
- 2026-10-17 10:32-10:34: near the session limit: make sure background work survives; start a run now.
- 2026-10-17 14:18: a quick update on what's done, how it went, what's left.
- 2026-10-17 14:25: keep this record and append every request to it; make local runs robust (continue or resume after a PC shutdown, guards so long runs don't fail silently, keep a record of everything).
- 2026-10-17 14:49: which fonts the /meta dashboard uses (answered: Instrument Serif for headings and big numbers, Instrument Sans for text; both free on Google Fonts), for another project.
- 2026-10-17 15:12: pause here; a job script and a prompt for Shreyas's cloud agent to run the setup unattended (long runs, the suite, a meta run), results pushed to GitHub; a milestone check against the hackathon; wake at 7:10/7:15 pm to continue.
- 2026-10-17 19:10: (scheduled resume) cloud agent's 9 runs reviewed; fixed the generation-14 crash; diagnosing the 2D bin-packing plateau.
- 2026-10-17 20:36: is 99.95% on knapsack leakage (pre-training, evaluator)? explain the textbook rule; a per-generation chart for every problem; an honest read of the runs (answered: algorithm found, not leakage; chart sent; offered an ablation hiding reference statistics from the Researcher).
- 2026-10-17 22:30: round 6 beat the records; stopping rule met; wrap-up.
- 2026-10-18 00:17: new open-ceiling problems (invented, no reference, no textbook rule, varied objectives: task performance, speed and scaling, games, one judgement-call objective), a test bench and a job with ablations (thinking modes), a prompt for the cloud agent and a time estimate; keep it short on context.
- 2026-10-18 13:10: meta run analysis (paused: not worth it on this VM); new open problems: a game (also a fast video-game-style one), debugging a program, a math value/construction; jobs gentle on the shared 2-core VM; no meta tests; don't improve the evolver itself, only adapt it to the new problems.
- 2026-10-20: catch up on everything since; the meta loop is scrapped; analyse the ~23-hour open-suite job (results/open/) and say what it tested and what it shows.
- 2026-10-20 18:13: continuity/memory across generations (append context vs an Avy-inspired memory architecture), evolve programs, a population, a richer evaluator; a discovery-level test problem (benchmark if possible); an overnight job (≤ 8 h, 2-core ARM VM) for the Hermes agent; presentation on Oct 21. Full brief, verbatim, with the to-do list: docs/BRIEF_2026-10-20.md.
- 2026-10-21 00:31: verify the 'beat AlphaEvolve May 2025' claim rigorously; are seeds cheating?; document model settings and the milestone; build v4.5 (v4 fixed from its traces) and v5 (the researcher), test, package one overnight job (both in parallel) for Hermes; progress log + updates (00:41). Brief: docs/BRIEF_2026-10-21.md.
- 2026-10-21 01:43: v5's fixes were patches: rethink the structure (beliefs that freeze the search, narrowing, thinking spirals); balance depth and breadth (keep deepening what works, always branch at other points); structured planning; the job must start only after the v4 job completes.
- 2026-10-21 02:12: the v4 job is done; analyse it in depth from the traces and runs (how each run progressed, atlas-s1's steady climb, the model's behaviour, failure points, stalls), then carry the lessons into v4.5 and v5 and finish the other deliverables.
- 2026-10-22 00:06: TL;DR; the mutator loop should form a halo around the deep loop (as fixed in v1); read every trace in depth (v4 55 gens, v4.5 and v5 20 gens); build two next versions: a conservative stream that strictly and substantially improves v4 (v4.6) and an ambitious agentic stream where the system controls its generations (v6); say what is being built before building; test everything, including real end-to-end runs; overnight job for Hermes. Standing rule: Hermes prompts never tell the agent to kill processes or to set up crons; Shreyas checks in himself. Brief: docs/BRIEF_2026-10-22.md.
- 2026-10-22 22:36: does the setup build a false ceiling (try less the better it does; does continuity cause it)? Look at v4 only (150 generations) and the VRP run; seeds explained; how much the system prompt matters; a Hermes prompt to continue the VRP job to generation 100 (done; also found and fixed the VRP program cut-off). Analysis: docs/V4_CEILING.md.
- 2026-10-22 23:21: build v4.7: v4 with every false-ceiling fix, a strict improvement, not a new architecture; clean, tested, job-ready, pushed. (23:24: the Hermes agent is also DeepSeek V4.1 Flash and calls every flat curve a ceiling.) Brief: docs/BRIEF_2026-10-22_V47.md.
- 2026-10-23 00:21: v4.7's first draft only bolted on a third loop: fix the main loop itself (done: lines). Stop the VRP v4 job; run v4.7 on the VRP too.
- 2026-10-23 03:34: do LLM-driven evolutionary searches grok (long plateaus, then sudden climbs; hidden progress)? Write it up as a planned experiment (docs/RESEARCH_PLATEAUS.md).
- 2026-10-23 03:43: document everything on GitHub: v4.7's aims, every variant, what was tried, what worked, what failed; keep a project map current (docs/VERSIONS.md); point to the grokking question.
- 2026-10-23 03:50: on the autocorrelation problem, first warm-start v4.7 from the 150-generation run's best and see how far it gets; the from-scratch v4.7 run later. Keep the old Atlas or start fresh? (Both, as two runs of one job: docs/V47_WARM.md.)
- 2026-10-23 10:51: after the overnight jobs: (A) analyse both and a Hermes prompt (push the Helix results, package the VRP results); (B) VRP v4 vs v4.7: noise or real? (C) VRP warm start from the best program, many generations; (D) continue the autocorrelation warm runs; (E) the plateau/grokking experiments; (F) a new variant: revive closed approaches on today's state, exploration inverse to progress (wide early, deep while climbing, wide/backtracking on stalls). Plan first; Shreyas sets priorities. Brief: docs/BRIEF_2026-10-23.md.
- 2026-10-23 11:28: build one new version (v7) in v4's lineage, a strict improvement not held to v4's shape: no line-closing rules (a fixed threshold doesn't adapt; any improvement counts); the main path continues when flat, with exploration beside it (revive approaches from the Atlas on today's state, backtrack, new things) rising as progress stalls; whatever picks up gets depth; broad at the start. Plan first (plainly, not as features), then build without stopping (pre-approved). Then ready jobs: VRP and autocorrelation, both warm-started from the best code, side by side on the VM, many more generations. Benchmarking versions is deferred. (Done: helix7/, docs/V7_DESIGN.md, docs/V7_JOB.md.)
