# Review: is the deep loop cashing in on lucky hits?

Run reviewed: `20261011-181101-full` (3 generations, DeepSeek V4.1 Flash, 40 LLM calls). Evidence comes from the console log, the hypothesis log and the call log of that run, and from the prompts in `helix/prompts/`.

## Verdict

**No.** The loop is doing what its prompts tell it to do, but that isn't what we designed it to do.

- **Wide gets lucky, as intended.** In generation 1 the Mutator wrote p0011 and the best score jumped from −8.378 to −7.455.
- **Deep never cashes it in.** After that jump the best score never moved again:
  - 8 hypotheses were tested: 0 supported, 5 flat, 3 refuted.
  - The best deep program was +0.041 over its base. Every other deep program scored the same as its base or worse.
  - In generation 3 the deep branch didn't run at all.
- **The cause is structural.** The deep loop has no step that answers "why did this program win?", and no step that turns an answer into a better program. Its tests are built to *distort* the winner, not to *improve* it.

## What we intended vs what happens

| Step we intended | What actually happens |
|---|---|
| Wide tries random things; sometimes one lands. | ✅ Works. p0011 (wide, gen 1) is the only real gain in the run. |
| Deep notices *that* program did much better. | ❌ Nothing marks a jump. The Researcher sees 8 programs ranked by score and spreads its hypotheses across them. In gen 2 only 2 of 4 tests were on p0011. |
| Deep works out *why* it did better. | ❌ The winner has nothing to be compared against in a controlled way (see 1 below), so the Researcher guesses. Its own reasoning says: *"Inconsistent signal — noise"*, *"which is responsible? Not clear."* |
| Deep turns the "why" into code that builds on the winner. | ❌ Every test is an exaggeration (×3, ×8, sign flips) that pushes the winner *away* from what made it good, so they all score lower. No step turns what was learned into a better program. |
| The improved program becomes the new base. | ❌ Deep never produced one. Worse, its deliberately distorted test programs went into the next pool and used up the Mutator's attention: in gen 3 a Mutator was asked to improve p0024 (−7.815, an exaggerated copy of p0011) instead of p0011 itself. |

This is also why the chart shows a jump and then scattered points below it. The best-ever line is kept, but after a jump neither branch makes programs *near* the winner. Wide writes a new idea from scratch each time, and deep writes distorted copies.

## The structural problems, most important first

### 1. "Why did it win?" can't be answered the way the loop asks it

The Mutator prompt says *"Prefer a genuinely different idea … a different formula altogether"*. So a lucky winner from wide differs from its parent and from every other program in many ways at once. Comparing it with the others can't show which of its parts made the difference. The Researcher is left eyeballing whole programs that differ everywhere, and its reasoning in gen 3 says so explicitly.

**Missing:** an attribution step. Knock out each part of the winner, one at a time, by removing or neutralising it, and score each version. The parts whose removal costs the most are *why it won*. This is a controlled experiment that actually answers the question, and it's cheap: the evaluator takes under a second per program.

### 2. The test always distorts, whatever the hypothesis claims

The hypotheses are causal ("the `consumed` term is what makes p0011 beat the others"). The prompts force the test to be an exaggeration:

- Researcher prompt: *"Make the change big enough to show a clear effect: exaggerate the aspect under test rather than nudging it."*
- Coder prompt: *"push it far enough that the effect will show up."*

7 of the 8 tests in this run were a 3× to 12× change or a sign flip. The eighth (h0006) transplanted p0011's `consumed` term into the weaker p0010, which is closer to the right idea, but it was aimed at p0010 rather than the winner and came back flat. On a program that is already good, pushing any one weight that far moves it off its sweet spot, so the score drops *whether the claim was true or not*. An exaggeration answers "does this part matter at all?". It doesn't answer "is this why it won?", and it never produces a better program.

Example: h0005 claimed `consumed` is why p0011 wins, then tested 2.0 → 6.0. The score went down. We still don't know whether `consumed` is why it wins.

### 3. Nothing turns a finding into a better program

Findings are logged as verdicts and nothing acts on them.

