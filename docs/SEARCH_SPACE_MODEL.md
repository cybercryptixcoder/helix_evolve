# A model of the search space, and what to build next (October 27, 2026)

The request: `docs/BRIEF_2026-10-27.md`. The earlier reasoning this builds on: `docs/SEARCH_SPACE.md` (why the search
stays on one hill) and `docs/V8_DESIGN.md` (the register of hills). Nothing here is built yet.

This document:
1. makes the map from the October 27 discussion precise;
2. checks it against what the runs (v4 to v8) actually did, with new measurements;
3. collects what other fields do with the same problem;
4. proposes a mathematical model of the search space;
5. answers the questions from the discussion one by one;
6. proposes v9, and how it plugs into Helix;
7. proposes a proof-of-concept ladder, so the system is trusted before it is scaled;
8. discusses persistence, an evolutionary agent, and RL;
9. says how confident I am, and what I recommend.

---

## 0. In one page

- **The map is right, and it has a precise form.** A program answers a set of design questions (axes); each answer
  is a value; a design is a point; a program is one implementation of that point; the score after climbing at that
  point is its height. The space is a **growing, hierarchical, categorical design space**, and the score over it is
  best modelled as **a few main effects plus a few pairwise interactions** (sparse functional ANOVA). The interactions
  are "features overlapping"; they are what creates several hills.
- **The axes are few, and they recur.** v8's Cartographer was asked 82 times to list design decisions. It wrote 460
  different wordings, but about 98% of them fall into 9 recurring axes. The number of basic features does look
  roughly fixed at this level, as you guessed; what grows is the number of **values** on each axis, and the
  **sub-axes** under them. But v8 never kept the axes: it re-derived them each time and reused the same labels for
  different decisions (59 different decisions were called "D1"), so no program ever got a coordinate.
- **The biggest measurable flaw is how new hills are judged.** Across 15 from-scratch runs, a run's best after 20
  programs had no rank correlation with its best after 120 (Spearman -0.09). The run that became Helix's 0.94 hill
  was the 4th lowest of 15 after 20 programs, and three of the four highest ended in the 0.8825 trap. In v8,
  restarts got a median of 3 experiments before pausing; three reached 0.90-0.914 within 12, which is higher than
  the record's own run was after 40 programs (0.878). **A hill's height is not visible from its foot.**
- **A "flip" of one decision was often not one decision.** A flip of the budget-allocation decision produced a
  program described as abandoning the record's whole lineage and seeding from scratch. The LLM, asked to move along
  one axis, often jumped many. The flips that stayed faithful landed at the record's height on a different shape.
- **The mathematical frame for an LLM search:** every such system samples programs from the LLM's own prior, tilted
  by the score. Restarts sample that prior, which is why they all fall into the same well. **A coordinate is a way to
  sample where the prior is thin:** "write a program whose decision A is a2 and B is b3" puts mass where "write a good
  program" never goes. That is what "dropping on a random point of the map" means for us.
- **Others are on higher hills of the same problem** (second autocorrelation inequality): ImprovEvolve 0.951 without
  a human edit, GigaEvo 0.948, ThetaEvolve 0.947, test-time RL 0.959; Helix 0.9414. Helix climbs well. What it lacks
  is reaching and fairly judging other hills.
- **Proposed v9 = v8 + a design map with stable coordinates + a model of the landscape + directed drops + a fair
  race between hills + ablations that say what helps and what hurts.** Strictly additive: while the record climbs,
  a generation is v8's.
- **Trust before scale** (your note): a ladder of three proofs, cheapest first: an offline replay on the 3,625
  programs v8 already has (no runs), a planted landscape with a known best (seconds per run, no model), then a small
  live run against a simple baseline.
- **On persistence and agents:** the loop already is enforced persistence, and it works for the reason long-task
  benchmarks show models fail (they repeat failed actions or give up). It turns into an agent for open-ended tasks
  only as far as the evaluator can be trusted; a private run's overfitting is the warning. RL on the model during
  a problem is real and strong (0.959 on this problem), but needs GPUs; the map is the cheap persistence we can have
  now.

---

## 1. The map, made precise

| Word | Meaning | Example (autocorrelation) | Example (VRP) |
|---|---|---|---|
| **Axis** (feature, direction, decision) | A question every program answers, explicitly or by default | How is the non-smooth max handled? | How is the first solution built? |
| **Value** (option) | One answer to that question | hard max with tie-averaging; a soft-max surrogate; a linear program | myopic greedy; regret insertion; a savings construction |
| **Point** (coordinate, design) | An answer to every axis | (soft-max, log-heights, frozen zeros, coarse-to-fine, L-BFGS, ...) | (regret insertion, ruin-and-recreate, SA acceptance, ...) |
| **Program** | One implementation of a point: details, tuned numbers, code quality | p1554 | p0601 |
| **Climb** | Improving the implementation while the point stays the same | polishing schedules, better step sizes | cheaper moves, caching |
| **Height of a point** | The best score programs at that point reach after climbing | 0.9414 for the record's design | |
| **Hill** | A region of points (and programs) that climb to the same top | the record's spiky-comb family | T40's family after its new start |
| **Move** | A change of program; its size is how many axes it changes | 0 axes: a polish; 1: a flip; many: a jump | |

