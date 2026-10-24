# Exploring the search space: what it is, why the search stays on one hill, and how to find others

Shreyas's question (October 24, `docs/BRIEF_2026-10-24.md`): Helix climbs well, so how do we discover other hills to
climb? This document reasons about that conceptually first, checks the reasoning against what the v7 runs did
(`docs/V7_RESULTS.md`), and only then says how it could become add-ons to v7. Nothing here is built yet.

## 1. What the runs say, in short

- **v7 did what it was designed to do.** Exploration ran in most generations, nothing was closed, and paused tracks
  came back. On the VRP, a track that started worse took the record 22 generations later and then climbed.
- **It was not restarting from scratch at each stall.**
  - Backtracks went one step back: every autocorrelation backtrack root was within 0.2% of the record.
  - The restarts from scratch (the bold experiments built from Code Zero) all fell into the model's default basin.
    On the autocorrelation problem, all 19 such tracks peaked at or below 0.8825, the textbook construction. On the
    VRP, they mostly stayed at Code Zero's level.
- **The one real change of hill came from changing something every program shared.**
  - A VRP bold experiment noticed that every program in the tree started from the same myopic greedy, and replaced it.
  - It was worse at first. Once on that hill, the run climbed +0.26% in 22 generations, against +0.11% in the 78
    before.
- **The planner reasoned that way 9 times on the VRP**, and almost never (3 times in 100 generations) on the
  autocorrelation problem, where the bold slot's wording ("Code Zero, to build from nothing") sent every bold
  experiment back to scratch.
- **On the autocorrelation problem the current hill is exhausted locally.** 68% of children handed back their start
  unchanged, and 100 generations moved the record by 2.2e-5.
- **A higher hill exists there:** the best known result is 0.9626, against Helix's 0.9413.

So the problem is not that the search doesn't explore. It explores often, but in two ways that can't find new hills:
- **tiny steps back**, which return to the same hill;
- **restarts from scratch**, which fall into the same default hill.

## 2. What the search space is

There are four layers:
1. **Program text.** It is astronomically large, and mostly meaningless: changing one character is a "move" that
   tells us nothing. This is not the space to reason in.
2. **Design.** A program is a set of decisions.
   - For the VRP: how the first solution is built, which moves repair it, which moves are accepted, how the time is
     split, whether subproblems are solved exactly, how routes are represented.
   - For the autocorrelation problem: how the function is represented (steps, resolution), which objective is
     optimised (the true max, or a smoothed surrogate), with which optimiser, from which support, on which schedule.

   Each decision has options. **This is Shreyas's "approaches" space, and it is the right one.** A program is a point
   in it, and an LLM edit usually changes one or two decisions.
3. **Behaviour.** What the program produces: the construction, or the routes. Some of its properties can be measured
   by code (resolution, how much of the support is zero, how flat f∗f is; how many trips, which truck mix, how fast it
   reaches its final cost).
4. **The score**, a function of the behaviour.

A **hill** is a family of designs that share their key decisions and differ in details. Climbing changes details.
Changing hills means changing a key decision.

Three properties of this space matter:

- **The axes are not given.** Nobody lists the decisions in advance. They exist as far as somebody has noticed that a
  choice was made. New options can always be invented, so the space grows as it is explored.
- **Some axes are frozen.** A decision that Code Zero made, and that every descendant kept, is an axis the search has
  never moved along. The VRP's greedy start was one: by the planner's own reading at generation 57, every program
  in the tree shared it. **A maximum along the axes being varied can be a slope along a frozen one.** This is
  Shreyas's "falling into the next dimension", and the VRP's breakthrough is a case of it.
- **Decisions interact.** The rest of a design is tuned for its current options. Change one decision and the rest is
  now mistuned, so the program scores worse until it is re-tuned. That is why a genuinely different idea looks worse
  first (T40 started 0.14% down). **A new option must be judged by the height of its hill, after a short climb, not
  by its first score.**

## 3. Why the search stays on one hill

1. **Only some axes move.** The planner refines what the champion does. It rarely asks what every program does the
   same way.
2. **Restarts sample the model's prior.**
   - In machine learning, a random restart works because the starting point is drawn independently of the landscape.
   - Here a restart is "write me a fresh program", drawn from what the model would write anyway. That is very
     concentrated: 19 of 19 autocorrelation restarts landed at or below the textbook 0.8825.
   - Restarting more often will not fix this.
3. **New options are judged too fast.** On the VRP, eight more shared-assumption changes were tried. Each started
   slightly worse, got one follow-up, and paused. Only T40 was woken, by a lucky mutation.
4. **Failed directions leave no measurement.** When an idea fails, the program hands back its start. The search learns
   "no gain", not "this direction costs 0.3%" or "this one costs 0.001%". The planner gets almost no information
   about the shape of the landscape around the champion.
5. **There is no map.** The planner sees a tree of programs and a list of findings. It doesn't see:
   - which decisions exist;
   - which have been varied, and how much;
   - which never have been.

## 4. Shreyas's probing idea, examined

**The idea.** Treat approaches as axes, probe each one locally to learn which way improves, and climb in that
direction. With a few dozen axes, a little probing per axis is affordable.

