# Ideas to explore (not built)

Ideas for where Helix goes next. Each says what it is, why it might work, and how it could fail. Newest first.

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