**Resolving the confusions from the discussion:**

- **Tree versus map.** The tree is the *history*: who came from whom. The map is the *space*: where each program
  sits. A branch is a move, and every move changes zero, one or several coordinates. The tree is a path drawn on the
  map. Both pictures are right, and they are different objects.
- **Branching early is not the same as jumping far.** Branching from an early program differs in many coordinates
  from the current champion only because the early program hadn't made the later decisions yet. The size of a jump
  is the number of axes changed (a Hamming distance), not how far back in the tree it starts. That is why v7's
  "backtracks" went one step back on the same hill (`docs/V7_RESULTS.md`): far back in time, close on the map.
- **"On a new axis we are at zero."** Not quite, and your collaborator's instinct was right: every existing program
  already answers the new question, by default (the "frozen axes" of `docs/SEARCH_SPACE.md`: the VRP's myopic greedy
  start was one). When an axis is discovered, every program gets the value "what it does now". The map doesn't move
  where we are; it reveals where else we could go.
- **"Features overlap"** is interaction (biologists call it epistasis): the best value of one axis depends on the
  value of another. A soft-max surrogate may only pay off with a different optimiser. Interactions are what create
  several hills: without them, improving one axis at a time would reach the single top.
- **Every branch a feature, or a combination?** Each move changes a combination of coordinates; a new *axis* is born
  only when a move changes something none of the existing axes describes.

**Two coordinates per program.** A design coordinate says where a program *aimed* (its decisions, read from its
code). A behaviour coordinate says where it *landed* (what it produces, measured by code: v8's shape and trip
signatures). They are different on purpose: v8's calibration found that three of v7's VRP "decision changes" didn't change
what the program produced at all (`docs/V8_DESIGN.md`, distances 0.007, 0.007, 0.000). Design says what to try; behaviour
says whether it is new.

---

## 2. What the data say (new measurements, October 27)

### 2.1 The axes are few and recur, but v8 never kept them

v8's Cartographer listed the decisions every known hill shares, 82 times over 400 generations (8 per scan, 656 in
all). Grouping the 656 by keyword (a rough grouping):

| Recurring axis | Times named |
|---|---|
| how the objective and its max are handled (hard max, soft-max, surrogate, ties) | 150 |
| representation and parametrisation (heights, log-heights, squares, blocks, splines) | 85 |
| escape mechanism and search paradigm (perturbation, structural edits, restarts) | 81 |
| resolution and grid strategy (coarse-to-fine, lifts, prolongation) | 80 |
| support and zeros (frozen, revived, pruned) | 71 |
| budget and time allocation across phases | 65 |
| starting point | 48 |
| optimiser core | 47 |
| symmetry and structure (periodic, quotient) | 15 |
| other (mostly "what quantity is optimised", "constraint enforcement") | 14 |

- **About 98% of the names fall into 9 axes.** At this level of abstraction the number of basic features looks
  roughly fixed, as the discussion guessed.
- **But the labels were not stable.** 460 different wordings; 59 different decisions were labelled "D1" at one time
  or another. Each scan started from scratch. So:
  - no program was ever given a coordinate;
  - no axis accumulated a history (which values were tried, how they did);
  - a flip of "D1" in one generation and a flip of "D1" in another were flips of different things.

### 2.2 Early height does not predict a hill's height

Across the 15 from-scratch runs of v4, v4.5 and v5 (120 programs each, the same problem, the same start):

| | Rank correlation with the run's final best (Spearman) |
|---|---|
| best after 20 programs | **-0.09** |
| best after 40 programs | 0.50 |

- **The run that became Helix's best hill** (v4 atlas-s1, 0.939 at 120 programs, later 0.9414) was the 4th lowest
  of 15 after 20 programs (0.845), and 6th lowest after 40 (0.878).
- **Three of the four runs that were highest after 20 programs ended in the 0.8825 trap.** The trap is a hill that
  is easy to climb fast. Early height can be worse than uninformative: it can point at the trap.

### 2.3 v8 judged new hills after a few steps

