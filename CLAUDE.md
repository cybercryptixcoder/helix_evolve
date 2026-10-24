# Notes for agents working in this repo

- **Fresh session? Read `docs/HANDOFF_2026-10-24.md` first** (everything: versions, lessons, VM, open tasks; the VRP in `docs/VRP_CONTEXT.md`). Then **`docs/BRIEF_2026-10-24.md`** (the current request: v8, a register of hills, `helix8/`,
  `docs/V8_DESIGN.md`, jobs in `docs/V8_JOB.md`; before it, how to explore more of the search space: the v7 results
  are in `docs/V7_RESULTS.md`, the reasoning in `docs/SEARCH_SPACE.md`). Before it:
  `docs/BRIEF_2026-10-23.md` (v7, `helix7/`, and its two jobs) and `docs/BRIEF_2026-10-22_V47.md` (v4.7). It
  holds Shreyas's request, the notes and decisions, and the live to-do list. v7's design: `docs/V7_DESIGN.md`; its
  jobs: `docs/V7_JOB.md`. After any context compaction or
  session reset, re-read it before doing anything else, and keep its to-do list updated and pushed. Earlier briefs:
  `docs/BRIEF_2026-10-22.md` (v4.6, v6), `docs/BRIEF_2026-10-21.md` (v4.5, v5), `docs/BRIEF_2026-10-20.md` (v4).
- `docs/VERSIONS.md` is the project's map: every version, what it tried, what worked and failed, with links. Update it
  (and `docs/WORKLOG.md`) whenever a version, job or finding of consequence lands: Shreyas wants all of it tracked on
  GitHub. Open research questions: `docs/RESEARCH_PLATEAUS.md`.
- Then `docs/REQUESTS.md` (every request and standing rule) and `docs/WORKLOG.md` (what was done and found, newest first).
- Commit and push often, as `Shreyas Naik <119774329+cybercryptixcoder@users.noreply.github.com>`, with no AI attribution.
- Never commit `.env` or any Luminal key.
- Shreyas's cloud VM is small (2 ARM cores, ~4 GB free RAM, shared with other agents): jobs run one at a time, gently.
- Agent prompts for jobs (Hermes) never tell the agent to kill processes or to create cron jobs or check-ins for
  itself: Shreyas checks in himself (an agent's own restart cron once killed a running job every 12 minutes).
