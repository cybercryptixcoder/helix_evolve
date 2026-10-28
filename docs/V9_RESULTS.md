# What the v9 job did (v8-s1 continued, generations 701-800, October 27-28, 2026)

Data: `results/v9warm/v9-s1` (pushed in full), `results/v9warm/REPORT.md`, `VERIFICATION.md`. Every number below was
computed from those files.

## The outcome

- **The record moved by 2.5e-13** (0.9414417439927 -> 0.9414417439930, verified three ways). In effect, no progress.
  v8's last stretches were already flat: +3.7e-10 in generations 500-600, +8.5e-11 in 600-700.
- 100 generations, 726 programs (705 valid), 1,937 model calls, 16.5M tokens in and 4.1M out, about 212 s a
  generation (about 6 hours).
- **No new hill near the top.** 77 hills are registered; 8 of them already top out at 0.9414 or more (H30, H50, H22,
  H2, ...), all within 3e-7 of each other. Distinct designs keep arriving at the same height.

## Where the budget went

| | Programs | Handed back their start unchanged | Gained more than 1e-9 |
| --- | --- | --- | --- |
| Deep (planned) | 300 (283 valid) | 257 | 26 |
| Wide (mutations) | 300 (296 valid) | 219 | 77 |
| Alternatives handed back | 126 | 29 | 4 |

- **About 70% of the experiments worked on the record's own hill.** 256 of 300 deep experiments were built on a
  0.941442 base, as were 167 of 300 wide ones; on average 4.7 of the 6 programs a generation handed back their start.
- **The wide loop's real gains were on weak bases**, up to +0.10 (0.83 -> 0.93), climbing old, lower hills back to
  about 0.9414 at best.

## What the design map did

- **It worked mechanically.** 12-18 decisions throughout, 1,163 programs placed, 23 discoveries, 14 consolidations
  and 188 option regroupings (the map is rewritten every generation; the model keeps rewording).
- **The model says one interaction dominates:** whether a global structure (a periodic comb, symmetry) is imposed,
  crossed with how the heights are parametrised (direct, log, signed), 61% of the explained variance; effort 21%.
- **Asked-for coordinates mostly did not land.** 74 blueprints asked for 132 decision values; 55 landed (42%), and
  21 blueprints landed in full.
- **The map's calls cost about 21% of the tokens** (annotator 12.6%, the Cartographer and upkeep 2%; the distiller and
  navigator are v8's).

## What exploration did

62 explorations were opened: 18 drops, 18 flips, 18 backtracks, 8 ablations.

| Kind | Opened | Experiments each | Best reached |
| --- | --- | --- | --- |
| Drop (2-4 decisions changed from the record) | 18 | 1 (one had 8) | 0.58-0.85; 10 never produced a valid program |
| Flip (one decision) | 18 | 1, except four that raced (13-47) | the four that raced tie the record on its own hill; others 0.64-0.78 or nothing |
| Backtrack | 18 | 1-2 | 0.9412-0.94144, all on old hills (H3, H22, H24, H30, H39, H61) |
| Ablation | 8 | 1, except one (18) | the one that raced ties the record on its own hill |

**The race was captured by the record's hill.** Flips and ablations of the record that changed nothing landed back
on H22, tied the record, and so always sat at or above the cohort's median at equal effort: they kept being
promoted (to rungs of 32 experiments). In 35 of 100 generations all three racing slots were H22 copies, in 62 one or
two. 117 of the 199 experiments spent on explorations opened in v9 went to H22. The rule that stops a drop that lands
on a known hill below its top did not cover flips and ablations that land on the record's own hill. Meanwhile 49 new
explorations got one experiment each and waited in the queue: **a new region was never climbed.** That is the
"judged at its foot" failure v9 was built to fix, back through a different door.

## What it says

- **v9 neither helped nor hurt the score.** v8 was already flat here. The new machinery ran as designed, but its
  exploration was starved: 3 slots a generation, most of them held by the record's hill.
- **Drops near the record land low.** Changing 2-4 decisions of a finely tuned construction drops it to 0.58-0.85
  before any climbing (strong interactions; the map's own model says so).
- **The model is a poor decoder of far coordinates** (42% of asked-for values landed). Far, random points are the
  hardest to write.
- **The current space may be saturated at about 0.94144.** Eight distinct hills top out within 3e-7 of each other.
  Others reached 0.951-0.9626 with different representations (basin hopping on LLM-written operators, test-time RL,
  warm starts from other structures). Every Helix hill shares a uniform-grid step function polished by a first-order
  optimiser; that shared assumption may be the ceiling, and it is not an axis on the map.

## Continuing from GitHub

- The run's records are complete on GitHub: programs (4,351), the full trace (1,937 calls), findings, plans, tracks,
  hills, the map, the history, the report, the verification and the continuation pack.
- **Constructions:** the releases `constructions-v8-s1` (3,235) and `constructions-v9-s1-g800` (1,055) together hold
  3,848 of the 4,146 valid constructions. **The other 298 were left out by a bug:** the uploader judged them with the
  problem's default limit of 200,000 steps, while these runs allow 1,000,000 (v4.7's `max_n`). Every one of the 298
  failed only that check (the 206 "failed verification" of the v8 upload are the same cause). Fixed: the pack and the
  vault now use the run's own limit (`helix9/pack.problem_module`).
- **Releases now chain:** a release names the releases it builds on (`--base`), holds only what they lack, and a
  download restores the whole chain. The job's end-of-run upload builds on its source's release. Tested
  (`tests/test_helix9_run.py`), and the chain reading tested live against the real releases (3,848 held).
- **One step left, on the VM** (the 298 exist only there): upload them as `constructions-v9-s1`, built on the two
  existing releases. The prompt for Aether:

> In /home/ubuntu/helix_v5_run, run `git pull`, then run once:
> `python3 -m helix9.vault upload --run runs/v9warm/v9-s1 --folder runs/v9warm/v9-s1/constructions,runs/v8warm/v8-s1/constructions --tag constructions-v9-s1 --base constructions-v8-s1,constructions-v9-s1-g800`
> and report its last line (it starts with "vault:"). Don't change, stop or kill anything else, and don't set up
> any cron job or check-in.

After that, a continuation restores every valid construction of v8-s1 and v9-s1 from `constructions-v9-s1` alone.
