# Notes for agents working in this repo

- **Paused (November 3, 2026).** The results and their evidence: `docs/RECORDS.md` (README's table). The VM's
  offload to GitHub releases: `docs/OFFLOAD.md` (`scripts/offload_vm.sh`, `tools/offload.py`). Any claim added to the
  README must be added to RECORDS.md with its source, run, round, program and a re-check.
- **Latest (October 29, night): v10.2** (`docs/design/V102_DESIGN.md`; `docs/jobs/V10_JOB.md`, top; `scripts/run_v102.sh`): Helix
  from Code Zero with the deep research's axes, explorations built from nothing and judged on their own climb, at the
  published LLM systems' constraint (n <= 50,000), measured against their values and budgets (`helix10/compare.py`).
  Shreyas: no home-built industry baseline; compare with published ones under their constraints.
- **Before that (October 28, late): v10.1** (`docs/jobs/V10_JOB.md`, top; `scripts/run_v101.sh`): Helix against the world's best
  program at the same constraint (n <= 100,000, 300 s per program; the bar in `helix10/baseline.py`), the invariant
  audit (`helix10/audit.py`), the v10 runs paused and continued.
- **Before that (October 28, evening): v10 built** (`helix10/`, `docs/design/V10_DESIGN.md`): the field's knowledge on the
  second autocorrelation inequality (`docs/analysis/AC2_SOTA.md`: the record is 0.963588110582, arena #1; the constructions in
  `data/field_ac2`) as borrowed axes, Atlas findings and, in the warm mode, starting points; two jobs side by side
  (`docs/jobs/V10_JOB.md`, `scripts/run_v10.sh`, the Aether prompt, the odds). Request and to-do: `docs/history/BRIEF_2026-10-28.md`.
- **Before that (October 28): the v9 job analysed** (`docs/analysis/V9_RESULTS.md`), the night's conversation verbatim
  (`docs/history/CONVERSATION_2026-10-28.md`), and every idea and open decision from it (`docs/research/IDEAS.md`, top section). v10 is
  Shreyas's to design, after discussion.
- **Before that (October 27, night): the research case** (`docs/research/RESEARCH_CASE.md`): the research question (can a discovery system map the space it searches, steer past its model's prior, and change that space when it runs dry?), three research questions, the evidence in hand, and a plan to NeurIPS 2027. Before it, a narrower first pass (`docs/research/RESEARCH_DIRECTION.md`) and a survey brief (`docs/research/SURVEY_BRIEF.md`).
- **Before that (October 27): v9 built** (`helix9/`, `docs/design/V9_DESIGN.md`; the simulator's results in `docs/analysis/V9_SIM.md`; the
  job continuing v8-s1 in `docs/jobs/V9_JOB.md`, `scripts/run_v9_warm.sh`; the viewer `viz/mapview.html`). The request and
  to-do: `docs/history/BRIEF_2026-10-27.md`; the reasoning: `docs/research/SEARCH_SPACE_MODEL.md`.
- **Fresh session? Read `docs/history/HANDOFF_2026-10-24.md` first** (everything: versions, lessons, VM, open tasks; the VRP in `docs/research/VRP_CONTEXT.md`). Then **`docs/history/BRIEF_2026-10-24.md`** (the current request: v8, a register of hills, `helix8/`,
  `docs/design/V8_DESIGN.md`, jobs in `docs/jobs/V8_JOB.md`; before it, how to explore more of the search space: the v7 results
  are in `docs/analysis/V7_RESULTS.md`, the reasoning in `docs/research/SEARCH_SPACE.md`). Before it:
  `docs/history/BRIEF_2026-10-23.md` (v7, `helix7/`, and its two jobs) and `docs/history/BRIEF_2026-10-22_V47.md` (v4.7). It
  holds Shreyas's request, the notes and decisions, and the live to-do list. v7's design: `docs/design/V7_DESIGN.md`; its
  jobs: `docs/jobs/V7_JOB.md`. After any context compaction or
  session reset, re-read it before doing anything else, and keep its to-do list updated and pushed. Earlier briefs:
  `docs/history/BRIEF_2026-10-22.md` (v4.6, v6), `docs/history/BRIEF_2026-10-21.md` (v4.5, v5), `docs/history/BRIEF_2026-10-20.md` (v4).
- `docs/VERSIONS.md` is the project's map: every version, what it tried, what worked and failed, with links. Update it
  (and `docs/WORKLOG.md`) whenever a version, job or finding of consequence lands: Shreyas wants all of it tracked on
  GitHub. Open research questions: `docs/research/RESEARCH_PLATEAUS.md`.
- Then `docs/REQUESTS.md` (every request and standing rule) and `docs/WORKLOG.md` (what was done and found, newest first).
- Commit and push often, as `Shreyas Naik <119774329+cybercryptixcoder@users.noreply.github.com>`, with no AI attribution.
- Never commit `.env` or any Luminal key.
- **Test live, with the real model, always** (Shreyas, October 27): fake models are for crash tests only. Every
  element of anything built is tested end to end live. The key goes in the repo's `.env` (gitignored); keys are
  temporary: ask Shreyas for a current one if the one you have is refused.
- Shreyas's cloud VM is small (2 ARM cores, 12 GB RAM, disk 83% full, shared with other agents): jobs run gently; budget in `docs/jobs/AETHER.md`.
- **Running anything on the VM: read `docs/jobs/AETHER.md` first** (Aether, the VM agent, formerly called Hermes: what it is
  for, the VM's specs and budget, how to write an airtight job, tracing, Luminal, the prompt template).
- Agent prompts for jobs (Hermes) never tell the agent to kill processes or to create cron jobs or check-ins for
  itself: Shreyas checks in himself (an agent's own restart cron once killed a running job every 12 minutes).
