# Helix: the research question and the case for it

October 27, 2026 (late). Written as the case for pursuing a paper with the advisor; it replaces the narrower first
pass in `docs/RESEARCH_DIRECTION.md` (kept for its tables). Shared as a doc too, with two diagrams; this is the text.

**In short.** Discovery systems built on language models search inside the space their model already imagines.
Helix's work points to a question about getting past it: can a discovery system map the space it searches, steer to
where its model would not go, and change that space when it runs dry? We have a working instrument and early evidence.
A problem suite, matched-budget comparisons and three measurements make this a paper of the Go-Explore kind (a
diagnosis, a principle, a method and broad evidence), aimed at NeurIPS 2027.

## The question

Every LLM-guided discovery system samples programs from its model's prior and keeps those that score well. Selection
in effect re-weights what the model proposes. So the search inherits the model's habits: its default designs, and the
assumptions every program shares.

The research question: **can a discovery system map the space it searches, steer to where its model would not go, and
change that space when it runs dry?**

The principle we propose: make the design space explicit, move in it on purpose, and change it when it is exhausted. A
design space is the set of decisions every program answers (how a solution is represented, what is optimised, how a
first solution is built, how bad moves are escaped), with the options for each. A program's answers are its
coordinates.

Three ways past a model's prior, by where they act on the search loop (selection, then prompt, then model, then
evaluator, and back):

| Approach | Acts on | What it does | Examples | Its reach |
| --- | --- | --- | --- | --- |
| Re-weight | Selection | Shows the model different past programs | FunSearch, AlphaEvolve, OpenEvolve, ShinkaEvolve | Stays near what the model has already written |
| **Re-represent** | **The prompt** | **Asks for coordinates on an explicit map of design decisions** | **PlanSearch, Idea Search; Helix builds the map and changes it** | **Reaches regions no program has visited, without training** |
| Retrain | The model | Changes the model's weights on search data | SOAR, TTT-Discover, ThetaEvolve | Moves the prior itself, at the cost of GPUs |

## Why now

The field's most visible recent results all point at the same bottleneck: models generate inside a narrow space, and
more search or more training mostly re-weights it. Recent systems have begun to write ideas down (Idea Search, PIEVO,
below). As far as we found, none treats the design space as a coordinate system that the search builds, moves in on
purpose, and changes.