**What holds.**
- The space is small enough to map: dozens of decisions, not billions.
- Signed probes give direction cheaply. This is a finite-difference gradient over designs.
- More axes give more ways out. This is a real phenomenon in high dimensions: most points that look stuck are saddle
  points, with some direction still going down (Dauphin et al., 2014).

**Three corrections.**
1. **At a local maximum, every probe along the axes being varied is worse.** That is what a local maximum is.
   Probing those axes confirms the maximum; it doesn't escape it. The escape is along axes not yet varied (the frozen
   ones), or by a large step to another option.
2. **Many axes are discrete.** "Direction" means which option, and there may be no opposite. "If one direction hurts,
   the other helps" holds on a slope, not at a top, where both hurt.
3. **A probe must be a kick and a short climb**, because of the interactions above. The probe's value is the height
   it reaches after re-tuning, not its first score. Otherwise every real new idea reads as negative.

**What it becomes.**
1. Map the decisions, including the frozen ones.
2. On a strong program, change one decision at a time to an option not yet tried.
3. Let it climb a few steps.
4. Record the height reached.

That is how new hills are found and measured. The continuous "extent" of an option (a temperature, a time split) is
better tuned by the program itself, inside its own CPU budget. Model generations are the expensive resource; they
should be spent on discrete changes of design, not on tuning numbers.

## 5. The replay-the-chain idea, examined

**The idea.** When backtracking to an old, weak program, apply the whole chain of improvements that led to the
champion in one go, so it catches up at once.

**What the data say.**
- This already happens implicitly. On the VRP, one bold restart from Code Zero rebuilt most of the chain in 5
  follow-ups: 1.40 to 1.635, just below the hill it came from. The model knows the chain; it is in the Atlas.
- **But the chain is the hill.** Replaying it on an older seed rebuilds the same design and lands on the same hill.
  Shreyas's own doubt about this avenue is borne out.

**What it becomes.** Don't go back in time. Go sideways: keep the champion's chain and change one key decision under
it (a transplant). That is what the VRP's breakthrough did. It is cheaper than a replay, because nothing is redone,
and it leads to a different hill, because one key decision is different.

## 6. How machine learning and optimisation escape local optima, and what carries over

| Technique | What it does | Does it carry over? |
|---|---|---|
| **Random restarts** (multi-start) | Start from independent points; keep the best | Only if the starts are genuinely diverse. Here they collapse into the model's prior. It carries over as **directed restarts**: "build a program whose decision X takes option Y", aimed at parts of the design space not yet visited |
| **Noise and annealing** (SGD noise, simulated annealing; Kirkpatrick 1983) | Accept worse moves, so barriers can be crossed | Yes: v7's side tracks do it, and T40 is the proof. New options need a longer acceptance than one follow-up |
| **Basin hopping and iterated local search** (Wales & Doye 1997; Lourenço et al.) | Kick, re-optimise locally, keep if better | **The right model for probes.** The kick size matters: too small returns to the same hill (our backtracks), too large is a restart (our bold experiments). One key decision is the middle size |
| **Variable neighbourhood search** (Mladenović & Hansen 1997) | When stuck under one kind of move, switch to another kind; a local optimum for one is often not one for another | The classical form of "add a dimension". Our neighbourhood is "change a detail of the champion"; the other neighbourhoods are "change decision k" |
| **More dimensions** (over-parameterisation, saddles, connected minima; Garipov et al. 2018) | In high dimensions, true local minima are rare | Supports finding and varying frozen axes |
| **Continuation, smoothing, curricula** (graduated non-convexity; Bengio et al. 2009) | Solve an easier or smoothed problem first, then sharpen it | Yes, and it has already worked here: the autocorrelation record line came from a soft-max surrogate objective. More generally: optimise a proxy for a while (another resolution, a smoothed objective, a different time limit or instance weighting), then return to the true score |
| **Diversity: niching, islands, quality-diversity** (MAP-Elites, Mouret & Clune 2015; novelty search, Lehman & Stanley 2011) | Keep the best solution of each region of a descriptor space, so stepping stones survive. Objectives can be deceptive: the path to the best solution often passes through poor scores | Yes. The descriptors can be design options or measured behaviour (properties our evaluators already print). v7's side tracks are a partial version |
| **Surrogate models, Bayesian optimisation, bandits** (UCB, Thompson sampling) | Spend trials where expected improvement or uncertainty is highest | Yes: what to explore can follow how little is known about each part of the map, not only how long the record has stalled |
| **Recombination** (crossover) | Combine components from different solutions | Yes, at the level of decisions: take decision X from one hill's best and Y from another's |
| **Tabu lists** (Glover) | Forbid recently visited moves | Partly in place already (no repeating a failure on the same construction) |

**The lesson that ties these together.** Methods that escape local optima reliably do two things:
1. they change the kind of move (variable neighbourhoods, basin hopping);
2. they keep and judge solutions per region instead of only globally (niching, quality-diversity).

Neither restarts nor small steps do this. Restarts work in machine learning only because there the starting points
really are random.

