# What Shreyas has asked for

The running record of every request, so nothing is lost across context compactions or session resets. Each line has a status: **done**, **doing**, **todo**, or **standing** (a rule that applies all the time). New requests are appended to the log at the bottom, with the date, as they arrive (including mid-run ones), and the lists above are updated to match.

Last reviewed: 2026-10-17, from the full message history Shreyas pasted in.

## Standing rules

- **standing**: Commit and push regularly to GitHub, in Shreyas's name (`Shreyas Naik <119774329+cybercryptixcoder@users.noreply.github.com>`), with no AI attribution in commits.
- **standing**: Keep documenting everything (worklog, design docs, this file).
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

## 1. Understand the existing system (session start)

- **done**: Walk through run 8's trace in plain language: each generation, the hypotheses, whether there is a separate hypothesis step, the lifetime of one cycle, which models looked at what, what reasoning was done, and whether it did what was *intended*. (`docs/RUN8_WALKTHROUGH.md`)
- **done**: Read the repo enough to work on it.
- **done**: Make the viewer less cluttered (a guided walkthrough page instead of everything-behind-a-click). (`viz/walk.py`)

## 2. Make the evolver do what was intended

- **done**: For each intent the system missed, trace the cause (system prompt, structure, other) and fix it, or rebuild from the ground up keeping the structure: a Researcher going deep, a Mutator going wide, Coders. Enforce intent without limiting the agents. (`docs/V3_DESIGN.md`, `helix3/`)
- **doing**: Iterate: run small runs, review traces (subagents), fix, repeat, several rounds, until it is "insanely good". Rounds 1-4 done on binpack2d; a 15-generation run is next.
- **doing**: Beat records (binpack2d: 27.5% at 5 generations, 34.6% best).

## 3. Test suite (generality, no flukes, no leaks)

- **done**: Many verifiable problems: binpack2d, binpack1d, knapsack, set cover, TSP, online scheduling, graph colouring, job shop, CVRP (vehicle routing, added on request). Held-out families, hidden baselines, references never shown to agents. (`suite/`)
- **doing**: Small generality runs on 2-3 other problems (TSP started).
- **done**: Everything plugged in for Shreyas to run big suite runs himself.

## 4. Meta-evolution (code by me, runs by Shreyas)

- **done**: An evolutionary loop that evolves the evolutionary loop, using the same kind of LLM search. The best strategy is swapped into the outer loop and the process continues. (`meta/`)
- **done**: The evaluator runs the suite and measures the degree of improvement, speed, generations to improve, flatlining.
- **done**: The outer loop reads the inner runs' traces.
- **done**: An LLM supervisor that keeps it running, fixes crashes, hot-swaps.
- **doing**: Make long meta runs robust: resume after any interruption (including a machine restart), preflight checks, fail loudly and early (the first 4-hour run died in its first second on a missing package).

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
- **doing**: Compare modes in runs (round 3: Researcher at low; round 4: none, with a max breakthrough at generation 5).

## 9. Robustness of runs on Shreyas's machine

- **doing**: Runs keep going or pick up where they left off after any interruption, including turning the PC off (resume automatically on restart); guards so a 4-hour run doesn't fail silently; keep a record of everything.

## Log of requests

- 2026-10-17 (session start): walkthrough of run 8; cleaner viewer; commit in Shreyas's name.
- 2026-10-17: the marathon (sections 2-5, 7), the Luminal keys.
- 2026-10-17: after an interruption: check background work, report what was affected; give a plan in terms of the original requests.
- 2026-10-17: don't stop; guards and interruption handling on every background run; CVRP; no leaks or warm starts; UI images; the vision (section 6); speed (section 7); thinking modes (section 8); context checks; a long background run before a session ends.
- 2026-10-17 10:32-10:34: near the session limit: make sure background work survives; start a run now.
- 2026-10-17 14:18: a quick update on what's done, how it went, what's left.
- 2026-10-17 14:25: keep this record and append every request to it; make local runs robust (continue or resume after a PC shutdown, guards so long runs don't fail silently, keep a record of everything).
