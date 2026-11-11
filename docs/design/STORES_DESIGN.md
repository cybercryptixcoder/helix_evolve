# The context store and the guidance store (November 11, 2026)

Shreyas asked for this on November 11. It replaces the November 9 knowledge bank.

## Why

Two kinds of knowledge enter a run before it starts, and they need different treatment.

- **Facts.** What the problem is, its rules, and what is known about its domain. These are true by definition.
- **Guidance.** Approaches that might help: the field's methods and our own hunches. These may be wrong *for this
  problem*, so the search has to be able to find that out, and must not get stuck following advice that doesn't work.

The November 9 knowledge bank mixed the two, and it never learned from what happened when an entry was used.

## The three memories

| | Context store | Guidance store | Atlas |
|---|---|---|---|
| Holds | Facts about the problem and its domain | Approaches that may help, each a hypothesis | What this run tried and learned |
| Written by | Us, before the run | Us, before the run | The run |
| Changes during a run | Never | Each entry's record grows | Grows every generation |
| Removed | — | Never: an entry's record changes how it reads | Never |
| Seen by | Every agent | The planner and the mutators (every entry with its record); a coder (the entries it uses) | The planner, through its map |

## How guidance is tested

1. The planner, or a mutator, reads the guidance with each entry's record, and cites the entries an experiment
   draws on (`"guidance": ["G3"]`, or a `GUIDANCE: G3` line from a mutator).
2. The coder gets the full text of the cited entries and writes the program. The program is run and scored, as
   always.
3. **The entry's record** is computed by code from the measured results of the programs that cited it: how many
   gained, how many didn't, how many failed, the best gain, and the latest attempts with what each one tried. The
   record is never the model's opinion.
   - It counts programs from earlier generations only, so every agent of a generation sees the same record.
   - It is read from the archive, so it needs no file of its own and is right after a resume.
4. **The Atlas** records the specific attempt. The Distiller is told which entries each program drew on, and asked
   to say in its finding how the entry was implemented and what that did ("G3, implemented as …: no gain because …").

So one failed attempt never removes an entry. An untested entry invites a first try. "Tried 5 ways, never gained"
tells the planner the entry probably doesn't apply here, and lists the ways already tried, so a next attempt must be
different. A record of gains says to build on it.

## The two stores are kept apart from the Atlas

- The guidance store holds only a tally per entry and pointers to the programs (ids). The details live in the Atlas
  and the archive.
- A fact the run discovers is an Atlas finding, never a context entry. The context store is our statement of the
  problem, and only we change it.
- The run does not add guidance entries. Guidance is what we bring in; the Atlas is what the run learns.

## In the code

- `lean/stores.py` (about 100 lines): the store texts, the guidance's records, the citations.
- Wired into the loop and the Atlas: about 30 changed lines.
- A problem supplies `context` and `guidance` as text. With neither, every prompt is as before (tested), so lean's
  golden version is unchanged by default.
- `inspiration: "guidance"`: a mutator gets the guidance instead of another strong program (so the population is not
  shown one program to copy again and again).

## Open, for later

- The system prompts still carry one line of problem wording: the program's signature and its limits. Moving it
  into the context store would make the prompts fully generic. This would be a separate change, tested against v4's
  text.
- How much guidance is too much: every entry goes to the planner and the mutators in full. With a large store, a
  one-line index with entries opened on demand (as the Atlas does) would be the next step.