- **h0008 found something useful.** It flipped `+0.4*tight_rem` to `−1.5*tight_rem` on p0011, and anticorr got 3.35 points worse. So `tight_rem` is clearly one of the things that makes p0011 good. The obvious next move (try 0.6 or 0.8 instead of 0.4) never happened.
- **The Researcher worked it out but was cut off.** In gen 3 it reasoned its way to exactly these follow-ups ("scale `tight_rem` up 0.4 → 1.5", "raise `balance`"), but its reply hit the token limit before the JSON (see 5).

**Missing:** an exploit step. For the parts that attribution says matter, make moderate changes (about ×0.5 to ×1.5, or a refined version of the same mechanism), and transplant them into other strong programs. These are the programs deep should hand to the next generation, not the exaggerated tests.

### 4. Deep's attention isn't anchored on the winner

- **The prompt spreads it out.** The Researcher prompt says *"Mix safe bets on the strongest program with at least one bolder idea"*, and lets it choose any of the 8 programs it's shown as a base.
- **The budget shows it.** After the jump, the lucky hit got exactly 2 LLM calls of deep work, both exaggerations. In the same two generations 12 Mutator calls went to unrelated new ideas.
- **No jump signal.** The Researcher is shown each program's score and parent, but not how much it beat its parent, so a lucky jump looks like any other row.

### 5. Operational: replies cut off at the 6,000-token limit

8 of the 40 logged calls returned exactly 6,000 tokens, meaning they were cut off:
- 1 Researcher call;
- 5 Mutator calls;
- 2 of the repair calls that followed them.

The prompts already ask for short reasoning, but in these calls the model deliberated at length anyway ("Let me think about this problem carefully…").

- **Gen 3 Researcher:** cut off mid-sentence, so there was no JSON, "no usable hypotheses", and the **whole deep branch was skipped for that generation**.
- **Mutators:** no code block, so a repair call wrote the program without the reasoning that led to the idea.

### 6. Smaller things

- **A test that changes nothing is reported as "flat".** h0003 changed code but moved every family by exactly 0.00, so the change never affected a single placement. It should get its own verdict (for example "no effect"), so the Researcher doesn't read it as evidence.
- **A test that changed two things.** h0007 changed two coefficients at once, breaking the one-change rule, so its result can't be attributed to either.

## What to change

Structural changes, in order. The first four are the fix; the fifth stops generations being wasted.

1. **Give deep two kinds of experiment instead of one.**
   - **Cause test (knock-out):** remove or neutralise one part of the champion, and see how much it was worth. This answers "why did it win".
   - **Improve test (moderate step):** change a part that matters by a moderate amount (about ×0.5 to ×1.5), refine its mechanism, or transplant it into another strong program. This produces candidates.
   - **Keep exaggeration** only as an optional probe, and stop the prompts requiring it. Today the Researcher prompt ("exaggerate … rather than nudging") and the Coder prompt ("push it far enough") forbid exactly what the improve step needs.
2. **Anchor deep on the champion, especially right after a jump.**
   - When a new best appears, mark it ("p0011 is new and beat the previous best by 0.92").
   - Spend most of that generation's deep budget on it: first knock-outs to find its key parts, then improve tests on those parts.
3. **Close the loop from finding to code.** Every cause finding should lead to at least one improve test in the next generation, aimed at that same part. The research log should say which finding each new test builds on.
4. **Don't let test programs pose as candidates.** Knock-outs and exaggerations are measurements. Keep their results in the research log, but only improve tests (and wide's programs) should compete for the next pool and be shown to the Mutator.
5. **Make replies fit.**
   - Detect a cut-off reply (`finish_reason == "length"`) and retry once, asking for the answer with no reasoning.
   - Or ask for the JSON or code *first* and the reasoning after it, so cutting off the end loses only reasoning.
   - Never skip a whole branch because one reply was cut off.

## How to tell it's fixed

In the next run, after wide makes a jump, look for three things:

- the following generation's research log shows knock-outs on that program, naming which parts mattered and by how much in each family;
- the generation after that has improve tests on those parts;
- **the best score rises again from deep**, not only from new wide luck.

The report's "where the improvements came from" table should show deep rows after each wide jump.
