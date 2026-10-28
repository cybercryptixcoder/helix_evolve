# Survey brief: LLM-guided program search

October 27, 2026. A brief for the research agent who will run the literature survey. Hand it over as it stands,
on its own: everything below this paragraph is addressed to that agent. (Don't hand the agent this repository's other
documents with it: they describe the team's system, which the survey is meant not to see.)

## Your task

Survey a research area and report what exists, how it was evaluated and published, and what the community expects of
a paper in it. A small team will use your report to decide what to work on. Its value lies in being accurate and
complete, not in reaching a conclusion.

The survey is not for two things:

- **It is not an assessment of any project, ours included.** You are not shown the team's system. Do not try to
  judge whether any idea is new, unique or good enough.
- **It is not a search for support.** Evidence that a direction is crowded, hard or unrewarded is as useful as
  evidence that it is open.

Write every finding as a description of the field: "prior work does X, evaluated on Y, published at Z". Never write
"this makes idea W novel".

## The area and the team

**The area.** A large language model writes and repeatedly edits programs; an automatic evaluator scores each
program; a search loop, often evolutionary, decides what to edit next. Common names: evolutionary coding agents,
LLM-driven program search, code evolution, LLM-guided evolutionary search, automated algorithm design with LLMs.
Representative systems: FunSearch, AlphaEvolve, OpenEvolve, ShinkaEvolve.

Applications in scope:

- mathematical constructions that improve a bound, such as the autocorrelation inequalities, packings, the
  Heilbronn problem and kissing configurations;
- the design of algorithms and heuristics, such as combinatorial optimisation, competitive programming and
  scientific code.

**The team** (context for which venues and standards matter, not for evaluation): a small group using an inexpensive
model through an API and a small CPU-only machine, running long searches of hundreds of generations. It aims to
publish at a machine learning, AI or evolutionary computation venue, possibly a mathematics venue.

**The date** is late October 2026. The field changes month to month: include preprints up to the present, and say
when a finding may already be out of date.

## Ground rules

1. **Describe; don't rank ideas by novelty.** Don't use "novel", "unique", "first" or "gap" in your own voice. When
   authors claim to be first, report it as their claim ("the authors state that…").
2. **Search on every side.** For each question, look for accepted and rejected papers; results that held and results
   later matched by simple baselines; mechanisms that helped and ablations where they did not. Record what you find
   even when it complicates the picture.
3. **Primary sources.** Read the paper itself (method, experiments, appendix), not only abstracts, blogs or
   summaries. Confirm venues on the conference's or journal's own pages, or on OpenReview. Label preprints as
   preprints and workshop papers as workshop papers.
4. **Every claim checkable.** Give a link and a location (section, table or page) for each fact. Quote briefly, one
   or two sentences, when the wording matters. If you can't find something, write "not found" and what you tried.
   Never fill a gap with a guess, and never cite a paper you have not opened.
5. **Numbers as published.** Copy values exactly, with their source. When sources report the same result
   differently, list each value and its source.
6. **Facts apart from interpretation.** Mark your own reading as "Interpretation:".
7. **Dates and versions.** Give each paper's date and version, and note when a later version changed a claim.
8. **Beyond the famous papers.** Use several entry points (see Method), and cover evolutionary computation,
   quality-diversity, AutoML and hyperparameter optimisation, algorithm configuration, operations research and
   mathematics, not only machine learning conferences.

## Part 1: what a publication in this area looks like

The aim is to learn the bar: what published work in this area contains, and what it was asked to show.

**1.1 Inventory.** Build a table of works from 2023 to October 2026 in which an LLM-driven program search reports
results on mathematical constructions or algorithm design. Columns:

- work (linked) and date;
- venue and status: main track, workshop, journal or preprint;
- kind of contribution: method, discovery, open framework, benchmark or dataset, analysis or critique, position;
- number and kinds of problems;
- models used;
- budget reported: cost, model calls, wall-clock, hardware;
- runs per problem (seeds);
- baselines and ablations;
- headline claims, in the authors' terms.

**1.2 One problem or many.** How are results on a single problem reported and received?

1. AlphaEvolve's result on the second autocorrelation inequality: in which documents was it reported, alongside how
   many other problems? Has any of it appeared at a peer-reviewed venue?
2. Every work that improved the second autocorrelation inequality (and the first and third), by any method, with or
   without LLMs. For each: what it contributed beyond the number (a method, a proof, structure in the construction, a
   generalisation, an explanation of why it works), and where it was published.
3. Papers whose whole contribution is one problem, in mathematics venues and in ML or evolutionary computation
   venues: what they contain, and where they appeared. What separates those published in journals from those that
   remain arXiv notes?
4. Among method papers, the fewest problems with which work was accepted at a main track, and at a workshop, and what
   else those papers offered.

**1.3 What reviewers ask for.** Read the public reviews and meta-reviews of submissions in this area, accepted and
rejected: OpenReview for ICLR 2025 and 2026, NeurIPS 2025 and TMLR, and ICML 2026 where public. Extract the
recurring requests and criticisms (baselines, matched budgets, seeds, number of problems, contamination, cost
reporting, ablations, simplicity, reproducibility, significance), with short quotes and links. Count how often each
comes up.

**1.4 Evaluation norms.** What counts as a fair comparison now? Report the practices the literature recommends or
uses, who recommends them, and how widely they are followed. Examples: matched models and budgets; simple baselines
such as independent sampling; a tuning ceiling for each result; private test sets; independent verification of
constructions; contamination checks. Which problem suites and benchmarks are standard, which are emerging, and what
are their known weaknesses?

**1.5 Contributions without a new record.** Which papers in the area were published without a best-known result:
analyses, negative results, datasets, benchmarks, cost studies, reproductions with open models? What evidence did
they offer, and where were they published?

**1.6 Venues and dates.** List the venues that publish this work, with scope, format, page limits and deadlines from
November 2026 to June 2027, each confirmed on the official page. Include main tracks, datasets and benchmarks tracks,
workshops (such as AI for Math, MATH-AI, and workshops on LLMs and evolutionary computation), EvoStar's EvoLLMs
track, GECCO, TMLR, and mathematics journals that publish computer-assisted constructions.

**1.7 Record histories.** For the second autocorrelation inequality and four or five other problems used often in
this area (the first and third autocorrelation inequalities, circle packing for n = 26 and 32, the Heilbronn problem,
kissing numbers, Erdős's minimum overlap problem), list every improvement of the best known value: date, value,
method, model if any, budget if stated, source. Note whether each was independently verified, and where reported
values conflict.

## Part 2: the mechanisms, in this field and beyond

The aim is to map what exists around nine families of mechanisms used in LLM-guided search, wherever they have been
studied. For each family, cover the LLM program search literature and at least two neighbouring fields. For each work
you find, record:

1. **How it realises the mechanism, and in what setting:** what is searched, what the model reads or produces, what
   is learned, and how it is used.
2. **The evidence on whether and when it helps, and at what cost,** including null and negative results.
3. **Open problems** its authors state.
4. **How claims about the mechanism are usually tested:** baselines, ablations, metrics.

| Family | What to cover | Neighbouring fields to search first |
| --- | --- | --- |
| M1. Model-made descriptions of solutions | An LLM reads programs or edits and describes them along design dimensions, fixed in advance or found during the search: edit taxonomies, strategy labels, quality-diversity descriptors defined or judged by a model. How the reliability of such labels is measured: agreement between readings, between models, against people. | Quality-diversity; qualitative coding and content analysis; mining of code changes in software engineering |
| M2. Estimating which choices matter | Estimating the effect of design choices or edits from a search history (surrogate models, functional ANOVA and other importance measures, ablation analysis between configurations, credit assignment to edits, motifs or lineages), and using the estimates to pick the next change (Bayesian optimisation, Thompson sampling, bandits over choices). | Hyperparameter optimisation; algorithm configuration; design of experiments; surrogate-assisted evolution |
| M3. Interventions on strong solutions | Removing, swapping or reverting one component of a good solution to learn what it contributes, as analysis or as a search operator. Replaying earlier states of a search. | Ablation studies in ML; delta debugging; genetic improvement; causal analysis of programs |
| M4. Budget across parallel lines of search | Racing, successive halving and Hyperband, population-based training, island models with migration or restarts, bandits over parents or lineages, pausing and resuming lines, fairness between young and old lines. | Hyperparameter optimisation; algorithm configuration (racing); multi-armed bandits; parallel evolutionary algorithms |
| M5. Memory across long runs, restarts and versions | Archives, logs of insights, registers of what has been tried, avoiding repeated or cyclic exploration, warm-starting a new version of a system from an earlier run's state. | Open-endedness; tabu search; continual and lifelong learning; experiment tracking in science |
| M6. Testing search policies cheaply | Synthetic or simulated landscapes (NK landscapes, landscapes with planted structure, benchmark generators, simulators of the search itself) used to compare or tune search strategies before real evaluations. The evidence on how well such results transfer to real runs. | Fitness-landscape theory; benchmarking in evolutionary computation; simulation-based evaluation in operations research |
| M7. Low budgets | Results with small, cheap or open models; CPU-only evaluation; cost per improvement; how results scale with budget. | Compute-efficiency studies in ML; anytime algorithms |
| M8. Long-horizon dynamics | Plateaus, stagnation, cycling and loss of diversity over hundreds to thousands of generations, and the interventions that address them. | Evolutionary dynamics; premature convergence and diversity maintenance; directed evolution in biology |
| M9. Integrity of results | Evaluators that can be exploited, numerical loopholes, contamination from training data, overfitting to public test sets, independent verification of constructions. | Reward hacking; benchmark contamination; computer-assisted proof and verified numerics |

## Part 3: synthesis

Summarise the field in two to four pages, every point cited:

- **Patterns of publication, 2025 to 2026:** which kinds of contribution appeared at which venues, and with what
  evidence. A table.
- **The bar, by contribution type:** for a method paper, an analysis paper, a dataset or benchmark paper and a
  discovery paper, a checklist of what accepted papers showed and what reviewers asked for.
- **Questions the field states as open,** from future-work and limitations sections and from reviews, grouped by
  mechanism family.
- **Where evidence is thin or in conflict,** and what would settle it.

Do not recommend what the team should do, and do not compare these findings with any particular system.

## Method

1. **Write the queries first.** Before searching, write your queries for each question and keep them in the
   screening log. Use several communities' terms: "LLM-guided evolutionary search", "code evolution", "evolutionary
   coding agent", "automated algorithm design", "genetic improvement", "hyper-heuristic", "program synthesis",
   "quality-diversity", "algorithm configuration", "surrogate-assisted".
2. **Use several entry points:** Google Scholar; Semantic Scholar, including the citations of key papers; arXiv
   listings (cs.NE, cs.AI, cs.LG, math.CA, math.CO); OpenReview; DBLP; ACL Anthology; ACM Digital Library (GECCO);
   IEEE Xplore (TEVC, CEC); Springer (EvoStar); workshop pages and their accepted papers; GitHub and Hugging Face for
   code and datasets; curated reading lists.
3. **Chain citations both ways** from the seed list: what each paper cites, and who cites it.
4. **Screen widely, read deeply.** Screen at least 100 candidates and log each: title, link, date, kept or not, a
   one-line reason. Read the 30 to 50 most relevant in full; for the rest, the abstract and the experiments suffice.
5. **Fill an extraction card** for each paper read in full: citation and link; date, version, venue and status; kind
   of contribution; problems; models; budget; seeds; baselines; ablations; main results, with exact numbers;
   mechanism families used (M1 to M9); limitations the authors state; open questions; public reviewer comments; your
   notes, marked as interpretation.

**Seed list.** A starting point, not a boundary. It includes work that supports and work that criticises the area;
verify every detail given here yourself.

- Systems and their reports: [FunSearch](https://pmc.ncbi.nlm.nih.gov/articles/PMC10794145) (Nature, 2023);
  [AlphaEvolve](https://arxiv.org/abs/2506.13131);
  [Mathematical exploration and discovery at scale](https://arxiv.org/abs/2511.02864) (Georgiev, Gómez-Serrano, Tao,
  Wagner); [OpenEvolve](https://huggingface.co/blog/codelion/openevolve);
  [ShinkaEvolve](https://iclr.cc/virtual/2026/poster/10007692);
  [CodeEvolve](https://aclanthology.org/2026.findings-emnlp.1345/); [GigaEvo](https://arxiv.org/abs/2511.17592);
  [ThetaEvolve](https://arxiv.org/abs/2511.23473);
  [Learning to Discover at Test Time](https://arxiv.org/abs/2601.16175);
  [ImprovEvolve](https://arxiv.org/abs/2602.10233); [AlphaResearch](https://arxiv.org/abs/2511.08522);
  [DeepEvolve](https://arxiv.org/abs/2510.06056); [EinsteinArena](https://arxiv.org/abs/2606.10402).
- Analyses and critiques:
  [Simple Baselines are Competitive with Code Evolution](https://arxiv.org/abs/2602.16805);
  [What Do Evolutionary Coding Agents Evolve?](https://arxiv.org/abs/2605.20086);
  [Barbarians at the Gate](https://arxiv.org/abs/2510.06189).
- Single-problem work on the second autocorrelation inequality:
  [Matolcsi and Vinuesa](https://doi.org/10.1016/j.jmaa.2010.07.030) (2010);
  [Boyer and Li](https://arxiv.org/abs/2506.16750) (2025); [Jaech and Joseph](https://arxiv.org/abs/2508.02803) (2025).
- Heuristic design and open-endedness: EoH, ReEvo, LLaMEA, MCTS-AHD, [QDAIF](https://arxiv.org/abs/2310.13032),
  Darwin Gödel Machine.
- Benchmarks:
  [ALE-Bench](https://papers.nips.cc/paper_files/paper/2025/hash/e555eab2c68f886052f404397ea52001-Abstract-Datasets_and_Benchmarks_Track.html),
  [AlgoTune](https://proceedings.neurips.cc/paper_files/paper/2025/hash/9a648e8e1014c2427156dcb5465cd488-Abstract-Datasets_and_Benchmarks_Track.html),
  HeuriGym, CO-Bench, FrontierCO, [BLADE](https://arxiv.org/abs/2504.20183).

## What to deliver

Deliver each part as soon as it is complete, in this order:

1. **Part 1** (questions 1.1 to 1.7), with the inventory table (also as CSV) and the record histories.
2. **Part 2,** one section per mechanism family, each with a table of the works found.
3. **Part 3,** the synthesis.
4. **The screening log** (CSV) and the extraction cards.
5. **A bibliography** (BibTeX) of every work cited, each entry checked to exist, with its DOI or arXiv id and a link.
6. **What you could not find or access,** and the questions the survey could not answer.

Write in Markdown, plainly and briefly. Lead each section with its finding. Use tables where items are compared. Keep
sentences under 25 words.

If time runs short, finish Part 1 first, then families M1 to M5, then the rest, and say what is incomplete.

## Out of scope

- Judging, ranking or recommending any project or idea, including whether something is new.
- Running code, reproducing results or downloading large datasets: note their links instead.
- Contacting authors, posting anything or creating accounts.
- Content you cannot access legitimately: list it as not accessed.
