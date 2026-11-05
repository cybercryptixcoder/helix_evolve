# Run 8, walked through

A plain-language walk through run 8 (`results/20261017-014858-full`, 5 generations of the default feature engine from Code Zero), written to answer one question: **is the system doing what it was meant to do?** Not "did the code run", but "does the behaviour match the intent".

HANDOFF.md §7 is the reference for how the engine works. This file follows one run through it.

---

## 1. Who is in the factory

Only three of the stations are LLMs. Everything else is ordinary code.

| Station | LLM? | What it gets | What it gives back |
|---|---|---|---|
| **Library** | no | — | The current champion: a weighted sum of the features kept so far. Empty at the start. |
| **Inspect** | no | The champion | For one training instance per family, the champion's packing next to a near-optimal packing of the same jobs: bins used, jobs per bin, common bin make-ups, stranded bins, room left. |
| **Researcher** | yes | The packing comparison, the champion's features with their weights and importance, the room left per family, the research log, and a "lens" to look through | 4 feature ideas as JSON, plus at most 100 words of analysis |
| **Coder** | yes (one call per idea) | One idea, and the list of features that already exist | The idea written as `feature(item, bins, capacity)`, plus one sentence |
| **Mutator** | yes (4 calls) | **Only** the champion's code and its score, and an instruction: "a variant of feature X" or "a fresh feature" | A feature, and a name |
| **Fit** | no | Every feature from both loops | A verdict per feature: rejected by the probe, refuted, flat, or a gain on validation |
| **Accept** | no | The features that gained on validation | The new champion; the verdicts go into the research log |

Every LLM is DeepSeek V4.1 Flash on Luminal, with **thinking switched off** (`reasoning_effort: none`). Temperatures: Researcher 0.6, Coder 0.2, Mutator 0.8.

**Is there a separate hypothesis step?** No. The Researcher's reply *is* the hypotheses. Each idea has four parts:

- `claim`: what it saw in the packings and why it thinks it happens;
- `feature`: the measurement that would let the policy see it;
- `target`: which number in the comparison should move, and which way (the prediction);
- `builds_on`: an earlier idea from the log, if any.

Nothing ever tests the prediction. Fit scores the *feature*, not the *claim*: it asks "is the policy better with this measurement than without it", never "did the number the Researcher named actually move". The `target` is saved with the idea and not used again.

---

## 2. One cycle, start to finish (generation 0 into generation 1)

**Generation 0.** Code Zero goes into the library. With no features, every bin scores 0, and on a tie the oldest bin wins, so the policy is First Fit. Score −9.181. No LLM is involved.

**Generation 1, step 1: Inspect** (code). Code Zero packs one instance of each family, and so does a near-optimal packer. The differences are striking: in `large`, 436 bins against 382, with 55 bins *stranded* (one resource almost full, the other more than a quarter empty) against 2; in `anticorr`, 348 against 299, with 104 stranded against 0.

**Step 2: the Researcher** (one call, 6.7 s). It is told: here is the policy (no features yet), here is where the room is (anticorr 17 points, large 15, bimodal 8...), here are the packings, the log is empty; propose 4 features, and this generation look at *what a bin looks like just before and just after its last placement*.

Its reasoning, in its own short analysis: the champion never compares bins at all, and the packings show two failures, loose stranded bins (large, bimodal) and missing 4-job bins (anticorr). Its four hypotheses:

1. Prefer bins whose two leftovers end up balanced, so nothing is stranded.
2. Prefer the bin whose tighter leftover ends smallest (tightest fit), to pack denser.
3. In anticorr, prefer bins with slack on the resource the job *doesn't* use much.
4. Prefer bins that still have room for another typical job.

**Step 3a: four Coders**, in parallel (about 1.5 s each). Each gets one idea and writes it. They say which reading they chose when the idea is ambiguous ("I read *heavy* as the larger demand").

**Step 3b: four Mutator calls**, at the same time. Each sees the empty policy, its score and "write a fresh feature". It sees no packings, no ideas, no log. With nothing to vary, all four are fresh. It wrote: an imbalance-times-fullness score, a cosine between the bin's room and the job, "prefer the bin whose tighter resource ends fullest", and a thin-strip waste estimate. The Mutator explains nothing; it returns code and a name.

**Step 4: Fit** (code, about 13 s for all eight).

