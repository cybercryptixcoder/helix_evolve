# Design note: exploring genuinely untried territory (P3, P4, P5) — for discussion

Status: a proposal (Nov 6, 2026). Nothing here is built yet. Background: the Oct 29 discussion of axes as dials
(`docs/history/CONVERSATION_2026-10-29.md`) and the circle-packing dry run (`docs/history/BRIEF_2026-10-29.md`).

## The problem, as stated

- **P3.** The search settles in one region and polishes it.
- **P4.** The model isn't creative: it rewrites its favourite ideas.
- **P5 (Shreyas, Nov 5).** Force genuinely untried solutions, controlled by settings we choose, not by the model's
  creativity.

## What the lean runs show

**Where a run ends up varies far more than how well it climbs.** Same setup, same budget, different seeds:

| Problem | Range of final results | Spread |
|---|---|---|
| AC2 | 0.838 to 0.926 | 10% |
| AC1 | 1.509 to 1.589 | 5% |
| 32 circles | 2.8107 to 2.9396 | 4% |

The worst runs aren't failing to climb. They climb a poor region slowly: AC1 plan-s1 improved all the way to
program 176 and finished 5% behind.

**When the final region is decided.** The rank correlation between a run's rank at program k and its final rank,
over the 15 runs of each experiment:

| Problem | k = 15 | k = 30 | k = 60 | k = 90 |
|---|---|---|---|---|
| 32 circles | 0.70 | 0.69 | - | - |
| AC1 | 0.03 | 0.46 | 0.72 | 0.88 |
| AC2 | 0.46 | 0.23 | 0.28 | 0.39 |

- **Circles:** the region is chosen within the first 15 programs.
- **AC1:** within about 60.
- **AC2:** late jumps keep reordering the runs. floor-s1, for example, went from 0.85 to 0.92 between programs 120
  and 150.

**Earlier evidence:**
- **Oct 29:** the random seed alone, which only decides the first idea's tie-breaks, made a 0.04 difference on AC2.
- **The dry run:** a mechanical climb over six dials barely beat random sampling with the same number of
  evaluations.
- **v9:** only 42% of requested changes actually landed in the code.

**So exploration has a real target:** reaching better regions, more often, on purpose.

## Options, simplest first

| | What it does | What we control | What it costs |
|---|---|---|---|
| X1 **Restarts** | When a line hasn't gained in K rounds, start a new line from Code Zero. It is judged on its own climb, and its mutations stay on it. | K, and how many lines run at once | no new parts; tests whether more starts beat one longer climb |
| X2 **Forced-different starts** | As X1, but the new line's first program must differ from every existing line on named points. The planner is shown each line's one-line summary and told what to differ on. A check measures whether it landed far: the distance between the result shapes. | how far (a distance threshold), and on what | one check; the risk is v9's again (requested differences don't land) |
| X3 **Dials** (the Oct 29 idea) | The model writes the program with its ingredients as named numbers (a `DIALS` dict). The system climbs the dials numerically, with no model call per point, and jumps by setting them far apart. The model is called only to add a new ingredient when the climb stalls. | the jump size, the dial ranges, how often to add an ingredient | the most new code; the dry run warns that a dial climb may not beat random sampling |

## Proposed order

1. **X1 first.** It is cheap and answers one question: is the regional variation above usable by just starting more
   lines? If X1 doesn't help, forcing differences won't either.
2. **Then X3, as a prototype on one problem (AC1).** This is the version that matches "force it by setting
   parameters". It is also the idea that sets Helix apart from other evolutionary loops.
3. **X2 only if X3 can't be made to work.** It's the version closest to v10.2, which we've seen fall back into the
   model's habits.

## For Shreyas

1. What counts as "untried": different code and ideas, or a different result (a different region of the output)?
   X2 and X3 measure different things.
2. Is X3, the dials, the version you want built, or has your thinking moved since Oct 29?
