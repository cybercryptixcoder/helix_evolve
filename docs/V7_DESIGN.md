# Helix v7: exploration that follows progress (October 23, 2026)

Code: `helix7/`. Tests: `tests/test_helix7.py`. The job: `docs/V7_JOB.md`. The request: `docs/BRIEF_2026-10-23.md`
(task F, and the request of 11:28).

## What it is for

v4 climbs well for about 40 generations and then polishes one construction. v4.7 broke the autocorrelation record
from a line it opened on an alternative construction, and then its own rule closed that line while it was still
climbing (generation 182). Shreyas's request for v7:

- remove the line-closing rules: "any improvement is significant", and "a fixed threshold is not something that
  adapts";
- the main path continues even when it is flat, because progress can be hidden for a while before it shows;
- exploration inversely proportional to progress: deep while the record climbs, wider the longer it stalls;
- exploration means trying new things, and also going back: an approach that failed on an earlier construction can
  work on today's, so it should be revived on the current state; earlier states can be revisited;
- whatever picks up gets depth;
- broad at the start, so the search doesn't sink into the first basin.

v7 stays in v4's lineage. While the record climbs at its usual pace, a generation has v4's shape: three planned
experiments on bases the planner chooses, and three mutations of parents sampled from the whole archive. What
changes is what happens when the record stalls.

## What is kept

**From v4 (`helix4/`):**
- the roles: the Researcher with its Navigator, the Coders, the Mutator, the Distiller;
- the two loops: three planned experiments and three mutations per generation, so the compute per generation is
  unchanged;
- the Atlas: findings with statuses computed from measured results, and the tree of attempts, which v4.7 had dropped
  (it may be one reason v4.7 started slower on the VRP);
- children start from their base's construction;
- the wide loop samples parents from the whole archive.

**From v4.7 (`helix47/`):**
- programs can hand back an alternative construction, which is scored and kept as its own program;
- gains count only above a noise floor;
- a failure is shown with the construction it was tried on; the map is balanced (best and newest "works" findings,
  open questions, the newest failures, older failures grouped by construction);
- plans aim at a target instead of a confirm-or-refute prediction;
- no countdown ("Generation 214", not "of 290");
- programs shown up to 30,000 characters, replies up to 16,000 tokens, constructions up to 1,000,000 steps.