- *Check:* does it compile, use only numpy and math, return one finite number per bin, run fast enough? If not, its author gets one repair attempt.
- *Probe:* add the feature on top of the champion at four weights (+0.4, −0.4, +0.1, −0.1) and score on the training split. If it is worse than the champion by more than 0.08 at every weight, it is rejected here. (At generation 1 the champion is empty, so only the sign matters; that's why the four numbers come in two identical pairs.)
- *Trial,* for survivors only: search the feature's own weight, then refit all the weights twice, once with the feature and once without, and credit the feature with the difference, on training and on separate validation instances.

All eight were rejected by the probe. Three of them were the same idea (tightest fit, written once by the Mutator and twice by the Researcher's ideas), and all three scored exactly −0.350: tightest fit fills one resource and strands the other, which is worse than First Fit here.

**Step 5: Accept** (code). Nothing passed, so nothing is kept. The verdicts go into the research log. Each of the Researcher's four ideas is logged as **refuted**, with no number, because a feature rejected by the probe never gets a validation score. The Mutator's features aren't in the log at all.

That's the whole cycle. The only things that carry into generation 2 are the champion (unchanged) and four "refuted" lines.

---

## 3. Generation by generation

| Gen | Lens | Champion after | Kept |
|---|---|---|---|
| 0 | — | −9.181 (0%) | Code Zero |
| 1 | just before / after a bin's last placement | −9.181 | nothing |
| 2 | how size classes share a bin | −7.356 (20.8%) | `class_match_residual` (deep) |
| 3 | open a new bin or use an open one | −7.356 | nothing |
| 4 | just before / after a bin's last placement | −7.125 (23.5%) | `closing_bin_penalty` (deep) |
| 5 | how size classes share a bin | −6.774 (27.5%) | `big_with_big_room_penalty`, `bimodal_small_slot_for_large` (both deep) |

**Generation 2: the big jump.** The Researcher read the log and drew a real conclusion from it: the generation-1 balance ideas failed *because they ignored the arriving job*, so all four new ideas depend on the job. The one that worked is named and argued as "class matching", but the formula it asked for is a plain stranding penalty: score a bin negatively if this job would leave it with under 5% of one resource and over 25% of the other. +1.51 on validation. Stranded bins dropped to 0 in every family. The Mutator, still with nothing to vary, wrote four fresh features; one was the generation-1 cosine feature again, with identical results. The Researcher was also told "the small refinements are used up", which was false: there had been nothing to refine yet.

**Generation 3: nothing.** Now the Mutator had one feature to vary, so three of its four slots were variants of the stranding penalty (softer thresholds, different scaling), all rejected by the probe. The Researcher looked at opening a new bin versus using an open one; one of its ideas was generation 1's tightest-fit idea again with a penalty on the new bin. All eight rejected.

**Generation 4: Best Fit arrives.** The Researcher's key observation: the champion *never finishes a bin*; in `large` it closes bins with 12-14% left in both resources, where the optimum leaves 3% and 0%. It proposed "prefer the bin that ends up fullest overall", which is the textbook Best Fit rule. Kept (+0.18 validation), and by the end the feature the policy relies on most. Another idea was generation 2's complementary pairing with the sign flipped; the probe tries both signs, so it was the same test again. All four Mutator features (three more stranding variants) rejected.

**Generation 5: two small gains.** Five features passed validation, three from the Researcher and, for the first time, two from the Mutator. Combined best first, two Researcher features joined, both about where large jobs go; the other three, including both Mutator features, added nothing on top of them. One kept feature works the opposite way to its own claim: the claim said "reward bins that close cleanly or keep room for another large job", the formula rewarded tight and punished roomy, and the optimiser fitted a negative weight, so what the policy actually does is "for large jobs, prefer bins that keep 20% room in both resources".

---

## 4. Intent against what happens

| What was intended | What the code does | Matches? |
|---|---|---|
| The Mutator goes **wide**: tries many different things | It sees only the champion's code, aims 3 of its 4 slots at the champion's own features, and has no memory between generations | **No.** 0 of 20 kept; 7 of 9 variants were of one feature; it repeated a whole feature a generation later |
| The Researcher goes **deep**: forms hypotheses based on how earlier hypotheses scored | It reads the log and does adapt (generation 2 is a clear case), but the log gives only a verdict word, and a probe rejection reads as "refuted" with no number | **Partly.** The reasoning is real but thin, and it learns from claims, not from what the formula actually measured |
| A hypothesis is tested by a variant that **exaggerates one aspect** of the champion, to see if that aspect helps or hurts | No such step. A hypothesis becomes a *new measurement*, credited with the difference it makes. Exaggeration probes were the first design and were removed after runs 1-2 (HANDOFF §9) | **No.** It's a different design |
| The hypothesis's prediction is checked | The `target` ("stranded bins in large should fall") is stored and never compared with the next packing | **No** |
| Results go **back and forth** between evaluator, Researcher and Mutator | Results go only Fit → Accept → Library. The Mutator never sees verdicts; the two loops never exchange anything except through a kept feature | **No** |
| The system **orients itself** and avoids the same loop | The only steering is a fixed rotation of three lenses, and extra slots after 2 stalled generations. Nothing recognises that two ideas are the same | **No** |
| Visible reasoning | Thinking is off. The Researcher's claims and 100 words are the only "why"; the Mutator gives none | **Little** |

**What does work:** the Researcher reading packings is genuinely useful (every kept feature came from a concrete observation in them: stranded bins, unfinished bins, how large jobs pair), and Fit's with-versus-without credit is a fair and cheap judge. The engine reached in 5 generations what the old engine reached in 30.

---

## 5. What this means for the search-space work

The gaps above are the missing pieces of a search:

- **An identity for each approach.** Two features that give the same probe scores on the same champion rank bins the same way. That's a free fingerprint for "this has been tried".
- **A ledger of the space**, shared by both loops, so the Mutator stops re-proposing and the Researcher sees what was *measured*, not just what was *claimed*.
- **Checked predictions**: compare the Researcher's `target` with the next packing comparison, so a hypothesis is judged as a hypothesis.
- **Branching instead of one greedy line**: today a feature is judged alone on top of one champion, so features that only help together never survive.
- **Directed width**: the Mutator's slots aimed at unexplored regions of the ledger, not at the champion's strongest feature.
