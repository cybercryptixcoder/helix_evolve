# Notes for agents working in this repo

- **Read `docs/BRIEF_2026-10-22.md` first** (the current request: study the traces, build v4.6 (conservative) and v6
  (agentic), the next overnight job). It holds Shreyas's request verbatim, the notes and decisions, and the live,
  staged to-do list. After any context compaction or session reset, re-read it before doing anything else, and keep
  its to-do list updated and pushed. Earlier briefs: `docs/BRIEF_2026-10-21.md` (v4.5, v5), `docs/BRIEF_2026-10-20.md`
  (v4).
- Then `docs/REQUESTS.md` (every request and standing rule) and `docs/WORKLOG.md` (what was done and found, newest first).
- Commit and push often, as `Shreyas Naik <119774329+cybercryptixcoder@users.noreply.github.com>`, with no AI attribution.
- Never commit `.env` or any Luminal key.
- Shreyas's cloud VM is small (2 ARM cores, ~4 GB free RAM, shared with other agents): jobs run one at a time, gently.
- Agent prompts for jobs (Hermes) never tell the agent to kill processes or to create cron jobs or check-ins for
  itself: Shreyas checks in himself (an agent's own restart cron once killed a running job every 12 minutes).
