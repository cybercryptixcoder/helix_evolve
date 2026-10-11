# Review 2: why the curve is still shallow

Reviewed: the latest run's dashboard log (generations up to 10, champion p0088 at −6.961), against the code at `6f2332e`. Review 1, on the 18:11 run, is in this file's git history.

## Short answer

The deep loop now does what review 1 asked. It takes the champion apart with knock-outs, then makes moderate improve tests, and knock-out programs stay out of the pool. **Two structural problems still keep the curve shallow, and both sit outside the deep loop:**

1. **The population has no memory.** Each generation the pool is rebuilt from *that generation's* new programs plus the single best. The 2nd–5th best programs ever found are thrown away. Half the Mutator's work then goes into "improving" whatever the last batch produced, even when it's bad.
2. **The wide branch is mostly wasted.** 15 of the 17 Mutator calls in this log hit the 8,000-token limit (45–61 s each) before writing code. So wide's programs are mostly *repair* rewrites, made without the reasoning that led to the idea, and wide is what sets the length of every generation.

Fixing both is quick. Three more changes make better use of the deep budget (sections 3–5).

| Question | Answer |
|---|---|
| Does the Mutator mutate the deep loop's new code? | **Partly.** Half its variants start from the champion, which is often a deep or deep-lineage program. The other half start from pool slots 2–4, and those are refilled every generation with the latest batch's results, good or bad. |
| Is the earlier disconnect fixed? | The part review 1 described is. The one you saw in the graph (late mutations as bad as the worst code) comes from problems 1 and 3 below. |

## 1. The pool forgets everything except the single best (biggest problem)

`run.py`, `generation()`:

```python
next_pool = []
for b in branches:
    next_pool += [p.id for p in self.survivors(out[b][0], self.a.top_x)]   # top X of THIS generation's new programs
next_pool = list(dict.fromkeys(next_pool + [best.id]))                    # + only the single best ever
```

`survivors()` ranks only the programs made this generation, so the next pool is "the top 4 new wide programs + the top 4 new deep programs + the champion", however bad the new ones are. A program that was 2nd best last generation is dropped unless it's the champion.

**Effects:**
- **The Mutator works on poor programs.** `wide()` takes the top 4 of that pool. Slot 0 is the champion and slots 1–3 are usually last generation's newest outputs. Half the variants go to those slots, which is why the log shows Mutators asked to "write a program that scores higher than **−8.018**" while "the best shown is **−6.961**". They mutate a recent failure, not the 2nd–4th best program ever found.
- **The Researcher works on poor programs too.** It sees the same pool, so its comparison programs are also mostly the latest, often weak, batch.
- **Good deep work disappears.** A deep improve test that scored well but didn't beat the champion survives one generation, then vanishes.

**Fix:** keep the best programs found so far, the usual (μ+λ) evolutionary selection:

```python
candidates = old pool (non-probe) + this generation's new programs (non-probe, valid, not duplicates)
next_pool  = top K by score   (K ≈ 8–10, e.g. 2 × top_x)
```

To keep some variety, cap how many pool slots one lineage can hold (for example at most 3 programs sharing the same parent), or reserve 1–2 slots for the best *wide* programs. This is a few lines in `generation()`; `survivors()` can stay as it is.

## 2. Almost every Mutator reply is cut off

From the call log, Mutator calls between 19:07 and 19:11:

| | Calls |
|---|---|
| Hit the 8,000-token limit (45–61 s, no complete program) | **15** |
| Finished normally (4–5 s) | 2 |
| Repairs that themselves broke ("cut off mid-expression", "missing `return`") | several |

The Mutator deliberates in its reply ("We need to write a new priority function… Let me think about…") and ignores "under about 150 words". So each wide batch takes about 60 s plus a repair round, and the repair rewrites the program from a one-line summary. The deep branch, by contrast, finishes in about 35–40 s (Researcher about 33 s, Coders about 3 s). **Deep and wide run in parallel, so wide's truncation alone sets the length of every generation.**

**Fix:** the same one that worked for the Researcher.
- **Code first.** "Start your reply with the ```python block. After it, at most two sentences naming the idea."
- **A per-role output limit.** Give the Mutator something like 2,500 tokens, so a deliberating reply fails in seconds, not a minute.
- **One retry on a cut-off reply:** "Reply with ONLY the ```python block". Include the cut-off reply's own reasoning in that retry, so the idea isn't lost.

Expected effect: generations about twice as fast, and wide programs that are the model's actual idea.

## 3. The Mutator is told to throw the program away

`helix/prompts/mutator.md`: *"Prefer a genuinely different idea over nudging a constant … a different formula altogether."* Its replies show it doing exactly that: "All the shown programs are weighted sums of l… Let me think about a genuinely different approach."

