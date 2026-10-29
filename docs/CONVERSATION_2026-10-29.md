# The conversation of October 29, 2026 (evening): making Helix defensible; what an axis is

Shreyas's messages are kept **verbatim** (spoken, then transcribed; nothing corrected), each followed by the reply as
given. Times are Eastern (EDT). The notes and decisions are in `docs/BRIEF_2026-10-29.md`; this file is the record.

---

**Shreyas, October 29, 16:41:**

> Okay now we're just going to discuss some stuff because I feel like somehow simply winging the runs is not really helping us.
>
> First of all I'd like you to take a look at our current run and its progress. I would like you to just not deeply analyse it but at least give it a surface-level look and comment on how it's going. I don't think it's going great. Although it is still at Jan 46, I guess it's significant for that but I'm not really sure that counts as much.
>
> We need to have a proper conversation here about a couple of things:
> 1. What are our claims? It could be multiple too because there were a couple. What are we trying to achieve? What are we trying to prove? What is our bet, sort of, what the whole thing is about? We're trying this approach but we need to be able to justify that approach to any researcher and say, "Hey this is why we're doing this approach and this is why it's worth publishing: this is why it is better and also different." The crucial bit is the proof for that, right? The proof is the empirical verification.
> 2. Proving that empirically. How do we prove that empirically? What are we comparing with? What are we setting as constraints and then what are we doing with that? In terms of proof what is it that we are trying to do here? The runs that we're doing, or the runs that we haven't done yet but we should probably do, are like comparing something, right? We can showcase that a certain method is better by showcasing that we get a better score over a certain constraint or so on. That's the other thing.
>
> The next thing is figuring out what problems to take up because now this is one problem but there are other problems that we could also take up. As we discovered the papers published don't just showcase one benchmark. The second autocorrelation problem is hardly two lines in the arXiv paper so we need to do better than that. We need to show a bunch of different stuff and perhaps all of them together show a certain trend. That is the other thing.
>
> The third thing is the actual setup itself. I think we're kind of deep enough into a rabbit hole that I am somewhat conceptually detached from what the current state of the build is. I need to understand that intuitively to the point where I can reason about it so that the next change that we do is in accordance with what I have reasoned. Importantly the next run that we do needs to be directed at making a case for ourselves.
>
> Now I am less keen on a specific number and more so thinking about how to defend this to Amulia and to just the research community in general. We need to make a case not just for this surviving as a project but also for it being something really interesting that should be looked into. We do that not just with our runs but also by pointing at evidence that suggests what our hypothesis is.
>
> If we have evidence, and not just from our own work but also from existing literature, we want evidence that suggests a certain thing that needs to be now explored in order to determine whether it is that thing. We're showing that this is a gaping hole in the literature and that we need to fill it. We need to make a good case for that because this will also be presented to someone from Amazon. They need to be interested to work with us in order for them to take it forward.
>
> This can't just be something like, "Oh this barely survives as a concept." No this is something that should really be important and worth it such that whoever we present it to would be missing out if they weren't to join us. Since this discussion needs to be a discussion, I need to first catch up on my existing thoughts. You can get that from a recent conversation that has been pushed to GitHub and that was done, I believe, last night or last morning. You should find that in GitHub.
>
> You will also see some thoughts, some dots about my ideas, and go through the docs that are more conceptual or related to ideas or thoughts. Less so about the actual documentation for the code, but more so about the conceptual stuff. Go through that so that you're caught up with where I am mentally and let's take it from there.
>
> These are a couple of things that we need to really focus on: our focus is now to make a defensible research project, more than it is to beat a single record. The hope is still to beat that record because that would be proving something in itself and something significant at that. That is there but understand the framing of this entire thing.
>
> The goal here is not for you and me to sit and figure out a way to improve the current setup. It is to either figure out how to back up our claims and hypotheses, or extend them, or modify them. If we're discovering that certain things don't hold, then we change our hypothesis and make an alternative one or a variant of it. That's fine because that's part of the research process. We begin with a hypothesis, realise it's not true, and discover what the actual thing is.
>
> Overall the objective here is not to prove or disprove this one thing. It is to have this research project as a whole be defensible, not just that specific hypothesis. The research project is not built around one sentence. The research project is this thing we're trying to explore and work with, this manner of thinking, and this approach we're taking. This is the research project.
>
> We just need to make this defensible and remember the best defences come from simple statements. If I can, in simple plain English, justify something in hardly a couple sentences, then that really goes to show the strength of that argument. We can always use plenty of jargon terms and point to plenty of specific things about this research domain that are flawed (this or that, this and that), and then use that to justify our position. Yes those detailed arguments can be made in the paper, I suppose, but with Amulya I'm not going to talk about all of that stuff.
>
> Amulya's conversation with me was fairly simple and straightforward. He asked me some very simple questions and ideally I would want you to go through that conversation with Amulya as well. That is available in the transcript of this conversation, which you will have to find on your own by reading this conversation transcript from earlier. You will not find his name but you will find the conversation as Speaker 1 and Speaker 2. Just go through that. He is pointing to very simple things and telling me very simple reasons. About why I need to spend more time actually thinking about the project.
>
> He had simple questions. His question was whether successfully beating this record is enough to write a paper in this domain, whether your approach is actually better than the other approach, and what is justifying that. Is this field requiring you to showcase something else?
>
> In general he was asking me these questions and they're very straightforward questions. They don't need answers that require all the knowledge in the world. He was asking me questions as a researcher and even at that he is not an expert in evolutionary algorithms. He is not an expert in this exact domain but he is a seasoned researcher and he knows what kinds of questions to answer and to ask.
>
> For him I don't need to give him these domain-specific detailed responses. No, he's looking for straightforward answers and straightforward defences and those are the strongest ones. Let's keep that in mind as well.
>
> In this message I've asked you for a lot of things. Some of these can come as answers as if we already have the answers to them. They can come as complete well-formed responses or they can come as, "Okay this is worth thinking about and let's figure out how," and then the discussion continues from there.
>
> To begin with make a note of everything from this message because this message that I'm sending you now is an important one. Make a note of it: everything that we want to do in this message. Yeah come back with a good response.

