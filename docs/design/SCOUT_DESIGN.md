# The Scout: search at the start of every generation (November 12, 2026)

Shreyas asked for it on November 11: an agent that searches the web, code and the research literature every
generation, for the planner (the deep loop) and the mutators (the wide loop). Code: `lean/scout.py`; off by default
(`--scout`), so lean's golden version is unchanged (tests: 16 of 16).

## What it does, each generation

1. **Reads where the run stands:** the best program, its idea and its feedback; what the last generation tried and
   what came of it (gains, failures and their causes); the Atlas's latest findings; the guidance entries and their
   records; the web items tried before and their records; and its own search log.
2. **Writes a diagnosis and two sets of queries** (one model call, thinking "low", as the planner):
   - deep (4), for the planner: where the run is stuck and how others get out of exactly that; how to implement an
     idea the run is pursuing; facts that decide between two directions;
   - wide (one per mutator): approaches neither in the guidance nor tried in the Atlas, each different.
   Each query has a kind: web (the whole web, papers' full texts included: the passages that answer the query's
   purpose), code (repositories, gists, Q&A) or paper (a research index: titles and abstracts; at most one per
   generation).
3. **Searches:** web with Exa (`auto`, highlights guided by the query's purpose); papers with OpenAlex (semantic
   search, abstracts); code as below. Never repeats a query from its log; never shows a page shown before; keeps 2
   results per query with at least 200 characters of content.

   **Code is real source code, as written** (since November 12: before, code results were often a pull request's
   task list, a release's changelog or a README). Exa finds where the code is (GitHub, gists, Stack Overflow); a GitHub
   pull request, issue, release or doc page counts as a pointer to its repository. For each repository (up to 4 per
   query) the Scout lists its source files (GitHub's API); the model picks the files that serve the query's purpose and
   names the identifiers to look for; each file is read raw (indentation intact) and the part where those identifiers
   are densest is kept (up to 6,000 characters, starting at the enclosing definition). Stack Overflow questions give
   their top answers with code blocks as written (Stack Exchange's API). Code queries describe the code to see and ask
   for what is likely to exist (a known move, model or data structure, a library's usage), not the problem's exact
   variant; they may be about any programming difficulty the run has, not only methods. `GITHUB_TOKEN` (optional)
   raises GitHub's limit from 60 to 5,000 calls an hour.
4. **Hands out the results** as items W<generation>.<k>: the planner gets the deep items and the scout's diagnosis,
   each mutator the items of its own wide query. An experiment or mutation that draws on items cites them; its coder
   gets them in full.
5. **Records:** each cited item's record (gained / no gain / failed) is computed from the archive, as guidance's is,
   and shown to the planner and the Scout in later generations. The Distiller is told which items a program used.

Everything is logged in `scout.jsonl` (the diagnosis, every query, every result, the items' text, each search's cost
as Exa and OpenAlex report it, errors); a resumed run continues it.

## Costs and limits

- Exa: about $0.007 per search with highlights (`costDollars` in each reply); free $10 a month plus $20 at signup;
  10 requests a second; refused, never charged, past the free credit without a payment method.
- OpenAlex: $0.001 per semantic search (the reply's `X-RateLimit-Cost-USD`); free $1 a day; semantic search 1 request a
  second.
- A generation: about 6 Exa searches and 1 OpenAlex search: about $0.04.

## How it was tested (live, real model, real search)

- Replayed on a real run's state at two points (after generation 1 and after generation 5 of the aborted fair run):
  different diagnoses (early: the moves never change the truck count; late: a plateau, single moves can't free a
  truck) and different queries; results with method passages from papers' full texts, a top SDVRP solver's repository
  (Alkaid-SDVRP, first at the DIMACS challenge), and code (jsprit's string removal). The planner with the brief cited
  items in every experiment and changed direction in 2 of 3; without it, plans were also sound but drew on nothing new.
- A live run of generations from that state on Colab: the agents, citations, records and costs, end to end.
- Real code (November 12), replayed live on Colab after generation 8: a code query on operator scheduling read
  ALNS's roulette-wheel selector and stopping criterion (N-Wouda/ALNS); one on Benders decomposition read two
  logic-based Benders implementations, one for a heterogeneous-fleet routing problem. A direct test read HGS-CVRP's
  SWAP* (`LocalSearch::swapStar`) whole, from its first line. Before the prompt asked for code likely to exist, a
  query for the problem's exact variant got only loosely related files.
