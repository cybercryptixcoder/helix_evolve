# Ideas to explore (not built)

Ideas for where Helix goes next. Each says what it is, why it might work, and how it could fail. Newest first. The
newest section (October 27-28) also marks each item as decided, leaning, open or an idea.

---

## October 27-28, 2026 (night): ideas, directions, research questions and open decisions


Everything worth exploring from the conversation of October 27-28. Most items are
**open**: things to think about, not decisions. Each says where it came from and what is known so far. The full
conversation of October 27-28 (verbatim) is `docs/CONVERSATION_2026-10-28.md`; the evidence is in
`docs/V9_RESULTS.md`, `docs/RESEARCH_CASE.md` and `docs/SEARCH_SPACE_MODEL.md`.

**Status words:** *decided* (agreed), *leaning* (Shreyas's stated preference, not final), *open* (to think about),
*idea* (raised once, not discussed further).

---

### 1. What we are building, and what "discovery" means here

#### 1.1 The goal, in Shreyas's words (*decided*)

> "The objective with what we're trying to build is simply to build something that is amazing at searching for a good
> solution [...] What we want to do is get to really, really good solutions, which are a little more rare to find in
> the search space. What we need to be able to do is be really good at exploring that."

Good solutions come quickly either way; the system's worth is in reaching the rare, really good ones.

#### 1.2 Discovery system or search system? (*open*)

- **Shreyas's worry:** borrowing axes from other people's work turns a discovery system into "a search system that
  searches through discovered axes"; the brilliant ideas come from people, the system finds "the best version" of
  them. Perhaps human-AI collaboration is what brilliant discovery takes, and perhaps that's even good.
- **Counterpoints raised:** every human discoverer starts from others' ideas; what makes a discovery is an output
  nobody had, not empty inputs. Helix has already discovered on its own: the routing breakthrough came from noticing
  that every program shared the greedy start and replacing it (nobody supplied it); v9 found 23 decisions itself;
  the autocorrelation result came from scratch. Discovery has levels (Boden): combining ideas, exploring a framing,
  transforming the framing. Helix does the first two well and the third occasionally.
- **A middle ground:** two channels side by side: borrowed axes (collaboration with the world's knowledge) and the
  system's own axis discovery (the invariant audit, section 3). Report both.

#### 1.3 Is discovery independent of the model's intelligence? (*open; a research question*)

- **Shreyas's working hypothesis:** beyond a threshold, a discovery system is largely agnostic to model intelligence:
  "A smarter model would discover something quicker while a dumber model would take longer for the same."
- **The refinement discussed:** each idea has its own threshold. For ideas the weaker model can reach, time stands in
  for intelligence. Ideas the model almost never writes (one in a billion) are out of reach in practice whatever the
  budget. Evidence: RL stays inside the base model's reach (Yue et al., NeurIPS 2025); GigaEvo progressed only after a
  model swap; TTT-Discover reached 0.947 with an 8B model and 0.959 with 120B; AlphaEvolve's cheap models added variety
  but couldn't finish the hardest construction; all 19 of our fresh restarts fell into the same basin.
- **The architecture moves the boundary:** asking for coordinates the model would never choose, or for a change to
  what every program shares, turns a one-in-a-billion idea into a one-in-a-thousand one. Shreyas expects it can move it
  "even more so than one would expect if done right".
- **The experiment (idea):** the same Helix with cheap, mid and frontier models (Fable 5.1 or Opus 5.5 for short runs);
  plot height against budget. Same-shape curves shifted in time support the hypothesis; different plateaus refute it;
  if the map narrows the gap between models, structure is substituting for intelligence.

#### 1.4 The model as a compiler: ideas from outside, search over their combinations (*leaning*)

- **Shreyas's proposal:** axes come from outside (a one-time deep research pass per problem: every existing approach);
  combinations of approaches are ideas; the search forces the model through that space mechanically. The model only
  turns a described point into code; "If, let's say, the code somehow already existed for each of these different
  points [...] we wouldn't need the LLM at all." The only intelligence threshold is turning a description into code
  "reliably and predictably"; past it, results are a matter of time.
- **Where the assumption is weaker than it looks (from our data):**
  - a point doesn't determine its code or its score: many implementations per point, and on the autocorrelation
    problem most of the record hill's late progress was within-point polish; a 2026 study found tuning only the
    constants of mid-run programs matched the run's final best in 13 of 15 cases;
  - building a new combination isn't mechanical: in v9 only 42% of requested decision values landed (21 of 74
    blueprints fully), and combinations nobody wrote before are the hardest.
- **An implication (not a design):** make the model's role truly mechanical: it writes a point's code once, a classical
  optimiser tunes the numbers, the map searches the points. Then model skill enters only through measurable fidelity
  (did it build the point asked for?) and quality (how high does that point's code climb?).
- **The defensible claim:** "Given a fixed space of ideas, a model's capability affects discovery mainly through
  implementation fidelity and speed. Above a fidelity threshold, budget closes the gap between weaker and stronger
  models." Falsifiable: stronger models plateauing higher on the same axes would refute it.
- **Closest ancestors to address:** automated algorithm design from components (SATenstein 2009; irace; AutoMOEA,
  "the configuration space is actually a design space"). The novelty is what the language model adds: no pre-written
  components (ideas described in text, implemented on demand), axes harvested automatically from the literature, and
  combinations nobody has implemented become runnable. "LLMs turn algorithm configuration from a closed library into
  an open space defined in text."

---

### 2. Searching the map: drop wide, climb, repeat

#### 2.1 Shreyas's search scheme (*leaning; v10 is his to design*)

> "Beyond a certain point, if you have scored really well, we need to be able to go extremely wide. On the map, this
> would look like dropping a whole bunch of points on a whole bunch of different spots, which are completely different
> from each other. [...] Then we allow our search to climb to basically find the top of the hill for each of those
> points. [...] we basically just keep the best hills. [...] Then we run the thing again."

- Rounds: drop many far-apart points, climb each, keep the best hills, drop again.
- **"A little cleverer than random":** the first round random; later rounds take "a pseudo-random, calculated, very
  large step away" so new points never land within the explored radius of earlier ones and never climb the same hills.

#### 2.2 What is known that bears on it (*open*)

- **It is a well-founded idea with classical names:** multistart with clustering (multi-level single linkage: don't
  start a climb near a point already explored), farthest-point and low-discrepancy sampling (spread the points),
  Go-Explore, novelty search, island restarts with elitism.
- **Climbing is the expensive part.** In Helix a climb is many model generations; the record's hill took hundreds; v8's
  best restarts reached about 0.91 in 8-12 experiments. Twenty drops climbed properly could cost thousands of
  programs. Faster climbing may mean moving climbing into CPU-side optimisation inside each program.
- **"Far on the map" is not "a different hill".** Different coordinates often climb to the same height (8 hills tie at
  0.94144). The exclusion radius may belong on where a point ends up (its construction or behaviour), not only where
  it starts.
- **Far random points are the hardest to build** (42% of requested values landed even for near jumps): a read-back
  check is needed so a point is where it was asked to be.
- **The map may not contain the taller hills** (section 3): dropping widely within today's axes may only find more
  0.94144-level hills.

#### 2.3 Rejecting hills quickly; "shoot to the top quickly and move on" (*open*)

- A run's best after 20 programs had no rank correlation with its final best (-0.09); after 40, a moderate one (0.50).
  v9 effectively rejected new hills after one experiment, and found nothing. Judging the first score is the failure
  mode to avoid.
- Options to weigh: a fixed small climbing budget for every point, then cut (successive halving with an honest
  reference curve); estimating a hill's top from its climbing curve (rising bandits); predicting height from the map
  before spending; making the climb itself cheaper.

#### 2.4 The three agreed steps for the map (*decided as the plan from the October 27 discussion*)

1. **Is the number of axes fixed?** Roughly at the top level (about 9 recurring decisions cover 98% of names; v9's map
   held 12-18); not underneath (options keep growing; 188 regroupings in 100 generations).
2. **Quantify each axis.** Categorical options read off the code: reading is reliable (12 of 13 decisions at 80%+
   agreement); writing is not (42% of requested values landed).
3. **Random values on each axis make random points; many points; explore from each.** v9's drops changed only 2-4
   decisions of the record and were never climbed, so this has not been tested yet.

---

### 3. Finding the axes

#### 3.1 The worry: the map may not contain the taller hills (*Shreyas's priority*)

> "The first and most important thing that I notice here is that the map may not contain the taller hills and that
> means that there is another axis or other axes that we haven't tapped into."

Evidence: 8 distinct hills top out within 3e-7 of 0.94144; higher results (0.951-0.9626) used different
representations; every Helix hill shares a uniform grid of heights polished by a gradient optimiser, which is not an
axis on the map.

#### 3.2 Axis discovery first, then the loop, in series (*leaning*)

Shreyas's proposal: "The first would be to find all the axes and then run the evolutionary loop." Discussed: a
dedicated phase finds most axes; but some only appear once the search reaches a region (decisions that exist only
under another, like a cooling schedule under annealing), so the loop keeps cheap alarms running and reopens discovery
when one fires.

#### 3.3 Can the axes be found provably or definitively? (*open*)

Not for an open-ended program space: an axis is a decision someone has noticed, and any finite list is a coordinate
system we chose. What is achievable:

1. **Completeness by construction at the top level:** every program must represent a solution, build a first one,
   define what it optimises, search, split its time and return a result. These stages are guaranteed axes; their
   options close only if we close them (with the risk of closing out the taller hills).
2. **Axes from the problem's mathematics,** not only from our programs (which can only show what our programs do).
   For the autocorrelation problem: the function class (uniform steps, free widths, smooth bumps, spikes), how the max
   is handled, symmetry, scale (50 to 1,000,000 steps), the start (scratch or known constructions).
3. **Read outside solutions onto the map:** how do the 0.951-0.9626 results differ from ours? A difference the map
   can't describe names a missing axis.
4. **Saturation, so confidence is a number:** keep sampling diverse programs and descriptions; when new axes stop
   appearing, estimate the chance the next sample shows one (rarefaction, Chao1, Good-Turing).
5. **Two alarms:** residuals (same coordinates, very different heights: an unmeasured decision exists) and the
   invariant audit (decisions every program makes the same way, invisible to residuals).

#### 3.4 The repeated invariant audit (*implemented in v10.1, `helix10/audit.py`; Shreyas's idea*)

> "Do you think it's possible to run a loop where you ask, 'What does every programme do in the same way?' over and
> over until there is nothing uniformly common between all of the programmes?"

- It works as a principled version of a known heuristic (Kaplan and Simon: people escape a wrong framing by noticing
  invariants), but it never runs dry by itself: all programs always share something (Python, arrays, floating point).
- **Sort each answer:** (1) a constraint of the problem (not an axis); (2) below the level we care about; (3) varyable
  but irrelevant (drop after one test); (4) a real frozen axis (the target). Stop when every answer is 1, 2 or 3.
- **"Splitting":** each invariant found needs alternative values actually built, or the loop keeps reporting it; then
  ask again within each group, which builds the hierarchy of axes and sub-axes.
- **Its partner:** "how do these programs differ?" finds the axes already varying; differences plus invariants cover
  every decision present in the programs.
- **The ceiling is the describer:** a model reports only invariants it has words for. Push it with several describers,
  outside material, and the residual test. The honest claim: "complete with respect to what these describers can
  articulate, with a measured discovery rate approaching zero."
- **A cheap first test (offered, not run):** one round of the audit on v9's 77 hills, a few model calls, no runs.

---

### 4. Warm starts and borrowed knowledge

#### 4.1 What the field does (*researched October 28*)

- **To claim a new world record (a discovery):** anything goes if disclosed, including the world's best solution, its
  code, or hints from papers. AlphaEvolve's maths results leaned on expert hints, known constructions and shown code
  (Georgiev, Gómez-Serrano, Tao, Wagner); ImprovEvolve's record 0.96258 started from AlphaEvolve's solution (labelled
  "+E"); systems research with OpenEvolve starts from the published best algorithm by default.
- **To claim a search method is better:** start from scratch or from simple programs, with the same knowledge as the
  comparison (TTT-Discover's maths runs; ThetaEvolve's main runs; Simple Baselines warns that knowledge in prompts
  inflates apparent efficiency).
- **Reporting:** two columns, warm-started results labelled.
- Starting from the best known construction gave "only slight gains" (ThetaEvolve) and is "too strong a prior towards
  exploitation" (TTT-Discover).

#### 4.2 Three levels of borrowing (*leaning: level 3*)

1. Their construction as our start: pure exploitation; a gain counts only as a discovery claim.
2. Their method or code: legitimate if disclosed.
3. **Only their idea, as a new axis on our map:** "probably what we would end up working with next. Also hopefully
   that's what helps us get past the record." They found a direction and stopped; we quantify it, try its other
   options, combine it with our other axes. Report as building on published knowledge; give baselines the same
   knowledge.

#### 4.3 Standing rule to reconcile (*open*)

The earlier standing rule says "No warm starts (a warm start only counts if the gain on top of it is very
significant)". Borrowing ideas as axes, reported in a separate column, is compatible with it; borrowing constructions
is not. Worth restating the rule explicitly.

---

### 5. Research questions and the paper (`docs/RESEARCH_CASE.md`)

#### 5.1 The question and principle (*proposed to the advisor*)

- **Question:** can a discovery system map the space it searches, steer to where its model would not go, and change
  that space when it runs dry?
- **Principle:** make the design space explicit, move in it on purpose, change it when it is exhausted.
- **Three ways past a model's prior:** re-weight (selection), retrain (weights), re-represent (condition the prompt on
  an explicit map). Helix is the third, without training.