## 7. How do we know a better hill exists?

In general you can't know for sure, but there are four honest signals:
- **Known results and bounds.**
  - Autocorrelation: 0.9626 has been reached, so a higher hill certainly exists. The Hölder bound of 1.0 is the
    absolute ceiling.
  - VRP: a lower bound on cost (a standard LP relaxation, solved by column generation) would say how far today's
    routes are from optimal on the training worlds.
    - If they are within a few percent, no program can be 2–10x better on cost, and the room is in speed.
    - If the gap is large, the room is real.

    This is an offline computation for us; it is never shown to the agents.
- **The spread of genuinely diverse climbs.** If diverse starts all climb to the same height, the landscape probably
  has one main hill. If they climb to different heights, there are several. Today's restarts are not diverse, so they
  say nothing.
- **Untried volume:** how many decisions, and options of each, have never been tried. The map counts it.
- **The climb after a change of decision.** The best evidence of a new hill is a track that keeps climbing after its
  change, as T40 did.

## 8. The concept: a map of the design space, probes that measure hills, and regions that are kept

**The concept.** Keep the climber. Add five things:

1. **A design map.** The decisions, their options and where every program sits. It includes the decisions every
   strong program shares (found by asking that question on purpose).
2. **Probes.** Change one decision of a strong program to an untried option, let it climb a few steps, and record the
   height of the hill it reached.
3. **Regions.** Keep the best program of each region of the map, so stepping stones survive and new hills are not
   judged against the old one's top.
4. **Directed restarts.** Restart only into regions of the map not yet visited, and check where a restart actually
   landed.
5. **Spending by knowledge.** Choose what to explore by how little is known about each part of the map, and by how
   fast its best is climbing. v7's stall level still decides how many slots explore; the map decides what they do.

**Why it should help a lot.**
- **On the VRP:** the run's one change of hill came from exactly such a probe, found by chance in a bold slot at
  generation 57.
  - The shared starting construction was there from generation 1, so a map asking "what does every program share?"
    would very likely have flagged it at once.
  - The 8 other shared-assumption changes the planner proposed were each judged after one follow-up. Probes would
    have climbed each before judging.
- **On the autocorrelation problem:** of the 74 side tracks opened, 49 were revives (no gains) or restarts from
  scratch (all into the 0.8825 well). That budget becomes probes on the record construction.

**What could make it fail, honestly.**
- **The map is only as good as the decisions the model can name.** On the VRP, the planner named shared assumptions
  readily. On the autocorrelation problem it rarely did, and the next hill there (towards 0.96) may need a
  qualitatively different construction that no single decision change reaches.
- **Descriptors for regions can be badly chosen.** Measured behaviour (computed by code) is safer than labels written
  by the model.
- **Probes cost several generations each**, so the map must be selective.

**Testing it before building it.**
1. **Offline, at no VM cost:** run the map-building step over the two v7 archives (653 and 602 programs).
   - Can it list sensible decisions?
   - Does it flag the VRP's shared greedy start in generation 1?
   - What does it flag on the autocorrelation problem?
2. **A short live test on the autocorrelation problem:** about 10 probes on the record construction, each with 3
   follow-ups: about 40 planned experiments.

## 9. As add-ons to v7 (not built yet)

**What stays as it is:**
- v7's stall level;
- the main track's guaranteed slot;
- tracks that are never closed;
- the wide loop's sampling;
- alternatives, the noise floor, warm starts.

They are what works.

**The add-ons, in the order to build them:**

1. **The design map: a new layer of the Atlas** (decisions, options, each program's position).
   - Written by a small extra step after the Distiller, which labels each new program's change by the decision it
     touched.
   - Every few generations, and whenever the stall level rises, a "what do all strong programs share?" scan.
   - The planner sees it as a compact table: each decision, its options, how often each was tried and its best score.
2. **A "probe" exploration slot, replacing revive.**
   - It changes one mapped decision of the champion or of a region's best to an untried option.
   - Its track gets 2–3 follow-ups that may re-tune but not undo the change.
   - On the autocorrelation problem, the probe's own construction is always handed back as an alternative, so its
     height is measured even when it is below the record.
   - The revive options become one source of options for a probe.
3. **Bold becomes a directed restart.**
   - "Build a program whose decision X takes option Y", aimed at an unvisited part of the map.
   - Its landing is checked by measured behaviour. If it lands in an occupied region below that region's best, it is
     not new, and it stops.
   - The "build from nothing" wording goes.
4. **Regions.**
   - Every track gets the region it sits in. The archive keeps each region's best.
   - Backtrack options and the wide loop's side parent are drawn from region bests.
   - Exploration slots are given out by a bandit score: how much is unknown, plus how fast the region is climbing.
5. **Combining** decisions from two regions' bests (later).

**Fixes on the way:**
- the v7 report's record count;
- pressure to keep VRP programs short (they grew to 132,000 characters, near what one reply can hold);
- the bold wording.

**First step:** the offline test of item 1 on the existing archives. If it would have found the VRP's breakthrough
decision early, items 2–4 follow. If it can't name meaningful decisions, the concept needs rethinking before any of
it is built.
