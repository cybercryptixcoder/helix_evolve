"""Rule-based decisions, used when the Navigator is off or its plan is unusable. The meta loop may edit this.

`view` is a plain dict built by the engine (see engine.Engine.view):
  gen, nodes [{id, title, state, tries, best_gain, last_gen}], features [{id, node, origin, status, best_probe,
  d_valid, gen}], library [ids], backlog [ids], config
"""


def allocate(view):
    """A plan shaped like the Navigator's. Effort follows evidence early, then deliberately over-samples the
    untried and unproven so the search doesn't collapse onto the first promising branch."""
    cfg = view["config"]
    n_research = cfg["researcher"]["experiments"]
    slots = cfg["mutator"]["slots"]
    gen = view["gen"]
    nodes = view["nodes"]
    promising = sorted([n for n in nodes if n["state"] == "promising"], key=lambda n: -(n["best_gain"] or 0))
    untried = [n for n in nodes if n["state"] == "untried"]
    unproven = sorted([n for n in nodes if n["state"] == "unproven"], key=lambda n: (n["tries"], n["last_gen"] or 0))

    research = []
    # early generations: mostly explore, because the map is thin and one lucky gain is not evidence
    explore_first = gen <= 1 or not promising
    if explore_first:
        for n in untried:
            if len(research) >= n_research:
                break
            research.append({"approach": n["id"], "mode": "explore", "why": "early: map is thin"})
        for n in promising[:1]:
            if len(research) >= n_research:
                break
            research.append({"approach": n["id"], "mode": "exploit", "why": "the one branch that gained"})
    else:
        for n in promising[:2]:
            research.append({"approach": n["id"], "mode": "exploit", "why": "it has gained before"})
        for n in untried:
            if len(research) >= n_research - 1:
                break
            research.append({"approach": n["id"], "mode": "explore", "why": "not tried yet"})
        if len(research) < n_research:
            for n in unproven:
                if len(research) >= n_research:
                    break
                research.append({"approach": n["id"], "mode": "probe", "why": "no gain yet, not proven dead"})
    if not research:
        research.append({"approach": "new", "mode": "explore", "why": "nothing in the tree yet"})
    research = research[:n_research]

    # parents for the Mutator: keep the top two kept features in, then spread one-per-approach across nodes
    kept = [f for f in view["features"] if f["status"] == "kept"]
    kept.sort(key=lambda f: -(f["d_valid"] if f["d_valid"] is not None else (f["best_probe"] or -99)))
    feats = [f for f in view["features"] if f["status"] in ("tried", "rejected", "kept")]
    feats.sort(key=lambda f: -(f["d_valid"] if f["d_valid"] is not None else (f["best_probe"] or -99)))
    n_vary = slots - cfg["mutator"]["fresh"]
    vary, seen = [], set()
    for f in kept[:2]:                                # variants of kept features win most often
        if f["id"] not in seen:
            vary.append(f["id"])
            seen.add(f["id"])
    for f in feats:
        if len(vary) >= n_vary:
            break
        if f["id"] in seen or f["node"] in {g["node"] for g in feats if g["id"] in vary[2:]}:
            continue
        vary.append(f["id"])
        seen.add(f["id"])
    vary = vary[:n_vary]

    combine = []
    bl = view["backlog"]
    for i in range(min(len(bl) - 1, cfg["combine"]["max_pairs"])):
        combine.append([bl[i], bl[i + 1]])
    return {"thinking": "rule-based plan (no Navigator)", "new_approaches": [], "research": research,
            "mutate": {"vary": vary, "fresh": slots - len(vary)}, "combine": combine, "prune": []}
