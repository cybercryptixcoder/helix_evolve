"""The problem interface. Every problem in `suite/` is a *priority problem*:

A solution is built one decision at a time. At each decision the policy scores the candidates and the
highest score wins (ties: the first candidate). The policy is a weighted sum of features, each written by
an agent as `feature(*args)` returning one number per candidate. Code Zero is the policy that scores every
candidate 0, so it always takes the first candidate.

A problem subclass provides (see docs/V3_DESIGN.md §4 and suite/README.md):

    name, title, families, description, signature, signature_doc
    instances(split)              -> list of dicts with at least "id" and "family"   (deterministic)
    run(instance, priority)       -> {"gap": % above the instance's reference, ...}
    n_candidates(args)            -> number of candidates in a decision
    floor(family)                 -> the best gap reachable (default 0)
    diagnose(instance, priority)  -> {metric: number}      (optional)
    reference_metrics(instance)   -> {metric: number}      (optional: the reference solution's)
    metric_notes                  -> {metric: what it means}  (optional, shown to the Researcher)
    diagnostic_ids                -> instance ids (train split) used for diagnostics (default: first per family)
    example_features              -> a few trivial features, only for crash tests (never shown to agents)
"""
from __future__ import annotations

import importlib


class Problem:
    name = "problem"
    title = "A problem"
    families: list = []
    held_out_families: list = []
    description = ""
    signature = "feature(*args)"
    signature_doc = ""
    metric_notes: dict = {}
    example_features: list = []
    # how many instances of each split the engine uses (problems may override)
    fit_split = "train"
    search_split = "train"      # the split searches, probes and refits run on (a problem may name a smaller one)
    candidates_arg = 1          # which argument of the signature holds the candidates (for writing programs)

    # ------------------------------------------------------------ must implement
    def instances(self, split):
        raise NotImplementedError

    def run(self, instance, priority):
        raise NotImplementedError

    def n_candidates(self, args):
        raise NotImplementedError

    # ------------------------------------------------------------ optional
    def floor(self, family):
        return 0.0

    def diagnose(self, instance, priority):
        r = self.run(instance, priority)
        return {k: v for k, v in r.items() if isinstance(v, (int, float))}

    def reference_metrics(self, instance):
        return {}

    def diagnostic_ids(self):
        seen, out = set(), []
        for inst in self.instances("train"):
            if inst["family"] not in seen:
                seen.add(inst["family"])
                out.append(inst["id"])
        return out

    # ------------------------------------------------------------ shared helpers
    def instance(self, split, iid):
        for inst in self.instances(split):
            if inst["id"] == iid:
                return inst
        raise KeyError(iid)

    def describe_diagnostics(self, champ, ref):
        """champ/ref: {instance id: {metric: value}} -> markdown table per instance, champion vs reference."""
        lines = []
        for iid, m in champ.items():
            r = ref.get(iid) or {}
            fam = iid.rsplit("-", 1)[0]
            cells = []
            for k, v in m.items():
                if k in ("gap",) or not isinstance(v, (int, float)):
                    continue
                rv = r.get(k)
                cells.append(f"{k} {fmt(v)}" + (f" (ref {fmt(rv)})" if rv is not None else ""))
            gap = m.get("gap")
            rgap = r.get("gap")
            head = f"- **{fam}** ({iid}): gap {fmt(gap)}%" + (f" (ref {fmt(rgap)}%)" if rgap is not None else "")
            lines.append(head + ("; " + "; ".join(cells) if cells else ""))
            extra = m.get("_text")
            if extra:
                lines.append("  " + extra.replace("\n", "\n  "))
        return "\n".join(lines)


def fmt(v):
    if v is None:
        return "?"
    if isinstance(v, float):
        return f"{v:.3g}" if abs(v) < 1000 else f"{v:.0f}"
    return str(v)


REGISTRY = {
    "binpack2d": "suite.binpack2d:BinPack2D",
    "binpack1d": "suite.binpack1d:BinPack1D",
    "tsp": "suite.tsp:TSPConstruct",
    "knapsack": "suite.knapsack:Knapsack",
    "scheduling": "suite.scheduling:Scheduling",
    "coloring": "suite.coloring:GraphColoring",
    "setcover": "suite.setcover:SetCover",
    "jobshop": "suite.jobshop:JobShop",
}


def load_problem(name) -> Problem:
    """A problem by name (see REGISTRY) or by 'module:Class'."""
    spec = REGISTRY.get(name, name)
    mod, cls = spec.split(":")
    return getattr(importlib.import_module(mod), cls)()


def available():
    out = []
    for name in REGISTRY:
        try:
            load_problem(name)
            out.append(name)
        except Exception:
            pass
    return out
