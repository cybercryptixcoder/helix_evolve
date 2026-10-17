# Run viewer

One HTML page that replays a Helix run as a factory floor: the agents are machines, every message between them is a parcel you can click and read, and every feature is a card that travels from the agent that wrote it to Fit, gets stamped, and either joins the library or goes to the scrap pile. The page works offline and needs nothing installed; open it in a browser.

```bash
python -m viz.export helix/runs/<run>                        # writes helix/runs/<run>/viewer.html
python -m viz.export results/<run> --out run.html            # published runs work too
python -m viz.export helix/runs/<run> --json trace.json      # the trace alone; drop it on viz/viewer.html
python -m viz.export helix/runs/<run> --notes notes.json     # include a written read of the run
python -m viz.export helix/runs/<run> --summarize            # ask the model for a 2-3 sentence summary of every call
```

`viz/viewer.html` opened on its own shows a drop zone: drop any trace JSON on it. A page built by `viz.export` has the trace inside it, so it can be sent or kept as a single file.

Feature-engine runs only (run 4 onward). Program-engine runs are refused with a message; see [Extending it](#extending-it).

## What's on the page

- **Floor.** The two loops laid out as in the project's flowchart: the deep loop on the left (Inspect, Researcher, Coder, with the research log beside it), the wide loop on the right (Mutator) behind the hazard-striped air gap, and the shared Fit and Accept down the middle, feeding the Library at the top. The big number painted on the floor is the generation.
  - Envelopes are messages. Click one to read exactly what was sent: a Researcher prompt opens at the section that envelope carried (the packings, the policy, or the research log).
  - Cards are features: blue from the deep loop, orange from the wide loop. They wait in Fit's tray, sit under test, get a badge (✓ kept, + passed validation, ✕ rejected, ~ flat, = redundant), then go to Accept or to the scrap pile. Kept ones dock in the Library as chips.
  - Click a machine to see what it did in the current generation: Fit lists every trial with its train and validation change, Inspect shows the packing comparison, the research log shows what the Researcher was given.
- **Inspector** (right). With nothing selected, the current generation: what happened, the champion before and after, every feature, and the run's own console lines. Select a call to read the prompt, the reply, the hidden reasoning (if any) and the system prompt, formatted or as exact text. Select a feature to see the idea behind it, its code, the probe results as a chart, and its verdict.
- **Parts.** Every feature in a grid, one row per generation, deep and wide side by side, each with what it set out to do.
- **Champions.** Progress to optimal by generation, and each champion's code with a diff against the previous one.
- **Notes.** A written read of the run, if one was included.
- **Transport.** Play and pause (space), step through events (← →), speed, a jump to each generation, and a timeline with a tick for every agent call (blue deep, orange wide) and a diamond for every feature kept.

## Timing

The floor runs on its own clock so a run can be watched in a minute or two. Order and overlap are real (the Mutator and the deep loop run at the same time, Fit tries one feature at a time, in the order the run did), and work takes longer on screen when it took longer for real, but durations are compressed: a 7 s Researcher call shows for about 2.6 s, a 2 s Coder call for about 1.2 s, and a fit trial between 0.6 and 3.2 s. Real seconds are shown in the caption and in every panel.

## The trace (`helix-trace/1`)

`viz/export.py` reads only the run folder's own records, so the viewer shows what the run logged, nothing recomputed (apart from the packing-comparison text and the progress units, which use the same helpers the run used).

| Key | What it holds | From |
|---|---|---|
| `run` | id, the settings that matter, Code Zero, final champion, summary, held-out result | `config.json`, `summary.json`, `heldout.json` |
| `prompts` | every distinct system prompt, keyed by a short hash | `llm_calls.jsonl` |
| `calls` | every agent call: role, generation, branch, feature, start and end (epoch), seconds, tokens, settings, finish, the exact user message, reply and hidden reasoning; `kind` is `first`, `retry` (code-only or JSON-only retry) or `repair` (fixing an error) | `llm_calls.jsonl` (or `.gz`) |
| `features` | every feature: idea link, code, probe points, trial timing, train and validation change, fitted weights and importance, status and verdict, the calls behind it | `features.jsonl`, plus `[mag]` and `[tim]` lines from the console |
| `ideas` | the Researcher's ideas: claim, measurement, expected effect, builds-on, verdict | `hypotheses.jsonl` |
| `champions` | every non-trial program: code, official score, families, progress to optimal | `programs.jsonl`, `helix/metrics.py` |
| `generations` | champion before and after, kept and retired, library weights and importance, packing comparison (data and text), timings, console lines | `generations.jsonl`, `helix/instruments.py` |
| `notes` | optional: `author`, `run`, `findings`, `generations`, `calls`, `features`, `nodes` (all markdown), and `auto` (ids of model-written summaries) | `--notes`, or `notes.json` in the run folder |

Notes. The probe points and per-trial timings come from the run's console output (`HELIX_TIMING=1` adds them). A run started from the dashboard has `console.log`; for a command-line run, save the output and pass `--console`, or the probe charts are simply left out. Call start times are rebuilt from the call log's clock time and duration, so they're accurate to about a second.

## Extending it

The page is one file, in sections marked with comments: `STYLE`, `GEOMETRY`, `SCHEDULE`, `FLOOR`, `INSPECTOR`, `TABS`, `TRANSPORT`.

- **Move a machine or a belt:** `NODES` and `PATHS` in `GEOMETRY` (SVG coordinates, 1190 × 790). Belt labels are `BELT_LABELS`.
- **Add a machine** (a proof specialist, say): add it to `NODES`, add belts to `PATHS`, then in `buildSchedule()` add `work("yournode", t0, t1, label, ref)` for what it does and `env(id, "belt_key", t0, label, tone, ref)` for each message it sends or receives. `nodePanel()` decides what clicking it shows.
- **Show a new kind of record:** add it to the trace in `viz/export.py` (`build_trace`), then read it from `T` in the page.
- **Program-engine runs:** the records differ (programs and hypotheses instead of features; a pool instead of a library). `build_trace` would map hypotheses to cards and the pool to the library, and `buildSchedule` would route cause/improve tests through Coder to the evaluator.
