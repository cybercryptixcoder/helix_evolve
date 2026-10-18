"""Rule-based decisions, used when the Navigator is off or its plan is unusable. The meta loop may edit this.

`view` is a plain dict built by the engine (see engine.Engine.view):
  gen, nodes [{id, title, state, tries, best_gain, last_gen}], features [{id, node, origin, status, best_probe,
  d_valid, gen}], library [ids], backlog [ids], config
"""


def allocate(view):
    """A plan with the same shape as the Navigator's: who researches what, what the Mutator varies."""
    cfg = view["config"]
    n_research = cfg["researcher"]["experiments"]
    nodes = view["nodes"]
    promising = sorted([n for n in nodes if n["state"] == "promising"], key=lambda n: -(n["best_gain"] or 0))
    untried = [n for n in nodes if n["state"] == "untried"]
    unproven = sorted([n for n in nodes if n["state"] == "unproven"], key=lambda n: (n["tries"], n["last_gen"] or 0))
    research = []
    # Only one exploit slot per generation: depth on the single best approach, not two half-deep ones.
    if promising:
        research.append({"approach": promising[0]["id"], "mode": "exploit", "why": "the strongest gained approach"})
    if len(promising) > 1 and view["gen"] % 3 == 0:
        research.append({"approach": promising[1]["id"], "mode": "exploit", "why": "second promising: occasional depth"})
    for n in untried:
        if len(research) >= n_research - 1:
            break
        research.append({"approach": n["id"], "mode": "explore", "why": "not tried yet"})
    if unproven and view["gen"] % 2 == 0 and len(research) < n_research:
        research.append({"approach": unproven[0]["id"], "mode": "probe", "why": "weak but unproven: occasional retry"})
    if not research:
        research.append({"approach": "new", "mode": "explore", "why": "nothing in the tree yet"})
    research = research[:n_research]

    feats = [f for f in view["features"] if f["status"] in ("tried", "rejected", "kept")]
    feats.sort(key=lambda f: -(f["d_valid"] if f["d_valid"] is not None else (f["best_probe"] or -99)))
    n_vary = cfg["mutator"]["slots"] - cfg["mutator"]["fresh"]
    # Kept features first (their variants win far more often), then near-misses; spread across approaches.
    kept = [f for f in feats if f["status"] == "kept"]
    rest = [f for f in feats if f["status"] != "kept"]
    vary, seen_nodes = [], set()
    for f in kept + rest:
        if f["node"] in seen_nodes and len(vary) < n_vary:
            # allow a second parent from the same approach only once slots run thin
            if len(seen_nodes) >= n_vary:
                continue
        vary.append(f["id"])
        seen_nodes.add(f["node"])
        if len(vary) >= n_vary:
            break
    combine = []
    bl = view["backlog"]
    for i in range(min(len(bl) - 1, cfg["combine"]["max_pairs"])):
        combine.append([bl[i], bl[i + 1]])
    return {"thinking": "rule-based plan (no Navigator)", "new_approaches": [], "research": research,
            "mutate": {"vary": vary, "fresh": cfg["mutator"]["slots"] - len(vary)}, "combine": combine, "prune": []}