**Reply:**

I've saved your message in full as `docs/BRIEF_2026-10-29.md` and pushed it. I read the October 28 conversation, the research case, the ideas doc and the earlier direction memo. The Speaker 1 / Speaker 2 transcript with Amulya isn't in what survives of this session's log; the only mention of "Speaker 1" is in your message today. If you paste it again I'll go through it word by word. Until then I've worked from his questions as you relayed them.

## The runs, at a glance

You're partly right. It's one encouraging result and one warning.

- **Seed 1 is at 0.9465 after about 57 generations.**
  - It passed best-of-25,600 at 151 programs and OpenEvolve's 0.9449 at 169 programs; both of those used 25,600.
  - That's the most interesting number we've produced.
  - It came from one exploration, built from nothing at generation 1 around "coarse-to-fine". Since generation 30 it has only been polishing that one design: +0.0006 in 27 generations.
- **Seed 2 is at 0.9045**: same setup, 0.04 lower.
- **The warning is the gap between seeds.** If one seed can land 0.04 below the other, no single run can carry a claim.
- **The space is being covered slowly:** only 8 and 6 of the 38 field ideas have been tried so far.

So, "not great" as a record attempt, but useful evidence. It shows the run-to-run variance, and that the gain came from an idea built from scratch.

## Amulya's questions, answered plainly

**Is beating the record enough for a paper?**
No. One number on one problem is a maths result, not an AI paper. AlphaEvolve reported this problem as one line among dozens, and no AI venue we found accepted a single-problem paper. A record is a good showcase, not the claim.

**Is your approach better than the other approach, and what justifies that?**
We don't have that proof yet. Our numbers sit beside other papers' numbers, but those used a different model and none of the literature we gave ours. A sceptic will say our model or our reading of the literature did the work, not our method.

**Does the field require something else?**
Yes, and it's the standard set by every method paper that got accepted:
- several problems;
- several runs each;
- a comparison at equal model, budget and knowledge;
- an experiment showing *our idea* is the reason, not something incidental.

## 1. The claims

Here they are in plain English, as you asked.

**The core claim (the bet):**
> Today's AI discovery systems ask a model for "a better program" and keep the winners, so they only explore where the model's habits lead. We write the space of ideas down as a map of design decisions and search it on purpose. That finds good solutions with far fewer tries, and reaches ones the model wouldn't write on its own.

**The practical claim (what Amazon would buy):**
> Give Helix a problem and the literature on it, and it turns the known ideas into a search space and finds the best combination of them, cheaply, with any model, and shows which decisions mattered.

**Two claims for later, kept open:**
- Breakthroughs come from changing what every program assumes. Our routing case is the example.
- Structure can stand in for a bigger model.

**Why it's different:** everyone else changes *which programs the model sees* (OpenEvolve, ShinkaEvolve) or *retrains the model* (TTT-Discover, ThetaEvolve). We change *what the model is asked to build*, using an explicit map.

## 2. The gap in the literature

The field's own results already point at it:
- Models repeat themselves and each other (Artificial Hivemind, a NeurIPS 2025 best paper).
- Training doesn't get a model past what it could already produce (Yue et al., NeurIPS 2025).
- Simple samplers match elaborate systems, and the authors conclude the search space matters more than the search method (Simple Baselines, 2026).
- Variety in *ideas*, not code, is what pays off (PlanSearch, ICLR 2025).
- About 30% of the code these systems add re-adds code they deleted earlier, so they don't know what they've already tried (EvoTrace, 2026).
- AlphaEvolve's best maths results leaned on humans telling it which approaches to use (Georgiev, Gómez-Serrano, Tao and Wagner).

