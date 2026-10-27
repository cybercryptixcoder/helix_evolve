"""v9's prompt texts (docs/V9_DESIGN.md). The rest comes from helix8/prompts.py and earlier.

Every text here is about how the search is organised; none says anything about the problem or about what worked. The
design map's axes and values shown to the models come from the run's own programs (its annotator and Cartographer),
like v8's descriptions of hills.
"""
from __future__ import annotations

from helix8 import prompts as P8

RESEARCHER_SYSTEM = """You lead the research in an evolutionary search for better programs. Each generation you plan \
{k} experiments, one per slot, as the brief says. For each one a coder writes a new program by changing a base \
program; it runs starting from its base's construction, with {budget:.0f} s of CPU, and is scored. Every program ever \
written is kept, in a tree (each points at its base), and any of them can be a base.

The system keeps two maps. The map of hills: a hill is a family of programs whose outputs are nearly the same; the \
system measures what each program produces and tells you which hill it is on. The design map: the design decisions \
(axes) the programs make, their options (values), which option each program uses (read by an annotator), and a \
statistical model of how each option relates to the score, with how sure it is. Untried options are where the most \
is unknown.

Some slots are main slots: build on the strongest line, as you judge best. Others are exploration slots, which the \
system opens when the record has gone longer than usual without improving. In them the system has chosen a target \
from the design map: a drop (several decisions changed at once, to land somewhere new on the map), a flip (one \
decision changed), or an ablation (one of the record's decisions undone, to measure what it is worth). Your job there \
is to plan how to build that target well, not to replace it. Other exploration slots continue a side track or go back \
to an earlier state. An exploration track is judged against other new designs at the same effort, not against the \
record: a new design starts low and needs a climb, and it keeps its slots while it keeps rising. Nothing is ever \
closed for good; the main line always keeps at least one slot.

You plan; you don't write code. A good plan has one clear idea per experiment, concrete enough for a coder to \
implement without guessing, and a target: the score it aims for, and what in the result will show whether the idea \
worked. A failure tells you about the construction it was tried on, not about the problem: on a different \
construction, the same idea can work. Don't repeat an experiment that already failed on the same construction unless \
you say what is different. The program should use its whole budget to push the score, not stop early."""

SLOT_TEXT = {
    **P8.SLOT_TEXT,
    "drop": "Slot {n} (explore: drop): build a program with this design, chosen from the design map (several decisions "
            "changed at once, to land somewhere the search has never been):\n{blueprint}\nEvery other decision stays as "
            "in the base, {base}, and its improvements that fit the new design carry over. The base is {base}. Plan how "
            "to build this design well; the system checks afterwards which decisions the program actually makes.",
    "flip9": "Slot {n} (explore: flip): change exactly one design decision of {base}, chosen from the design map:\n"
             "{blueprint}\nKeep everything else {base} does, so its improvements carry over. The base is {base}.",
    "ablate": "Slot {n} (explore: ablation): undo one design decision of the record, {base}, to measure what it is "
              "worth:\n{blueprint}\nKeep everything else {base} does. The base is {base}. A drop in score is the "
              "measurement, not a failure.",
}

MOVE_HINT = "The design map suggests trying, on this track: {move} (an option the model rates promising or knows little about)."

DROP_CODER_NOTE = """This experiment builds a specific design, chosen from the design map:
{blueprint}
Build exactly these decisions. Keep every other decision as in the base program, and carry over its improvements \
where they fit the new design. Push the new design as far as the budget allows: it is judged against other new \
designs at the same effort, not against the overall record.{alt}"""

FLIP_CODER_NOTE = """This experiment changes exactly one design decision of the base program, chosen from the design \
map:
{blueprint}
Keep everything else the base does, so its improvements carry over, and push the changed design as far as the budget \
allows: it is judged against its own track, not the overall record.{alt}"""

ABLATE_CODER_NOTE = """This experiment undoes one design decision of the base program, to measure what that decision is \
worth:
{blueprint}
Keep everything else exactly as the base does. Make the program work well with the undone decision, but don't add \
anything new: the point is a clean comparison.{alt}"""

MISS_NOTE = """The system read the track's last program and it doesn't yet make the target decisions: {missing}. Make \
the design take effect."""

MAP_HEADER = """## The design map ({axes} decisions found so far, {rows} programs placed on them; a model of the score \
over them, with its uncertainty)
Each decision lists its options: how many programs use it, their best score, and the option's effect on the score as \
the model estimates it (plus or minus its uncertainty; "untried" means nothing is known yet)."""

DISCOVER_SYSTEM = P8.CARTOGRAPHER_SYSTEM

DISCOVER_ASK = """The design map says the two programs below make the same design decisions:
{design}
Yet they score very differently: {a} scores {sa:.6f} and {b} scores {sb:.6f}, more than the map can explain. So some \
design decision that the map doesn't list probably differs between them.

## {a}
```python
{code_a}
```

## {b}
```python
{code_b}
```

What design decision differs? Name it as a question, and give each program's option in a few words. If none does (the \
difference is only tuning or luck), say so. Reply with one JSON object and nothing else:
```json
{{"decision": "the decision, as a question, or null", "{a}": "its option", "{b}": "its option"}}
```"""

MATCH_SYSTEM = P8.CARTOGRAPHER_SYSTEM

MATCH_ASK = """The design map lists these decisions (axes) so far:
{axes}

Below are design decisions named elsewhere in the same search. For each, say which axis above is the same decision \
(even if worded differently, or narrower), or "new" if none is. For a new one, give a short question naming it.
{items}

Reply with one JSON object and nothing else:
```json
{{"matches": [{{"item": 1, "axis": "A3"}}, {{"item": 2, "axis": "new", "question": "the decision, as a question"}}]}}
```"""

ALT_NOTE = P8.ALT_NOTE

CONSOLIDATE_ASK = """The design map below lists the design decisions (axes) of a search, with some of their options. \
Some axes may name the same decision in other words, or one may be a narrower version of another.

{axes}

Which axes are the same decision? For each such group, give the axis to keep first, then the ones to merge into it. \
Merge only true duplicates: two different decisions that are often made together are not duplicates. Keep at most \
{k} axes in all if you can do so honestly. Reply with one JSON object and nothing else:
```json
{{"merge": [["A2", "A9", "A16"], ["A1", "A10"]]}}
```"""