| v8 exploration (generations 291-700) | Tracks | Experiments per track (median) | Best (median) | Reached 0.90 or more |
|---|---|---|---|---|
| restart (a design unlike every known hill) | 61 | 3 | 0.822 | 3 |
| flip (change one shared decision of a hill's top) | 61 | 5 | 0.9414 | 33 (all but two on two record-height hills that flips founded) |

- **The three restarts that reached 0.90-0.914 started from Code Zero and did it within 8-12 experiments** (T94:
  0.914 in 12; T104: 0.9085 in 8; T96: 0.900 in 9). The record's own run was at 0.878 after 40 programs. They
  paused after 2 follow-ups without a gain, as designed, and were judged against a record that had more than a
  thousand experiments behind it.
- **Caveat:** v8's restarts had the record's chain of improvements in their prompt and twice the CPU per program of
  v4 (60 s against 30 s), so this is not a like-for-like race. The point is that nothing in v8 asked "how does this
  hill compare with the record's hill at the same effort?"
- **The record moved by 5e-7 after generation 384** (316 generations), while 73 hills were registered.

### 2.4 A move along one axis was often a jump along many

- **Unfaithful:** a flip of the budget-allocation decision founded a hill whose description reads "abandons the
  record's spiky-comb lineage entirely and instead seeds from scratch with two structured families". Several other
  flips are described as abandoning "the record's lift-and-polish lineage" or its "discrete structural edits".
- **Faithful:** the flip of the non-negativity handling to a squared parametrisation (h = v²) landed at the record's
  height, 0.94144, on a different shape (hill H30). So did a flip that replaced the escape mechanism (H22), though it
  was labelled as a flip of a different decision. 31 of the 33 flips that reached 0.90 ended on these two hills.
  Changing one axis at a time on this hill moves along a ridge of equal height. Biologists call this a neutral
  network.
- **So the LLM is a noisy decoder.** Asked for one coordinate change, it often produces another point. Without
  reading the result back, the map would record a flip that never happened (v8 already catches part of this through
  behaviour: "the change has not moved it off that hill yet").

### 2.5 Higher hills of this problem exist, and other machinery reaches them

| System | Second autocorrelation inequality | Note |
|---|---|---|
| Helix (v8, warm from v4.7 and v7) | 0.94144 | |
| ThetaEvolve | 0.9469 | as reported by ImprovEvolve |
| GigaEvo | 0.9478 | as reported by ImprovEvolve |
| ImprovEvolve (no human edit) | 0.9512 | the LLM evolves generate / improve / perturb operators, run as basin hopping |
| TTT-Discover, Qwen3-8B | 0.9472 | RL on the model's weights during the problem |
| TTT-Discover, gpt-oss-120b | 0.9591 | about $500 a run |
| AlphaEvolve V2 | 0.96102 | |
| ImprovEvolve with an expert edit, warm-started from AlphaEvolve's | 0.96258 | best known |

Helix's hill is not the tallest. Its climbing is strong (it climbed one hill for 500 generations), so the gap is in
reaching other hills and in judging them fairly, not in climbing.

---

## 3. What other fields do with the same problem

Grouped by the question each answers. Sources at the end.

### 3.1 How to search many basins: drop, climb, keep several regions

- **Basin hopping and iterated local search:** perturb, re-optimise locally, keep if better. Kick size decides
  everything: too small returns to the same basin (our backtracks), too large is a restart (our bold experiments).
  In design-space terms: a kick of 2-3 axes. ImprovEvolve is literally this: the LLM writes `generate`, `improve`
  and `perturb`, and the evaluator runs basin hopping with them.
- **TuRBO (trust-region Bayesian optimisation):** instead of one global model, several local regions run at once,
  each centred on its best point. A region grows after successes, shrinks after failures, and is replaced by a fresh
  one when it collapses. Each batch slot goes to whichever region's sample looks best: an implicit bandit. **Our
  tracks are trust regions;** what's missing is the rule that gives slots to regions by evidence, and the restart
  of a collapsed one somewhere new.
- **Go-Explore:** keep an archive of "cells", pick one (rarely visited ones more often), return to it exactly, then
  explore from it. It names two failures: *detachment* (forgetting promising frontiers) and *derailment* (exploring
  so wildly you never get back). The cell representation is the crux: downscaled frames, hand-chosen features, or
  (as future work) learned ones. **A design coordinate is our cell.**

### 3.2 What the landscape looks like

- **NK landscapes:** N decisions, each interacting with K others. K = 0 gives one smooth hill; as K grows, local
  optima multiply and become lower and more random. The number of hills is a property of the interactions.
- **Local optima networks:** compress a landscape into a graph whose nodes are basins and whose edges are the
  chances of moving between them. Our hill register is the start of such a graph; the edges (which kind of move
  leads from which hill to which) are not recorded yet.
- **Neutral networks** (Wagner): many genotypes share one phenotype and fitness. Drifting along a neutral network is
  how populations reach new phenotypes without paying a fitness cost. Section 2.4's ridge is one.

### 3.3 How designers map a design space

- **Designing network design spaces (RegNet):** treat a *population* of designs as the object of study. Sample
  hundreds from a space, plot the distribution of their errors, and constrain one axis at a time (shared bottleneck,
  widths that never decrease), keeping a constraint only if the distribution stays as good. They went from 16
  degrees of freedom to 6 without loss. **Lesson: learn which axes matter from populations, not from the single
  best.**
- **Component-wise algorithm design (AutoMOEA, irace):** an algorithm is a template whose components are categorical
  parameters. "The configuration space searched by irace is actually a design space." The automatically designed
  algorithms often matched, and sometimes clearly beat, six hand-designed ones. **Lesson: algorithm design spaces
  really are categorical, and small.**
- **Zwicky's morphological box:** list the parameters of a problem and the values of each; every combination is a
  configuration; a cross-consistency assessment removes the pairs that cannot coexist. The 1940s version of our map,
  including the pruning of impossible combinations.

### 3.4 How to model a score over a categorical space with few samples

- **Effect sparsity** (design of experiments): in most systems a few main effects and a few two-factor interactions
  explain most of the variation. Screening designs exist because of it.
- **BOCS:** a second-order model over binary (one-hot) variables, with a shrinkage prior that keeps most
  coefficients near zero; each step samples one model from the posterior (Thompson sampling) and picks the best
  input under it. Sampling, not the point estimate, is what keeps it exploring. Categorical variables become one-hot
  groups.
- **Functional ANOVA (fANOVA):** decomposes a fitted model's variance into each axis and each pair, which is
  exactly "what is helping and what is hurting".
- **Additive Gaussian processes:** the same idea with a smooth kernel, sums of low-order interaction terms.

### 3.5 How to get coordinates for things that aren't numbers

- **Latent-space optimisation (molecules):** an encoder maps a molecule to a continuous vector, a decoder maps
  vectors back, and the search runs in the vector space. The two failure modes are the encoder putting different
  things together and the decoder producing something other than what was asked. **For us: an annotator is the
  encoder, the coder is the decoder, and decoder fidelity must be checked by encoding the result again.**
- **QDAIF:** an LLM places texts on axes the user gives ("positive vs negative") and MAP-Elites keeps the best per
  bin. The axes are given; the authors name LLM-proposed axes as future work, and note the LLM judge becomes
  unreliable at the top of the quality range.
- **AURORA, AutoQD:** learn behaviour descriptors from data (an autoencoder; random features of behaviour plus a
  projection fitted to the archive) and refit them periodically as the archive grows. AutoQD's learned descriptors
  scored best on its main measure in all six of its tasks, ahead of hand-made ones. **Lesson: the axes can be
  refitted as the search goes.**
- **Code similarity is a poor axis:** a landscape study of LLM algorithm search found that text and syntax
  similarity correlate only weakly with differences in performance. Designs and behaviour, not code text.

### 3.6 How a space can grow while it is searched

- **NEAT:** networks start minimal and grow new genes (dimensions) during evolution. Three ideas carry over almost
  word for word:
  - every new gene gets a permanent *historical marking* at birth, so genomes of different sizes can be compared;
  - new structure starts neutral;
  - new structure is *protected* in its own species until it has been optimised, because it looks worse at first.
- **DreamCoder:** alternates between solving tasks with a library of abstractions and growing the library from what
  the solutions share (wake-sleep). The library is the axis set; it grows from solutions.
- **Stepping stones and novelty:** objectives can be deceptive, and the route to the best often passes through
  lower-scoring designs. The Darwin Gödel Machine's ablation shows it in an LLM system: without an archive of
  stepping stones its coding agent reached 23% on SWE-bench instead of 50%.

### 3.7 How to divide effort among candidates whose scores rise with effort

- **Successive halving / Hyperband, freeze-thaw optimisation, rising bandits:** start many candidates cheaply, extend
  the ones whose learning curves look most promising, and compare curves at equal effort, never a fresh candidate
  against a mature one. Our 2.2 is the reason this matters here.
- **MCTS-AHD:** population methods (FunSearch, EoH, ReEvo) discard a new heuristic unless it beats the worst of the
  current population, so slow starters die. Keeping every heuristic in a tree, and widening progressively, did
  better on routing and packing heuristics.

### 3.8 What LLM program search adds, and what it doesn't

- **The search samples the LLM's prior, tilted by the score.** SMCEvolve writes the target as
  p*(program) ∝ p₀(program | prompt) · e^(β·score): the LLM prior reweighted by reward. Whatever the machinery, the
  only places to act are the prompt (which changes p₀) and the selection (which changes the tilt).
- **Simple baselines are competitive:** independent sampling, and sampling conditioned on random earlier programs,
  matched or beat elaborate systems on most tasks tested. The authors found that **the search space and the problem
  formulation mattered most**, that evaluation noise picked lucky candidates, and that comparisons need simple
  baselines and repeated runs.
- **Variance is large:** a study of LLM heuristic design found results varied widely across runs and models; single
  runs can't support claims.
- **Novelty filters work cheaply:** in ShinkaEvolve, rejecting proposals whose code embedding is too close to an
  existing program gave most of the gain; an extra LLM novelty judge added little.

---

## 4. The mathematical model (the overarching question)

### 4.1 The object

- A **design space** X = A₁ × A₂ × ... × A_d, where each axis Aᵢ is a finite set of values that can grow, and some
  axes exist only under a value of another (an "SA cooling schedule" axis exists only if the acceptance rule is SA).
  This is a tree-structured categorical space, the same object hyperparameter optimisers handle (conditional
  parameters).
- A **program** is an implementation of a point x ∈ X. Many programs implement each point.
- The **height** h(x, e) is the best score programs at x reach after effort e (experiments spent climbing there).
  What we observe is y = h(x, e) + implementation noise.
- **Behaviour** b(program) is a measured signature (v8's shapes and trip sets). Hills are regions of behaviour.

### 4.2 Its structure: sparse main effects and interactions

Write the height at a fixed effort as a functional ANOVA decomposition:

h(x) = μ + Σᵢ gᵢ(xᵢ) + Σᵢ<ⱼ gᵢⱼ(xᵢ, xⱼ) + (higher-order terms)

- **Main effects** gᵢ: "this value is good whatever else you do".
- **Pairwise interactions** gᵢⱼ: "this value is good only with that one". This is "features overlap", and it is what
  makes hills. If interactions are mostly pairwise, a new hill is typically **2-3 coordinated changes away**, which
  is the right kick size for a drop, and exactly what single flips can't reach.
- **Effect sparsity** says few terms matter, so the model is learnable from hundreds of programs, which we have
  (v8's archive has 3,625).

### 4.3 The sampler: why coordinates matter more for an LLM than for an ML model

- In machine learning, a random restart works because the starting point is drawn independently of the landscape.
- Here every program is drawn from p₀(program | prompt). "Write a fresh program" draws from the model's default
  basin: 19 of 19 v7 restarts and most v8 restarts.
- A **blueprint** ("decision A takes a2, decision B takes b3, keep the rest") conditions p₀ on a coordinate. It moves
  probability mass to places p₀ alone almost never visits. It is importance sampling, steered by the map.
- So "drop on a random point" becomes: **draw a coordinate (uniformly over untried regions, or from the model's
  posterior), decode it with the LLM, read the result back, then climb.**

### 4.4 The space grows: how to discover the axes and search them at the same time

This has a clean statistical form:
- A new axis or value enters the model with a prior mean of zero effect and **large uncertainty**.
- Thompson sampling (draw a model from the posterior, aim at the best point under it) then explores new axes and
  values automatically, because uncertain terms are sometimes drawn high. Discovery and search are the same loop:
  **optimism under uncertainty applied to a growing set of variables.**
- **When to add an axis:** when the model can't explain what it sees. Two programs with the same coordinates and very
  different heights, or a big gain from a move the codebook can't describe, means an unmeasured decision exists. Ask
  "what differs between these two?" and add the answer. This is how statisticians find a missing variable: look at
  the residuals.
- **When to drop or merge:** an axis whose effect stays near zero with low uncertainty stops being drawn (RegNet's
  progressive simplification); two axes that always move together are one.

### 4.5 Climbing as a rising bandit

Each dropped point is an arm whose reward rises with effort, at an unknown rate, to an unknown ceiling. Section 2.2
says early rewards are poor predictors. The standard answer is successive halving with a reference curve: give every
new hill a small budget, extend those whose curve is at or above the reference curve **at the same effort**, and
compare to the record's curve as it was when it was that young, not to its current height.

### 4.6 What is general and what is problem-specific

- **General:** the procedure (codebook, annotation, model, drops, race, ablations) and a short list of **generic
  meta-axes** that every program-improvement problem has some version of: the representation of a solution; what is
  actually optimised (the true objective or a proxy); how a first solution is built; which local moves are used;
  how worse moves are accepted or escaped; how scale is handled (coarse-to-fine, decomposition); exact sub-solvers;
  how time is split; data structures and speed.
- **Problem-specific:** the values on each axis, the sub-axes, and the behaviour signature. The VRP's shared
  decisions in v7 (the starting construction, the route pool, trip structure, truck counts, an exact neighbourhood)
  and the autocorrelation axes in 2.1 are both instances of the generic list.
- **Transfer:** across problems, a record of *which meta-axis was the lever* (the VRP's start; the autocorrelation
  problem's objective handling) becomes a prior for the next problem. That is how the system gets better at
  improving *any* problem, in DreamCoder's sense of a growing library.

---

## 5. The questions from the discussion, one by one

1. **What is a direction?** An axis: a design question. A direction along it is a change of value.
2. **What is a point?** A value on every axis: a design. A program implements it; its height is what programs there
   reach after climbing.
3. **Mutation finds new axes; we also want jumps.** Yes. Both are needed, and they are different moves: axis
   discovery grows the map; a drop changes 2-3 coordinates at once to land elsewhere on it.
4. **Is the number of features fixed?** At the top level, roughly: about 9 axes cover 98% of what v8's Cartographer
   named over 400 generations. Below that, no: values keep being invented, and axes split into sub-axes. "Primary
   colours at the top, an open palette underneath" is the honest answer.
5. **Can a feature become a literal axis?** Yes, as a categorical one: an axis is a question, its values are named
   answers, and a program's position is read by an annotator. The numbers inside a value (temperatures, time splits)
   are better tuned by the program itself, as before. If a truly continuous axis is ever wanted, the latent-space
   route (embed designs, search the embedding) exists, but code similarity correlates poorly with performance, so
   I'd start categorical.
6. **Are features discrete?** Mostly, yes, which makes life easier, as the discussion guessed.
7. **How do we combine values into a coordinate and jump there?** By a blueprint the coder must follow, then reading
   the program back to check where it landed. Section 2.4 shows why the reading back is not optional.
8. **What are the limits of the box?** Feasibility (programs that run within the time and memory and produce a valid
   answer), the cross-consistency of values (pairs that can't coexist, Zwicky's pruning), and for the score, known
   bounds (1.0 is the absolute ceiling on the autocorrelation problem; an LP relaxation would bound the VRP).
9. **Cap at 27 features, expand if needed?** That is progressive design-space search, and it is sound with one
   change: always keep a small share of drops for new axes and values, because the axis you capped away may be where
   the hill is (the "addition versus swapping" worry is exactly this). In the model, the share is automatic: new
   values carry high uncertainty.
10. **Problem-specific or general?** Section 4.6: the procedure and the meta-axes are general; values and signatures
    are per problem; which axis was the lever transfers as a prior.
11. **Discover dimensions and search them at once?** Section 4.4: one Bayesian loop, with residual-driven discovery.

---

## 6. What to build: v9 = v8 + a design map

Everything in v8 stays (`docs/V8_DESIGN.md`): the hill register and behaviour signatures, v7's levels, the main
track's slot, tracks never closed, the wide loop, the Atlas. v9 adds seven parts.

### 6.1 A codebook with stable identities (`design_map.json`)

- Axes and values, each with a **permanent id given at birth** (NEAT's historical marking), a one-line definition, a
  parent axis if it is a sub-axis, and the generation it was born.
- **Seeded** from the generic meta-axes (4.6) and the Cartographer's first scan. The seeds are questions only, with
  no values, and are audited against the standing rule that prompts carry no hints from earlier traces
  (`docs/REQUESTS.md`); the values come from each run's own programs.
- **Grown, never renumbered:** later scans are *matched* against the codebook. A decision that matches an existing
  axis adds nothing (or a new value); a new one gets a new id. Merges are recorded as aliases.
- **Incompatible pairs** are recorded when a blueprint proves impossible (cross-consistency).

### 6.2 An annotator (the encoder)

- **One cheap model call per new valid program**, given the parent's coordinate and the diff: "which axes did this
  change, and to which values (existing, or new: name it)?". A child's coordinate is its parent's plus the changes.
- **Reliability:** a sample is annotated twice, independently; agreement per axis is reported. An axis that can't be
  annotated consistently is flagged, not used for drops.
- **Behaviour stays the referee** of whether a program is new (v8's signatures).

### 6.3 A model of the landscape

- A Bayesian linear model on one-hot coordinates with main effects and selected pairwise terms, with shrinkage
  (BOCS-style). numpy only; it fits in milliseconds.
- **Target:** each program's score as a gain over its base, plus each track's best at matched effort, so it models
  potential rather than polish.
- **Outputs, every generation:** each axis's importance (fANOVA), each value's effect with an uncertainty, the
  strongest interactions, the largest residuals, and samples of where the tallest untried point might be.
- **The planner sees it as a compact table:** "what helps, what hurts, what is untried" (your note's ask, made a
  standing view).

### 6.4 Drops (replacing restart)

- **Choose a target coordinate** by Thompson sampling from the model, restricted to points at least 2 axes (and at
  most about 4) from every known hill's top, and preferring untried values.
- **The coder gets a blueprint:** the target values on those axes, and, everywhere else, the record's values and its
  chain of improvements where they fit (v8's restart idea, kept).
- **Read it back.** If the targeted axes didn't land, retry once naming the mismatch; otherwise record it as a drop
  that landed elsewhere (still data for the model).

### 6.5 A fair race (replacing the 2-follow-up pause for drops and flips)

- **Rungs of effort:** 2, 4, 8, 16 experiments.
- **Promotion rule:** a hill moves to the next rung if its best at that effort is at or above the **reference
  curve**: the best of the run's earlier hills at the same effort since their foundation, starting with the
  record's own early curve.
- At most a few hills per rung; the rest pause (never closed, as in v7), and can be woken by the wide loop or the
  model.
- This uses the existing track machinery: it changes only when a track pauses.

### 6.6 Axis discovery triggers

- **Residuals:** the same coordinates with very different heights, or a big gain unexplained by its coordinate
  change, prompts a call: "what differs between these programs?". The answer becomes a new axis or value.
- **The Cartographer's scan,** merged into the codebook instead of replacing it.
- **Mutations that gain a lot** are annotated with priority.

### 6.7 Ablations on the record ("what is helping")

- Every few generations, one experiment reverts one of the record's values (on one axis) to an earlier value and
  measures the drop. The record's height gets attributed to its decisions, measured rather than guessed.
- The ablations double as the model's ground truth.

### 6.8 How it plugs into the code

| File | What |
|---|---|
| `helix9/codebook.py` | the axes and values, ids, matching, aliases, incompatible pairs |
| `helix9/annotate.py` | the annotator prompt, diff-based coordinates, double annotation |
| `helix9/model.py` | the sparse Bayesian model, fANOVA importances, Thompson samples |
| `helix9/race.py` | rungs, reference curves, promotion |
| `helix9/run.py` | subclasses `helix8.run.Run`: the drop slot, the race, the triggers, ablations |
| `helix9/prompts.py` | the drop blueprint, the map table in the planner's view |
| `helix9/report.py` | v8's report plus the map: axes, values, effects, races |

**Cost per generation:** the same 3 planned experiments and 3 mutations. Added: one cheap annotation call per new
program (a small prompt: parent coordinate plus diff), an occasional discovery call, and a model fit in
milliseconds.

**Why it should strictly improve on v8:**
- while the record climbs (level 0), a generation is v8's plus a read-only table;
- the budget that moves is v8's restarts (median best 0.82) and its 2-follow-up pauses;
- annotation is metadata; it can't break a program.

---

## 7. Trust before scale: a proof-of-concept ladder

Your note asks for a single unit we can trust and know is good before scaling. Three rungs, cheapest first, each
with a pass criterion decided before it runs.

### Stage 0: an offline replay on what v8 already has (no runs, a few hours of model calls)

1. Build a codebook from v8's 82 scans (canonicalise the 656 names).
2. Annotate a sample of v8's 3,625 programs, twice. **Pass:** agreement of at least 0.8 on most axes.
3. Fit the model on programs before generation G and predict the gains after it. **Pass:** better than predicting
   "no gain" or the parent's score.
4. Ask the model what helped and what hurt on the record's hill, and check that against the ablation-like evidence
   in the traces (the faithful flips of 2.4, for instance).
5. On the VRP archive (on the VM, private): does the map flag the starting construction as an untried, uncertain
   axis before generation 57, where T40 found it by chance?

If the annotation isn't reliable, or the model predicts nothing, v9's map is not worth building, and we know it for
the price of some model calls.

### Stage 1: a planted landscape with a known best (no model, seconds per run)

- A simulator where "programs" are coordinates on a planted NK-style landscape: a few main effects, a few pairwise
  interactions, a **deceptive default basin** that a simulated LLM prior prefers (like the 0.8825 trap), a taller
  hill 3 coordinated changes away, a **noisy decoder** (asked for a coordinate, it lands elsewhere with some
  probability), and climbing curves that rise slowly and differently per hill.
- Run v8's policy (restarts from the prior, flips, 2-follow-up pauses) and v9's (drops, read-back, race), each part
  on and off, over hundreds of seeds.
- **Pass:** v9 finds the planted hill much more often at the same budget, and the ablations say which part does it.
- It is a model of our situation, not our situation; its value is that it tests the logic where the truth is known,
  and shows which part helps and which hurts, cheaply.

### Stage 2: a small live run (the VM, gently)

- The autocorrelation problem from Code Zero, 40 generations: v8 against v9 against a simple baseline (sequential
  conditioned sampling, as in the "simple baselines" paper), with the same model, prompts and CPU.
- **Measures:** distinct hills reached, the best non-record hill at equal effort, the final best, cost.
- One seed each is what the VM allows; section 2.2 says single runs are noisy, so this tests behaviour (do drops
  land, do races promote) more than it ranks versions.

### Stage 3: scale

The VRP (on the VM), then the private problems (with their train/validation/test splits), then longer runs.

---

## 8. Persistence, an evolutionary agent, and RL

### The loop is enforced persistence

- METR's long-task study (2025): frontier models then completed about half of tasks that take people around two
  hours; the horizon doubles about every seven months; at 80% reliability it is 4-6 times shorter. The failures they
  describe are *repeating failed actions* (older models) and *giving up early* (newer ones).
- Helix fixes both by construction: the ledger means failures aren't repeated blindly, and the loop doesn't let the
  model stop. The v4 analysis measured the second one directly: the planner called the plateau "saturated" in 95% of
  its late analyses, and later versions, with the same model, went on to set records on the same problem.
- The same pattern is behind AIDE (a tree of solutions kept outside the prompt), the Darwin Gödel Machine (an
  archive of agents) and FunSearch. So the insight holds: put an agent at the front of the pipeline and in charge of
  managing it, and you have a persistent agent.

### Turning it into an agent for open-ended tasks

- **The evaluator is the whole question.** Evolution amplifies whatever the scorer rewards:
  - a private run on another problem rose steadily on its training years while its held-out result fell below the program
    it started from;
  - the VRP evaluator's short time caps rewarded fast convergence over final quality;
  - QDAIF's LLM judge became unreliable at the top of its quality range;
  - the "simple baselines" paper found noisy evaluation choosing lucky candidates.
- So the agent's first job is **building a trustworthy problem**: evaluator, data splits, held-out checks, a noise
  floor, a baseline, leakage checks. That is the step done by hand today (with the problem packages and Aether).
- **A concrete next step:** a "problem builder" agent with that checklist. It is buildable, and it is what makes
  "any open-ended task" possible.
- For tasks without a scorer (writing, strategy), an LLM judge can stand in, but only with held-out judges and human
  spot checks, because the loop will optimise the judge's blind spots.

### RL and fine-tuning for persistence

- **It works on exactly this kind of problem.** TTT-Discover trains the model with RL during a single problem and
  reached 0.959 on the second autocorrelation inequality (gpt-oss-120b) and 0.947 even with an 8B model, both above
  Helix. It costs about $500 a problem on rented GPUs.
- SEAL (a model that writes its own fine-tuning data) shows continual learning by self-edits is possible, and also
  its costs: forgetting earlier tasks, and 30-45 seconds per edit to score.
- **On the VM, no.** It has no GPU. But every Helix trace is training data: (context, program, score) triples by the
  thousand. If GPU budget appears, a LoRA fine-tune of an open model on Helix traces, or test-time RL within a run,
  is the natural v10.
- **The map is the cheap persistence now:** knowledge that survives across generations, runs and problems, in files,
  readable by any model.

---

## 9. How confident I am, and what I recommend

| Part | Confidence | Why |
|---|---|---|
| The fair race (6.5) | **high** | 2.2 and 2.3 measure the problem; the fix is standard and cheap; it only changes when tracks pause |
| A stable codebook (6.1) | **high** | 2.1 measures the instability; the fix is bookkeeping |
| The offline replay (stage 0) | **high** | no runs, and it answers the riskiest question first |
| Annotation reliability (6.2) | medium | LLMs label code decisions well in my experience, but 2.4 shows they also blur them |
| The model's usefulness (6.3) | medium | effect sparsity usually holds; on the autocorrelation problem, implementation quality within a design may dominate |
| Drops finding a taller hill (6.4) | uncertain | taller hills exist (2.5); whether 2-3 coordinated changes reach them is what stage 1 and 2 test |
| RL for persistence | right idea, wrong hardware now | 8 |

**What I recommend:** stage 0 first, then build v9 in two steps:
1. **v9a** = v8 + codebook + annotator + race + the map table (the high-confidence parts), with stage 1's simulator
   built alongside;
2. **v9b** = + model-driven drops, discovery triggers and ablations, once stage 0 says the map is real.

The alternatives are building all of v9 now (faster, but untested parts go to the VM together) or stopping at this
plan.

---

## Sources

- [First return, then explore (Go-Explore)](https://arxiv.org/pdf/2004.12919)
- [Scalable Global Optimization via Local Bayesian Optimization (TuRBO)](https://ar5iv.labs.arxiv.org/html/1910.01739)
- [Bayesian Optimization of Combinatorial Structures (BOCS)](https://arxiv.org/pdf/1806.08838)
- [Designing Network Design Spaces (RegNet)](https://arxiv.org/pdf/2003.13678)
- [Automatically designing state-of-the-art multi-objective evolutionary algorithms (AutoMOEA)](https://www.human-competitive.org/sites/default/files/bezerra-lopezibanez-stutzle-paper.pdf)
- [Morphological analysis (Zwicky box)](https://en.wikipedia.org/wiki/Morphological_analysis_(problem-solving))
- [An Efficient Approach for Assessing Hyperparameter Importance (fANOVA)](https://proceedings.mlr.press/v32/hutter14.html)
- [Additive Gaussian Processes](https://arxiv.org/pdf/1112.4394)
- [Local optima networks of neutral landscapes](https://www.arxiv.org/abs/1107.4162)
- [Wagner, Robustness and evolvability](https://www.ieu.uzh.ch/wagner/papers/Wagner_PRS08.pdf)
- [Automatic chemical design using a data-driven continuous representation of molecules](https://arxiv.org/pdf/1610.02415v3)
- [Quality-Diversity through AI Feedback (QDAIF)](https://arxiv.org/pdf/2310.13032)
- [Autonomous skill discovery with Quality-Diversity and Unsupervised Descriptors (AURORA)](https://arxiv.org/pdf/1905.11874)
- [AutoQD: Automatic Discovery of Diverse Behaviors with Quality-Diversity Optimization](https://arxiv.org/html/2506.05634)
- [Fitness Landscape of Large Language Model-Assisted Automated Algorithm Search](https://pith.science/paper/2504.19636)
- [Competitive Coevolution through Evolutionary Complexification (NEAT)](https://arxiv.org/pdf/1107.0037)
- [DreamCoder](https://arxiv.org/pdf/2006.08381)
- [Darwin Gödel Machine](https://arxiv.org/html/2505.22954v3)
- [In-Context Freeze-Thaw Bayesian Optimization](https://arxiv.org/pdf/2404.16795)
- [Efficient Automatic CASH via Rising Bandits](https://arxiv.org/pdf/2012.04371)
- [Monte Carlo Tree Search for LLM-Based Automatic Heuristic Design (MCTS-AHD)](https://arxiv.org/pdf/2501.08603)
- [SMCEvolve: Principled Scientific Discovery via Sequential Monte Carlo Evolution](https://arxiv.org/pdf/2605.15308)
- [Simple Baselines are Competitive with Code Evolution](https://arxiv.org/pdf/2602.16805)
- [Understanding the Importance of Evolutionary Search in Automated Heuristic Design with LLMs](https://arxiv.org/pdf/2407.10873)
- [ShinkaEvolve](https://arxiv.org/html/2509.19349v1)
- [ImprovEvolve](https://arxiv.org/html/2602.10233)
- [Learning to Discover at Test Time (TTT-Discover)](https://arxiv.org/pdf/2601.16175)
- [Measuring AI Ability to Complete Long Software Tasks (METR)](https://arxiv.org/html/2503.14499v3)
- [Self-Adapting Language Models (SEAL)](https://alphaxiv.org/abs/2506.10943)
- [AIDE: AI-Driven Exploration in the Space of Code](https://arxiv.org/html/2502.13138v1)
