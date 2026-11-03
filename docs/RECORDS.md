# Results, with the evidence behind each

This file backs every claim in the README's results table. For each result it gives: the value Helix beat, where that
value comes from, the run that beat it, when and under what limits, and the files anyone can check. Values are
truncated, not rounded. Everything was re-checked on November 3, 2026 (see "How these were checked" at the end).

## The problem

The **second autocorrelation inequality** is an open problem in analysis. For a non-negative function f, let
R(f) = ‖f∗f‖₂² / (‖f∗f‖₁ · ‖f∗f‖∞), where f∗f is f convolved with itself. The true maximum of R, called C₂, is
unknown. Any function you write down proves a lower bound C₂ ≥ R(f). People search over step functions (f constant
on n equal pieces), so a "construction" is a list of n non-negative heights, and a higher R is a better result.

- A construction can't be faked: its value is computed exactly from the heights, by anyone.
- The scoring is plain code; no model judges anything.
- This is the problem AlphaEvolve (Google DeepMind) and later LLM-driven systems report on, so their published
  values give a public scale.

## What "from scratch" means here

Every Helix run on this problem starts from the same trivial program: one that returns a constant function
(R = 2/3). The agents are never shown a published construction, a published value, or the scorer's code. What the
model already knows from its training can't be removed, and we don't claim otherwise.

The runs below differ in one way that matters:
- **Results 1-2 (Helix v4 to v8):** given nothing from outside, ever. One line of work in two stages:
  - Helix v4's run `atlas-s1` climbed from the constant function for 150 rounds (901 programs), to 0.940794.
  - Helix v4.7 then started a new run, `v47-s2`, from that run's best program alone, with an empty memory (its
    programs are numbered afresh: `p0001` is the constant function, `p0002` the program carried over). Helix v7 and
    then v8 continued that run where the previous version stopped. Round numbers count from the very start, so
    round 151 is v4.7's first.

  So nothing from outside entered at any point, but the search code changed between versions, and one restart
  carried over only the best program.
- **Run 4 (Helix v10.2):** also from the constant function, with no outside construction or code. But by design its
  agents were given a written summary of the methods published for this problem (9 design choices with 38 options,
  and 15 short findings with their sources), some published after the systems it is compared with. The full list is
  in [`helix10/sota.py`](../helix10/sota.py), and every agent call that used it is in the run's trace.

## The machine and the model (all runs)

| | |
|---|---|
| Computer | One Oracle Cloud virtual machine: Ampere A1, ARM (Neoverse-N1), **2 CPU cores**, 12 GB RAM, **no GPU**. Shared with other jobs |
| Each program | Run single-threaded, under a hard **CPU-time limit** (30 s in v4, 60 s in v4.7-v8, 150 s in v10.2) and a memory cap (1.5 GB; 2 GB in v10.2). At most 2 programs ran at once on the whole machine |
| Model | **DeepSeek V4.1 Flash** (`deepseek-ai/DeepSeek-V4.1-Flash`), one model for every agent, through Luminal's API. The planning agent (and, in later versions, a few reviewing calls) uses the model's reasoning mode at "low" effort; the coding, mutating and bookkeeping agents run without it ([docs/MODEL_SETTINGS.md](MODEL_SETTINGS.md); every call's settings are in the run's trace) |
| Programs per round | 6: 3 planned experiments (the reasoning loop) and 3 mutations (the exploring loop) |
| Training | None. No model is fine-tuned or trained |

v10.2's own record of the machine, written when each run started ([results/v102/sessions.jsonl](../results/v102/sessions.jsonl)):
`"machine": "aarch64", "cpus": 2, "mem_total_mb": 11925`, Python 3.12.3, and the exact code version
(git commit) of each run.

## The results

### 1. Above AlphaEvolve's first published result

