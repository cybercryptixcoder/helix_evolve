# Research question: do LLM-driven evolutionary searches grok?

Raised by Shreyas on October 23, 2026, 03:34. Status: **planned**, to run on the data of the v4.7 job and the earlier
jobs (nothing new needs to be collected first).

## The question

In machine learning, grokking is a long flat stretch in test performance followed by a sudden jump: the network
generalises long after it has fitted the training data. What makes it grokking, rather than just "flat, then a jump",
is **hidden progress**. While the measured metric is flat:
- something underneath keeps changing: a general circuit forms slowly;
- a pressure (weight decay) keeps penalising the memorised solution;
- until the general one wins, as a phase change.

Helix runs show long plateaus that sometimes end in sudden climbs:
- v4's runs sat in the 0.8825 trap, and atlas-s1 broke out at generation 10;
- a routing run sat flat for 10 generations, then gained 2.3% in one;
- the same routing runs restarted climbing at generations 43–49 after a flat spell.

So the question is: **do these jumps come from hidden progress that the score can't see, or are they lucky draws?**

## Where hidden progress could live in Helix

1. **In the code: potentiating changes.** A change that doesn't move the score but makes a later jump reachable. The
   evolutionary-biology parallel is Lenski's long-term E. coli experiment. The ability to use citrate appeared after
   about 31,000 generations, and replaying the history from frozen samples showed it was only reachable from
   late-generation ancestors: earlier "neutral" mutations had set it up.
   - Seen in Helix: on the routing problem, caching paths and cheaper validity checks barely changed the score, but
     they made each move much cheaper, which later let ruin-and-recreate pay off.
2. **In the memory (the Atlas).** Findings accumulate, especially "mechanism" findings, until the planner can combine
   them into an idea that none of them suggests alone.
3. **In the population.** Branches that look useless keep drifting. The routing plateau broke through a child of an
   old, weaker program, not the champion.

## What "generalisation" would mean here

- **The move from instance-specific tuning to a principle.** Early programs tune knobs that suit the current
  construction (or the training instances); the jump comes when the system finds the structure underneath. For
  example, "the maximum is the binding constraint, so treat it as one" was found independently by v4.5 and v5.
- **Literal generalisation, on the routing problem.** That problem has training worlds and held-out worlds. Does
  held-out performance lag behind training performance and then catch up suddenly?
- **The analogue of weight decay** is a complexity pressure. The routing coders are told to stay under 90,000
  characters and delete dead code. Does that pressure come before simpler, more general programs?

## The experiments (all on existing data, cheapest first)

1. **Is a breakout more likely the longer a plateau lasts?**
   - Across every run (v4: 9 runs plus the 150-generation run; v4.5, v5, v4.6, v6; v4.7 when finished; the routing
     runs), measure plateau lengths and the generations where they ended.
   - If plateaus end at random, the chance of a breakout is the same each generation, however long the plateau has
     lasted, like a dice roll.
   - If something accumulates, that chance rises with plateau length.
   - **Tool to write:** `tools/plateaus.py`, reading `history.jsonl` and `programs.jsonl`.
2. **A code replay (Lenski-style).**
   - For each big jump, take the change that produced it (its diff), and have a coder apply the same idea to
     ancestors from early, middle and late in the plateau before it.
   - Score each.
   - If the idea only pays off on late-plateau programs, the code carried hidden potentiation.
   - This needs a few model calls per jump.
3. **A memory replay.**
   - Rebuild the planner's view from the Atlas as it was early in a plateau, and as it was just before the jump.
     The findings log is append-only, so any generation's state can be rebuilt.
   - Ask the planner for experiments several times from each.
   - Count how often it proposes the breakthrough idea, or one equivalent to it.
   - If the later memory makes it much more likely, the memory carried the progress.
4. **Hidden-progress signals during plateaus.** Look for quantities that keep moving while the score is flat:
   - the number of distinct methods;
   - mechanism findings;
   - code size;
   - the diversity of constructions (how far the best few are from each other);
   - on the routing problem, the gap between training and held-out scores.

   Do any of them predict the next jump?

## Why it matters for v4.7

v4.7 closes a line after 4 generations without a real gain.
- **If hidden progress lives in the memory,** that's safe: findings are shared across lines, and a closed line's
  programs stay available as bases.
- **If it lives in a line's code,** closing could end a line just before its breakthrough. Experiment 1 tells us how
  long plateaus that end in jumps usually last, so the line-patience setting can be set from evidence.
- **If experiments 2 or 3 show potentiation,** a closed line could be reopened from its most potentiated point.

## Links

- The false-ceiling analysis: `docs/V4_CEILING.md`.
- v4.7: `docs/V47_DESIGN.md`.
- The version index: `docs/VERSIONS.md`.