#### 5.2 Research questions (*open*)

- **RQ1:** where do LLM-guided searches go, and why do they stall? (priors and trajectories read onto the map,
  including EvoTrace's 121 public runs)
- **RQ2:** can a search map its own space and steer by it? (validity; matched budget against simple, framework and
  generic-diversity baselines)
- **RQ3:** can it change its own space, and do breakthroughs come from that? (invariants, as in insight by constraint
  relaxation; plateau timing; replays)
- **New from tonight:** is discovery agnostic to model intelligence above an implementation threshold? (section 1.3)
- **New from tonight:** with borrowed axes, does search over their combinations beat the ideas' own authors? (1.4)
- **Earlier:** do LLM-guided searches "grok" (hidden progress during plateaus)? (`docs/RESEARCH_PLATEAUS.md`)

#### 5.3 Paper shape and venue (*open; decisions for the advisor*)

- A concept paper (diagnosis, principle, method, broad evidence) held to a method paper's evidence standard, records
  as showcase. Working titles in `docs/RESEARCH_CASE.md`.
- Two columns: from scratch (method credit) and with published axes (discovery with the world's knowledge).
- To decide: the claim to commit to; venue (NeurIPS 2027 target; ICML 2027 only if December pilots are strong);
  compute (about 2,500 CPU-hours and $2,000-5,000 of model calls, estimates); rigour (fix predictions first; a second
  rater); whether the real-data routing case can be reported.

---

### 6. Lessons from v9 to carry into v10 (*facts; the remedies are open*)

From `docs/V9_RESULTS.md`:

- The record moved 2.5e-13 in 100 generations; v8 was already flat.
- About 70% of experiments worked on the record's own hill; 4.7 of 6 programs a generation handed back their start.
- The race was captured by flips and ablations that tied the record on its own hill; 49 new explorations got one
  experiment each; nothing new was climbed.
- Drops near the record landed at 0.58-0.85 (strong interactions), and 10 of 18 never produced a valid program.
- The map's model: one interaction (imposed global structure x parametrisation of heights) explains 61%.
- The map's calls cost about 21% of tokens; the map is rewritten every generation as the model rewords options.

### 7. Infrastructure notes (*done or pending*)

- **Done:** constructions are judged by the run's own step limit (298 had been left out of GitHub); releases chain to
  their base releases and restore the whole chain.
- **Pending (Shreyas, via Aether):** one upload of the 298 missing constructions (`docs/V9_RESULTS.md`).

### 8. Other threads from earlier, still open

- **Persistence and an evolutionary agent:** the loop as enforced persistence; an agent that first builds a trustworthy
  evaluator for a new task (a "problem builder"); RL or fine-tuning for continual learning (`docs/SEARCH_SPACE_MODEL.md`
  section 8).
- **Training from the map:** does fine-tuning a model on map-guided search widen its own reach? (connects to Yue et
  al.'s finding that distillation from outside the prior widens a model).
- **Transfer across problems:** which decision was the lever on one problem as a prior for the next.
- **Explainable discovery:** the map says which decisions made a construction good; mathematicians want this.
- **The VRP lesson:** the evaluator's short time caps biased evolution toward fast convergence over final quality;
  rethink scoring (quality ceiling against speed).
- **Goal definition first, a separate evaluator agent that turns a spec into tests, and quantifying UI quality**
  (raised October 27; answered in conversation, not documented in detail).

---


## The next build: Helix as a researcher (October 20, 2026, late; the discussion that followed the idea below)

Agreed as the direction for the next version, to be built after the v4 overnight results are analysed. It
combines the scheduling idea below with what came out of the discussion about memory, retrieval and continuity.

### The goal
Make the search behave like one human researcher working on a problem for weeks, not a fresh hire every round. Every
run of an experiment is **intentional**: it belongs to a purpose on an agenda, with a stated reason and a stated
"if this, then that". No blind arrows in the dark.

### What the researcher holds (always in context, small)
1. **The theory of the problem**: a handful of beliefs about what governs the score, each with a confidence and
   pointers to the experiments behind it. Code checks the pointers are real and computes whether the numbers
   support each belief (as Atlas does now).
2. **The agenda**: the purposes it is pursuing. Each item says what it wants to find out, why, what it is waiting on,
   and what it will do depending on the answer ("if A gains, B; if not, C").
3. **Where it is**: its position on the agenda: the current item and the step within it.

### Everything has a timeline, not just a state
The theory, the agenda and the notebook of reasoning steps are each a **timeline with branches** (a tree of
versions), not a single current state. The context shows the current state; every earlier version and every other
branch stays reachable, so the agent can go and look at what it believed, or planned, at any point and why it
changed. Nothing is overwritten, only superseded.

### No drift: edits, not rewrites
Drift comes from regenerating text (compaction rewrites and loses things). So the theory and the agenda are never
regenerated: they change through explicit operations (add, revise, mark done, drop, branch), each with its reason
("revised step 3 because experiment 41 showed …"). Anything untouched stays word for word. Finished items collapse to
a one-line outcome with a pointer to the full record: small, and still lossless.

### Continuity is constructed, not a fixed window
The continuity for step n+1 isn't "the last k steps". It's **the specific earlier steps this one actually depends
on** (say steps 2, 6 and 7): the step that set up the plan item it is working on, the steps whose results it is
acting on, the step where the belief it is testing was last revised. Every step records which earlier steps it
follows from, and every agenda item records the steps that created and advanced it, so code can follow these links
and assemble the continuity deterministically. The model can add a link ("this connects to step 4") but continuity
never depends on a search succeeding. This is the "jump back on the timeline" idea: resuming a thread means being
placed back at the steps that matter to it, with the new results attached.

### Then retrieval, for what step n+1 specifically needs
With the theory, the agenda, the position and the constructed continuity in hand, the agent knows what it is
missing, so retrieval becomes **explicit questions** it asks ("has anything like this been tried?", "what did the
best program on branch B do differently?"), answered from an index of experiments organised by what each changed and
which belief it tested. The current agenda item usually names what to fetch already. This is the answer to "how do
you know which books to fetch without knowing every book": the plan is the catalogue.

### One step of the researcher
Resume (code picks the item whose results arrived, or an interrupt) → read theory, agenda, position, constructed
continuity and the new results → ask any explicit questions → decide: conclude (revise the theory), continue
(schedule the next experiment), branch (fork the item), park, or abandon (with the reason) → edit the agenda and the
theory by operations → leave a note at the tip of the thread. Coders implement the scheduled experiments; the
evaluator runs them; code wakes the item when they finish.

### Code owns the chronology
Scheduling, waiting, which item resumes next, the jump back, and the context assembly are all code. The model
decides; it is not trusted to remember to come back. Two rhythms on top: **interrupts** (a big surprise anywhere,
such as another branch jumping ahead, wakes the researcher out of turn) and the **step back** (every so often, a
review of the whole agenda and theory: prune, merge, re-prioritise, link threads deliberately).

### What stays from v4
Whole programs, a population tree, code-computed feedback, evidence checked by code, the memoryless wide loop running
alongside as a guard against tunnelling.

### How it would be tested
As a new condition against Atlas (and the control), same problem, same compute, compared by programs evaluated or
compute spent rather than by generation (the run becomes event-driven). Measures: whether follow-up experiments on an
agenda item gain more often than fresh ideas; whether items resolve rather than being forgotten; how often plans are
revised and whether revisions follow evidence; the final score.

### Open question
Should each belief be a separate item edited one at a time (safe, but risks becoming a pile of facts), or should the
theory also have a short paragraph the agent rewrites at each step back (coherent, but rewriting can drop things)?
Leaning: separate beliefs, plus a versioned summary paragraph at step backs.

---

## The researcher that schedules its own work (October 20, 2026, Shreyas)

**The idea.** Today the Researcher does the same routine every generation: read the memory, plan N experiments, wait
for results, repeat. With real continuity it doesn't have to. It could keep a **research agenda**: a task list it
writes for itself, beside the memory graph. "Try A. If A gains, try B next; if it doesn't, try C instead." The
system runs the scheduled experiments (in parallel where possible). When they finish, code **jumps the agent back to
the point in the memory graph where it made that plan**: its own reasoning from that moment, what it expected, and
the conditional next steps it set itself, now with the results and the findings drawn from them attached. It reasons
from there, updates the agenda, and goes on.

- The **memory graph** is the past (what happened, what it means); the **agenda** is the future (what I intend to
  do, and under what conditions).
- The LLM triggers the scheduling; **code owns the chronology**: it tracks which experiments belong to which plan,
  fires the jump back when they're done, and assembles the context for that moment. The LLM isn't trusted to
  remember to come back or to find the right place on its own.
- The system prompt has to explain this world to the model: that it is one continuing researcher, that it can
  schedule, that it will be returned to its own decision points.

**Why it might work.**
- It is the sharpest fix for the gap v4 is testing: the model losing its own line of thought. Returning to the exact
  decision point is like resuming a paused function with its result in hand (an `await` that returns), rather than
  re-reading a diary and reconstructing what it meant.
- It bounds context naturally: the agent is given the local context of one decision plus what came back, not the
  whole history, which is the Avy lesson (steered, local recall beats dumping everything).
- Multi-step ideas stop getting lost. "First find a better parametrisation, then push the resolution" currently
  has to be rediscovered each generation; with an agenda it's a plan the agent committed to.
- Pre-registered branches ("if it gains, B; if not, C") turn experiments into real tests: the agent has said in
  advance what each outcome will mean.

**How it could fail.**
- **Commitment to stale plans.** A surprise elsewhere (another branch jumps ahead) should interrupt the agenda. It
  needs a rule for when to drop or re-plan, or it will dutifully follow a plan the evidence has overtaken.
- **Agenda sprawl.** Many open threads, each waiting on results: something (code) must decide which thread resumes
  next, cap the number of open plans, and expire old ones.
- **Single noisy results driving branches.** A conditional plan decides on one experiment's outcome; a program's
  search is stochastic, so "A didn't gain" may be bad luck. Plans may need repeats or margins before branching.
- **Less exploration.** An agent following its own plans can tunnel; the memoryless wide loop still matters.
- **Generations stop meaning much.** The run becomes event-driven (resume when results arrive), so comparisons with
  other conditions must be by number of programs evaluated or compute spent, not by generation.

**A cheap first version, on top of Atlas.** When the Researcher plans, it also writes for each experiment "if it
gains, next: …; if not, next: …", stored as a plan node in the graph. When those experiments finish, the next
planning call opens with that plan node (its reasoning, predictions, conditional next steps) plus the results and new
findings, instead of the generic map. Compare against Atlas as it is now.

**What the October 21 results can say about it first.** Whether Atlas's planner already picks up its own open
questions and builds chains of experiments ("builds on F12"); whether those chains gain more often than fresh ideas.
If continuity helps at all, this is the next step.