| | |
|---|---|
| The value beaten | **0.8962**, AlphaEvolve (Google DeepMind, May 2025): a 50-step construction. DeepMind states "0.8962 ≤ C₂"; their construction, re-scored here, gives 0.896279944155 ([alphaevolve_results](https://github.com/google-deepmind/alphaevolve_results), notebook B.2; also cited as 0.8962 by [Boyer & Li](https://arxiv.org/abs/2506.16750) and [TTT-Discover](https://arxiv.org/abs/2601.16175), Table 2) |
| Beaten by | Helix v4, run `atlas-s1`, from scratch, given nothing from outside |
| When | Round 10, program `p0057` (the 57th program), R = 0.907611556938 |
| Limits | 30 CPU seconds per program |
| Evidence | [results/v4/atlas-s1/](../results/v4/atlas-s1/): every program with its code and score (`programs.jsonl`), every model call with its full prompt and reply (`trace.jsonl.gz`), the per-round log (`history.jsonl`, `run.log`), the settings (`summary.json`). Code: [`helix4/`](../helix4/), job: [`scripts/run_v4_jobs.sh`](../scripts/run_v4_jobs.sh), [docs/V4_JOB.md](V4_JOB.md) |

The same program is also above **0.901564** (Boyer & Li, NC State, 2025, 575 steps, found by simulated annealing and
gradient methods; [arXiv:2506.16750](https://arxiv.org/abs/2506.16750)). TTT-Discover's Table 2 lists this value as
the "best human" result.

### 2. Above the best result found by human researchers

| | |
|---|---|
| The value beaten | **0.941362**, Jaech & Joseph (Aug 2025), a 2,399-step function found by a gradient search they designed ([arXiv:2508.02803](https://arxiv.org/abs/2508.02803): "c ≥ .94136"). Their published construction ([function.py](https://github.com/ajaech/autocorrelation_inequality)) re-scores at 0.941362894974; a copy is in [data/field_ac2/](../data/field_ac2/). [ThetaEvolve's paper](https://arxiv.org/abs/2511.23473) calls it the "previous human best" |
| Beaten by | The same line of work (see "What from scratch means"), given nothing from outside, during the Helix v8 stage |
| When | Round 352, program `p1324` of the second stage, R = 0.941364540. About 2,220 programs from the very start (901 in the first stage, 1,322 new ones in the second) |
| Where it ended | **0.941441743993** (round 700, program `p3596`, 104,992 steps). Exact rational arithmetic, with the heights rounded to integers (itself a valid construction), certifies **C₂ ≥ 0.941441740905** |
| Limits | 30 CPU seconds per program for rounds 1-150, 60 s after that. About 23 CPU hours of program time up to round 352 (6.2 in the first stage, 17.0 in the second) |
| Evidence | Second stage, rounds 150-700: [results/v8warm/v8-s1/](../results/v8warm/v8-s1/), whose `programs.jsonl` holds every program of the stage, so the lineage of `p1324` can be traced back to `p0002`; `history.jsonl` has every round; `trace.jsonl.gz` has the v8 rounds' model calls, and [results/v47warm/v47-s2/](../results/v47warm/v47-s2/) and [results/v7warm/v7-s1/](../results/v7warm/v7-s1/) the earlier ones. First stage, rounds 0-150: [results/v4/atlas-s1/](../results/v4/atlas-s1/) (rounds 1-20) and [results/v4cont/atlas-s1/](../results/v4cont/atlas-s1/) (all 150, with every program; its best, `p0885`, is the second stage's `p0002`). Best construction: [`best.npy`](../results/v8warm/v8-s1/best.npy). Code: [`helix4/`](../helix4/), [`helix47/`](../helix47/), [`helix7/`](../helix7/), [`helix8/`](../helix8/); jobs: [`scripts/run_v47_warm.sh`](../scripts/run_v47_warm.sh), [`scripts/run_v7_warm.sh`](../scripts/run_v7_warm.sh), [`scripts/run_v8_warm.sh`](../scripts/run_v8_warm.sh), [docs/V8_JOB.md](V8_JOB.md); verification: [results/v8warm/VERIFICATION.md](../results/v8warm/VERIFICATION.md) |

**Read it as:** a higher value than any human-designed search has published, from a trivial start, on one 2-core
machine with an inexpensive model. **Not:** a world record. AI systems have gone higher since (0.961 and above; see
"What Helix did not beat").

`atlas-s1` was 1 of 9 runs started by Helix v4 (3 kinds of memory × 3 seeds, 20 rounds each). It was the best of
them after 20 rounds (0.939016; the others ended between 0.882 and 0.934, see [results/v4/](../results/v4/)) and the
only one continued this far. Helix v4.7 started two runs from it; the one continued is `v47-s2`.

### 3. Above the published LLM-driven systems, with far fewer programs (Helix v10.2)

Helix v10.2, run `v102-helix` (seed 1), from scratch, with the written summary of published methods described above.
Limits, chosen to be as tight as or tighter than the systems compared: **at most 50,000 steps** (the size of
AlphaEvolve V2's construction), **150 CPU seconds per program**, **400 rounds (2,564 programs)**.

The published values and budgets are as the papers report them: [TTT-Discover](https://arxiv.org/abs/2601.16175),
Table 2 (AlphaEvolve, OpenEvolve, best-of-N, TTT-Discover) and [ThetaEvolve](https://arxiv.org/abs/2511.23473),
Table 2.

| System | Its value | Its model | Its programs | Its time per program | Helix passed it at | Helix's program |
|---|---|---|---|---|---|---|
| AlphaEvolve (May 2025) | 0.8962 | Gemini 2.0 Pro + Flash | not stated | not stated | round 4 | `p0021` (21st), 0.897662 |
| Best of 25,600 samples | 0.9344 | gpt-oss-120b | 25,600 | 10 min | round 24 | `p0146` (146th), 0.937953 |
| Jaech & Joseph (human, Aug 2025) | 0.941362 | — | — | — | round 26 | `p0161` (161st), 0.944645 |
| ThetaEvolve, without RL | 0.9434 | DeepSeek-R1-0528-Qwen3-8B | 51,200 | 350 s limit | round 26 | `p0161` (161st), 0.944645 |
| OpenEvolve | 0.9449 | gpt-oss-120b | 25,600 | 10 min | round 27 | `p0164` (164th), 0.945662 |
| ThetaEvolve, with RL at test time | 0.9469 | the same 8B model, trained during the run | 33,280 | 350 s limit | round 227 | `p1419` (1,419th), 0.947592 |

Where it ended: **0.948610408760** (round 400, program `p2563`, exactly 50,000 steps). Exact rational arithmetic
certifies **C₂ ≥ 0.948610407407**. Cost: 2,564 programs, 82.3 CPU hours of program time, 7,376 model calls, about
93 million tokens, about 4 days on the machine (shared with the second seed).

**Read it as:** with the published ideas in hand, Helix passed OpenEvolve's reported value within 164 programs of
150 s each (OpenEvolve: 25,600 programs of up to 10 minutes) and ThetaEvolve's with-RL value within 1,419 (theirs:
33,280, with a model trained during the run), starting from a constant function rather than ThetaEvolve's 0.9055
starting program.

**What this does not control for:**
- The model is different (DeepSeek V4.1 Flash against gpt-oss-120b, an 8B model and Gemini 2.0).
- Helix's agents had a summary of methods published after some of these systems ran. That is the point being
  tested (can Helix search the field's ideas as a space), but it is an advantage those systems didn't have.
- **One of two seeds.** The second seed, `v102-helix-s2`, run the same way, ended at **0.941244146241**: it passed
  AlphaEvolve's 0.8962 (round 52) and best-of-25,600 (round 101), but not Jaech & Joseph, ThetaEvolve or OpenEvolve.

Evidence: [results/v102/v102-helix/](../results/v102/v102-helix/) (`programs/` and `trace/`: every program and every
model call, in gzipped parts of 10 rounds with an `index.json`; `history.jsonl`; `run.log`; `summary.json`;
`best.npy`), [results/v102/COMPARISON.md](../results/v102/COMPARISON.md) (written by the run itself),
[results/v102/VERIFICATION.md](../results/v102/VERIFICATION.md), the second seed in
[results/v102/v102-helix-s2/](../results/v102/v102-helix-s2/). Code: [`helix10/`](../helix10/), job:
[`scripts/run_v102.sh`](../scripts/run_v102.sh), design: [docs/V102_DESIGN.md](V102_DESIGN.md),
[docs/V10_JOB.md](V10_JOB.md).

## What Helix did not beat

| Value | Who | Steps | Helix's best in that size |
|---|---|---|---|
| 0.959180 | TTT-Discover (Jan 2026), gpt-oss-120b trained during the run | 50,000 | 0.948610 |
| 0.961021 | AlphaEvolve V2 (Georgiev, Gómez-Serrano, Tao, Wagner, Nov 2025) | 50,000 | 0.948610 |
| 0.963588110582 | the best known: EinsteinArena's leaderboard #1 (ClaudeExplorer, Jul 2026), polished on GPUs | 1,999,999 | — |

**Runs that started from other people's constructions** (v10 and v10.1 "warm" runs) made no meaningful gain:
- Started from the leaderboard's #1 construction (0.963588110582), the run ended at 0.963588148491 (+3.8e-8, almost
  all of it from the field's own polishing method run at the start). The leaderboard requires +1e-5 for a new #1, so
  this is **not** a record ([results/v10/VERIFICATION.md](../results/v10/VERIFICATION.md)).
- Started from the best known construction with at most 100,000 steps (0.962273842955), the run gained 2.6e-13
  ([results/v101/COMPARISON.md](../results/v101/COMPARISON.md)).

## Other problems (Helix v3, October 17)

Nine standard optimisation problems, each with instances the search never saw. "Progress" runs from 0% (the starting
program) to 100% (optimal, or the best known bound). The textbook rule was hidden from the agents.

| Problem | Rounds | Helix, unseen instances | The textbook rule |
|---|---|---|---|
| Knapsack | 10 | 99.95% | 98.2% (value per weight) |
| Machine scheduling | 10 | 99.2% | 98.2% (least-loaded machine) |
| Set cover | 10 | 98.5% | 93.3% (cost per new element) |
| Travelling salesman | 10 | 97.8% | 95.9% (nearest neighbour) |
| Vehicle routing (capacitated) | 10 | 92.6% | 84.4% (nearest customer that fits) |
| Job-shop scheduling | 10 | 75.7% | 66.3% (most work remaining) |
| Graph colouring | 10 | 64.8% | 61.1% (DSatur) |
| 1D bin packing | 10 | 37.6% | 19.3% (Best Fit) |
| 2D bin packing | 13 | 28.8% | 3.1% (Best Fit) |

Every run, with its traces: [results/v3/](../results/v3/); the write-up: [docs/WORKLOG.md](WORKLOG.md) ("The cloud
batch", October 17). These beat simple rules, not the best known algorithms for each problem.

## How these were checked (November 3, 2026)

- **Every construction above was re-scored twice:** by the repo's verifier ([`tools/verify_ac2.py`](../tools/verify_ac2.py):
  Helix's scorer, a line-by-line port of DeepMind's own verification code, and exact rational arithmetic) and by a
  separate 15-line scorer written from the definition for this check. All agree to 12 digits with the values above.
- **Every "passed at" figure** was recomputed from the run's own `programs.jsonl`: the first valid program whose
  score is above the published value.
- **Every outside value** was checked against its paper or repository (links above). Jaech & Joseph's and
  AlphaEvolve's constructions, and the leaderboard's, were re-scored from the arrays themselves.
- Where sources differ, both are given: TTT-Discover's table calls Boyer & Li's 0.9015 the "best human" result and
  lists ThetaEvolve at 0.9468; ThetaEvolve's own paper reports 0.9469 and calls Jaech & Joseph's 0.9414 the
  previous human best.

**To check any of it yourself:**

```bash
git clone https://github.com/cybercryptixcoder/helix_evolve && cd helix_evolve
pip install numpy scipy
python tools/verify_ac2.py --alphaevolve-may-2025 \
  results/v4/atlas-s1/best.npy results/v8warm/v8-s1/best.npy results/v102/v102-helix/best.npy
```

**To run it again:** see "Reproducing a run" in the [README](../README.md#reproducing-a-run). A new run is a new
sample: the model's replies aren't seeded, so the numbers will differ from run to run (as the two v10.2 seeds did).
