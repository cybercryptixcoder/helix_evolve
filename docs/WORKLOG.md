# Work log

A running record of the work on Helix since the handoff: what was asked, what was done, what was found, and what was decided. Newest first. HANDOFF.md stays the reference for how the system works; this file is the history of how it is changing.

---

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
