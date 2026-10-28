# The conversation of October 27-28, 2026 (night): from the research case to v9's results and the axes

Shreyas's messages are kept **verbatim** (spoken, then transcribed; nothing corrected). Each is followed by the reply
as given. Times are Eastern (EDT). It begins one message before the request to analyse the v9 run, as asked.

The documents this conversation produced: `docs/RESEARCH_CASE.md` (the research case, also a shared doc),
`docs/V9_RESULTS.md` (the v9 job analysed), and `docs/IDEAS.md` (every idea, direction and open question from it).
Earlier that evening: `docs/RESEARCH_DIRECTION.md` and `docs/SURVEY_BRIEF.md` (superseded), and the advisor's
two questions (is one problem publishable; what similar work exists), recorded in `docs/REQUESTS.md`.

## 1. The research agent: survey further and make the case for a paper

**Shreyas, October 27, 22:59:**

> Okay. In all actuality, you are the research agent, and there was some residual stuff left from where I copied that earlier message. That's how it still says to write a research guide. Essentially, if you feel like you have already done justice to that research, then this would be the end of it. If you think there's further survey to be done from your end, you can go ahead and do that. You are essentially the researcher, and I need you to do this now. An important part of this is to:
>
> 1. not think about my evolutionary setup as a narrow build
> 2. not be pessimistic or demotivating at all
>
> The objective here is to figure out how to get this setup to be something worth publishing, make a case for that, and figure out how to make that case. For Amulia, the person that I want to work with, who I had the conversation with, I just need to make the case that, hey, right now, it's not at the state where we need it. But doing so-and-so and having this as our goal, we can have something ready to publish, so that's worth doing. Now, back to the first thing where I said this particular survey should not be thinking about my build as a narrow thing. In that discussion with Amulia, I essentially told him about an earlier version of this setup, and now it's grown, not just in terms of what has been implemented. I'm not trying to just get a paper out of the code that we've written. I am very well aware now that just one metric is not going to make a paper. The thing here is to figure out what is. When I was saying, "Don't think of my project narrowly," it means that you think of it conceptually. We have made a lot of conceptual progress here, and that is sort of what I am hoping to get a paper out of, and perhaps even more on top of it: learning more on top of it. If there is a research question to be answered that is not well addressed, or is addressed to an extent but we're building on top of it, then that gives us something to work with. That conversation with Amulya really makes it seem like, "Oh, I'm just trying to get a paper published. That shows this architecture, but that architecture is not the crux. The research question is the crux. The architecture is just a means of supporting that and showcasing that, or using that conceptual thing. We tested it empirically, and this is what we were able to achieve." Yes, the architecture is also what contributes to it, because that's essentially our research method. Our architecture is our research method: how we manage to use this concept to build something that could break records. Different metrics would be the results and benchmarks that we showcase, and the research question is the thing that we're trying to understand, explore, and do. This is actually meant to not be a narrow paper, because I hate papers that are just one small empirical addition or just one small detail that is being added to something very generic. I hate those kinds of papers where they're just adding one more statistic, not even a real contribution. It's just one more statistic that is being added, one more thing measured because no one measured it. I hate papers like that. I want to write something that is actually a really good paper, and a good paper in the sense that it contributes significantly in the conceptual realm and showcases that by building this thing. That's the whole thing I'm getting out of this. I'm really trying to do something cool here. I'm trying to build something really good and make a really good paper. I don't want to just "qualify" for making this a paper. I want to make this a genuinely good paper that someone reads, appreciates, and respects.For that, we need to figure out. Here, when I say "don't be pessimistic and don't be discouraging," what I mean is don't say that: "What we have right now is nowhere close to what we can publish." I'm like, "I know that." Rather, it's more so:
>
> * How can we progress in this research direction to have something good to publish?
> * How can we reframe our thing that we're working on to be something that can be published?
> * What else can we do?
> * What can we add?
> * How can we build on top of what exists?
> * What kind of papers do get published in this realm?
> * Those two kinds that Amulya mentioned, right? What kind of papers get published there?
> * What we do, how we do it
>
> That's the kind of exploration I want you to do. I want you to figure out how, not just say that it's not up to the mark. That's what I meant by the second part, which is: don't be discouraging. I think you have an idea of what I want to do. Good luck. Spend a good amount of time exploring, and come back to me with what I need to know. The survey of the landscape is to:
>
> * Figure out what exists, what kind of papers get published in this realm, and even tangential realms.
> * Figure out whether we can build on top of something, whether we can contribute to something, and whether we can answer some open questions.
> * See if all of the things that we look into help us reframe our research question or frame our research question, and so on.
>
> Make this worth it. Good luck. Explore well.

**Reply:**

I've written the case for Amulya as a doc: **Helix: the research question and the case for it**. It's also saved and pushed to the repo as `docs/RESEARCH_CASE.md`.

**The research question.** Today's LLM discovery systems can only reach what their language model would already write, and Helix's work points past that limit. The question: can a discovery system map the space it searches, steer to where its model would not go, and change that space when it runs dry? Helix is the method, and the records and the routing case are the showcase.

**Why it's worth Amulya's time: the field's own recent results point straight at it.**
- **Artificial Hivemind** (NeurIPS 2025 best paper) found that models repeat themselves and each other.
- **Yue et al.** (NeurIPS 2025 runner-up) showed RL doesn't get past what the base model can already sample.
- **PlanSearch** (ICLR 2025) found that variety at the level of ideas, not code, is what makes search pay off.
- **Krishnamurthy et al.** (NeurIPS 2024) showed models explore only when handed summary statistics, and its authors doubt such summaries can be built for complex tasks. Helix's map is that summary, built for open-ended search.
- **The 2026 analyses** of these search systems found the search space matters more than the search algorithm, and that about 30% of added code re-adds lines deleted earlier.
- **A 2026 debate** argues AI can't change its own conceptual space, and that testing whether it can "may be an unsolved problem".

