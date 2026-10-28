# Helix: the publication bar and a research direction

October 27, 2026 (late). A first survey, after the advisor's review asked two things: what a publication in this area
looks like (is improving one problem, AC2, publishable, or only a method that improves many?), and what similar work
exists in other contexts, so the project can be positioned and defended against "it is a rearrangement of known
parts". The brief for a fuller, unbiased survey by a separate agent is `docs/SURVEY_BRIEF.md`; this document is my own
reading, and that survey should confirm or correct it.

**In short.** Improving the second autocorrelation inequality (AC2) alone will not carry a paper at an ML venue, and
our record of 0.94144 sits below seven published results from AI systems. The strongest route to a paper is to make
Helix an instrument: test, on public traces from other systems as well as ours, whether a model-built map of design
decisions is read reliably and predicts which changes help.

## One problem or many: what got published

Main tracks accepted methods shown on four to nine problems or domains; the one two-problem method appeared as a
workshop poster. Single-problem papers on AC2 are mathematics, and the one in a journal carries analysis, not only a
number.

| Work | Problems | What it contributed | Where |
| --- | --- | --- | --- |
| [FunSearch](https://pmc.ncbi.nlm.nih.gov/articles/PMC10794145) (2023) | Cap set and online bin packing at its core | A method, and new results on a famous open problem | Nature |
| [AlphaEvolve](https://arxiv.org/abs/2506.13131) (2025) | Many in mathematics, plus Google's computing stack; AC2 (0.8962) was one result among them | A system and its results | White paper and arXiv; no peer-reviewed venue found, including in DeepMind's [May 2026 update](https://deepmind.google/blog/alphaevolve-impact/) |
| [Georgiev, Gómez-Serrano, Tao, Wagner](https://arxiv.org/abs/2511.02864) (2025) | 67 | AlphaEvolve at scale, with Deep Think and AlphaProof; what makes a problem suitable | arXiv |
| [ShinkaEvolve](https://iclr.cc/virtual/2026/poster/10007692) | 4 domains | Sample efficiency: a circle packing record in 150 samples | ICLR 2026, poster |
| [TTT-Discover](https://icml.cc/virtual/2026/spotlight/84891) | 4 domains, 2 in mathematics | Reinforcement learning at test time on an open model | ICML 2026, spotlight |
| [CodeEvolve](https://aclanthology.org/2026.findings-emnlp.1345/) | AlphaEvolve's 9 problems, plus heuristic design | An open framework; an open-weight model at about a tenth of the cost | Findings of EMNLP 2026 |
| [ImprovEvolve](https://icml.cc/virtual/2026/82453) | 2: hexagon packing and AC2 | Evolving the operators of basin hopping | ICML 2026 AI for Math workshop, poster |
| [ThetaEvolve](https://arxiv.org/abs/2511.23473), [GigaEvo](https://arxiv.org/abs/2511.17592), [AlphaResearch](https://arxiv.org/abs/2511.08522) | 4, 5 and 8 | Open frameworks, test-time RL, a benchmark | arXiv |
| [Simple Baselines](https://arxiv.org/abs/2602.16805) | 4 domains, including 9 math problems | A critique: two simple baselines match complex pipelines | arXiv |
| [What Do Evolutionary Coding Agents Evolve?](https://arxiv.org/abs/2605.20086) | 16 tasks, 4 frameworks | An analysis of search traces, and a public dataset | arXiv |
| [Matolcsi and Vinuesa](https://real.mtak.hu/7892/) (2010) | 1: AC2 | A construction and its analysis | Journal of Mathematical Analysis and Applications |
| [Boyer and Li](https://arxiv.org/abs/2506.16750); [Jaech and Joseph](https://arxiv.org/abs/2508.02803) (2025) | 1: AC2 | Constructions found by annealing and by gradient descent | arXiv; no journal reference listed |

So, on the first question: AlphaEvolve did not publish on AC2 alone, and no ML venue in this list accepted a
single-problem result.

## Where our AC2 result stands

Published lower bounds, higher is better. Budgets differ by orders of magnitude (from $20 runs to about $500 a run),
and some systems used frontier models, so this is not a fair race. Its point is narrower: our number beats only the
best result without an LLM, by 0.00008, so it cannot carry a paper on its own. (A chart of the same values is in the
shared doc.)

| Result | Value | Source |
| --- | --- | --- |
| ImprovEvolve + expert edit (2026) | 0.96258 | [ImprovEvolve](https://arxiv.org/abs/2602.10233) |
| AlphaEvolve V2 | 0.96102 | ImprovEvolve; [TTT-Discover](https://arxiv.org/abs/2601.16175) gives 0.9610 |
| TTT-Discover, gpt-oss-120b | 0.9591 | TTT-Discover |
| ImprovEvolve, Gemini 3 Flash | 0.9512 | ImprovEvolve |
| TTT-Discover, Qwen3-8B | 0.9472 | TTT-Discover |
| ThetaEvolve, 8B model | 0.9469 | ImprovEvolve; TTT-Discover gives 0.9468 |
| OpenEvolve, gpt-oss-120b | 0.9449 | TTT-Discover |
| **Helix v8 (ours), DeepSeek V4.1 Flash** | **0.94144** | v8-s1, verified three ways |
| Jaech and Joseph, Adam (no LLM) | 0.94136 | [Jaech and Joseph](https://arxiv.org/abs/2508.02803) |
| GigaEvo | 0.94063 | ImprovEvolve |
| Best of 25,600 samples, gpt-oss-120b | 0.9344 | TTT-Discover |
| Boyer and Li, annealing (no LLM) | 0.90156 | [Boyer and Li](https://arxiv.org/abs/2506.16750) |
| AlphaEvolve, May 2025 | 0.8962 | AlphaEvolve |
| ShinkaEvolve at $20 | 0.8955 | [Simple Baselines](https://arxiv.org/abs/2602.16805) |
| Matolcsi and Vinuesa (2010, no LLM) | 0.88922 | [Matolcsi and Vinuesa](https://real.mtak.hu/7892/) |
| CodeEvolve | 0.8811 | ImprovEvolve |
| Sequential sampling at $20 | 0.8795 | Simple Baselines |
| Independent sampling at $20 | 0.8739 | Simple Baselines |

## What reviewers and critics now expect

The field has turned sceptical of complex search pipelines: a paper must show that its machinery beats simple
baselines at equal cost, or it must claim something other than a better search.

- **Simple baselines at a matched budget.** With $20 a problem, sequential sampling without fitness selection matched
  or beat ShinkaEvolve on 6 of 9 math problems. The authors conclude that the search space matters far more than the
  search algorithm ([Simple Baselines](https://arxiv.org/abs/2602.16805)).
- **Matched conditions, stated.** Same models, same domain knowledge in prompts, same verifier and budget, and the
  binding constraint named. A paper should say whether it proposes a search method or reports a discovery (Simple
  Baselines).
- **A tuning ceiling beside every headline.** Bayesian optimisation of the constants in intermediate programs matched
  or beat the run's final best in 13 of 15 cases. About 30% of the lines added during search re-introduce lines
  deleted earlier ([EvoTrace](https://arxiv.org/abs/2605.20086)).
- **Full configurations, costs, comparisons and contamination checks.** Report models, iterations and cost; compare
  with the starting program and the state of the art; check whether a result is a rediscovery
  ([Barbarians at the Gate](https://arxiv.org/abs/2510.06189)).
- **Robust verifiers.** Searches exploit leaky numerics; continuous losses help; and the method suits constructions
  already within reach, not problems needing deep new insight ([Georgiev et al.](https://arxiv.org/abs/2511.02864)).
- **Several seeds, with confidence intervals,** where evaluations are noisy (Simple Baselines).

## The work closest to each Helix mechanism

Every Helix mechanism has close relatives; what differs is the setting and how they are combined. This pass was
narrow, so treat the survey agent's Part 2 as the reference.

| Helix mechanism | Closest in LLM program search | In other fields | How the setting differs |
| --- | --- | --- | --- |
| The design map: a codebook of design decisions the model builds and keeps tidy, with every program placed on it | [EvoTrace](https://arxiv.org/abs/2605.20086): a model labels each edit with one of 9 fixed types, κ 0.77 against people. [QDAIF](https://arxiv.org/abs/2310.13032): a model judges diversity on axes people choose | Codebooks and inter-rater agreement in qualitative research | Helix's decisions are specific to the problem and found during the search |
| The landscape model, and changes chosen from it by Thompson sampling | [AlphaMemo](https://arxiv.org/html/2606.20625v1): edit motifs from syntax-tree diffs, outcomes kept as Beta posteriors. [LineageEvo](https://arxiv.org/html/2610.29663): experience and budget per lineage | Importance of hyperparameters by functional ANOVA; ablation analysis between configurations; [LLAMBO](https://arxiv.org/abs/2402.03921), an LLM inside Bayesian optimisation | AlphaMemo and LineageEvo search short formulas for trading signals; Helix searches whole programs |
| Drops, flips and ablations of strong programs | EvoReplay (in EvoTrace): re-tunes constants, removes components and swaps models at past search states | Ablation studies; delta debugging | EvoReplay analyses after the fact; Helix uses interventions as moves |
| The race between explorations, with a waiting queue | ShinkaEvolve: a bandit over models. Islands in CodeEvolve. LineageEvo: budget across lineages | Successive halving and Hyperband; population-based training; racing in algorithm configuration | Helix's lines are explorations of a design decision, judged at rungs |
| Memory across runs and versions: the Atlas, the register of hills, warm starts | ThetaEvolve and ImprovEvolve restart from earlier best solutions. [EinsteinArena](https://arxiv.org/abs/2606.10402): agents borrow ideas through forums. [PhyloEvolve](https://arxiv.org/pdf/2601.14523): a tree of variants with scored modifications | Tabu lists; archives in open-ended search | To be mapped by the survey (family M5) |
| The simulator of planted worlds, for testing search policies | None found in this pass | NK landscapes and benchmark generators in evolutionary computation | To be mapped by the survey (family M6) |
| A cheap model on a CPU-only machine | CodeEvolve: an open-weight model at about a tenth of the cost. ThetaEvolve: an 8B model. TTT-Discover: about $500 a run | Compute-efficiency studies | Helix v9 measured about $0.10 a generation |

On the second question: the defence against "rearrangement" is unlikely to be a single new mechanism. It is more
likely a question the literature itself leaves open, measured carefully; EvoTrace's authors, for instance, call for
interventions against cycling. The next section names one such question.

## Four directions compared

Direction A is the only one that is both open, as far as this pass shows, and affordable on our machine. B is the
conventional method paper, but its compute is out of reach for now; C is best folded into A; D is closed to us.

| Direction | The question | Data and cost | What it must show | Venue | Main risk |
| --- | --- | --- | --- | --- | --- |
| **A. The design map as an instrument** | Can a model build a map of design decisions that is read reliably, predicts which changes help, and explains cycling, on any system's search, not only ours? | [EvoTrace](https://huggingface.co/datasets/ZIB-IOL/EvoTrace) is public: 121 runs, 16 tasks, 4 frameworks, 5 models, about 10,700 programs. Plus Helix's own runs. Model calls only; my estimate is tens of dollars to read EvoTrace once, to be measured in a pilot | Agreement between readings, checked against a person on a sample; a held-out test of prediction against baselines (score alone, EvoTrace's edit types, code similarity); replication across tasks and frameworks; tests fixed in advance | A workshop first; then ICML 2027 (paper due about January 22, projected) or NeurIPS 2027 (about May 21, projected) | The signal is weak: our one test gave +0.16 (p = 0.04) on 120 changes, and may not replicate |
| **B. A matched-budget method study** | Do Helix's map, race and memory beat simple baselines and open frameworks at equal cost? | AlphaEvolve's 9 math problems, the same model, $20 a problem, at least 3 seeds, an ablation per mechanism. ShinkaEvolve took about 10 hours a problem in Simple Baselines: by my estimate, a thousand machine-hours in all | Wins over both simple baselines and ShinkaEvolve, with confidence intervals; each mechanism paying its way | ICML 2027 or NeurIPS 2027 | The critique literature finds complex pipelines rarely win; our 2-core shared machine cannot run it |
| **C. Long-horizon traces as data** | What happens over 700 and more generations: plateaus, cycling, hills? | Helix's runs, with every model call logged | A clean, documented release, with analyses that extend EvoTrace's 100-iteration runs | NeurIPS 2027 Datasets and Benchmarks, or as part of A | Thin as a paper on its own |
| **D. AC2 as mathematics** | A better bound, with structure or a proof | Large search spaces and compute | A value above 0.96258, plus analysis | A mathematics journal | Out of reach: seven AI results are already above ours |

## Recommendation, and the next four weeks

Take A as the main line, with C as its dataset. Keep B for later, and only if A shows the map helps. Stop treating
the AC2 record as a goal: let the v9 run finish, and use its traces as data for A.

The paper A would make: an LLM-built map of design decisions, applied to search traces from four frameworks and to
our own long runs. It reports how reliably the map is read, whether it predicts which changes help better than
simpler signals, and whether it explains the cycling EvoTrace measured. A clear negative result would still be
publishable at a workshop.

- [ ] Hand the survey brief to the agent; read Part 1 when it lands.
- [ ] Download EvoTrace and check that it holds what readings need: full programs, parents, diffs, scores.
- [ ] Pilot: run the replay on three EvoTrace runs (an autocorrelation task, circle packing, one ALE task) and
      measure agreement, the predictive test and cycling.
- [ ] Write a one-page plan of A's tests, fixed before the full analysis.
- [ ] After the pilot, choose the venue: a workshop first, or straight to ICML 2027.

The EvoStar 2027 deadline (November 16, EvoLLMs track; [EvoStar 2027](https://www.evostar.org/2027/?p=25)) is too
close for A unless the pilot is unusually quick.

## Sources

- [Simple Baselines are Competitive with Code Evolution](https://arxiv.org/abs/2602.16805) (Gideoni, Risi, Gal; v2 October 2026)
- [What Do Evolutionary Coding Agents Evolve?](https://arxiv.org/abs/2605.20086) (Pelleriti et al., May 2026); [EvoTrace dataset](https://huggingface.co/datasets/ZIB-IOL/EvoTrace)
- [Learning to Discover at Test Time](https://arxiv.org/abs/2601.16175) (TTT-Discover); [ICML 2026 spotlight](https://icml.cc/virtual/2026/spotlight/84891)
- [ImprovEvolve](https://arxiv.org/abs/2602.10233); [ICML 2026 AI for Math workshop poster](https://icml.cc/virtual/2026/82453)
- [ShinkaEvolve at ICLR 2026](https://iclr.cc/virtual/2026/poster/10007692)
- [CodeEvolve, Findings of EMNLP 2026](https://aclanthology.org/2026.findings-emnlp.1345/)
- [ThetaEvolve](https://arxiv.org/abs/2511.23473); [GigaEvo](https://arxiv.org/abs/2511.17592); [AlphaResearch](https://arxiv.org/abs/2511.08522)
- [AlphaEvolve](https://arxiv.org/abs/2506.13131); [AlphaEvolve impact update, May 2026](https://deepmind.google/blog/alphaevolve-impact/)
- [Mathematical exploration and discovery at scale](https://arxiv.org/abs/2511.02864)
- [FunSearch](https://pmc.ncbi.nlm.nih.gov/articles/PMC10794145)
- [Barbarians at the Gate](https://arxiv.org/abs/2510.06189); [EinsteinArena](https://arxiv.org/abs/2606.10402)
- [AlphaMemo](https://arxiv.org/html/2606.20625v1); [LineageEvo](https://arxiv.org/html/2610.29663); [PhyloEvolve](https://arxiv.org/pdf/2601.14523)
- [QDAIF](https://arxiv.org/abs/2310.13032); [LLAMBO](https://arxiv.org/abs/2402.03921)
- AC2 constructions: [Matolcsi and Vinuesa](https://real.mtak.hu/7892/); [Boyer and Li](https://arxiv.org/abs/2506.16750); [Jaech and Joseph](https://arxiv.org/abs/2508.02803)
- Venues: [EvoStar 2027](https://www.evostar.org/2027/?p=25); [ICML 2027, projected](https://www.opencurious.com/ai-conference-deadlines/icml-2027); [deadline list](https://opencurious.com/ai-conference-deadlines)
