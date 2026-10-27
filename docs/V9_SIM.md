# v9 in the simulator: what it found, and what changed because of it (October 27, 2026)

The simulator (`helix9/sim.py`, stage 1 of the proof of concept in `docs/SEARCH_SPACE_MODEL.md`) runs v8's and v9's
search logic on planted worlds where the truth is known, thousands of times, in seconds each. It is a model of our
situation, not our situation: its value is that it tests the logic where the answer is known, and shows which part
helps and which hurts. Reproduce any table here with
`python -m helix9.sim --batch --seeds 40 --seed0 41 --families ... --policies ... --out DIR`.

## The worlds

Eight decisions with four options each (one or two hidden at first). Planted hills: a trap where the coder's habits
are (0.88, quick to climb), the record's hill (0.94, already climbed: every run is a warm start, like the v9 job,
with 4 earlier explorations paused after 3 experiments), a **taller hill (0.962) three coordinated changes away**,
and decoys. A program's score is its design's height minus a gap that closes with the effort spent there, so a new
hill looks low at first. The coder builds what it is asked with 75% fidelity per decision and drifts; the annotator
reads a decision right 90% of the time. 120 generations of 3 planned experiments and 3 mutations.

| Family | What differs |
|---|---|
| broad | the default (about 2% of random 2-4-decision drops from the record land where a climb ends above it) |
| easy | a wider taller hill (about 9%) |
| slow, fast | the taller hill matures slowly (tau 25) or quickly (tau 5) |
| hidden | one of its three changes is on a decision nobody has named yet |
| rugged | 8 decoy hills and a rougher surface |
| narrow | a very narrow taller hill (about 0.1%): hardly reachable |
| smooth | one hill, no interactions (climbing only) |
| cold | from Code Zero, nothing known, 150 generations |

**The measure:** how often the run ends on the taller hill near its top ("taller hill"), and the true height of
its final best, compared seed by seed with v8 on the same world (better / worse, with a two-sided sign test).

## 1. The first draft of v9 was not better than v8

2,160 runs (9 families, 10 policies, 24 seeds):

| Policy, against v8 | Taller hill | Seeds better / worse | p |
|---|---|---|---|
| v8 | 33.3% | | |
| v9 (first draft) | 31.5% | 49 / 62 | 0.26 |
| v9 with random drops (no model) | 33.3% | 45 / 63 | 0.10 |
| v9 with v8's patience (no race) | 35.6% | 56 / 50 | 0.63 |
| v9 without read-back | 31.9% | 46 / 67 | 0.06 |
| v9 without discovery | 28.7% | 47 / 61 | 0.21 |
| v8 with the race | 32.4% | 47 / 67 | 0.08 |
| a simple baseline (sequential conditioned sampling) | 13.9% | 14 / 101 | <0.001 |

Every Helix variant beat the simple baseline by far, and none differed from v8 beyond noise. A second batch with
40 new seeds per world made it clearer: the draft was **worse** than v8 (50 seeds better, 73 worse, p = 0.047).

## 2. Why: the race had throttled breadth

Tracing single runs showed the cause. The taller hill was usually reached in passing (some program landed in its
basin in every run), but a run takes it only if an exploration lands near enough and then climbs it. v8's winning
moves were often a single flip of the record that landed on the taller hill at once. v8 makes many such probes; the
draft made few:

| Over 120 generations (broad world, 12 seeds) | Explorations opened | Follow-ups on them |
|---|---|---|
| v8 | 57 | 169 |
| v9, first draft | **11** | 218 |
| v9, as shipped | 74 | 152 |

The draft opened a new direction only while fewer than 3 tracks raced, and a track keeps racing while it rises,
which on these worlds is for a long time. So it spent its exploration on deepening a few tracks, and stopped probing.
The race was right about depth and wrong to buy it with breadth.

**The fix (in `helix9/run.py` and the simulator alike):**
- **breadth is kept:** about half the exploration slots open new directions whatever races (one slot: every other
  generation; two: one each);
- **at most 3 race at once:** when a fourth arrives, the weakest at equal effort waits in the queue and is taken
  again in turn;
- **racing tracks that gained at their last experiment are served first**, then in turn.

Two smaller fixes came from the same traces: the simulator's warm start now gives the earlier explorations real
curves and judges them as the v9 job does (the queue of earlier explorations), and the job does the same for v8-s1's
146 explorations (81 qualify; 2 race at once, the rest wait their turn).

## 3. v9 as shipped is better than v8

