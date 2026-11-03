# Helix

**A team of AI agents that writes programs to solve hard problems and keeps improving them, round after round.**
Two loops work side by side around one exact scorer: a reasoning loop that forms a hypothesis about why programs score
as they do and tests one change at a time, and an exploring loop that varies programs without any plan. A memory of
what was tried, and what it showed, carries the work from round to round.

Built by Shreyas Naik (with Sai Vikram for the first version, at a hackathon on October 11, 2026, Luminal's track
*"Build a Self-Improving Agent Team"*), then developed through ten versions to November 2026.

> **Status (November 3, 2026): paused.** Every run, with all its records, is on GitHub (see "Where everything is").
> Any run can be restored exactly and continued.

## Results

The main test problem is the **second autocorrelation inequality**, an open problem in analysis: find a non-negative
step function f that makes R(f) = ‖f∗f‖₂² / (‖f∗f‖₁ · ‖f∗f‖∞) as large as possible. Each function found proves a lower
bound on an unknown constant. A result can't be faked (anyone can compute it from the function), and AlphaEvolve and
later AI systems report their results on it, so it has a public scale.

Every Helix run starts from a constant function (R = 2/3). It runs on **one 2-core ARM cloud machine with no GPU**,
with **one inexpensive model (DeepSeek V4.1 Flash)** and no training.

| What Helix beat | Its value | Best of that Helix run | Which Helix, and how it started | When it passed it |
|---|---|---|---|---|
| AlphaEvolve's first published result (Google DeepMind, May 2025) | 0.8962 | 0.939016 (20 rounds) | v4, from scratch, nothing from outside; 30 s per program | round 10, 57th program |
| The best result found by human researchers (Jaech & Joseph, Aug 2025) | 0.941362 | **0.941441** | v4 → v8, from scratch, nothing from outside, ever; 30-60 s per program | round 352, about 2,220th program |
| OpenEvolve (as reported by TTT-Discover; 25,600 programs of up to 10 min) | 0.9449 | 0.948610 | v10.2, from scratch, given a written summary of published methods; ≤ 50,000 steps, 150 s per program | round 27, 164th program |
| ThetaEvolve with reinforcement learning at test time (33,280 programs) | 0.9469 | **0.948610** | the same run | round 227, 1,419th program |

Not beaten: TTT-Discover (0.9591) and AlphaEvolve V2 (0.9610) at the same size limit, and the best known value,
0.963588 (at 2 million steps, polished on GPUs). Starting from other people's best constructions, Helix made no
meaningful gain. The v10.2 figures come from one of its two runs; the other ended at 0.941244.

**[docs/RECORDS.md](docs/RECORDS.md) has the evidence for every row:** where each outside value comes from (paper and
table), the exact run, round and program, the limits, the machine and model, links to every program and every model
call (full prompt and reply) of the run, what each comparison does not control for, and how each number was
re-checked. Each result is certified by exact rational arithmetic.

Check them yourself (a few minutes on a laptop):

```bash
git clone https://github.com/cybercryptixcoder/helix_evolve && cd helix_evolve
pip install numpy scipy
python tools/verify_ac2.py --alphaevolve-may-2025 \
  results/v4/atlas-s1/best.npy results/v8warm/v8-s1/best.npy results/v102/v102-helix/best.npy
```

**On nine other optimisation problems** (knapsack, scheduling, set cover, travelling salesman, vehicle routing,
job-shop, graph colouring, 1D and 2D bin packing), Helix v3 beat each problem's textbook rule on instances it never saw
during the search, with no change to the system between problems ([table](docs/RECORDS.md#other-problems-helix-v3-october-17)).

## How it works

![Two loops around one judge: the exploring loop (Mutator) and the reasoning loop (Researcher, Coder) both send programs to one exact evaluator](docs/helix_two_loops.png)

Each round:
1. **The exploring loop** picks parent programs from everything found so far and asks the model for variants. It sees
   only code and scores, never the plan, so it stays a source of surprises.
2. **The reasoning loop** reads a map of its memory and opens only what it needs; a planning agent decides what to
   test next, why, and what it expects; coding agents write those experiments.
3. **The scorer** (plain code, no model) runs every program under a CPU-time limit and scores it exactly.
4. **A recording agent** turns the results into findings, each tied to its evidence, and adds them to the memory.

Nothing is deleted, and no agent keeps a conversation: only the programs and the memory carry over. The exploring loop
gets lucky; the reasoning loop works out why, and builds on it.

Later versions add what the traces showed was missing: side lines of exploration judged on their own progress (v7), a
register of the distinct solution families found, measured by code (v8), a map of the design choices behind every
program (v9), the published methods as choices on that map (v10), and new designs built from nothing and judged on
their own climb (v10.2). Every version, what it tried, and what happened: [docs/VERSIONS.md](docs/VERSIONS.md).

## Reproducing a run

The record runs used the job scripts in [`scripts/`](scripts/) (for example
[`scripts/run_v102.sh`](scripts/run_v102.sh); its header lists every setting) on the machine described above, with
the settings recorded in each run's `summary.json`. A run needs an API key for DeepSeek V4.1 Flash on Luminal, in a
`.env` file ([LUMINAL.md](LUMINAL.md)). A new run is a new sample: the model's replies aren't seeded, so the numbers
differ from run to run, as the two v10.2 seeds did.

To continue one of these runs exactly where it stopped, restore its folder (next section) into `runs/` and start its
job script again with more rounds (`GENS=...`): every job resumes from its saved state.

## Where everything is

| What | Where |
|---|---|
| Every run's records: every program with its code and score, every model call with its full prompt and reply, every round, the settings, the best construction | [`results/`](results/), one folder per version and run |
| Every construction of the later runs (thousands per run) | GitHub releases `constructions-*` ([helix9/vault.py](helix9/vault.py)) |
| A byte-for-byte copy of every run folder as it was on the machine, with every file's SHA-256 | GitHub releases `archive-*`; restore with `python3 tools/offload.py restore --unit <unit> --out <dir>` ([docs/OFFLOAD.md](docs/OFFLOAD.md)) |
| The published constructions used for comparison | [`data/field_ac2/`](data/field_ac2/) |
| Design documents, job instructions, analyses of every run | [`docs/`](docs/) |
| The research question this work became | [docs/RESEARCH_CASE.md](docs/RESEARCH_CASE.md) |
| The first README (hackathon to October 2026), with the bin-packing runs | [docs/README_2026-10.md](docs/README_2026-10.md) |

## Running it

```bash
pip install -r helix/requirements.txt
python -m helix.run --fake-llm --generations 2    # the original loop, offline, no key needed
python -m helix.ui                                # its dashboard at http://127.0.0.1:8765
```

The autocorrelation versions run from their job scripts (`scripts/run_v*.sh`, each with a `FAKE=1` test mode);
[docs/AETHER.md](docs/AETHER.md) describes how long jobs are run on the cloud machine.
