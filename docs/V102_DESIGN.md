# Helix v10.2: from Code Zero, the field's ideas as axes, against the published systems (October 29, 2026)

Shreyas's requests (October 29):
- 01:56: "1 + 3". Start from nothing (option 1). Build ideas instead of patching them onto the champion (option 3):
  an exploration starts from nothing or from its own construction, is judged on its own climb, and keeps climbing
  until it overtakes. "If you give us the axes, we will search that as a search space."
- 02:12: drop the industry baseline. A home-built AlphaEvolve-style loop is a basic version and can't stand in for the
  industry's systems. Run our own runs, with the axes from the deep research.
- 02:14: compare with existing published baselines under the constraint they followed, as v10.1 did with the step
  limit.

## What is compared, and why that comparison is valid

We don't rebuild anyone's system. We run Helix under the constraints the published systems report, and set our numbers
beside theirs. The published LLM-driven systems on this problem (the second autocorrelation inequality, higher is
better):

| System | Value | Model | Programs evaluated | Time per program | Start | Source |
| --- | --- | --- | --- | --- | --- | --- |
| AlphaEvolve | 0.8962 | Gemini 2.0 Pro + Flash | not stated | not stated | scratch | arXiv:2506.13131 |
| Best-of-N | 0.9344 | gpt-oss-120b | 25,600 | 10 min | random | TTT-Discover, Table 2 |
| OpenEvolve | 0.9449 | gpt-oss-120b | 25,600 | 10 min | random | TTT-Discover, Table 2 |
| ThetaEvolve, without RL | 0.9434 | R1-Distill-Qwen3-8B | 51,200 (100 steps x 512) | 350 s | a 0.9055 program | arXiv:2511.23473, Table 2 |
| ThetaEvolve, with RL | 0.9469 | R1-Distill-Qwen3-8B, trained at test time | 33,280 (65 x 512) | 350 s | a 0.9055 program | the same |
| TTT-Discover | 0.9591 | gpt-oss-120b, trained at test time (about $500) | 25,600 (50 x 512) | 10 min | random | arXiv:2601.16175 |
| AlphaEvolve V2 | 0.9610 | Gemini 2.0 Pro + Flash | not stated | not stated | scratch | Georgiev, Gomez-Serrano, Tao, Wagner (Nov 2025); 50,000 steps |

The pre-LLM human best was 0.9015 (Boyer & Li, 2025); Jaech & Joseph's 0.9414 (Aug 2025) is the best by hand-built
optimisation.

v10.2 runs under these systems' constraints, or under tighter ones:
- **From scratch:** Code Zero (a constant function, R = 2/3). No construction or program of the field.
- **At most 50,000 steps:** the size of AlphaEvolve V2's construction, the largest a published system reports.
  TTT-Discover and OpenEvolve state no limit. The limit is enforced exactly (`helix10.run.ExactView`), and the
  verification re-checks every best construction.
- **150 CPU seconds per program** (single-threaded, on a 2-core VM shared by two runs). Theirs: 10 minutes or 350 s.
- **About 1,000 programs in all** (6 a generation, about 150-200 generations in 80 hours). Theirs: 25,600 to 51,200.

The measure is the published value and **the number of programs Helix needed to pass it**
(`helix10/compare.py`, results/v102/COMPARISON.md). A value passed with fewer programs, less time per program and a
step limit no larger is a valid claim against that system, as reported.

Differences that remain, stated in the report:
- **The model.** Helix uses DeepSeek V4.1 Flash. The others use gpt-oss-120b, an 8B model trained at test time, and
  Gemini 2.0.
- **The knowledge.** Helix gets the field's ideas as of October 2026 (`docs/AC2_SOTA.md`), and some of them were
  published after these systems ran, for example the iterated Dinkelbach of March 2026. This is the claim under test,
  not a confound to hide: give Helix the literature's axes and it searches them as a space. Separating "the knowledge"
  from "searching it as a space" takes an ablation run with the same knowledge but no axes, described below.

## What v10.2 changes in Helix (helix10/run.py, Config.build / wide_own / build_cap; `--cold` in helix10/job.py)

1. **A cold start with the field's axes** (`Run.seed`, mode "cold"). At generation 0, before Code Zero runs:
   - the field's 9 decisions and 38 options go on the design map, next to the 8 generic questions;
   - its 15 findings go into the Atlas, with sources.

   Exploration is biased towards the field's options as in v10: each is built once (coverage), then about half the
   new explorations take one.
