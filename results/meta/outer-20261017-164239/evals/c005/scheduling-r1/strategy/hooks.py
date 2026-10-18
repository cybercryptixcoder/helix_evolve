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
    for n in promising[:2]:
        research.append({"approach": n["id"], "mode": "exploit", "why": "it has gained before"})
    for n in untried:
        if len(research) >= n_research - 1:
            break
        research.append({"approach": n["id"], "mode": "explore", "why": "not tried yet"})
    if unproven and view["gen"] % 2 == 0:
        research.append({"approach": unproven[0]["id"], "mode": "probe", "why": "weak but unproven: occasional retry"})
    if not research:
        research.append({"approach": "new", "mode": "explore", "why": "nothing in the tree yet"})
    research = research[:n_research]

    feats = [f for f in view["features"] if f["status"] in ("tried", "rejected", "kept")]
    feats.sort(key=lambda f: -(f["d_valid"] if f["d_valid"] is not None else (f["best_probe"] or -99)))
    vary, seen_nodes = [], set()
    for f in feats:                                   # one parent per approach: spread the width
        if f["node"] in seen_nodes:
            continue
        vary.append(f["id"])
        seen_nodes.add(f["node"])
        if len(vary) >= cfg["mutator"]["slots"] - cfg["mutator"]["fresh"]:
            break
    combine = []
    bl = view["backlog"]
    for i in range(min(len(bl) - 1, cfg["combine"]["max_pairs"])):
        combine.append([bl[i], bl[i + 1]])
    return {"thinking": "rule-based plan (no Navigator)", "new_approaches": [], "research": research,
            "mutate": {"vary": vary, "fresh": cfg["mutator"]["slots"] - len(vary)}, "combine": combine, "prune": []}
