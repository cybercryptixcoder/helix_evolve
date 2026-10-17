# Work log

A running record of the work on Helix since the handoff: what was asked, what was done, what was found, and what was decided. Newest first. HANDOFF.md stays the reference for how the system works; this file is the history of how it is changing.

---

## October 17, 2026 (later): a plain walk through run 8

### What was asked

The viewer does too much: everything sits behind a click and it's hard to follow. Shreyas wants to be *taken through* the run instead: what happened each generation, what the agents hypothesised, where each message went, and above all whether the system does what it was designed to do (the intent, not whether the code ran).

### What was done

- [RUN8_WALKTHROUGH.md](RUN8_WALKTHROUGH.md): who each station is (only the Researcher, Coder and Mutator are LLMs), one full cycle from Code Zero through generation 1, each generation in turn, and a table of intent against actual behaviour.
- Two facts confirmed in the code while writing it: the Researcher's `target` (its prediction) is saved and never checked (`evolve.py`, `record_hypotheses`); and an idea rejected by the probe is logged as "refuted" with no number (`evolve.py`, `verdict`).

### Open

- Whether to rebuild the viewer as a guided, narrated step-through (one step at a time, the explanation visible without clicking) rather than a free-running factory floor. Not started; waiting for Shreyas.

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