2. **Explorations are built from nothing** (`make_slots`, `target_slot`, `build_child`). A new exploration starts
   from Code Zero, on its own track. It is either an option of the field, or a new design from the map: a v9 drop,
   whose other decisions are given as the design the map sampled.
   - The planner's slot and the coder's note say: write a whole new program around this design, don't patch any
     program, and expect a first score below the record.
   - Its later experiments continue from its own construction.

   v10.1 built every option as a flip of a converged record: 41 of 48 programs moved their start by less than 1e-6.
3. **Judged on its own climb, until it overtakes** (`is_copy`, `live`). A built exploration races only against
   other new designs at equal effort, under the "rising" rule: it goes on while it rises.
   - It is never stopped for sitting on a known hill below its top. On its way up it may pass the record's hill;
     v10.1 stopped such tracks.
   - Past the last rung it stays live while it keeps gaining.
   - If it passes the record, it becomes the main track, as before.
4. **At most 4 built explorations race at once** (`cap_builds`). Past the cap, a slot that would open a new one
   serves a racing one instead, so the open ones get the experiments to climb. Racing tracks in all: 5.
5. **The wide loop works the explorations' own lines** (`wide_own_parents`, `wide_child`). Each generation:
   - one mutation goes to the record's track;
   - the others go to the bests of the live explorations, the least-mutated first;
   - an exploration's mutation is shown no "strong program for ideas", because the record's code would pull it back
     to the record's design.
6. **Kept from v10 and v10.1:**
   - 2 of the 3 planned experiments explore every generation;
   - the invariant audit runs every 10 generations (a round skipped for want of programs is no longer logged as an
     empty one);
   - the Atlas's field findings.

Fixed along the way: helix47's `ProblemView` never went below the module's own limit of 200,000 steps, so v10.1's
100,000 class ran with 200,000 (p4446 had n = 200,000). `ExactView` now holds every run, the warm start and the
reference stream to exactly their limit.

## The jobs (scripts/run_v102.sh; docs/V10_JOB.md, "v10.2")

- `ARM=helix SEED=1` (v102-helix) and `ARM=helix SEED=2` (v102-helix-s2): two seeds, because a single run from
  scratch is noisy. In v4, four of nine runs fell into the 0.8825 trap.
- They replace the v10.1 jobs. Seed 1 pauses v101-axes and v101-field; seed 2 pauses v101-warm. Each pause is one
  stop signal; the v10.1 job finishes its generation and pushes, and the v10.2 job waits for it.
- `ARM=field`: optional. It is the world's best program (ClaudeExplorer's iterated Dinkelbach and velocity cycles)
  chained from nothing, using at most half of seed 1's CPU, and is reported at equal CPU.
- 150 s per program, at most 50,000 steps, up to 400 generations or 80 hours.

## Possible ablation (not built): the same knowledge without the axes

A third seed with the findings in the Atlas but no borrowed decisions on the map would show how much of the gain comes
from searching the ideas as a space rather than from knowing them. It needs one switch (no `seed_axes` in
`Run.seed`) and a third slot on the VM.

## How likely each outcome is (honest)

From earlier Helix runs from Code Zero, without the field's axes:
- v4's Atlas reached 0.9390 by generation 20 and 0.9408 by generation 50, then went flat;
- the line of runs from v4.7 to v9 ended at 0.941442 after about 800 generations;
- in v4, four of nine runs were trapped at 0.8825.

The field's own optimisers from nothing reach 0.90-0.93. Its program from nothing reached 0.876 in 8 rounds here.

| Outcome, by the end (either seed) | Odds |
| --- | --- |
| Above AlphaEvolve (0.8962) and best-of-25,600 (0.9344), with under 1,000 programs | about 85% |
| Above ThetaEvolve without RL (0.9434) and OpenEvolve (0.9449), with 1/25 of their programs | about 45% |
| Above ThetaEvolve with RL (0.9469) | about 35% |
| Above TTT-Discover (0.9591) or AlphaEvolve V2 (0.9610) | about 10% |

The robust claim is likely to be sample efficiency against best-of-N and AlphaEvolve's first result. The claim worth
making, above OpenEvolve and ThetaEvolve with a small fraction of their programs, is about even. It depends on the
built explorations of the field's optimisers (Dinkelbach, the beta cascade, coarse-to-fine upsampling) climbing within
the run.
