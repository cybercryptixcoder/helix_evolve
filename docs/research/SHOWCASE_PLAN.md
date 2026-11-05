# Plan: more problems, compared fairly with published systems (November 2026, not started)

Status: **planned only**. Nothing here has been run. The cloud machine is busy with other work until at least
November 7.

## The aim

Results on more than one problem, each compared with published systems under the same constraint, so that a reader
can check every claim the way they can check [RECORDS.md](../RECORDS.md) today.

## The rule for a fair comparison (the same as RECORDS.md)

For each problem:
1. a published value from a paper or repository, with its table, the system, model and budget it reports;
2. the constraint it was obtained under (problem size, time per program, number of programs), and Helix run under
   that constraint or a tighter one;
3. Helix starting from a trivial program, with no published construction or code given to the agents (if published
   ideas are given, as in v10.2, it is stated);
4. an exact, independent verifier for every result, and at least two seeds reported;
5. the result, the round and the program that passed each published value, linked as in RECORDS.md.

## Candidate problems

These are the problems that the published LLM-driven systems (AlphaEvolve, OpenEvolve, ShinkaEvolve, ThetaEvolve,
TTT-Discover) report on, so a like-for-like comparison exists. Every value must be re-checked against its source
before a run is designed around it.

| Problem | Why it fits | What to verify first |
|---|---|---|
| First autocorrelation inequality (minimise) | Same machinery as the problem Helix already ran on; exact verifier exists | the values and budgets in TTT-Discover's and ThetaEvolve's tables |
| Third autocorrelation inequality | The same | the same |
| Erdős's minimum overlap problem | A step-function construction with an exact score | AlphaEvolve's and TTT-Discover's values and budgets |
| Circle packing in a unit square (n = 26, n = 32; maximise the sum of radii) | The most common benchmark across these systems, with reported sample counts | each system's value, n, and number of programs |

## The run

One job per problem, v10.2's code with the problem plugged in (a problem is one file: statement, scorer, trivial
starting program), two seeds each, at the published systems' constraint. Estimated a few days of the 2-core machine
per problem at v10.2's settings; the circle-packing problems are much cheaper to evaluate.

## Before starting

- Verify every published value and budget from the papers (not from memory).
- Write the exact verifier for each problem and test it on the published constructions where they are public.
- Test the whole job live with the real model, as every earlier job was.
