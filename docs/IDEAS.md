# Ideas to explore (not built)

Ideas for where Helix goes next. Each says what it is, why it might work, and how it could fail. Newest first.

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
