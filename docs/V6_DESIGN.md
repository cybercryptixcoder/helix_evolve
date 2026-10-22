# Helix v4.6 and v6: design (October 22, 2026)

Two new versions, one per stream (naming: `docs/BRIEF_2026-10-22.md`, section 2):
- **v4.6, the Atlas stream (conservative):** v4 → v4.5 → v4.6. It keeps v4's architecture (a planned deep loop, a
  memoryless wide loop and the Atlas memory) and fixes what the traces showed was wrong with it.
- **v6, the agentic stream (ambitious):** v5 → v6. A new architecture. There are no fixed loops: an agent decides
  each round how the compute is spent.

Every fix below comes from something seen in the real traces (`docs/TRACE_STUDY.md`, cited as §n). Both versions
are in `helix6/`, share one engine, and run the same problem, evaluator and models as v4, v4.5 and v5.

## The four ideas behind both versions

1. **Method and state are separate.** A program is a *method*, its code. Its output is a *state*, a construction.
   In v4 a child always started from its parent's construction, so a method could only be tried on the
   construction it grew up on. Two things in the traces follow from that:
   - Mutators transplanted the record's method onto stale states (§1).
   - Mature methods only reached a better basin by luck, through a fresh start (§9).

   In v4.6 and v6, every experiment names both: *this method, run on this state* (the best construction, any
   program's construction, or none).
2. **Time is a resource the planner spends.** A fixed 30 s per program could not finish a high-resolution stage
   (§3), so experiments that never ran their change were recorded as failures (§2). Now:
   - the planner splits the deep loop's CPU among its experiments (v4.6), or gives an action 1-3 units (v6);
   - a program that used its whole budget and returned its start unchanged is labelled **INCONCLUSIVE**. The label
     is shown to the planner and the Distiller and never counts as evidence against an idea.
3. **Plateaus are measured by rate of return, not by "any gain".** v5's stop rule ("3 experiments without a real
   gain") never fired in a tail of +1e-5 gains (§10). The new rule: a run is in a **polishing tail** when the
   record rose less than 3e-4 over the last 3 generations, or a v6 thread is **due** when its last 3 actions did.
   The prompt then lists the kinds of change tried during the tail and asks for a different kind.
4. **Memory is about ideas, scoped to where they were tested.** Atlas had filled with knob tweaks by quota, and the
   idea-level findings had dropped out of view (§4). Findings were also read as general laws when they held for one
   weak family (§5). Now:
   - each experiment has a *kind of change*, and the map shows a table of the kinds tried with what each gave;
   - the findings that mattered (a gain of at least 1e-3) stay on the map permanently;
   - every finding shows the state it was tested on.

## Shared engine (helix6/run.py, evaluate.py, sandbox.py, toolkits.py, prompts.py)

| Change | What it does | Evidence |
|---|---|---|
| Method × state | `child6(base, state)`: the coder changes `base`'s code, and the program starts from `state`'s construction (or `None` for a fresh start). The delta is measured against the state, so a gain is a real gain. | §1, §9 |
| Problem toolkit | Programs can `from helix_problem import score`, the evaluator's own formula (identical to 1e-12), instead of writing their own scorer. | §7 (a wrong (A+B)/3 steered v4.5-s3) |
| INCONCLUSIVE | No change after ≥ 90% of the budget. The feedback says the idea may never have acted and should get more time. | §2 (20 of 54 deep experiments in gens 21-40) |
| Structure vs values | The planners are told to reason about the objective's structure (invariances, better-conditioned formulations) but to measure values with programs. A claimed limit is a hypothesis. | §6 (the gen-9 breakthrough came from structural reasoning) |
| Scoped evidence | Findings are true of the state they were tested on. | §5 |
| Prompt diet | The record's code is shown once. An opened finding shows its latest 8 pieces of evidence. | §8 (76 KB prompts) |
| Kept from v4.5 | keep_best and SIGXCPU, stage lines in the printout, shared gains, the planner's recent reasoning, capped planning, the epistemic guards. | §11 |

## v4.6 (helix6/atlas.py, `--condition v46`)

Same loop as v4: each generation, 3 deep experiments planned by the Researcher and 3 wide mutations. What changed:

- **The halo.** The wide loop now works around the deep loop, as in the hackathon's v1 fix:
  - 2 of the 3 mutations take parents from the **frontier**: programs within 0.002 of the record, plus last
    generation's top 3 deep children. Selection is weighted toward rank and recency.
  - A frontier parent more than 0.001 below the record runs on the record's state, not its own.
  - The third mutation takes a **donor** method from off the frontier and transplants it onto the record's state.
    This is the useful part of the old diversity, without stale starts.

  In v4 atlas-s1, 25 of 60 wide parents in generations 1-20 were more than 0.01 below the record (§1). In v4.6
  none can be: a test checks this on a population with a stale tail.
- **Method × state in the plan.** Each experiment names its `base` (method) and its `state` ("best", a program id,
  or "none"), plus `kind`, `seconds`, hypothesis, change, prediction, and what to do if it gains or not.
- **Time split.** The planner splits 90 s of deep CPU (for example 45/30/15, 60/30, or one 90 s experiment). Each
  experiment gets between 15 and 90 s.
- **Atlas around ideas:**
  - Map 1 is the tree.
  - Map 2 is the table of kinds of change (tried, gains, best gain, inconclusive, failed, last generation).
  - Map 3 has the key findings (best gain ≥ 1e-3, always shown) and the latest 18.
  - The Distiller merges first and writes at most 4 new findings per generation, at the level of ideas, each with a
    tag (its kind of change).
  - A "fails" finding whose evidence is all inconclusive is filed as a question.
  - Statuses count inconclusive evidence separately.
- **The polishing tail.** When the record rose less than 3e-4 over 3 generations, the prompt says so, lists the
  kinds tried since the tail began, and asks for a kind not on the list.
- **No forced roles.** v4.5's fixed explore and challenge slots are gone: the planner chooses, with the evidence in
  front of it.

## v6 (helix6/agent.py, `--condition v6`)

An agent with the compute of one v4 generation per round: **6 units of 30 s**. It spends them with three actions:

| Action | Units | What it does |
|---|---|---|
| `experiment` | 1-3 | A coder changes a method as planned. It runs on a chosen state (the best, any program's, or none). |
| `mutate` | 1 per variant | Mutator variants of a state's own program, run on that state: a halo on demand. With `method`, the mutator transplants another program's method onto that state instead. |
| `continue` | 1-3 | Re-run a program, unchanged, from its own construction for more time, so an investment can mature. It costs no code. |

Units the agent leaves unspent go to mutations of the record, so there is always a halo.

The agent keeps three things, all as append-only event logs:
- **Theory** (`theory.jsonl`): mechanisms and conjectures, each with what would refute it. A statement that claims
  a limit ("optimal", "ceiling", "true maximum") is always filed as a conjecture at low confidence. This is v5's
  guard, which kept all six v4.5/v5 runs out of the textbook trap.
- **Threads** (`threads.jsonl`): the questions it is pursuing. Each action names its thread. A thread is DUE when
  its last 3 actions, over at least 2 rounds, raised the record by less than 3e-4. The agent must close it or
  revise it with a genuinely different approach. A due thread ignored for 2 rounds is parked by the system.
- **Atlas** (as in v4.6): the findings graph, the kinds-of-change table and the scoped statuses, written by the
  Distiller after every round.

Each round makes two calls:
1. A non-thinking navigator call chooses what to open (programs and findings), as in Atlas.
2. One thinking call (capped, as in v5) makes the decision. It sees the record, progress, the map, the states it
   can build on, its threads, its theory and its last 3 decisions with what came of each action.

Why this is the ambitious stream: the system, not a fixed schedule, decides each round:
- depth or breadth;
- new code or more time;
- which method goes on which state;
- when a line of inquiry is finished.

v5 had the theory and the threads but a fixed round shape (explore, challenge, branch slots), so it could not
spend a round finishing an investment or putting a whole round into one idea.

## What the job tests

`scripts/run_v6_jobs.sh`: v4.6 × 3 seeds and v6 × 3 seeds, 30 generations (rounds) each, 30 s per unit. That is the
same compute per generation as v4, v4.5 and v5 (180 CPU-s). The baselines, at generation 20:

| Version | Seeds at gen 20 | Median |
|---|---|---|
| v4 Atlas | 0.93902, 0.89227, 0.88244 | 0.89227 |
| v4.5 | 0.87513, 0.89706, 0.92635 | 0.89706 |
| v5 | 0.87234, 0.87185, 0.93367 | 0.87185 |

v4 atlas-s1, continued: 0.94024 at generation 30, 0.940794 at 55.

v4.6 is meant to beat v4 and v4.5 strictly: a higher median and a higher worst seed at generation 20, and a
generation-30 best that reaches atlas-s1's 0.940. v6 is the exploratory bet. What to look at:
- whether the agent spends its units differently from a fixed schedule (continues, multi-unit experiments,
  transplants);
- whether its threads close and its stop rule fires;
- whether that converts into a higher record.

The report (`helix6/report.py`) puts every version on one chart. The verification re-scores every best
construction three ways.

## How to run

```bash
python -m helix6.run --condition v46 --seed 1 --gens 30 --budget 30 --out runs/v6/v46-s1     # one run
python -m helix6.run --condition v6  --seed 1 --gens 30 --budget 30 --out runs/v6/v6-s1
python -m helix6.run --condition v6 --gens 3 --budget 2 --fake --out /tmp/t                   # no model calls
python -m pytest tests/test_helix6.py -q                                                       # 14 tests
nohup bash scripts/run_v6_jobs.sh > v6_jobs.log 2>&1 &                                          # the overnight job
```

Files per run: v4's (`programs.jsonl`, `history.jsonl`, `plans.jsonl`, `findings.jsonl`, `trace.jsonl`,
`state.json`, `summary.json`, `best.py`, `best.npy`), plus `meta.jsonl` (each program's state, seconds, kind,
inconclusive flag, action and thread) and, for v6, `threads.jsonl` and `theory.jsonl`.
