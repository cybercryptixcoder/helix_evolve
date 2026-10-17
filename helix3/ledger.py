"""The ledger and the approach tree: everything tried, what it measured, how it did, and where it sits.

Identity: a feature's *fingerprint* is the within-decision rank of every candidate over a sample of decision
states. Two features with |correlation| >= duplicate_rho rank candidates the same way (up to sign, which the
optimiser fits anyway), so the second is a duplicate and isn't evaluated again.

Certificates (the only things that prune):
  inert      the feature ranks every candidate the same in every sampled decision: it can't change a choice
  duplicate  it ranks like an already-evaluated feature (fingerprint |rho| >= duplicate_rho)
  span       within every decision it is a linear combination of the kept features (R^2 >= span_r2), so adding
             it can only re-weight what is already there
An approach is pruned only when every feature tried under it holds a certificate.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import numpy as np


def rankdata(a):
    """Average ranks (1-based, ties share their mean rank), as scipy.stats.rankdata; numpy only."""
    a = np.asarray(a).ravel()
    sorter = np.argsort(a, kind="mergesort")
    inv = np.empty(sorter.size, dtype=np.intp)
    inv[sorter] = np.arange(sorter.size, dtype=np.intp)
    s = a[sorter]
    obs = np.r_[True, s[1:] != s[:-1]]
    dense = obs.cumsum()[inv]
    count = np.r_[np.nonzero(obs)[0], len(obs)]
    return 0.5 * (count[dense] + count[dense - 1] + 1)

MAX_K = 64          # candidates per state used for fingerprints (a fixed subset per state)


@dataclass
class Feature:
    id: str
    name: str = ""
    code: str = ""
    origin: str = ""                # deep | wide | combo
    gen: int = 0
    node: str = ""                  # approach id
    kind: str = ""                  # deep: probe | improve; wide: variant | fresh
    parent: str = ""                # the feature a wide variant varied
    idea: dict = field(default_factory=dict)     # hypothesis, measure, prediction {...}
    coder_note: str = ""
    measures: str = ""              # the code's own docstring: what it actually computes
    status: str = "new"             # new | invalid | duplicate | inert | span | rejected | tried | kept | retired
    verdict: str = ""
    width: int = 1
    scales: list = field(default_factory=lambda: [1.0])
    weights: list = field(default_factory=lambda: [0.0])   # scaled weights (only meaningful when kept)
    probe: list = field(default_factory=list)              # [[w, delta], ...] delta = gap reduction (+ = better)
    best_probe: float | None = None
    best_w: float | None = None
    d_train: float | None = None    # trial: gap reduction on train, with vs without (+ = better)
    d_valid: float | None = None
    trial_x: list = field(default_factory=list)
    prediction: dict = field(default_factory=dict)          # outcome of the check
    duplicate_of: str = ""
    certificate: dict = field(default_factory=dict)
    error: str = ""
    calls: list = field(default_factory=list)
    kept_gen: int | None = None
    importance: float | None = None
    retired_gen: int | None = None

    def effective_weights(self):
        return [w * s for w, s in zip(self.weights, self.scales)]

    def record(self):
        return asdict(self)


@dataclass
class Node:
    id: str
    title: str
    description: str = ""
    parent: str = ""
    origin: str = ""                # navigator | researcher | wide
    state: str = "untried"          # untried | promising | unproven | pruned
    created_gen: int = 0
    features: list = field(default_factory=list)
    best_gain: float | None = None
    last_gen: int | None = None
    notes: list = field(default_factory=list)
    certificate: list = field(default_factory=list)
    streak: int = 0                 # generations in a row with experiments here and no gain
    gains: list = field(default_factory=list)    # [[gen, best gain that generation], ...]
    benched_gen: int | None = None
    revived_gen: int | None = None

    def record(self):
        return asdict(self)


class Ledger:
    def __init__(self, duplicate_rho=0.98, span_r2=0.995):
        self.features: dict[str, Feature] = {}
        self.nodes: dict[str, Node] = {}
        self.library: list[str] = []
        self.backlog: list[str] = []            # near-misses worth retrying in combination
        self.duplicate_rho, self.span_r2 = duplicate_rho, span_r2
        self.states = []                        # sampled decision args
        self.subsets = []                       # per state: candidate indices used
        self._fp = {}                           # fid -> fingerprint vector
        self._vals = {}                         # fid -> centred raw values (for span)
        self._n_f = self._n_n = 0

    # ---------------------------------------------------------------- ids
    def new_feature(self, **kw) -> Feature:
        self._n_f += 1
        f = Feature(id=f"f{self._n_f:03d}", **kw)
        self.features[f.id] = f
        return f

    def new_node(self, title, **kw) -> Node:
        self._n_n += 1
        n = Node(id=f"a{self._n_n:02d}", title=title, **kw)
        self.nodes[n.id] = n
        return n

    def lib(self):
        return [self.features[i] for i in self.library]

    # ---------------------------------------------------------------- fingerprints
    def set_states(self, states, n_candidates, seed=0):
        rng = np.random.default_rng(seed)
        keep, subs = [], []
        for args in states:
            k = n_candidates(args)
            if k < 2:
                continue
            keep.append(args)
            subs.append(np.sort(rng.choice(k, MAX_K, replace=False)) if k > MAX_K else np.arange(k))
        self.states, self.subsets = keep, subs
        self._fp, self._vals = {}, {}

    def _values(self, f, n_candidates):
        from helix3.policy import call_feature, compile_feature
        fn = compile_feature(f.code)
        out = []
        for args, sub in zip(self.states, self.subsets):
            v = call_feature(fn, args, n_candidates(args))
            out.append(v[sub])
        return out

    def fingerprint(self, f, n_candidates):
        if f.id in self._fp:
            return self._fp[f.id]
        vals = self._values(f, n_candidates)
        ranks, cent = [], []
        for v in vals:
            s = v.sum(axis=1)
            r = rankdata(s) - (len(s) + 1) / 2
            sd = r.std()
            ranks.append(r / sd if sd > 1e-12 else np.zeros_like(r))
            cent.append(v - v.mean(axis=0, keepdims=True))
        fp = np.concatenate(ranks) if ranks else np.zeros(1)
        self._fp[f.id] = fp
        self._vals[f.id] = np.concatenate(cent) if cent else np.zeros((1, 1))
        return fp

    @staticmethod
    def similarity(a, b):
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-12 or nb < 1e-12:
            return 0.0
        return float(abs(a @ b) / (na * nb))

    def certify(self, f, n_candidates, against=None):
        """Mechanical certificates for one feature. Returns {} or {"type": ..., ...}."""
        fp = self.fingerprint(f, n_candidates)
        if np.linalg.norm(fp) < 1e-12:
            return {"type": "inert", "why": "ranks every candidate equally in every sampled decision"}
        pool = against if against is not None else [g for g in list(self.features.values())
                                                     if g.id != f.id and g.status not in ("invalid", "new", "duplicate", "checking")]
        best, best_id = 0.0, ""
        for g in pool:
            try:
                s = self.similarity(fp, self.fingerprint(g, n_candidates))
            except Exception:
                continue
            if s > best:
                best, best_id = s, g.id
        if best >= self.duplicate_rho:
            return {"type": "duplicate", "of": best_id, "rho": round(best, 4)}
        lib = [g for g in self.lib() if g.id != f.id]
        r2 = None
        if lib:
            for g in lib:
                self.fingerprint(g, n_candidates)
            A = np.concatenate([self._vals[g.id] for g in lib] + [np.ones((len(self._vals[f.id]), 1)) * 0], axis=1)
            y = self._vals[f.id].sum(axis=1)
            sst = float(y @ y)
            if sst > 1e-12:
                coef, *_ = np.linalg.lstsq(A, y, rcond=None)
                r2 = 1 - float(((y - A @ coef) ** 2).sum()) / sst
                if r2 >= self.span_r2:
                    return {"type": "span", "r2": round(r2, 5), "of": [g.id for g in lib]}
        out = {"nearest": best_id, "rho": round(best, 4)} if best_id else {}
        if r2 is not None:
            out["lib_r2"] = round(r2, 4)       # how much of it the kept features already explain
        return out

    def span_r2_of(self, f, n_candidates):
        """R^2 of f regressed on the kept features within each decision (1 = it adds nothing)."""
        self.fingerprint(f, n_candidates)
        lib = [g for g in self.lib() if g.id != f.id]
        if not lib:
            return None
        for g in lib:
            self.fingerprint(g, n_candidates)
        A = np.concatenate([self._vals[g.id] for g in lib], axis=1)
        y = self._vals[f.id].sum(axis=1)
        sst = float(y @ y)
        if sst <= 1e-12:
            return 1.0
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        return 1 - float(((y - A @ coef) ** 2).sum()) / sst

    def nearest(self, f, n_candidates, ids):
        fp = self.fingerprint(f, n_candidates)
        best, best_id = 0.0, ""
        for i in ids:
            g = self.features.get(i)
            if g is None or g.id == f.id or g.status in ("invalid", "new"):
                continue
            s = self.similarity(fp, self.fingerprint(g, n_candidates))
            if s > best:
                best, best_id = s, g.id
        return best_id, best

    # ---------------------------------------------------------------- tree bookkeeping
    def update_nodes(self, gen, margin):
        for n in self.nodes.values():
            fs = [self.features[i] for i in n.features if i in self.features]
            tried = [f for f in fs if f.status not in ("new", "invalid")]
            own = [f for f in tried if f.status != "duplicate"]          # a duplicate's inherited result is not new evidence
            gains = [f.d_valid for f in own if f.d_valid is not None]
            n.best_gain = max(gains) if gains else (max((f.best_probe for f in own if f.best_probe is not None),
                                                        default=None))
            if fs:
                n.last_gen = max(f.gen for f in fs)
            if n.state in ("pruned", "benched"):
                continue
            if any(f.status in ("kept", "retired") or (f.d_valid or -1) > margin for f in own):
                n.state = "promising"
            elif tried and all(f.certificate.get("type") in ("inert", "duplicate", "span") for f in tried) and \
                    (len(tried) >= 2 or any(f.certificate.get("type") != "duplicate" for f in tried)):
                n.state = "pruned"
                n.certificate = [{"feature": f.id, **f.certificate} for f in tried]
            elif tried:
                n.state = "unproven"
            else:
                n.state = "untried"

    def save(self, path):
        data = {"features": [f.record() for f in list(self.features.values())],
                "nodes": [n.record() for n in self.nodes.values()],
                "library": self.library, "backlog": self.backlog}
        path.write_text(json.dumps(data, indent=1, default=float))
