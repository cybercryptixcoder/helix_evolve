# The private routing problem (VRP): everything known, without the code or data

The plug-in (`helix_vrp/`) and all data are private. They are never committed here, and the real data must never be
read by an LLM. The package travels as `helix_vrp.zip`. The latest copy was built on October 24, in the session's
scratchpad. A fresh session must ask Shreyas for the zip, or for the VM folder, before changing the plug-in.

## The problem

- **What it is:** a heterogeneous-fleet vehicle routing problem from Shreyas's work. A depot ships goods to villages,
  through staging points (subbases). Trucks come in several types, each with a capacity, a fixed cost, a cost per km,
  and a maximum number of trucks.
- **Hard rules:** road load limits (which truck classes may use which roads), depot at both ends of a trip, and the
  arcs that exist.
- **Cost:** fixed cost per truck used, plus distance cost. Cost is the first priority; speed second. Shreyas: "MILP
  ... out of the question" as the main method; long runs are not wanted.
- **The current method** (their code, kept unchanged inside the package): a greedy initial solution plus local search;
  simulated annealing and LNS variants exist. Code Zero is a faithful port of greedy plus local search, about 14k
  characters.

## The plug-in (`helix_vrp/`)

- **Programs** define `solve(instance, time_limit, report)`. They return a list of trips
  (`{"truck_type", "nodes": [depot, ..., depot], "deliveries": {village: tons}}`) and call `report(trips)` on each
  better solution.
- **The evaluator** (`evaluator.py`), in two tiers:
  - **public:** one synthetic development instance, whose output is shown to the agents, plus a size ladder for
    scaling;
  - **private:** the compiled real (or fake) instances; only normalised numbers leave.
- **The score:** Q = the geometric mean of (reference cost / program cost), the reference being the greedy initial
  solution, times (1 + an efficiency bonus capped at 3%: speed to final quality, and scaling). Any invalid private
  solution makes the program invalid.
- **Sandbox** (`sandbox.py`): CPU and memory limits (1200 MB per program on the VM), blocked paths.
- **v8's signature:** `solution_signature` hashes each trip's (truck type, village set). `signature_distance` = 1 −
  the mean Jaccard over instances. Hashes only: no ids or names in run folders. A test checks private names never
  appear.
- **Data:**
  - `fakeworld.py` makes fake worlds in the real formats: train = 3 worlds × 3 instances; held-out test = 4 worlds.
  - `prepare.py` compiles them through the real loaders and benchmarks the current methods.
- **Running Helix on it** (`run_vrp.py`):
  - it patches helix4's prompts to VRP wording, unclips programs (bases shown whole; best block 45k characters), and
    allows 32k-token replies with a 90k-character guidance;
  - `install` (v4), `install47`, `install7` and `install8` (built from one class factory, `_vrp_run_class`);
  - flags `--version v4|v47|v7|v8`, `--seed-program file.py|runs/x/programs.jsonl:pid` (v7/v8 keep Code Zero as
    p0001), `--warm-from DIR` (v8);
  - v7/v8 configs: `gain_floor` 5e-4, `calibrate` 2 (the start evaluated 3 times; the spread is the noise floor),
    `HILL_RADIUS` 0.12.
- **The job** (`scripts/run_vrp_job.sh`):
  - env vars VERSION, SEEDS, GENS, HOURS, MAX_WAIT_MIN, HELIX_EVOLVE, HELIX4_SLOTS_DIR, SEED_PROGRAM, WARM_FROM, FAKE;
  - makes the fake worlds once and runs the runs;
  - scores the 3 best programs of each run, plus the current methods, on the held-out worlds
    (`results/held_out_scores_<v>.md`; the earlier versions' runs are included for comparison);
  - writes `REPORT_<run>.md` for v7/v8 and packs `vrp_results_<v>.tgz`. Nothing is pushed.
- **Score aids:** `score.py` (held-out scoring), `benchmark.py`, `private_report.py`. Tests: `tests/test_vrp.py`
  (63 tests).

## The runs and what they taught (all on fake data on the VM)

| Run | Result |
|---|---|
| v4 atlas-s1/s2, 49 generations | best atlas-s1/p0292: train 1.6443, **held out 1.6961** (+20.8% quality over greedy plus simulated annealing, 1.3865) |
| v4.7 from Code Zero | 1.642 held out: behind v4, maybe noise. Rule 1 closed lines too early |
| v7, warm from p0292, 100 generations | train 1.6505, **held out 1.7060** (+21.6%). Its one change of hill: a bold flip of the shared myopic-greedy start (T40, gen 57) started worse, was woken by a mutation at gen 79, then climbed +0.26% in 22 generations |
| v8, continuing v7 from gen 100 | running. The map begins with 3 hills: T40's (the record), the hill before it (10 of v7's explorations ended there, 9 at distance 0.000 or 0.001), Code Zero's |

**Lessons:**
- **Code-length clipping is a hidden ceiling.** The coder was shown cut-off programs, and children broke.
- **Under a fixed time limit, speed is quality.**
- **Plateaus broke from changing a shared component, not from polishing.**
- **The measured evaluation noise is 0.0012%**, far below the 0.2% assumed earlier, so the 5e-4 floor ignores small
  real gains for pacing. They are still kept.
- **Programs bloat:** 55k → 132k characters in 100 generations.
- **The VM:** about 70 s of CPU per evaluation, about 7–9 minutes a generation with two runs sharing the slots.

**Open questions:**
- How far is the record from optimal? An LP lower bound would tell (task 10).
- Is a genuinely different algorithm family a higher hill? Shreyas believes the VRP has much more room than ac2.

## Real data

Shreyas runs it on his Mac. The package README has the real-data steps: point `--blackbox` at a private folder made
from `blackbox_template/` and run `prepare` there. The winners from fake data get scored on real data. Never upload
real data or real results anywhere an LLM can read.