First on the 40 seeds the fix was chosen on (240 paired runs: 86 better, 56 worse, p = 0.015), then confirmed on
**40 fresh worlds per family** it was never tuned on:

| Family (40 new seeds each) | Taller hill, v9 vs v8 | True height, v9 vs v8 | Seeds better / worse | p |
|---|---|---|---|---|
| broad | 45% vs 35% | 0.9493 vs 0.9469 | 14 / 7 | 0.19 |
| easy | 75% vs 75% | 0.9578 vs 0.9573 | 14 / 12 | 0.85 |
| slow | 15% vs 18% | 0.9430 vs 0.9428 | 5 / 6 | 1.00 |
| fast | **68% vs 30%** | 0.9532 vs 0.9475 | 22 / 5 | 0.002 |
| hidden | 32% vs 28% | 0.9487 vs 0.9481 | 8 / 6 | 0.79 |
| rugged | 72% vs 70% | 0.9872 vs 0.9829 | 20 / 9 | 0.06 |
| cold (from Code Zero) | 0% vs 0% | 0.8870 vs 0.8834 | 5 / 1 | 0.22 |
| **all** | **43.9% vs 36.4%** | | **88 / 46** | **< 0.001** |

v9 is better overall and in no world worse beyond noise. The gain is largest where a new hill shows its height
quickly (fast) and where there are many hills to choose between (rugged); where the taller hill matures slowly
(slow), neither version reaches it in 120 generations, and v9 is no better.

## 4. Which parts of v9 do it

Each part switched off in turn, on 30 more fresh worlds per family (seeds 41-70; 180 paired runs each; v9 here is
the shipped policy under its own name, so its random stream is independent of section 3's):

| Policy | Taller hill | Against v8: better / worse (p) | Against v9: better / worse (p) |
|---|---|---|---|
| v8 | 45.6% | | 38 / 62 (0.021) |
| **v9** | **56.1%** | **62 / 38 (0.021)** | |
| v9 without breadth (the draft's cap) | 46.1% | 44 / 53 (0.42) | **36 / 61 (0.014)** |
| v9 with random targets (no model) | 52.8% | 72 / 43 (0.009) | 58 / 55 (0.85) |
| v9 with v8's patience (no race) | 53.3% | 56 / 44 (0.27) | 53 / 50 (0.84) |
| v9 without the queue of earlier explorations | 54.4% | 69 / 34 (0.001) | 61 / 45 (0.15) |
| v9 serving racing tracks in turn only | 57.2% | 74 / 35 (< 0.001) | 56 / 48 (0.49) |
| v9 without read-back | 55.6% | | 55 / 45 (0.37) |
| v9 without discovery | 51.7% | | 50 / 52 (0.92) |

What this says, plainly:
- **Breadth is what the race needed.** Without it v9 falls back to v8's level; with it, v9 is better.
- **The gain comes from where v9 jumps:** drops and flips on the map, from the record, at least 2 decisions from
  every known hill, instead of restarts from the coder's habits. Choosing those targets at random on the map does
  about as well as choosing them with the model: in these worlds the model's choice adds nothing measurable. Its
  value would show where decisions have unequal, learnable effects; the replay's second verdict tests that on the
  real archive.
- The race (against v8's patience), the queue, read-back and discovery each move the result by a few points, none
  beyond noise in these worlds. They stay: the race and the queue are what the live job's continuation needs (81 of
  v8's paused explorations qualify), and read-back and discovery are what keep the map honest when real readings
  are wrong, which the simulator's tidy annotator rarely is.

## 5. What the simulator can't say

- Its coder, annotator and landscape are stand-ins with chosen error rates; the replay (stage 0, the job's first
  step) measures the real annotator's reliability on v8's archive, and the live run tests the real coder.
- Its effect sizes are not predictions for the autocorrelation problem: they say the logic works where the truth is
  known, and which parts carry it.
- One live run is one sample. The job tests behaviour (do drops land, does the race promote, does the queue revive the
  right explorations, does breadth hold) more than it ranks versions.

## Seeing it

`viz/mapview.html` shows simulator runs side by side with live runs: the planted landscape behind the map (contours
or terrain), every program placed on it, the record's path, the race's curves. Presets: a fast world (seed 69) and a broad
world (seed 59), each run by v9 and by v8; on both, v9 takes the taller hill and v8 doesn't.
`python -m helix9.mapview sim --family fast --policy v9 --seed 44 --out x.json` writes any other.