**The gap in one sentence:** everyone agrees the space of ideas is the bottleneck, but no system treats that space as something you write down, search on purpose and extend.

## 3. The empirical proof

You were right to drop the home-built AlphaEvolve-style loop: a basic rebuild proves nothing about the industry. But "compare only with published numbers" can't prove the claim either, because model and knowledge differ. So the proof needs three layers, strongest first.

**a. Take the map away, keep everything else.**
This is the core experiment, and it isn't a stand-in for anyone. Run Helix with the same model, budget, start and literature, but with the ideas given as text instead of as a map to search. If the map version wins across problems and runs, the claim is proven, and it also answers "the knowledge did it."

In one sentence: *same everything, remove the map, it does worse.*

**b. The real systems, run as published.**
OpenEvolve and ShinkaEvolve are open source. We run them unmodified, with our model, our budget and the same literature. That isn't a rebuild, and it's what TTT-Discover's authors did themselves: they ran OpenEvolve under their own model and budget.

**c. Published numbers under matched constraints, as supporting evidence.**
That's what v10.2's report does now: the programs we needed to pass each published value.

**The fixed constraints in every comparison:**
- the same model;
- the same programs per run (and we report tokens);
- the same CPU per program;
- the same start;
- the same knowledge;
- at least 3 runs per setup.

