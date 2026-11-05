# Reviewing a run against the intent

What every trace review checks: whether Helix behaved the way it is meant to, not just where it got. Used for the iteration rounds in `docs/WORKLOG.md`, and it's the same list the meta loop's Researcher is pointed at.

Start with `python -m helix3.digest <run>`; then read `trace.jsonl` for the details (each line is one event: `call`, `plan`, `research`, `feature_done`, `probe`, `trial`, `prediction`, `accept`, `tree`, `gen_end`...).

## The checklist

**Wide loop**
1. Are the Mutator's parents spread across approaches, or piled on one feature?
2. How many of its features are duplicates (certified) or invalid? Does the retry after a duplicate produce something different?
3. Does anything from the wide loop gain, get kept, or become a parent or a "find" the Researcher builds on?

**Deep loop**
4. Does the Researcher name a mechanism from the diagnostics, or a symptom?
5. Does it use both `probe` and `improve` experiments, and do probe experiments test one thing?
6. Do predictions name real metrics, and how often do they hold? Does it learn from predictions that failed (later generations)?
7. Does it pick up the Mutator's finds?
8. Do the Coders' readings match the experiments (look at "Code computes" vs "Asked to measure")?

**Navigator**
9. Does the tree hold genuinely different approaches? Are promising ones deepened (sub-approaches) and unproven ones retried occasionally?
10. Are prune requests sensible, and do certificates actually hold?
11. Does effort follow evidence across generations (the plan changes after results)?

**Fit and accept**
12. What share dies at the probe? Are near-misses retried in combination, and does that ever work?
13. Are kept features redundant with each other? Does anything get retired?

**Overall**
14. Progress curve: steady, or one jump then flat? Compare with earlier rounds at the same generation.
15. Cost: calls, tokens, seconds per generation; where the time goes.