**Dropped:** lines and the code that closes them (v4.7's rules 1 and 2). Nothing is closed in v7.

## Tracks

Every program is on a track.
- **The main track** holds the record.
- **Side tracks** are opened by exploration experiments.
- A child is on its base's track, unless its experiment opens a new one. Mutations and alternatives stay on their
  parent's track.
- When v7 continues a v4.7 run, its lines become tracks: paused side tracks, except the record's line, which is the
  main track.

The main track changes only when another track's program beats the main track's best by more than the floor. A
polish below the floor doesn't move it.

## How much exploration: from the run's own rhythm

- **The stall `s`:** the number of finished generations since the record last rose above the floor. A warm start
  counts as a record, so a continued run starts at `s = 0`.
- **The typical gap `T`:** the median of the run's last 8 gaps between records, clamped to 1–12 generations. It is 3
  until the run has two gaps.
- **The level:**

  | Stall | Level | Planned experiments |
  |---|---|---|
  | `s <= T` | 0 | 3 main (v4) |
  | `T < s <= 2T + 1` | 1 | 2 main, 1 exploration |
  | `s > 2T + 1` | 2 | 1 main, 2 explorations |

- **The main track always keeps at least one planned experiment**, however long it has been flat.
- **A cold start explores in its first 3 generations:** 1 main and 2 explorations, so the search starts broad. A
  warm start doesn't: it starts from a state that already climbed.

The thresholds are relative to the run's own pace, so they adapt to the problem: on a problem where records come
every generation, a 3-generation stall is long; where they come every 10, it isn't. They decide how the slots are
shared out, and never end anything.

## What an exploration slot does

An exploration slot first continues a **live** side track. If there is none, it opens a new one, of the kind used
least so far (two slots in one generation get two different kinds):

- **Revive.** Re-apply an approach the Atlas recorded on another construction to the current best.
  - The options are findings tried on other constructions than the best: failures first (round-robin over the
    constructions they were tried on, the closest to the record first), plus two ideas that worked elsewhere and are
    not already in the best's lineage.
  - The planner picks one (`"revives": "F12"`), and the coder is shown its claim.
  - The base is always the current best.
  - Each finding is revived once per record, so a new record makes every finding revivable again.
- **Backtrack.** Go back to an earlier state and push it in a direction that works now, or one never tried from it.
  The options are:
  - the best alternative constructions;
  - the states just before the biggest gains on the record's lineage;
  - the best programs of paused side tracks;
  - the best programs of other branches (programs that split from the record's lineage at least 1% lower).

  States already used as the root of a track are not offered again.
- **Bold.** A genuinely different construction or search, from any base, Code Zero included.

## Side tracks: judged against themselves

- A side track is judged against its own best, not the record. It may start worse than its base: it still gets a
  follow-up (`track_patience = 1`).
- **Live:** it beat its own best in its last follow-up, or it has just opened. A live track gets an exploration slot
  when there is one.
- **Paused:** a follow-up didn't beat its own best. Its programs stay bases for anything, and it is a backtrack
  option.
- A paused track becomes live again if any of its programs gains, from a mutation, say.
- **Order among live tracks:**
  1. those still owed their first follow-up;
  2. then by how much of their gap to the record their last gain closed. A track climbing fast towards the record
     goes first; one creeping far below it, like a fresh start from Code Zero, goes last.
- **Breadth guarantee:** with two exploration slots, one new direction opens every other generation, even if two
  live tracks could take both slots.
- **Promotion:** a side track that beats the record becomes the main track. The old main track becomes a side
  track, and nothing is lost.

## The wide loop

The wide loop broadens with the stall:
- level 0: v4's rank-based sampling (exponent 1);
- levels 1 and 2: flatter sampling (exponent 0.5);
- level 2: one of the three parents comes from a side track or an alternative.

## What the planner sees

In order:
1. the problem;
2. the best program, with the steps that built it (gains only, flat steps counted);
3. Map 1, the tree of attempts, with the points where a side track starts marked;
4. Map 2, the findings, with the noise floor stated;
5. the last generation in full, each program labelled with its track and kind;
6. the side tracks (live first);
7. the slots of this generation, with their options.

The system prompt says that exploration slots open when the record has gone longer than usual without improving,
that an exploration may get worse before it gets better, and that nothing is ever closed. It never asks whether a
construction is saturated.

## Noise

- **ac2:** the score of a construction is exact, so the floor is the relative gain floor (1e-6).
- **The VRP:** scores move between evaluations of the same program.
  - At the start, v7 evaluates the starting program 3 times.
  - It takes the median as its score, and the relative spread as the floor, if that is above 5e-4 (`noise.json`).

## Fixed numbers that remain, and why

| Setting | Value | What it decides |
|---|---|---|
| `typical_window`, `typical_default`, `typical_max` | 8, 3, 12 | the run's own record rhythm, read robustly |
| the level thresholds | `T`, `2T + 1` | when the 3rd and 2nd planned slots turn to exploration |
| `track_patience` | 1 | follow-ups a side track gets without beating its own best before it pauses (it can wake) |
| `early_gens` | 3 | the broad start of a cold run |
| `wide_alpha_stalled` | 0.5 | how much flatter the wide loop samples when stalled |

None of these closes anything. The only things they decide are how the six children of a generation are shared out,
and in what order.

## Risks to watch

- **A fresh track can hold a slot.** A bold track from Code Zero gains easily for many generations far below the
  record, and it can keep a slot. The order by gap closed and the breadth guarantee limit this. The report
  (`helix7/report.py`) shows each track's experiments, so it can be checked.
- **Revive depends on the Distiller's scoping.** A finding's construction is the most common base among its
  evidence.
- **After a long flat spell, `T` stays small**, so the run keeps exploring at level 2. This is intended, and the main
  track keeps its slot.

## Files

| File | What |
|---|---|
| `helix7/run.py` | `Config`; `Run` (tracks, the stall and level, revive and backtrack candidates, slots, experiments, the wide loop, calibration); the fake model |
| `helix7/memory.py` | `Atlas7`: statuses with the floor, scoped failures, the balanced map, the tree with track starts, the planner's brief, the Distiller with track labels |
| `helix7/prompts.py` | the planner's system prompt, the plan format, the slot texts, the coder's note for explorations |
| `helix7/warm.py` | start a v7 run from a v4 or v4.7 run (`continue` or `best`) |
| `helix7/report.py` | `REPORT.md`: records, levels, slots and tracks, generation by generation |
| `scripts/run_v7_warm.sh` | the autocorrelation job (`docs/V7_JOB.md`) |