The measures are the best score at equal budget, the budget needed to reach each published value, and, as the mechanism check, where the records came from (ideas the model wouldn't have chosen itself?).

## 4. Which problems

Pick problems where published numbers already exist, that score in seconds on a CPU, and that look different from each other:
- **Maths inequalities:** the first, second and third autocorrelation inequalities, and Erdős's minimum overlap. AlphaEvolve, ThetaEvolve and TTT-Discover all report these.
- **Packing:** circle packing (26 and 32 circles), where ShinkaEvolve's 150-sample result is the bar to beat on efficiency.
- **Geometry:** Heilbronn triangles.
- **Applied:** online bin packing (FunSearch's), and routing if Naandi's data owner allows.

That's six to eight problems.

The trend to show is not "we win everything." It's that on every problem the map gets to good solutions with fewer tries, and the records come from ideas the model wouldn't have picked itself.

## 5. The setup, in plain terms

- **The map:** a list of design decisions with options for each, for example "how is the solution represented?" or "how is the hard maximum handled?". On a cold start it holds 8 generic questions plus the literature's 9 decisions and 38 options. Every program gets read onto it.
- **Each generation, 6 programs:**
  - 1 improves the current best;
  - 2 explore: either continuing an exploration, or starting a new one written *from scratch* around an untried option;
  - 3 small mutations: 1 on the best, 2 on the explorations.
- **Explorations** compete only against each other at equal effort. They continue while they keep improving and take over if they overtake the best.
- **Learning from the map:**
  - a small statistical model learns which options help;
  - every 10 generations an audit asks "what does every program do the same way?" and turns the answer into a new decision.
- **What's weak right now:**
  - covering the space is slow;
  - runs vary a lot;
  - after the first breakthrough, most effort becomes polishing one design.

If you want a one-page diagram of this, I can make it.

## Decisions for you

1. **Headline claim:** the core claim ("the map gets past the model's habits") or the practical one ("literature in, best combination out")? I'd lead with the practical one for Amazon and the core one for the paper.
2. **The proof:** is layer (a) plus layer (b) acceptable to you? It's our own controlled test plus the real open-source systems, not a rebuild.
3. **The next run:** I'd make it the first instance of (a) on this problem: map against no-map, 3 runs each, about 60 generations. Seed 1 did most of its climbing by generation 30. That gives us a case on one problem within days.
4. **The current runs:** they occupy the VM. Stop them now, or let them reach about 100 generations first?
5. **Compute:** the full suite (6–8 problems × 3–4 setups × 3 runs) doesn't fit on two cores. Is there a cluster or credits through Amulya, or Amazon?

---

**Shreyas, October 29, 16:53:**

> Okay now, one thing that I noticed is that changing the seed would drastically change the growth rate. We were doing this thing where we were trying to randomise the start point of a search on the map itself, right? We had this higher-dimensional map. If you look up that conversation, especially the one that I had with my friend about this map, this contour map, expanding in circles, and all of that, going to one part of the map is essentially what we were trying to figure out.
>
> How do you jump to a different part of the map? Everything we did was simply finding a new direction. It was not really jumping to a new part of the map. Is the seed doing that for us? Changing the seed, does that put us on a different part of the map? Excuse me, because that could also be something we do, right? Searching from a whole bunch of different random points

**Reply:**

Short answer: no. The seed doesn't put us on a different part of the map, but your observation is pointing at exactly the right thing.

**What the seed actually does.** Both seeds start from the same point: Code Zero, a constant function. The seed only controls the random tie-breaks: which program the mutations start from, which untried idea gets built first, and how the planner samples the map. The model's own writing isn't seeded at all, so it varies on its own. The two runs only diverged because of the order they happened to try ideas in:

- **Seed 1** built "coarse-to-fine" (start with a few steps, then refine) from scratch in generation 1. That one design carried it to 0.9465. Every record since has been polish on it.
- **Seed 2** built "L-BFGS with Anderson acceleration" (a choice of optimiser) first, then "average-pool down", then "a tall spike plus a comb" in generation 4. That last one is its best, at 0.9045.

**So the seed isn't a jump, it's luck in the first idea.** That luck alone made a 0.04 difference. It's the strongest evidence yet for your contour-map picture from the conversation with your friend: where you start the climb matters more than how well you climb. It matches two earlier measurements:
- a run's best after 20 programs didn't predict its final best (rank correlation −0.09);
- all 19 fresh restarts climbed into the same basin.

**Are we jumping today?** Partly. v10.2's "build from nothing around one idea" is a half-jump. It fixes one decision, say coarse-to-fine, but lets the model choose everything else. The model fills those choices with its habits, so every build lands near the model's favourite region on the other axes. A real jump would fix a value on *every* axis, a full random coordinate, and build that from nothing. v10.2 can do that (a "drop" built from nothing gets the whole sampled design), but none happened in either run, because the field's ideas took every new slot first.

**What your idea becomes, done properly:**
1. Draw many full coordinates, each a value for every decision, spread far apart on the map.
2. Build each from nothing and give each the same fixed climbing budget.
3. Keep the best few; then drop new points far from everything already explored.
4. Repeat.

It's also a clean experiment for the paper: many spread-out starting points against one start, at equal budget, over several runs. Our two seeds are already a tiny accidental version of it.

**Two things the runs say we'd have to handle:**
- **Building a far point faithfully is hard.** In v9 only 42% of the requested decisions actually landed in the code, and those were near jumps. Each built point needs a check that it is where we asked, or we'd be climbing the model's habits again under another name.
- **Climbing is the expensive part.** Seed 1 needed about 25 generations to get its idea to the top, so a fixed budget per point decides how many points we can afford. That's where your "shoot to the top quickly, then move on" question comes back in.

**Choose the next run** (the earlier five decisions still stand alongside this):
- **(a)** The multi-start experiment on this problem: N spread-out full coordinates against today's one-start setup, equal budget, 3 runs each.
- **(b)** The "map vs no map" test I proposed earlier first, and multi-start after it.
- **(c)** Both in one design. Multi-start is a way of *using* the map, so "no map", "map with one start" and "map with many starts" make a three-way comparison.

I'd lean (c). It's the cleanest story: no map, then a map, then a map you can jump across. But it's three setups × 3 runs, so it needs the compute question answered first.

---

**Shreyas, October 29, 17:02:**

> Yeah you keep pushing on what is to be done now but like I said, in this conversation I want to first just understand where we are, clearly.
>
> Now let's try to understand some of the terms that we've made for ourselves because we've invented a lot of stuff and half of them are things I don't even know properly yet. The axes, right? So far I have only spoken about the axes conceptually. I've not actually seen what one looks like so I want to know what the axes are for the current run. I want to know what a value, a specific number on that axis, looks like. I want to know what a positive value or a negative value, or more importantly, an increase or decrease in value on that axis, looks like. I need to get some clarity on that.
>
> If you remember from the conversation I had with my friend, there were three questions:
> 1. The number of axes is fixed.
> 2. How do we quantify values on an axis, like how do we quantify the concept?
> 3. I think it was: how do we set random values onto that to get a jump and get a random point on the map?
>
>
> I don't remember exactly what the third was but essentially it's that. First I want to get some clarity on what one actually looks like. Let's take the real example we're working with and I want to know what the axes are and what it means to go up and down it because if we're building a search space, it needs to be real, right?

**Reply:**

Here's the real map from the seed 1 run as of generation 57, pulled from its published files. The most important thing first, because it changes how to picture everything else.

## An axis isn't a number line

An axis is a **question every program has to answer**. A "value" is **one of the named answers** to it, not a number. There's no up or down and no positive or negative. It works like "cuisine" (Italian, Thai, Mexican), not like "temperature". The only notion of distance is **how many answers two programs differ on**.

This run has 20 questions; 19 of them have answers. Six of them, with real answers and how often each was used:

| Axis | The question | Some answers (programs using it, best score) |
|---|---|---|
| A1 | How is a solution represented? | dense grid of heights (285, 0.9465) · spline/Fourier coefficients (14, 0.848) · softmax parameterisation (3, 0.839) · adaptive mesh (never tried) |
| A3 | What does the search optimise while it runs? | Dinkelbach ratio iteration (135, 0.9465) · exact max subgradient (83, 0.914) · smooth max surrogate (18, 0.914) · exact line search on R (never) |
| A11 | Which optimiser does the inner work? | L-BFGS (275, 0.9465) · momentum gradient (31, 0.854) · annealing / random search (14, 0.850) · trust-region Newton (never) |
| A13 | How is the number of steps chosen? | coarse-to-fine upsampling (107, 0.9459) · native length (94, 0.9465) · exact k-fold repeat (56, 0.914) · zero-pad to the limit (19, 0.904) |
| A14 | What is f's overall shape? | sparse packets under a smooth envelope (124, 0.914) · heavy comb block at one end (47, 0.9463) · tall spike plus comb (25, 0.9465) · arcsine density (9, 0.867) |
| A20 | Is a symmetry imposed? | none (307, 0.9465) · even symmetry (35, 0.914) · unimodal (1, 0.774) |

A **point on the map** is one answer to every question. The current record, p0353 at 0.946543, reads:
- dense grid;
- Dinkelbach;
- L-BFGS;
- native length;
- only the tied maxima targeted;
- FFT convolution;
- no symmetry;
- a smoothed maximum (log-sum-exp);
- …and so on, one answer for each of the 17 questions it was read on.

An early program, p0004 at 0.612, shares some answers with it, such as dense grid and L-BFGS. It differs on others: a periodic torus instead of a finite interval, and a heavy comb block instead of no read shape.

**Moving on this map:**
- A **step** means changing one answer. In the code it's a "flip", for example L-BFGS becomes Adam.
- A **jump** means changing many answers at once.
- The **score** is the height.

So the contour-map picture survives, but the ground is a grid of categories, not a smooth surface.

## Your three questions, answered honestly

**1. Is the number of axes fixed?**

No. This run began with 8 generic questions and the 9 from the literature. The model's scans and the discovery step have added more since, to 20. It's also messier than it should be:
- **Questions overlap.** "Coarse-to-fine" appears under both time-splitting (A8) and step count (A13). Normalisation is asked twice (A12 and A24). Smoothing the maximum is asked twice (A3 and A26).
- **Some answers are duplicates in other words.** A13 has "coarse to fine, upsampling" and "start coarse and upsample" as separate options.

**2. How is a value quantified?**

Only as a named category. A second model reads each program's code and says which answer it gives to each question. Nothing on the map is numeric. Some questions have a hidden order the map ignores; the number of steps (50 to 50,000) is the obvious one. The reading is also imperfect:
- the record sits on the track built around "coarse-to-fine", yet it was read as "native length";
- it has no reading at all for shape (A14) or fine structure (A15).

**3. Can we set random values to get a random point?**

In principle, yes. Pick one answer per question at random. The answers available in this map already multiply out to about 2 × 10¹⁵ points. But there are two catches:
- some combinations don't make sense together;
- a point only exists once the model has written a program for it. In v9 only 42% of requested answers actually showed up in the code.

## The part that matters most for your picture

There are **two layers**, and we've been talking as if there were one.

- **The map** decides which design a program uses: its answers to the questions.
- **Inside each point** sits everything the map doesn't describe: the exact numbers, the tuning, the implementation details. Thousands of different programs share one coordinate, and their heights differ.

Seed 1's run shows it plainly:
- its big gains came early, when it was changing answers;
- from generation 30 to 57 it barely moved on the map, climbing +0.0006 *inside one point* by polishing details.

So "hills" on our map are not smooth slopes you walk up answer by answer. A point is a small region of its own. Most of the climbing happens inside it, out of the map's sight. The map is good at saying *which designs* we've tried. It says nothing about *how far* each design has been pushed.

Which part would you like to dig into next: the overlaps, the missing numeric order, or the two-layer picture?

---

**Shreyas, October 29, 17:12:**

> I need shorter and more concise responses from you so that we can keep this conversation going and have this be more of a discussion and a back-and-forth rather than just a one-sided reading.
>
> With the axes already, I see a disconnect between what I had envisioned and what's been implemented or what's been taken forward, and that wasn't conveyed to me. I feel like, going forward, that should be a standing rule: the manner in which something is being implemented and the disconnect between what is being implemented and what was asked for should be conveyed clearly.
>
> With that set aside, the axes themselves: you're saying it's something that doesn't have a number attached to it. It's more so something that takes a bunch of different possible answers to a question. How do we search through that? Searching through that simply means trying all possibilities and that doesn't really form a surface because it doesn't form a continuous surface. Each answer is essentially an approach. Rather than encoding directions, like increase and decrease in a certain thing, we're capturing ideas themselves on the axis, on a single axis, which is not okay.
>
> An idea needs to be a combination of axes. There's some disconnect here because the thing is, each different answer produces a completely different type of result. Each different answer to the question produces a completely different type of result, which is discontinuous.
>
> What I wanted to do is essentially have something, not monotone, with one specific aspect that either you can do more of or you can do less of. For example if all of these approaches were taken, you could encode them as: Are you doing more of this approach or less of this approach? If you were to do only one of those approaches, that would mean that all other values are zero and this particular one is sitting at one, and vice versa. That is what I was envisioning.
>
> In that view what can an axis be? I feel like a whole idea or a whole approach is too broad for it to go on one axis. One axis needs to be something rather simplistic. Each individual axis should be rather simplistic. Even if it is an entire idea we need some way of doing more or less of a certain thing. If we explored literature and found 17 different approaches, can we do more or less of that thing? That's how you would create a surface that can actually be searched because without a surface you don't have anything to search. In which case why are we even calling this a search setup, right? It's not really doing that, is it? It's just trying permutations in no meaningful way.

**Reply:**

I've added your standing rule to the requests doc and pushed it. And you're right about the disconnect: I should have flagged it when the axes were built.

You're also mostly right about the search itself. What exists is a catalogue of approaches. The current search guesses which combination of answers to try next from past scores. That's a real kind of search over choices, but there's no surface and no "more or less". Neighbouring answers aren't related, so nothing about one tells you about the next.

Your version, where each approach is a dial from 0 to 1, can be made real. It needs "more of an approach" to mean something concrete inside a program. Two ways:

1. **Budget share.** One program skeleton runs several approaches, and each dial is the share of time that approach gets. "Only Dinkelbach" is (1, 0, 0…); a 70/30 mix is a real, different program. That gives a continuous surface. A plain numeric optimiser could then search the dials, with no model call per point. The model writes each approach once, as a component.
2. **Strength.** Each approach has its own natural "how much", such as smoothing strength, number of refinement stages or perturbation size. Each axis is that one simple quantity.

The catch with both: some approaches can't be mixed (two ways of representing f can't both run on the same array). Those stay as switches.

Is (1) what you pictured, or (2), or something else?

---

**Shreyas, October 29, 17:15:**

> Right that's where an axis comes into play. The whole point of this is to do that, right? I think it's okay to have binary axes as well. That just sort of adds to our search space but more so that's kind of the point, okay? That we take one thing and then we search through it. Some of this can be used as a manner to determine what actually counts as an axis, right? Because if they overlap or they do the same thing, then that's not useful. These axes are meant to do different things.

**Reply:**

Agreed. That gives us a working definition, which I'll write down as it stands:

**An axis is one simple thing a program can do more or less of: a dial, or a switch if it's binary.** To count as an axis it has to pass three tests:
1. **Independent:** you can turn it alone and still get a valid program.
2. **It matters:** turning it changes what the program produces.
3. **Not a duplicate:** it doesn't do the same thing as another axis. If two axes always move together, or have the same effect, they're one axis.

All three can be measured, not just argued. Turn one dial, keep everything else fixed, and see what changes.

Today's map would translate like this:
- **"How is the number of steps chosen?"** becomes a dial: the number of refinement stages, from 0 to k.
- **"How is the maximum handled?"** becomes a dial: smoothing strength.
- **Symmetry** becomes a switch.
- **"Which optimiser"** becomes a budget-share dial per optimiser, or stays a switch if they can't share a run.

Several of today's twenty questions would fail test 3. We saw coarse-to-fine appear under two questions, and normalisation twice.

Does that definition match what you had in mind?

---

**Shreyas, October 29, 17:22:**

> Now with this, the first goal here is to gain an understanding of what everything else is because we went and had a really good discussion in the conceptual realm (me and my friend). It's important that that translates to the right thing when converting it into an implementation.
>
> Now what do we know that the axis actually is? What do we know about what a specific point on this map is? What is this map itself? What do a high and a low on the map mean? How to search over this map?
>
> Also I'm still kind of shocked that, despite having such a big disconnect, we carried on with what we currently had in place. As in I kept saying we want to search over that space, that we want to start at different points, and that in a given region you would want to climb a certain hill. But if the points that are literally next to each other are completely unrelated to each other, then how do hills even form? How does it make sense that hills formed over there? What we're trying to do is climb the hills, right? How do you do that?
>
> The reason I was able to even come up with the term "hill" is that you would have a continuous surface that has ups and downs. Where you have a hill, everything in that hill is a bunch of related concepts. Every single one of the ones closest to the top is pretty similar to the one at the top. If there's a disconnect between one point and the one right next to it, how does that even happen? That makes no sense. It's kind of shocking to me that we even had that going all this while.
>
> Anyway now back to where we're at: what does a hill mean? How do we make sure that we actually have a continuous and smooth setup where each thing is related to the next thing? That is how we're able to smoothly slide through this and search for what we are looking for.
>
> Let's try to get a mapping between what something is conceptually and what it would actually look like. I want to see an actual example of it. Now in the current setup, what would be an axis? What would be the values for that axis, how would that change, and so on? I want to actually see that in practise or have it illustrated as it would be in practise.

**Reply:**

You're right to be shocked, and I should have flagged this long ago. Here's how "hills" were actually defined in the code.

**What a hill is today.** It isn't a region of the map. Since v8, two programs are on the same hill if the *functions they output look alike*: their shapes, compared at 64 points, are within a set distance. So hills live in the space of outputs. The map of questions and answers was added later, in v9, and it was never made continuous. That's why hills "formed" even though neighbouring answers on the map are unrelated.

**Concept to implementation, as it should be:**

| Concept | What it is in practice |
|---|---|
| Axis | One number or switch inside a program, e.g. smoothing strength |
| Point | A setting of every axis, which gives one runnable program |
| Map | Every possible setting |
| Height | The score that program gets |
| Neighbour | The same setting with one dial nudged a little |
| Hill | A region of settings that all score well, and score better towards one peak |
| Climbing | Nudging dials in the direction the score rises |
| Jump | A far-away setting, from which you start climbing again |

**A concrete example for this problem.** One program skeleton with six axes:
- number of steps, 50 to 50,000;
- number of refinement stages, 0 to 6;
- smoothing strength of the maximum, 10 to 10⁹;
- share of time on Dinkelbach versus random kicks, 0 to 1;
- kick size, 0 to 0.3;
- symmetry, on or off.

A point might be (20,000 steps, 4 stages, smoothing 10⁵, 80% Dinkelbach, kick 0.05, no symmetry), and that runs and scores, say, 0.93. Its neighbour moves smoothing to 2×10⁵ and scores slightly differently. That small change, giving a small difference in score, is what makes a surface. A hill is the patch of settings around the best one. A jump would be something like (500 steps, 0 stages, smoothing 10², 20% Dinkelbach, kick 0.3, symmetric).

These numbers already exist inside our programs. Today the model edits them by rewriting code, unseen by the map.

**The open question:** nobody has checked that this surface is actually smooth. A real check would be to take one program, turn two dials across a grid of values, and plot the scores. That costs about an hour of CPU. Do you want to see that before we go further?

---

**Shreyas, October 29, 17:38:**

> Now in certain cases, given access to something makes no sense because we know for certain that it only goes one way. For example the number of steps would only help a programme, right? If you were to give a programme a million steps instead of 20,000, that would obviously work better. That's just a one-dimensional thing, right? It just goes up, which is not very helpful because it will just put it to the max setting. I don't think that is a valid axis.
>
> The next thing is: how does knowledge translate into axes? An axis is basically every new thing you can do, right? Every new approach that you can do.
>
> Now if we are simply taking something like Dinkelbox and comparing it with a few other algorithms and just running those in series or in parallel to different extents, then that's one thing. Okay fine, I guess. The share of how long each of them runs for, each of those could be an axis. Even an approach or an algorithm can be deconstructed into axes, as in: you tried so much of this and then so much of that and that gives you this approach.
>
> It is, I think, important to make this distinction between this stuff

**Reply:**

Agreed. That gives a fourth test: **an axis must have a trade-off**, meaning its best setting sits somewhere in the middle. If more is always better, it's a resource, not an axis.

One small caveat about steps. Under a fixed time limit, more steps aren't free: each one makes every iteration slower, so 1,000,000 steps can lose to 20,000 in 150 seconds. That gives steps a trade-off, but the trade-off is just "time versus resolution". It's a budget question, not an idea, so I'd keep it out of the map too.

The distinction you're drawing, as I understand it, is three kinds of thing:

1. **Resources.** More is better, or it's a pure budget trade-off. Steps, time. These aren't axes; they're set once.
2. **Ingredients.** These are the pieces approaches are built from, each with an amount: how much time goes on Dinkelbach-style ratio updates, how strongly the maximum is smoothed, how big the random kicks are, how much of the mass sits in one spike. These are the axes.
3. **Approaches.** Dinkelbach, annealing, the spike-plus-comb shape. These are not axes. Each one is a *point*: a particular recipe of ingredient amounts.

So knowledge becomes axes by taking every approach from the literature apart into its ingredients:
- An ingredient that several approaches share becomes one axis, not several (that's the duplicate test).
- A new combination is simply a point between or beyond the known recipes. That's exactly how you search between ideas rather than only trying them one by one.

Is that the distinction you mean?

---

**Shreyas, October 29, 17:48:**

> Okay just to reason about and make this process easier, can we take a much much simpler problem, like a really simple problem, and think through that? The second autocorrelation problem, I have no idea about and I don't know how it works. It's just a problem that we pick because other people have also submitted results for it.
>
> What I need is a very very basic problem. You know how, in an exam, if you forget a rule or a formula or something, you just plug in really basic values, right? You just plug in a 0 or a 1 and you figure out, "Oh that makes sense," and immediately you're able to reason about it. In a similar manner can we do it for this?
>
> Let's take a real simple problem and for that let's find all the different axes: the resources, the ideas, how you would draw from literature, and so on and so forth. Let's just do that.
>
> Also the overarching thing about this project, I think, as I see it (I might be wrong and I might be forgetting some things from earlier or missing the point altogether), is that what we're trying to do is search over ideas as a search space rather than discovering them. We're not using an evolutionary loop to just try different things and hope for improvement, in which case we kind of rely on the LLM's reasoning (because the better an LLM can reason, the better it can direct itself towards a better solution).
>
> Right now what we are trying to do is essentially search through and find a good solution and that's how we're different, I suppose. For that intelligence plays a lesser role because we're literally searching through solutions. The intelligence of the model is simply to take an idea and convert it, basically translate it into code. It's just a translation tool, which is why there's a threshold: it should be capable of translating English to code reliably.
>
> Anyway that's what we're trying to do. We're trying to search over the space rather than just discover things through chance. The problem that we're dealing with is: how do you translate something like this into a search space? How do you map that as a search space and actually search it in a meaningful manner? That's the part we're kind of trying to figure out right now.
>
> Let's take a really simple problem and try this approach on that, perhaps even something we know the solution to. We want to see how we can come up with that solution using a search. Also remember this search is a stand-in for reasoning, okay? Meaning that our search should somewhat resemble reasoning, right? Because, for example, a model which is really intelligent will try something, see what worked, see what didn't work, and then it would reason through how to improve that, correct? But since we're trying to search through this space, we are also trying to point ourselves in the direction of that better idea but our search is a stand-in for that reasoning. A good check for us is that if we're doing things right, the steps we take and the kind of path that we take (like on a map), we're following a path up to the top of a hill. If you were to actually trace what happened along that path, it seems reasonable and it seems like a set of reasoning steps except that reasoning is not coming directly from the model itself. The model might contribute to it in some way but it's more so coming from the search mechanism because it is designed as such.
>
> Again we are not doing the reasoning in order to find this. We are following somewhat mechanical steps. We're seeing which side improves and which side does not. As a result of that, the path that we get, if you were to trace that, should make sense. It should kind of make sense why we ended up where we did from where we were. Let's try this as a dry run on a simple problem. First let's decide on a problem: something literally simple that I can reason through and that we can think about, and potentially even something that we know a good solution to. It should still be a little bit open so that our setup is actually applicable there because I don't think our setup is working on solved problems, right? We should know a good solution to it and be able to reason our way to it or search our way through it.

**Reply:**

Your framing matches mine: **we search a space of ideas instead of hoping the model reasons its way there**. The model only translates ideas into code. Your check is a good one, and worth keeping as a test: the path the search takes should read like a sensible chain of reasoning when you trace it afterwards.

For the problem, here are three candidates. All are easy to picture, have known good solutions, and still have room to improve:

1. **Shortest round trip through 50 cities** (the travelling salesman).
   - Everyone can picture it.
   - Known ideas: go to the nearest city next, untangle crossing paths, shake things up and redo.
   - The exact best route for 50 cities can be computed, so we'd know the target.
   - It's also close to the routing work.
2. **Packing items into the fewest boxes** (bin packing).
   - Very simple to state.
   - Known rules, like "put each item in the first box it fits", and a known lower bound on the number of boxes.
   - FunSearch used this one.
3. **Fitting circles into a square** (make n equal circles as large as possible).
   - Visual: you can see a good packing and a bad one.
   - Best answers are known for small n and still open for larger n.
   - ShinkaEvolve and AlphaEvolve report results on it, so it also gives us published numbers later.

I'd pick **1** for the dry run. It's the easiest to reason through by hand, and a trace like "untangling more helped, shaking harder hurt" reads naturally as reasoning. **3** would be my second choice, because it also connects to published benchmarks.

Which one?

---

**Shreyas, October 29, 17:52:**

> Okay let's do problem number 3. Make sure you explain the problem to me first, clearly and simply, and then let us try to do this by hand. Also one thing that is important is this conversation that we're having, which started sometime after 3 pm. I don't remember the exact time but sometime after 3 pm.
>
> I want this to stay with us, okay? I want this documented. Keep making notes on everything that I'm saying and also keep the verbatim text just in case. The verbatim text should go into this file, which I am less likely to tell a model to read.
>
> Make notes of everything that I'm saying and also keep making notes of what we decide on so that it is kept track of.

