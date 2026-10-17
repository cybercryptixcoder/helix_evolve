# Helix

**A team of AI agents that takes a deliberately bad program and keeps improving it, round after round, through two loops working side by side: a deep loop that reasons about why programs work, and a wide loop that explores without direction. Both loops share one evaluator.**

Helix was built by Shreyas Naik and Sai Vikram at a hackathon on October 11, 2026, for Luminal's track *"Build a Self-Improving Agent Team"*, and developed further on October 12. This page explains what we set out to build and why. [HANDOFF.md](HANDOFF.md) has the full story: how it works, every run, what we learned, the mistakes, and what is still unknown.

---

## The vision

Start from the dumbest reasonable program, **Code Zero**, and let a team of LLM agents improve it with nothing else: no hand-written improvements, no hints, no head start. Measure every round against that same starting point, and finally on fresh test cases the search never saw. The question isn't only *how good* the final program gets. It's whether the **structure of the team** makes it improve *faster and further*. Because every run starts from the same Code Zero, runs with different structures can be compared fairly.

The structure we proposed has two loops around one evaluator:

![The original concept: one shared evaluator, a deep loop on the left and a wide loop on the right](docs/original_concept.png)

*The original concept flowchart, from the start of the project ([HTML](docs/original_concept.html)).*

- **One shared evaluator.** The problem lives inside it, and it scores every program as a black box. Both loops pass through it, so their results are directly comparable.
- **The deep loop thinks.**
  - A *Researcher* reads the ranked programs and their scores, works out *why* some did well and others badly, and turns that into hypotheses.
  - A *Coder* writes one program per hypothesis, changing a single thing, like changing one letter in Wordle, so each result says something specific.
  - It keeps what works and goes narrow on purpose.
- **The wide loop explores.** A *Mutator* takes the best programs and writes variants with no research direction. It goes wide on purpose, so the search doesn't narrow too early around one idea.
- **The air gap.** The Mutator only ever sees programs and their scores, never the hypotheses or the research direction. That's what keeps the wide loop wide: if it could read the research, it would follow it, and the team would lose its diversity.
- **Code Zero** seeds both loops. It's First Fit (every bin scores the same, so the oldest bin that fits wins): the honest baseline that every gain is measured from.

Most LLM program search is a single loop of mutation and selection: the wide loop on its own. Helix adds a second, scientific loop beside it and keeps the two apart, to find out whether reasoning and exploration together beat exploration alone. (`--mode wide-only` and `--mode deep-only` run each loop alone as controls.)

## The problem

**Online 2D vector bin packing**, which is how a cloud places virtual machines on servers. Jobs arrive one at a time, each needing some CPU and some memory. Each must be placed at once and for good, on a server with room in both resources or on a new server. Use as few servers as possible.

We chose it because:
- it's measurable;
- it's hard (hard even offline, and here no job can be seen in advance);
- it has well-known heuristics to compare against;
- the best possible packing can be bounded, so we can say how far from perfect a program is, not just how much better than Code Zero.

The agents write one function, `priority(item, bins, capacity)`, which scores the bins a job could go into; the simulator picks the highest. [CONTRACT.md](CONTRACT.md) has the exact rules.

Progress is shown in three units:
- **The evaluator's score:** −(mean % of bins above a simple lower bound). Code Zero scores −9.18.
- **Waste:** extra bins per 100 that the optimal packing needs.
- **Progress to optimal:** 0% = Code Zero, 100% = the optimal packing.

The best classic online heuristic scores 8.9% progress. An offline packer that sees every job in advance scores 40.8%.

## How it's built

The idea stayed the same; *what* the agents write changed once.

**Program engine (version 1, runs 1-3).** Agents write whole programs, numbers included, close to the original concept:
- the Researcher works out why the best program wins by knocking out one part at a time, then proposes improvements;
- Coders write them;
- the Mutator writes variants;
- a small optimiser tunes the numbers in the best programs.

**Feature engine (version 2, the current default).** The first runs showed the agents were good at ideas and bad at numbers, and were judging programs from scores alone. So the work was split:
- agents write *features*: small functions that each measure one thing about a candidate bin;
- an optimiser sets how much each feature counts;
- a feature is kept only if it helps on validation instances the fitting never saw, compared with the same fit without it;
- the Researcher now also sees *how* the policy packs compared with a near-optimal packing of the same jobs. The Mutator still sees only code and a score.

![The current loop: Code Zero feeds the library; the deep loop (Inspect, Researcher, Coder) and the wide loop (Mutator) both feed Fit and accept, which returns the new champion to the library](docs/helix_loops.png)

*The two loops in the current engine ([HTML](docs/helix_loops.html)). [HANDOFF.md](HANDOFF.md) §6-7 has both engines step by step.*

## Where it stands

| Run | Engine | Generations | Best on train | Progress to optimal | Held-out test | Notes |
|---|---|---|---|---|---|---|
| 2 | programs | 30 | −6.793 | 27.4% | −6.755 (25.0%) | The reference run |
| 3 | programs | 17 | −7.511 | 19.1% | −7.161 | Most agent replies were cut off by the model's hidden thinking |
| 4 | features | 10 | −6.185 | 34.3% | −5.971 | **Not comparable:** started from a hand-written head start by mistake (since removed) |
| 5 | features | 10 | −6.986 | 25.1% | −6.703 (25.6%) | The first clean feature-engine run from Code Zero |
| 6 | features (fast loop) | 10 | −7.034 | 24.6% | −6.686 (25.8%) | |
| 7 | features (fast loop) | 25 | **−6.156** | **34.6%** | **−6.001 (33.7%)** | Best from scratch so far |

Every run's full trace (every agent call with its reasoning, every program, generation and feature) is in [`results/`](results/). Run 1 (the first hackathon runs) wasn't kept.

## Read next

| | |
|---|---|
| [HANDOFF.md](HANDOFF.md) | Everything: origin, design, repo map, both engines, every run, what we learned, mistakes, working rules, unknowns, next steps |
| [LUMINAL.md](LUMINAL.md) | Using the Luminal model API: the settings that work and how we found them |
| [CONTRACT.md](CONTRACT.md) | The problem, the program interface and the evaluator |
| [helix/README.md](helix/README.md) | The search loop: dashboard, commands, options |
| [evaluator/README.md](evaluator/README.md) | The evaluator and the baselines |
| [results/](results/) | Full traces of every run |
| [docs/next-concept/](docs/next-concept/) | The next concept: treating improvement as a search space of approaches, pruned by LLM reasoning |

## Quick start

```bash
pip install -r helix/requirements.txt
python -m helix.ui                       # dashboard at http://127.0.0.1:8765
python -m helix.run --fake-llm --generations 2    # offline test, no key needed
```

A real run needs a Luminal API key (see [LUMINAL.md](LUMINAL.md)); paste it under **Connect** on the dashboard.