So even when given the champion, the Mutator mostly writes a new program from scratch. In a search this far along, a from-scratch program usually scores like the early generations, which is the "mutations as bad as the worst" you saw.

That's also not the design. Wide was meant to make *variants of the top programs* ("general attempts to improve"), not new programs.

**Fix:** split the Mutator's slots.
- **Most slots (for example 4 of 6): variants.** "Keep this program's core; make one or two bold changes: add a new property of the bins, change the functional form of one term, change the rule for opening a new bin, or borrow a part from another program."
- **The other 1–2 slots: fresh ideas.** "Write a genuinely different program" stays for these, to keep diversity.

## 4. Knock-outs are re-run on every small new champion

`champion_plan()` spends half the deep budget (2 of 4 tests) on knock-outs whenever the champion has none recorded against it, including when the new champion beat the old one by only +0.058 and has the same parts.

In this log, h0037 knocked out `fit` on p0088. That cost 12.1, which we already knew from h0025 on its ancestor. The Researcher itself notes that "all parts are un-knocked out" only because the champion's id changed.

**Fix:**
- **Only for real jumps.** Run cause tests only when the jump is at least `--epsilon` (a real jump, not drift).
- **Only on parts that are new or changed.** Knock out only parts that differ from the champion's parent. Unchanged parts inherit the parent's knock-out results, which can be shown to the Researcher as "inherited from p00xx".
- **Otherwise improve.** Spend every slot on improve tests.

## 5. Improve tests are too slow at tuning numbers

Most improve tests are a single coefficient moved by about ×1.2: "geom 0.5 → 0.6", "penalty 0.16 → 0.20". The champion is a weighted sum of about five terms, so this is coordinate search done by an LLM, at 2 steps per generation and about 0.05 per step. In the research log, 21 of the 23 improve tests are "flat" and none is "supported".

**Fix: let a cheap optimiser tune the numbers, and the LLM design the structure.**
- **Tune.** Each generation, take the champion's numeric constants (parse them with `ast`) and run a short parallel local search: about 40–80 evaluations of ±10–30% perturbations, keeping any improvement. Each evaluation takes under a second, so with the existing workers this costs about 10–20 s of a roughly 40 s generation. Add the tuned program to the pool like any other deep program, with branch `tune`.
- **Repoint the Researcher.** Its improve tests go to *mechanisms*: new terms, new functional forms, a different new-bin rule, ideas aimed at the families where the excess sits (`anticorr` 15.6% and `large` 10.4% on p0088). Only the LLM can do that.
- **Guard against overfitting.** Accept a tuned program only if it improves by a margin. The final held-out `test` check already catches overfitting. If you want a separate check, I can add a `valid` split to the evaluator (different seeds, same families), which is a two-line change on my side.
- **For the pitch:** this isn't "just tuning numbers". The LLM finds structure, and the optimiser polishes it.

## Order of work and expected effect

| # | Change | Where | Size | Effect |
|---|---|---|---|---|
| 1 | Pool keeps the best K so far (μ+λ) | `run.py` `generation()` | ~10 lines | Mutator and Researcher build on the best programs, not on the last batch |
| 2 | Mutator: code first, smaller limit, code-only retry | `prompts/mutator.md`, `llm.py`, `run.py` `candidate()` | small | Generations about 2× faster; wide's programs are real ideas |
| 3 | Mutator: mostly variants, 1–2 fresh-idea slots | `prompts/mutator.md`, `run.py` `wide()` | small | Fewer "as bad as the worst" mutations |
| 4 | Knock-outs only for real jumps, only on new parts | `run.py` `champion_plan()` | small | Deep spends its slots on improving |
| 5 | Optimiser tunes constants; LLM improve tests go to mechanisms | `run.py` `deep()` + a small tuner | ~60–100 lines | Large quick gain on the current champion; LLM effort goes where only it can help |

**Honest expectation.** Changes 1–4 should roughly double progress per minute: shorter generations, no wasted wide calls, and a population that remembers. Change 5 should give a clear one-off step on the current champion, then keep it tuned.

A gain in the next 10 generations bigger than everything so far (−9.18 → −6.96, 2.2 points) is unlikely from loop changes alone. Most of the remaining excess is in `anticorr` and `large`, and part of it is the lower bound being loose (it ignores job shapes), so 0% isn't reachable. Real headroom is smaller than the numbers suggest.

## How to tell it worked

- The pool line in each generation's record lists programs from several generations, not only the latest one.
- Mutator calls finish in well under 15 s, with almost no repairs.
- Mutator targets other than the champion score close to the champion, not around −8.
- The best score rises in most generations, with rows from `deep`, `tune` and `wide` in the report's "where the improvements came from" table.
