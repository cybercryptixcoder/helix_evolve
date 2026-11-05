# v10.1 after about 3 hours (October 29, 01:00; data at f67898b)

**The comparison:** v101-axes 0.941441744965 -> 0.941441754556 (+9.6e-9) against the field's program from the same
start 0.941441752245 (+7.3e-9, flat); v101-warm 0.962273842985 -> +2e-13, the field's program +0 (flat). Helix "leads"
on both, by noise-level amounts. Nothing meaningful has moved.

## What the programs did (48 in axes, 35 in warm)

- **Almost everything is polishing one converged construction.** Axes: 41 of 48 changed their start by less than 1e-6;
  37 started from a 0.94144 base. Warm: 26 of 35; 17 started from the 0.962274 seed.
- **Borrowed ideas are built as polishers of the record, not as constructions.** A flip to "Dinkelbach",
  "irregular blocks" or "the field's blueprint" gets the record as its start, changes the optimiser, and hands the
  record back nearly unchanged (it lands on the record's hill and the race stops it). The few programs that built
  the idea as a new construction scored 0.72-0.91 at their foot and were handed back only as "alternatives" beside
  the start; one track that kept climbing one (T316) went 0.844 -> 0.909 in one experiment.
- **The wide loop spends 2 of 3 mutations on v9's old 0.941 lineages** (22 of 26 in axes, 16 of 19 in warm),
  polishing them by 1e-11 to 1e-5.
- **A bug in the warm run:** plans could name the 2M world record (out of the size class) as a base; four main
  experiments failed on length (fixed: such a base is replaced by the main track's best, and those tracks are hidden
  from the planner).
- **A climb worth noting:** a wide mutation on the 50k import KiroScientist (0.9505) reached 0.9605 (+0.01) in one
  program: the lower imports have room; the polished vertices don't.
- **Pace:** 17-28 minutes a generation; the bar gets few slots (858 CPU-s against 10,771) but it has converged
  anyway on both polished starts; from nothing it is still climbing (0.845 -> 0.876).

## Why

1. **The test as designed can't discriminate.** Both starts are converged vertices for every polishing method (the
   field's program adds ~1e-9 and stops; so does ours). At such a start, a fair comparison measures who finds the
   last 1e-9, which says nothing about searching axes.
2. **Anchoring.** Every program is handed the record's construction and judged against it, so an idea is applied to
   that construction rather than built; building a different construction costs 0.03-0.2 at its foot.
3. **Climbing a new idea takes many experiments,** and at 300 s a program and 20-28 minutes a generation a new track
   gets about one experiment every half hour.
4. **The field's own history agrees:** nobody reached the 0.962 basin from concepts; every construction above 0.96
   inherits a high-resolution lineage. From concepts alone, the field's best program reaches 0.876 so far.

## Options (open: Shreyas's call)

- **Compare from scratch:** Helix from Code Zero with the field's axes against the field's program from nothing (the
  bar is already running: 0.876 and climbing). Equal start, equal compute, room to climb: a method claim.
- **Compare from a start with room:** both from the field's 50k constructions (0.950-0.961), where a single program
  just gained 0.01.
- **Build ideas, don't patch them:** exploration slots start from nothing or from the idea's own construction, and
  are judged against their own curve (not the record); wide mutations restricted to the run's own lineages.