| Finding | Where | What it means for discovery systems |
| --- | --- | --- |
| Models repeat themselves, and different models give nearly the same answers ("Artificial Hivemind") | [NeurIPS 2025, best paper](https://blog.neurips.cc/2025/11/26/announcing-the-neurips-2025-best-paper-awards/) | Generators share narrow priors, so swapping models does not by itself widen the search |
| Reinforcement learning on verifiable rewards does not reach beyond what the base model can already sample; distillation from another model does | [NeurIPS 2025, oral and best-paper runner-up](https://neurips.cc/virtual/2025/oral/119945) | Learning from one's own outputs narrows; new regions need a signal from outside the prior |
| Diversity at the level of ideas, not code, is what turns more samples into more solved problems (PlanSearch) | [ICLR 2025](https://iclr.cc/virtual/2025/poster/31034) | Search should happen in idea space; code is the wrong level |
| Models fail to explore in simple bandit tasks unless handed summary statistics, which the authors doubt can be built for complex settings | [NeurIPS 2024](https://arxiv.org/html/2403.15371v3) | An external, summarised map is what makes a model explore; building one for open-ended search is open |
| Simple samplers match elaborate pipelines; the search space matters more than the search algorithm, and widening it helps every pipeline | [Simple Baselines, 2026](https://arxiv.org/abs/2602.16805) | The space is the lever: a system that widens its own space attacks the bottleneck directly |
| About 30% of the lines added in a search re-introduce lines deleted earlier; the authors call for search that remembers what it discarded | [What Do Evolutionary Coding Agents Evolve?, 2026](https://arxiv.org/abs/2605.20086) | Systems do not know, at the level of design, what they have already tried |
| The advice in the prompt strongly shapes results, different models suggest very different approaches, and the method is "likely not the right tool" where deep new insight is needed | [Georgiev, Gómez-Serrano, Tao, Wagner, 2025](https://arxiv.org/abs/2511.02864) | Expert framing is a hidden input; a system that finds its own framing is the open step |
| The population a search keeps collapses even while the generator stays varied; code novelty barely tracks functional novelty | [NeurIPS 2026 workshop paper](https://neurips.cc/virtual/2026/175781) | Diversity must be measured and steered at the level of design, not text |
| AI agents are argued to be unable to change their own conceptual space (Boden's "transformational creativity"), and testing for it "may be an unsolved problem" | [Franceschelli and Musolesi, 2026](https://www.emergentmind.com/papers/2604.13242); [Schapiro, Black, Varshney, 2025](https://arxiv.org/html/2504.18687v1) | An operational test, and a system that passes it, would be a contribution in its own right |

There is also a NeurIPS 2026 workshop named for this problem, "Self-Evolving Diversity-Driven Search for Robust AI
Systems" ([workshop list](https://blog.neurips.cc/2026/08/10/announcing-the-neurips-2026-workshops/)).

## Three research questions

Each question stands on its own, and each teaches something whatever the answer. Together they test one thesis:
discovery past the prior needs an explicit, changeable map of the design space.

**RQ1. Where do LLM-guided searches go, and why do they stall?**

- **Measured by:** the design coordinates of fresh programs sampled from several models (how concentrated is each
  model's prior over a problem's design space?), and of whole search trajectories from several frameworks: ours, and
  the 121 public runs of four frameworks in [EvoTrace](https://huggingface.co/datasets/ZIB-IOL/EvoTrace). Also:
  cycling at the level of design, the decisions every program shares (invariants), and whether early height predicts a
  region's final height.
- **We expect:** searches stay in a few basins of the prior; stalls coincide with axes worn out and invariants never
  varied; early height says little about final height.
- **It teaches:** a measured account of why LLM discovery plateaus, across models and frameworks.

**RQ2. Can a search map its own design space, and use the map to go where its model would not?**

- **Measured by:** how reliably the map is read (agreement between readings, and with a person on a sample); whether
  it predicts which changes help; and, at matched budget, distinct hills reached, best score, coverage of the design
  space, and how often the best region lies where the prior rarely goes.
- **Baselines:** independent sampling, sequential sampling, OpenEvolve, ShinkaEvolve, and generic diversity methods
  (higher temperature, verbalized sampling, PlanSearch-style ideas), so the gain can be traced to the map rather than
  to diversity alone.
- **We expect:** asking for untried coordinates reaches more distinct hills, and taller ones where the best lies
  outside the prior's wells.

**RQ3. Can a search change its own space, and is that where breakthroughs come from?**

- **Measured by:** decisions that every program shares, found and then changed (an operational test of changing the
  space); the share of record jumps that follow such a change; whether the chance of a breakout rises with a plateau's
  age; and replays from earlier states, to see whether progress was building up unseen.
- **We expect:** the largest jumps follow changes to invariants, as in the routing case below: the machine analogue of
  insight by constraint relaxation ([Knoblich, Ohlsson et al., 1999](https://www.kognition.uni-koeln.de/literature/Knoblich_etal_1999.pdf)),
  and an operational version of Boden's transformational creativity.
- **It teaches:** whether "insight" in machine search is real, measurable and engineerable.

## What we already have

| Finding | Measured | Where |
| --- | --- | --- |
| Restarts return to the model's default basin | 19 of 19 fresh restarts peaked at or below 0.8825, the textbook construction | `docs/SEARCH_SPACE.md` |
| A region's height is invisible from its foot | Rank correlation -0.09 between a run's best after 20 programs and its final best (15 runs); the eventual record's run was 4th lowest of 15 at that point | `docs/SEARCH_SPACE_MODEL.md` |
| New ideas are erased before they are judged | Children handing back their start unchanged rose from 31% to 72%; the planner called the point "saturated" in 15%, then 95%, of its analyses, but the memoryless mutator stalled too: the cause is mostly the machinery | `docs/V4_CEILING.md` |
| A breakthrough came from changing an invariant | Routing: replacing the greedy start that every program shared gave +0.26% in the next 22 generations, against +0.11% in the 78 before | `docs/SEARCH_SPACE.md` |
| The design vocabulary converges | About 98% of 656 decision names fall into 9 recurring axes | `docs/SEARCH_SPACE_MODEL.md` |
| The model is a noisy decoder, and the landscape has neutral ridges | One-decision changes often changed several; the faithful ones reached the record's height on a different shape | `docs/SEARCH_SPACE_MODEL.md` |
| The map can be read reliably | 12 of 13 decisions read with at least 80% agreement, live, on 458 programs; it ranks 120 later changes better than chance (+0.16, p = 0.04) | `results/v9warm/replay/REPLAY.md` |
| Steering by the map works where the truth is known | Planted worlds: the taller hill reached in 43.9% of runs, against 36.4% without coordinates (280 worlds, p < 0.001); a simple sampler about 14% in an earlier batch; breadth is essential | `docs/V9_SIM.md` |
| The real model follows a blueprint | On a live planted problem, the coder built 8 of 9 target decisions and the run reached the taller hill | `docs/V9_DESIGN.md` |

Results that showcase it: the second autocorrelation inequality at 0.94144, above the best published human result
(0.94136), with an inexpensive model on a 2-core CPU machine at about $0.10 a generation; a real-data routing case
(private; reported only with the data owner's permission); and the instrument itself (nine versions, runs past 700
generations with every model call logged, a simulator with planted worlds, an offline replay, a live viewer,
continuation from GitHub alone).

## Where it sits, and what is ours

| Approach | Recent work | What it does | Where Helix goes further |
| --- | --- | --- | --- |
| Re-weight | [ShinkaEvolve](https://iclr.cc/virtual/2026/poster/10007692) (ICLR 2026), [VendiEvolve](https://genaicreativity.org/icml2026/files/40/40_paper.pdf), [EvoDiverse](https://arxiv.org/html/2606.10587v1), MAP-Elites in AlphaEvolve and OpenEvolve, [QDAIF](https://arxiv.org/abs/2310.13032) | Diversity through selection, on axes people choose or on code embeddings | Axes found by the search, per problem, driving what the model is asked to write |
| Retrain | [SOAR](https://arxiv.org/pdf/2507.14172) (ICML 2025), [TTT-Discover](https://arxiv.org/abs/2601.16175) (ICML 2026), [ThetaEvolve](https://arxiv.org/abs/2511.23473) | Moves the prior itself; GPUs and hundreds of dollars a problem | No training: the same effect sought by conditioning, on any model, on a CPU |
| Re-represent | [PlanSearch](https://iclr.cc/virtual/2025/poster/31034) (ICLR 2025), [Idea Search](https://arxiv.org/html/2608.08958), [EvoLattice](https://arxiv.org/html/2512.13857v2), [PIEVO](https://arxiv.org/html/2602.06448v1), [ImprovEvolve](https://arxiv.org/abs/2602.10233) | A flat bank of ideas scored by use; a fixed change of what is evolved; principles grown when results surprise | Coordinates (decisions with exclusive options); interactions make hills; equal-effort judgement; the space changed by finding what every program shares |
| Analyse | [EvoTrace](https://arxiv.org/abs/2605.20086), [Simple Baselines](https://arxiv.org/abs/2602.16805), [What Makes an LLM a Good Optimizer?](https://arxiv.org/html/2604.19440), [a landscape study](https://pith.science/paper/2504.19636) | Edit types, cycling, baselines, trajectories of 30 to 100 iterations | Design-level measurement across frameworks, and long horizons |

Concepts from other fields: Go-Explore's cells, with learned cells as its future work
([Nature 2021](https://arxiv.org/abs/2004.12919v3)); learned quality-diversity descriptors
([AutoQD](https://arxiv.org/html/2506.05634v1)); Bayesian optimisation over a
[growing search space](https://papers.nips.cc/paper/9350-bayesian-optimization-with-unknown-search-space); potentiation
in evolution ([Ferguson and Lalejini, 2026](https://arxiv.org/abs/2608.09833)); insight as representational change,
found by noticing invariants (Kaplan and Simon) and reached by relaxing constraints (Knoblich, Ohlsson et al.).

What is ours: (1) an account (LLM discovery is bounded by its generator's prior; the ways past it fall into three
kinds; it predicts why simple baselines compete); (2) a principle (make the design space explicit, move in it on
purpose, change it when it runs dry); (3) its instrument, Helix, which does all three without training; (4)
measurements not yet made, as far as we found, at the level of design, across models and frameworks, over long
horizons. On "rearrangement": Go-Explore's parts all existed before it; the diagnosis, the principle and the evidence
made it a landmark. That is the shape of this paper.

## What kind of paper this is

| Kind | Exemplars | What carried it | How we use it |
| --- | --- | --- | --- |
| A discovery on one or a few problems | FunSearch (Nature 2023); single-problem bounds such as Matolcsi and Vinuesa (2010) | A result that matters to the problem's own field; AlphaEvolve reported its autocorrelation bound as one result among many | Our records and the routing case are the showcase, not the claim |
| A method that wins across problems | EoH (ICML 2024), MCTS-AHD (ICML 2025), ShinkaEvolve (ICLR 2026), CodeEvolve (EMNLP Findings 2026) | Gains at matched cost across a suite, simple baselines, ablations, several seeds | The standard of evidence we meet |
| A concept: a named failure, a principle, a method and broad evidence | Go-Explore (Nature 2021), PlanSearch (ICLR 2025), OMNI (ICLR 2024), Darwin Gödel Machine (ICLR 2026) | A diagnosis people recognise at once, a simple principle that answers it, evidence the principle is the cause | Our target |
| The science of a phenomenon | RL and the base model, Artificial Hivemind (NeurIPS 2025 awards), LLMs and in-context exploration (NeurIPS 2024) | A careful answer to a question many people care about | The shape of RQ1 and RQ3 |

Working titles: *Beyond the Prior: Discovery Systems that Map and Reshape Their Own Search Space*; *First Map, Then
Move: Exploring Past a Language Model's Prior in Program Discovery*; *Impasse and Insight in LLM-Guided Search* (an
RQ3 companion).

## The plan (to NeurIPS 2027, projected May 21; an ICML 2027 version only if December's pilots are strong)

| Work package | When | What | Cost (estimate) |
| --- | --- | --- | --- |
| 1. Suite and baselines | Nov 2-22 | About 10 problems (autocorrelation inequalities, Erdős minimum overlap, circle packing n = 26 and 32, Heilbronn; online bin packing, a routing heuristic, two or three ALE-Bench Lite tasks); independent and sequential sampling, OpenEvolve, ShinkaEvolve; same model and budget | Our time |
| 2. RQ1: priors and trajectories | Nov 9 - Dec 13 | 200 fresh programs per problem from three models; EvoTrace's 121 runs and ours, all read onto the map | Under $200 |
| 3. RQ2: is the map valid? | Nov 23 - Dec 20 | Reliability across problems and frameworks; a person labels a sample; predictive tests against simpler signals | Tens of dollars |
| Pilot results: go or adjust | Dec 20 | | |
| 4. RQ2: steering at matched budget | Dec 7 - Mar 7 | Suite x methods x 3 seeds at $20 a run; ablations: coordinates against generic diversity, the race, discovery, model-chosen against random targets | $2,000-5,000 of model calls; about 2,500 CPU-hours |
| 5. RQ3: changing the space | Jan 4 - Mar 28 | Invariants found and changed; which jumps follow them; plateau timing; replays | Hundreds of dollars |
| 6. Writing | Mar 29 - May 21 | The paper, released traces and code | |

## What it opens up

Insight in machine search (RQ3 at full depth, with our long traces as a dataset); transfer across problems (which
decision was the lever becomes a prior for the next); training from the map (does fine-tuning on map-guided search widen
the base model's reach, the persistence question made testable); explainable discovery for mathematicians; real-world
optimisation where practitioners need to trust an evolved method; an evolutionary agent for open-ended tasks.

## What to decide together

1. The claim to commit to: one paper with RQ1, RQ2 and first RQ3 results, or RQ1 and RQ2 now with RQ3 as a companion.
2. Venue and date: NeurIPS 2027; an ICML 2027 version only if the December pilots are strong.
3. Compute: about 2,500 CPU-hours and $2,000-5,000 of model calls (cluster, cloud credits or a grant).
4. Rigour: fix predictions and analyses before the main comparison; a second rater for the map's human check.
5. The showcase: whether the real-data routing case can be reported, with the data owner's permission.

Further sources (besides those linked above): [Intelligent Go-Explore](https://arxiv.org/abs/2405.15143v3);
[OMNI](https://mlanthology.org/iclr/2024/zhang2024iclr-omni); [Darwin Gödel Machine](https://iclr.cc/virtual/2026/poster/10007327);
[EoH](https://proceedings.mlr.press/v235/liu24bs.html); [MCTS-AHD](https://mlanthology.org/icml/2025/zheng2025icml-monte);
[CodeEvolve](https://aclanthology.org/2026.findings-emnlp.1345/); [FunSearch](https://pmc.ncbi.nlm.nih.gov/articles/PMC10794145);
[Verbalized Sampling](https://icml.cc/virtual/2026/poster/60489); [algorithmic diversity of model-generated code](https://arxiv.org/html/2503.00691v2);
[Dual-Surrogate Guided Search](https://arxiv.org/html/2607.13911v1); [insight and invariants, after Kaplan and Simon](https://escholarship.org/content/qt55s731n1/qt55s731n1.pdf);
[Matolcsi and Vinuesa](https://real.mtak.hu/7892/).