**Where it fits.** Recent systems push past the model's defaults in one of three ways:
- choosing which past programs the model sees (ShinkaEvolve, OpenEvolve);
- retraining the model (TTT-Discover, SOAR);
- writing ideas down for the model to work from (PlanSearch, Google's Idea Search).

Helix does the third more fully: a learned map of design decisions it can move across on purpose and change, without any training. On "rearrangement": Go-Explore's parts all existed before it too. Its naming of the problem, the principle it drew from that, and broad evidence made it a landmark. That is the shape proposed here.

**Three research questions, each worth knowing whatever the answer:**
1. **Why do searches stall?** Measured across several models and frameworks, using 121 public search runs from four frameworks plus ours.
2. **Can a search map its own space and steer by it?** Tested at equal budget against simple baselines, OpenEvolve, ShinkaEvolve, and generic diversity methods.
3. **Do breakthroughs come from changing the space?** Our routing breakthrough came from replacing the greedy start every program shared. That parallels insight in human problem-solving, which comes from dropping an assumption.

The doc also lists nine findings Helix has already measured, each with a link to its source in the repo.

**The plan:** six work packages to NeurIPS 2027 (deadline around May 21, projected), with a go-or-adjust pilot by December 20. My cost estimate is about 2,500 CPU-hours and $2,000–5,000 of model calls.

The doc ends with five decisions to make with Amulya: which claim to commit to, venue, compute, how rigorous to make it, and whether the routing case can be reported.

The two docs from earlier tonight (the survey brief and the narrower direction memo) are superseded. I can delete them if you like.

Amulya can't open the doc until you share it from its Share menu.

Sources:
- [Artificial Hivemind, NeurIPS 2025 awards](https://blog.neurips.cc/2025/11/26/announcing-the-neurips-2025-best-paper-awards/)
- [Does RL incentivize reasoning beyond the base model?](https://neurips.cc/virtual/2025/oral/119945)
- [PlanSearch](https://iclr.cc/virtual/2025/poster/31034)
- [Can LLMs explore in-context?](https://arxiv.org/html/2403.15371v3)
- [Simple Baselines are Competitive with Code Evolution](https://arxiv.org/abs/2602.16805)
- [What Do Evolutionary Coding Agents Evolve?](https://arxiv.org/abs/2605.20086)
- [Georgiev et al.](https://arxiv.org/abs/2511.02864)
- [Idea Search](https://arxiv.org/html/2608.08958)
- [PIEVO](https://arxiv.org/html/2602.06448v1)
- [Go-Explore](https://arxiv.org/abs/2004.12919v3)
- [Knoblich et al. 1999](https://www.kognition.uni-koeln.de/literature/Knoblich_etal_1999.pdf)
- [On the creativity of AI agents](https://www.emergentmind.com/papers/2604.13242)
- [Transformational creativity in science](https://arxiv.org/html/2504.18687v1)
- [NeurIPS 2026 workshops](https://blog.neurips.cc/2026/08/10/announcing-the-neurips-2026-workshops/)

*(The doc it refers to is `docs/RESEARCH_CASE.md`; the two diagrams in the shared doc are described there as a table.)*

---

## 2. Drop wide, climb, repeat; the three agreed steps; analyse the finished v9 run; is GitHub lossless?

**Shreyas, October 28, 03:31:**

> The objective with what we're trying to build is simply to build something that is amazing at searching for a good solution, as in, it is really quick to find a solution that is good. The important bit is that we can go further than just good, because we get to good solutions fairly quickly either way. What we want to do is get to really, really good solutions, which are a little more rare to find in the search space. What we need to be able to do is be really good at exploring that.
> Beyond a certain point, if you have scored really well, we need to be able to go extremely wide. On the map, this would look like dropping a whole bunch of points on a whole bunch of different spots, which are completely different from each other. It's important that they are at completely different points on the map itself.
> Then we allow our search to climb to basically find the top of the hill for each of those points. We should be able to do that fairly quickly because we're good at climbing hills. Then we repeat the process. Let's say we didn't find, so now we basically just keep the best hills. The top programs are going to be the highest hills we found.
> Then we run the thing again. This time, we again randomize to a whole bunch of new points and see how we do from there. We repeat the same again and again and again and see how it goes. That's kind of the goal here, right, so that we explore as much of the map as possible, as widely as possible.
> I think it is important for us to understand what each of the axes is and how it's being quantified, because there were three specific things that are in that discussion that we decided upon. Can you quickly list those three things for me?
> I believe they are:
> 1. Identifying if there is a fixed number of axes.
> 2. Being able to quantify things per axis.
> 3. Being able to randomize values on each of the axes to get a random point, and then getting many random points and then exploring from each of them.
> This is basically a search where we drop a whole bunch of random points, and then we search, and then we drop a whole bunch of random points again, and then we search, and then we do this over and over again.
> Maybe a little cleverer than random is that the first time we drop everything randomly. The second time is where we take a pseudo-random, calculated, very large step away from the current point onto a new point. That way, we ensure that we never step into the regions that have been explored.
> Imagine dropping a bunch of random points into a whole bunch of different spaces, like a whole bunch of different parts of the map. Now let's say you explore that region. Now that you've explored it, there's a certain radius around each of those points that has been explored. Now it makes no sense to have the new points also land in those same regions, because then you would climb the same hills. Our next random set of points should basically be a large jump away from our original set of random points, such that they do not climb the same hills.
> That's what I'm saying. Now I want you to reason about that. Then I want you to also deeply analyze the run that has now completed, which is basically Helix V9. It made no progress at all in terms of the actual score. I mean, it did, but it was on the order of the negative 15th exponent, so it doesn't really help a lot.
> Also, perhaps we need some way of rejecting hills quickly. Can we shoot to the top of the hill quickly and then move on? Maybe that's also worth thinking about. Anyway, you can do an analysis of the traces and everything that we've got for the current run. See what happened under the hood and tell me what you find.
> Don't just design the new version immediately, because for the 9th version, I kind of gave you the complete freedom to figure out how to build and then build. The 10th version I kind of want to take on myself in terms of what is to be built, but that'll happen after a little bit of discussion and back-and-forth, and understanding what we achieved on V9, or if we completely failed, or if it was completely useless. That's something we need to figure out.
> Also check that now everything is pushed to GitHub and that, going forward, everything would be lossless if we were to continue from GitHub.

**Reply:**

### The three steps we agreed on

Your list is right:
1. **Is the number of axes fixed?** At the top level, roughly yes: about 9 recurring decisions cover 98% of what the model names, and v9's map stayed between 12 and 18. Underneath, no: the options keep growing. The map was regrouped 188 times in 100 generations, because the model keeps rewording the same options.
2. **Quantify each axis.** Each axis is a categorical option that the model reads off the code. Reading is reliable: 12 of 13 decisions read with at least 80% agreement. Writing is not: when asked to build a given coordinate, only 42% of the requested values landed (55 of 132).
3. **Random values, many points, explore from each.** v9 never really did this. Its "drops" changed 2 to 4 decisions of the record, so they were near jumps, not random far points, and none of them got climbed.

### What v9 did under the hood

- **The record moved by 2.5e-13 over 100 generations.** That's no progress, though v8 was already flat (+8.5e-11 over its last 100). Six hours, 1,937 model calls.
- **About 70% of the budget went into the record's own hill.** 256 of 300 planned experiments and 167 of 300 mutations started from the record. On average, 4.7 of the 6 programs each generation handed their starting construction back unchanged.
- **The race was captured by copies of the record.** Flips and ablations that changed nothing landed back on the record's hill and tied it, so at equal effort they always ranked above the median and kept being promoted. In 35 generations all three race slots were such copies. Meanwhile 49 genuinely new explorations got one experiment each and sat in the queue. **Nothing new was ever climbed.** It's the "judged at its foot" failure again, through a guard that covered drops but not flips or ablations.
- **Drops near the record landed at 0.58 to 0.85, and 10 of 18 never produced a valid program.** Changing a few decisions of a tightly tuned construction breaks it, which matches the map's own finding that one interaction explains 61% of the variance.
- **The current space may be saturated.** Eight distinct hills top out within 3e-7 of 0.94144. Systems that went higher (0.951 to 0.9626) changed the representation itself. Every Helix hill shares one assumption: a uniform grid of heights polished by a gradient optimiser. That assumption isn't an axis on the map.

So v9 wasn't useless: the map ran as designed and gave a clear diagnosis. But its exploration was starved. It never tested whether dropping and then climbing finds taller hills.

### Your idea: drop wide, climb fast, keep the best hills, repeat away from explored areas

The idea is sound and well established in global optimisation. "Don't start a new climb near a point already explored" is how clustering multistart works, and spreading the points apart is farthest-point sampling. What the runs suggest you'd need to resolve:

- **Climbing is the expensive part.** In Helix, climbing a hill means many generations of model calls: the record's hill took hundreds, and the strongest v8 restarts reached about 0.91 in 8 to 12 experiments. Twenty drops climbed properly could cost thousands of programs. Climbing fast probably means pushing more of it into CPU-side optimisation inside each program, rather than more model edits.
- **Quick rejection collides with one measurement.** A run's best after 20 programs didn't predict its final best at all (rank correlation -0.09); after 40 it did, moderately (0.50). v9 effectively rejected new hills after one experiment, and that is exactly why it found nothing. A fixed small climbing budget for every point, then cut, is safer than judging the first score.
- **"Far on the map" isn't "a different hill".** Different coordinates often climbed to the same height: those 8 hills tie each other. So the exclusion radius probably belongs on where a point ends up (its construction), not only on where it started.
- **Far random points are the hardest to build.** Only 42% of requested values landed even for near jumps. Random coordinates need a read-back check to confirm the program is where we asked.
- **The map may not contain the taller hills.** Dropping widely within today's axes could keep finding more 0.94144-level hills. Some drops might need to vary the assumptions every program shares.

### GitHub and losslessness

- **Run records are complete on GitHub:** all 4,351 programs, the full trace of 1,937 calls, the map, tracks, hills, report, verification and continuation pack.
- **298 of 4,146 valid constructions were missing.** The uploader checked them against the problem's default limit of 200,000 steps, while these runs allow 1,000,000. This is also the real cause of v8's 206 "failed verification". I fixed the check.
- **Uploads now build on earlier ones.** v9's upload hadn't recorded that it depends on v8's. Each upload now names the earlier uploads it builds on, holds only what they lack, and downloading it restores the whole chain. Tests pass, and the chain reading works against the real uploads.
- **One step is left, on the VM**, because the 298 only exist there. The command for Aether is in `docs/V9_RESULTS.md`. After that, continuing from GitHub alone is lossless.

The full analysis is in `docs/V9_RESULTS.md`, and everything is pushed. I haven't designed anything for v10.

*(The full analysis, with the numbers and the Aether prompt for the last upload: `docs/V9_RESULTS.md`. Code changed: `helix9/pack.py`, `helix9/vault.py`, `scripts/run_v9_warm.sh`, tests in `tests/test_helix9_run.py`.)*

---

## 3. The map may not contain the taller hills: how do we find all the axes?

**Shreyas, October 28, 04:26:**

> The first and most important thing that I notice here is that the map may not contain the taller hills and that means that there is another axis or other axes that we haven't tapped into.
>
> The first question is: how do we discover all the axes? Perhaps there should be two things that are done in series, right? The first would be to find all the axes and then run the evolutionary loop.
>
> How do we find all the axes in a provable or definitive manner so that we're confident that these are the only axes that it can be varied upon? How do we land on a fixed set of axes? That's the first question.

**Reply:**

Short answer: we can't prove a complete list of axes for an open-ended program space. We can get a complete list relative to a defined scope, plus a measured confidence that we've found nearly everything. Here's why, and what is achievable.

### Why "provably all the axes" is impossible as stated

An axis is a design decision someone has noticed. Programs can do anything computable, so there is always another way to represent, transform or search that nobody has written down yet. Any finite list of axes is a coordinate system we chose, not a property of the space. The runs agree. The top level settled at about 9 decisions, but options and sub-decisions kept appearing until the last generation of v9. Some decisions exist only after another is made: a cooling schedule appears only once you choose annealing.

So "fixed" can only mean fixed at a chosen level of abstraction. Below that level, the space stays open.

### What we can do instead

**1. Completeness by construction, at the top level.** Every program for a problem must do a few things: represent a solution, build a first one, define what it optimises, search, split its time, and return a result. These stages are fixed by the shape of the computation, not by what we've seen. Each stage is a guaranteed axis, and each has a fixed set of options only if we close it.
- **What it gives:** a provably complete skeleton.
- **What it costs:** if we close the options, the taller hills may sit outside them.

**2. Derive axes from the problem's mathematics, not from our programs.** Our current axes came from reading our own programs. That means they can only describe what our programs already do, which is exactly the blind spot. For AC2, the objective's structure suggests axes directly:
- the class of function (uniform steps, free step widths, smooth bumps, spikes);
- how the max term is handled (hard max, smooth surrogates, relaxations);
- symmetry;
- scale, from 50 steps to 1,000,000;
- where it starts (from scratch, or from known constructions).

**3. Read in solutions from outside our search.** This is the most direct test of your worry. Higher AC2 results exist, from AlphaEvolve, ImprovEvolve and TTT-Discover, along with the published methods behind them. If our map can't describe how those differ from our 0.94144 programs, the missing axis is right there, named by the difference. The same works with programs sampled from other models, and from prompts like "list every fundamentally different way to attack this".

**4. Measure saturation, so confidence is a number.** Ecologists face the same problem: you can't prove you've found every species, but you can estimate how many you've missed. Keep sampling diverse programs and descriptions, and count how often a new axis appears. When new axes stop appearing, the curve flattens. Standard estimators (rarefaction, Chao1, Good-Turing) then give the probability that the next sample reveals a new one. We could say, for example, "95% confident the next 100 samples contain no new axis". We can't say "these are all the axes".

**5. Two built-in alarms for a missing axis:**
- **Residuals.** If the axes captured everything that matters, programs with the same coordinates would reach similar heights. Large differences at the same coordinates mean an unmeasured decision.
- **Invariants.** This check targets your exact concern. A decision every program makes the same way never varies, so the residual test can't see it. It needs its own audit: "what do all our programs do identically?" Every Helix hill uses a uniform grid polished by a gradient optimiser. That's a candidate axis with only one value ever tried, and the 8 hills tied at 0.94144 suggest it may be the ceiling.

### Axis discovery first, then evolution: mostly right, with one catch

A dedicated discovery phase up front should find most axes: the top-level skeleton, the problem's mathematics, outside solutions, and sampling until saturation. Then run the loop on a fixed top level. The catch is that some axes only become visible once the search reaches a region, as with decisions that only exist after another choice is made. So the loop should keep the two alarms (residuals and invariants) running cheaply, and reopen discovery only when one fires.

### A cheap first step

Before deciding the design, we could test the worry directly. Read the published higher AC2 constructions and methods onto v9's map, and run the invariant audit on our 77 hills. That tells us whether the missing axis is real and what it is, for a few model calls and no new runs.

Do you want that check first, or should we settle the discovery-phase design (options 1–4) before running anything?

---

## 4. Warm starts: is borrowing existing solutions cheating? What do other systems do?

**Shreyas, October 28, 04:36:**

> In my mind any time I think about taking an existing solution and giving it to our system as a warm start (given that we have not discovered that solution), it makes it so that our system is kind of cheating.
>
> What I'm wondering is whether the industry or the domain of research also thinks the same way. Did Alpha Evolves and all of these other evolutionary algorithms discover the best setup? Did they do that from scratch or did they also warm start their algorithms with a whole bunch of existing algorithms and allow it to then discover something even better?
>
> If that's the case then I guess we should be open to doing that as well. Arguably our setup might be able to discover something even better than theirs because what we do is explore the breadth of different axes. If they give us a new axis, it is possible that they only discovered that axis and they don't run a search mechanism like the one we do. They just discovered that something helped and kept it at that. If we can quantify that axis, then we should be able to cycle through it and find a potentially even better solution.  I want you to check what other researchers do. What is the general trend? What have other evolutionary systems done? Is it a general policy that everyone starts from scratch and then discovers on their own? Or is it an expected trend to simply take whatever the current best algorithm is and give that as a warm start to the setup? By the current best I mean the current best in the world.

**Reply:**

It isn't treated as cheating. It's treated as a different kind of claim, and the field's norm is: warm-start if you like, but say so and report it separately.

### What the systems actually did

| System | What it started from |
| --- | --- |
| AlphaEvolve, on 67 maths problems ([Georgiev, Gómez-Serrano, Tao, Wagner](https://arxiv.org/pdf/2511.02864)) | By default "a few simple initial programs", then heavy expert help when stuck. They suggested a known construction as "a good starting point" for the Kakeya needle problem. They "showed it the correct code" for Singer difference sets on the difference-bases problem, after which it beat the old bound. They told it about a Newton-type method for the autocorrelation problem. They say expert advice "almost always led to significantly better results" and present that as part of the method. |
| ImprovEvolve's 0.96258 (the AC2 record) | Started from AlphaEvolve's own best solution, plus an expert edit, and reported under a separate label (+E). Its own from-scratch-style result, 0.9512, is listed apart. |
| [TTT-Discover](https://arxiv.org/pdf/2601.16175) (ICML 2026) | Maths: from scratch on purpose. It warns that starting from the best known solution "might be too strong a prior towards exploitation". But it started its biology task from MAGIC, the prior best method, and one AtCoder task from the previous best program. |
| [ThetaEvolve](https://arxiv.org/pdf/2511.23473) | Main results from the provided initial program. Starting from AlphaEvolve's best solution was a separate experiment, and it gave "only slight gains": the best solution may already be a local optimum. |
| OpenEvolve in systems research ([Barbarians at the Gate](https://arxiv.org/html/2510.06189v1)) | Starts from the published best algorithm by default: "use public source (GitHub/paper) if available, otherwise use simple algorithm." |

### The general trend

- **To claim a new world record (a discovery):** start from anything, including the world's best solution, the code behind it, or hints from papers. That's accepted as long as it is disclosed. AlphaEvolve's maths results depended on it.
- **To claim your search method is better:** start from scratch or from a simple program, with the same knowledge as the systems you compare against. TTT-Discover stresses its from-scratch maths results for this reason. [Simple Baselines](https://arxiv.org/abs/2602.16805) warns that knowledge embedded in the prompt inflates apparent efficiency. It asks papers to say which of the two claims they are making.
- **How it's reported:** in two columns. Warm-started results are labelled ("+E", "with SOTA initialization") and listed next to the from-scratch ones.

Your instinct matches the method-claim standard, and so does the earlier standing rule that a warm start only counts if the gain on top of it is very significant. But "never warm-start" is stricter than the field.

### What this means for us

There are three levels of borrowing, and they mean different things:
1. **Their construction as our start** (the 0.96 array). This is pure exploitation. ThetaEvolve and TTT-Discover both found little left to gain locally, and a gain would only count as a discovery claim.
2. **Their method or code.** This is how ADRS, and AlphaEvolve with Singer sets, worked. It's legitimate if disclosed.
3. **Only their idea, as a new axis on our map.** This is your argument, and it's the most interesting one for us. They found a direction that helps and stopped there. We would add it as an axis, try its other options, and combine them with our other axes. Whatever we find beyond their solution is credit our search earns. It's still disclosed knowledge, so it belongs in the discovery column, but the gain on top of it is attributable to the method.

A clean way to report it would be two columns, as the field does:
- **Helix from scratch:** the method's credit, comparable to TTT-Discover and ThetaEvolve's main runs.
- **Helix with published axes added:** "given what the world knows, Helix finds X", labelled like ImprovEvolve's +E.

Using their solutions to fill gaps in our map, without starting from their constructions, keeps both columns honest.

---

## 5. Is this still a discovery system? Model intelligence versus search

**Shreyas, October 28, 05:00:**

> Okay the third option is quite promising, I think, and probably what we would end up working with next. Also hopefully that's what helps us get past the record.
>
> Now what I'm wondering (and this is just in my own head and kind of a little bit unrelated to the research aspect of it) is the fact that what I believed we were building is a discovery system: a system that can simply discover things, which is something amazing, right? You're building something that does the discovery for you, which is kind of insane if you think about it.
>
> I feel like this version of it, where we take an existing access and build on top of it, is not really true to that discovery aspect. In the sense that we're building a setup that takes different brilliant ideas that people have had and then it just searches over that space and finds something good (as in it finds the best version of that).
>
> Let's say I had an idea to approach a problem a certain way. This setup was able to find the best way to use that approach to the fullest extent and give us a result accordingly. That's the kind of system that we're building right now.
>
> It's not so much that the system itself is capable of coming up with those brilliant ideas, which is what we were hoping, which I presume would happen in the near future with bigger models. Using those, not even just in the future, maybe even just today, if I were to use something like Fable 5.1 or Opus 5.5, that would probably also be able to discover a lot more. Obviously it's a lot more expensive to run those models.
>
> My working hypothesis was that this sort of a discovery system is somewhat independent, to an extent, of the intelligence of the model. Obviously you cannot work with a 1-billion-parameter model. Beyond a certain threshold all that matters is how long you run the thing. A smarter model would discover something quicker while a dumber model would take longer for the same. Apart from that it's fairly agnostic to how smart the model is.
>
> That was the working hypothesis. I suppose that would fail here. In general we're not building a discovery system anymore. We're building a search system that searches through discovered axes. One might argue that's even good. Maybe we don't want the beautiful art of discovery to be automated. Maybe a human-AI collaboration is what it would take to make brilliant discoveries. Now the way that I've framed this message kind of implicitly puts it in one view of everything that we've got here but I would encourage you to not be limited to that view. You can completely disagree with me, you can completely agree with me, you can find a middle ground or something else. You don't have to fall into what is implicitly being stated here.

**Reply:**

I'd disagree with one part and keep another.

**Taking ideas in doesn't stop it being a discovery system.** Every human discoverer starts from other people's ideas. Most discoveries are new combinations of known ideas pushed somewhere nobody pushed them. Only occasionally does someone invent a new way of seeing the problem. Margaret Boden, who studied creativity, put this as three kinds: combining ideas, exploring within a framing, and transforming the framing itself. A scientist who reads the literature is still the one who discovers. What makes something a discovery is whether the output is something nobody had, not whether the inputs were empty. A system that may never read anything is handicapped for no good reason.

**Helix has already discovered things on its own.** The routing breakthrough came from the system noticing that every program shared the same greedy start, and replacing it. Nobody gave it that idea, and it is exactly the "transform the framing" kind. v9 also found 23 new decisions by itself. The AC2 result came from scratch and beat the best published human result. So the honest picture is: Helix discovers within reach of what its model can imagine. It occasionally makes the larger kind of move. It doesn't yet do that reliably. Importing axes doesn't replace that capability; it's a second channel next to it.

**Your hypothesis about model intelligence is half right, and the boundary is the interesting part.** Above a threshold, a smarter model is faster for ideas the weaker model can reach. For those ideas, time does stand in for intelligence. It fails for ideas the weaker model almost never writes. If the chance per sample is one in a billion, running longer doesn't rescue you in practice. The evidence leans this way:
- **RL stays inside what the base model can sample.** RL training on verifiable rewards didn't make models reach answers the base model couldn't already sample (Yue et al., NeurIPS 2025).
- **Swapping the model changed what was reachable.** GigaEvo's kissing-number progress came only after changing models.
- **Same method, different heights.** TTT-Discover reached 0.947 with an 8B model and 0.959 with a 120B model.
- **Cheap models helped AlphaEvolve but couldn't finish the hardest problem.** Its team found cheap models added useful variety, but couldn't produce the hardest construction.
- **Our own runs:** all 19 fresh restarts fell into the same textbook basin.

So there isn't one threshold; each idea has its own. The model's intelligence decides which ideas are reachable at all; run time decides how fast you get to the reachable ones.

**The architecture can move that boundary, and that's the strongest form of what you're building.** Asking the model for coordinates it would never choose, or for a change to something every program shares, pushes it toward ideas it rarely visits on its own. Prompting can't make an impossible idea possible, but it can turn a one-in-a-billion idea into a one-in-a-thousand one. If that works, structure is substituting for intelligence, which is the claim your hypothesis was reaching for.

**Your hypothesis can become an experiment instead of an assumption.** Run the same Helix with a cheap, a mid and a strong model (Fable 5.1 or Opus 5.5 for a short run), and plot height against generations.
- **Your hypothesis holds** if the curves are the same shape, shifted in time.
- **It fails** if they flatten at different heights.
- **The map is doing its job** if it narrows the gap between them.

This would fit naturally as a research question in the paper, and few people have measured it.

**On human-AI collaboration:** I don't think you have to choose. Today's best results already come from collaboration: AlphaEvolve's maths results leaned heavily on expert hints. The map gives Helix an unusually clean interface for it: a person adds an axis, and the system exhausts it and combines it with everything else. That's valuable now. Meanwhile, keep the from-scratch column and the "what does every program share?" audit as the test of autonomous discovery. If that column improves, you've built the stronger thing; if it doesn't, the collaboration column still stands.

---

## 6. Borrowed axes, the model as a compiler: a defensible claim?

**Shreyas, October 28, 05:13:**

> Okay this is cool. Like you said, an architecture can move the boundary of what the intelligence of the model sets and I would imagine even more so than one would expect if done right.
>
> If the architecture is a search mechanism, then ideas are not necessarily limited by the intelligence of a model. In the manner that we're doing it, ideas are essentially constructed from the rules we're setting for combinations of different things, meaning that we have taken approaches and put that into axes. Different combinations of those approaches are essentially ideas so at each point there is a construction of an idea. We're forcing the model to essentially search that space. If an idea exists in that search space, we can find it regardless of whether the model was capable of finding it on its own or coming up with an idea like that on its own.
>
> In this sort of a scenario maybe the axes are completely borrowed, as in we run one round of internet deep research and so on. We find all the different approaches that are existent in the world, what the best approaches are and so on, and we use that to construct our axes. That's a one-time thing for a given problem and then we turn that into a search space and search over it.
>
> Over here the model is not really contributing to ideating. That's not what the model is there for at all. The model is simply there to convert an idea into code because that's what these LLMs can do reliably, right? They can essentially take what you ask it to build and build it in code and do that fairly easily, right?
>
> Essentially the LLM is just another mechanical tool here that is not so much pressed for creativity as it is for following a process. It's not a system prompt that is telling it to, "Oh be creative and discover." It's a system prompt forcing it to follow a mechanism and not just a system prompt. Obviously it's the architecture itself too but we're forcing it to follow a mechanism that allows it to combine different axes and basically find points on this search space and search it in a very mechanical fashion.
>
> The only thing that the LLM is doing is writing the code. That's the part where the LLM fits in. If, let's say, the code somehow already existed for each of these different points, then imagine this search space: every point that exists, let's say, has code that is also present for it, okay? Somehow just magically, we wouldn't need the LLM at all. We would just run each of those codes and we would see the value of that and use that to essentially search for the best programme, and our search mechanism would just be to search over that space but the programmes don't magically exist and the LLM is what writes it. This is kind of what makes this setup intelligence-agnostic. The only threshold is that an LLM is smart enough to take a description of a certain programme and turn that into code reliably and predictably. That's essentially the only threshold of intelligence that the LLM would need to be above and past that it would simply be a matter of time.
>
> Again all of the axes and all of the ideas, we're not asking the LLM to discover. All of that can be taken, like we discussed earlier, but we search over that. That's the mechanism that we build. Does that make sense?
>
> Also is that a kind of defensible research claim or question or hypothesis and experiment, and also a defensible thing for the architecture itself (because we are borrowing the axes but we're searching over them)? Does that still count as category 3 of what we had listed above?

**Reply:**

Yes, it makes sense, and it's a coherent stance. Here it is in one sentence: ideas come from outside (the world's literature), turned into axes; the search over their combinations is the method; the language model is a compiler from a description to code. Under that stance, discovery means finding the best combination of known ideas, which nobody had tried, and that is a real kind of discovery. It's a narrower claim than "the system invents ideas", but it's testable, and cleaner.

### Where the "the model just compiles" assumption is weaker than it looks

Two things in our own data push back, and they're the core of the experiment, not reasons to drop it.

**A point doesn't determine its code, or its score.** Many programs implement the same combination. How well they do depends on implementation details, glue between components, constants and tuning.
- On AC2, almost all of the record hill's progress after its founding was this kind of within-point polish.
- One 2026 analysis of these search systems found that tuning only the constants of mid-run programs matched the run's final best in 13 of 15 cases.

So the model isn't only compiling; it's also doing the climbing within a point. That's where intelligence leaks back in.

**Compiling a new combination isn't mechanical.** In v9, only 42% of requested decision values actually landed in the code, and 21 of 74 blueprints landed fully. Combinations nobody has written before are the hardest to build faithfully, because the parts have to be adapted to each other.

There's an implication, not a design: you could make the model's role genuinely mechanical. It writes the code for a point once; a classical optimiser tunes its numbers; the map searches over points. Then the model's skill matters through two things you can measure: fidelity (did it build the point it was asked for?) and quality (how high does that point's code climb?).

### Is it defensible as a research claim?

Yes, but not as "intelligence doesn't matter beyond a threshold". A reviewer would knock that over with one example. The defensible version is:

> Given a fixed space of ideas, a model's capability affects discovery mainly through implementation fidelity and speed. Above a fidelity threshold, more budget closes the gap between weaker and stronger models.

That can be falsified, which makes it a good hypothesis. The experiment:
- **Setup:** the same harvested axes, the same search, and three or four models from cheap to frontier.
- **Measure:** fidelity of each model (fraction of requested values that land), the height reached within the same points, and height against budget.
- **Supported** if the curves are the same shape shifted in time, and reach the same plateau.
- **Refuted** if stronger models plateau higher on the same axes: then implementation quality is a form of intelligence the architecture can't replace.
- **Control:** each model also runs unconstrained ("be creative"). This shows how much the architecture lifts weaker models compared with stronger ones.

Either outcome is publishable, because it answers a question people genuinely argue about.

### Is the architecture defensible if the axes are borrowed?

It is, but be aware that its closest ancestor isn't LLM evolution. It's automated algorithm design from components. SATenstein (2009) built SAT solvers from a library of components; irace and AutoMOEA configured algorithms whose "configuration space is actually a design space". Reviewers from that community will say "this is algorithm configuration". The honest answer, and the real novelty, is what the language model adds:
- **No pre-written components:** each idea is described in text and implemented on demand, so the space isn't limited to what someone already coded.
- **Axes harvested automatically:** from the literature for each new problem, rather than hand-built by experts.
- **Combinations nobody has implemented:** arbitrary combinations of those ideas become runnable.

Framed that way, it's a genuine step: LLMs turn algorithm configuration from a closed library into an open space defined in text.

### Does it still count as option 3?

Yes: borrowing ideas as axes, not solutions or code. Two conditions keep it clean:
1. **Report it as building on published knowledge, as ImprovEvolve's "+E" does.** The ideas' credit goes to their sources; the best combination's credit goes to the search.
2. **Give the comparison systems the same knowledge.** Baselines should get the same harvested literature, for example in their prompt. Otherwise a reviewer will say the gain came from the research step, not the search. This is the "same domain knowledge in the prompt" point from the Simple Baselines paper.

If the axes come only from a deep-research pass, the system will never find an idea outside them, by construction. That's a legitimate scope. But it's worth keeping the small "what does every program do the same way?" audit, so the space can still grow, and so that column of autonomous discovery stays available to measure.

---

## 7. Asking "what does every program do the same way?" until nothing is common

**Shreyas, October 28, 05:17:**

> Do you think it's possible to run a loop where you ask, "What does every programme do in the same way?" over and over until there is nothing uniformly common between all of the programmes? Basically you keep splitting until there is no common factor. Would that allow you to find all the axes we need at this level of abstraction?

**Reply:**

Yes, I think it would work, and it's a principled version of a known heuristic. Kaplan and Simon found that people break out of a wrong framing by noticing invariants, things that stay the same across every attempt. It finds a great deal, but "until there's no common factor left" won't terminate on its own. It finds every axis the describer can name, not every axis that exists.

**Why it doesn't terminate by itself.** At some level every program will always share something: it's Python, it returns an array, it uses floating point, it runs within the time limit. So each answer the loop gives needs sorting into one of four kinds:
1. **A constraint of the problem** (the output must be a non-negative step function). This isn't an axis; it can't be varied.
2. **Below the level we care about** (variable names, code style). Ignore.
3. **Varyable but irrelevant:** changing it doesn't change behaviour or score. It's a real axis that doesn't matter; drop it after one test.
4. **A real frozen axis**, the target: a design choice every program happens to make the same way, whose alternatives might matter. The uniform grid polished by a gradient optimiser in every Helix hill is probably one of these.

So the stopping rule is: stop when every invariant it reports falls into 1, 2 or 3. That's checkable.

**What "splitting" should mean.** Once an invariant becomes an axis, the loop needs alternatives to that value, programs that actually do it differently; otherwise it will keep reporting the same invariant. Then ask the question again within each group, because some decisions only exist under a particular value (a cooling schedule exists only if you use annealing). Done that way, the splitting builds the hierarchy for you: the top-level axes first, then sub-axes within each branch. That's the right shape for this space.

**It also needs a partner.** Invariants are only half the axes. The other half already vary, and those come from asking "how do these programs differ?" Differences plus invariants together cover every decision present in the programs, including the ones made the same way every time.

**The real ceiling is the describer, not the loop.** The model can only report invariants it has words for. If every program shares something the model has no concept for, it will never name it. Three things push that ceiling:
- **Several describers:** different models notice different things (AlphaEvolve's team saw this with model choice).
- **Outside material:** the literature and higher-scoring solutions, read onto the same map.
- **The residual test:** programs at the same coordinates reaching very different heights are proof that an unnamed decision exists, even before anyone can name it.

So the honest claim would be: "complete with respect to what these describers can articulate, with a measured rate of new discoveries approaching zero." That's strong and defensible. "All axes, provably" isn't reachable.

It's also cheap to try. One round of the audit on v9's 77 hills is a few model calls and no new runs. It would show whether the uniform grid with gradient polishing comes out as a real frozen axis, and what else turns up. Should I run that?

---

## 8. Document everything

**Shreyas, October 28, 05:21:**

> Document everything that we have discussed tonight and push it to GitHub. Document everything extensively and make sure you keep my verbatim text as well. It is important that you capture everything that we have spoken about tonight because it is quite a lot. That begins from when I asked you to analyse the trace of the run that we did recently for V9, and maybe even one message before that. From there on I want the entire conversation to be taken note of very clearly. Keep all of my verbatim messages and push that to GitHub.
>
> Also create a new document, or use an existing document, with ideas, directions to explore, concepts, potential research questions, and anything else interesting from this conversation. Basically everything interesting from this conversation should go into that. There are a bunch of different things that we could potentially explore, potentially try, potentially consider. Some of these we've decided upon, some of these we have not. Most of these I would like to keep as open decisions, open things to think about, and just in general things to think about. I would need all of that also in a document. Make that and push that to GitHub please. Thank you.

**What was done:** this record (`docs/CONVERSATION_2026-10-28.md`) and the ideas document (`docs/IDEAS.md`), pushed.

---

## 9. v10: borrow the field's axes, two runs, break the record

**Shreyas, October 28, 18:21.** The full text of this message was lost when the session's context was compacted;
what survives is the summary's record, with these excerpts in his words:

> Okay, now can we look up the research on the second-order relation problem, find what the state of the art looks
> like, borrow those axes, and then allow our model to work with them? … I want this run to be the one that breaks
> the record. I want us to have some level of confidence … This is kind of where we prove our point … two things …
> 1. Run one evolutionary run where we literally give it the program and use that as a warm start. 2. Don't give it
> the program, but give it the concept and essentially use that as an axis. … not just for the best program in the
> world, but also for many of the top programs … collect is different approaches … Perhaps we would need somewhere to
> even bias the setup such that these axes are more important … Our Atlas already knows the extent to which the
> current approaches work … we need to make sure that is the case. … The record, by the way, is 0.97-something
> because I see that in the Einstein arena. I need you to find all the literature, or if not literature, then all the
> GitHub repositories, or if not GitHub repositories, all the posts … not only the number but the actual solution
> itself … We will do two runs: 1. Only the axes … 2. Both the warm start of the best program in the world and also
> the axes … We 10 will be the one to break the record, and I need you to tell me that with some level of confidence
> … If there are other things that need to be fixed or added, or removed … they can also be removed … getting the
> test job ready, writing the prompt for the agent … The first step … extensive research online … That internet
> research part is very important … This is meant to be deep research online … By the end of this turn, I want you to
> come back with a run ready to deploy. You can implement things that we discussed last night as well, if it helps us
> here.

**What was done:** the research (`docs/AC2_SOTA.md`), v10 (`docs/V10_DESIGN.md`, `helix10/`), the two-run job with
the Aether prompt and the odds (`docs/V10_JOB.md`, `scripts/run_v10.sh`), tested live; the request and decisions in
`docs/BRIEF_2026-10-28.md`. The reply's substance: the record is 0.963588110582, not 0.97; the field's own polish,
measured on one CPU core, adds +3.8e-8 to it and stops, so on the VM a record has to come from a structural idea the
field doesn't have; odds about 3% for v10-warm and under 0.5% for v10-axes, with v10-axes the cleaner test of the
research question (concepts only; the field's polish moves our record by 7e-9).
