"""The design map's codebook: the axes (design questions every program answers) and their values (the options),
each with a permanent id (docs/V9_DESIGN.md).

- An axis id (A1, A2, ...) and a value id (A1.v1, A1.v2, ...) are given once, at birth, and never reused or
  renumbered, like NEAT's historical markings: a coordinate written at generation 300 still means the same thing at
  generation 900.
- Names are matched before anything is added, so asking for an axis or a value that already exists (in other words)
  returns the existing id. Matching is deterministic: normalised words and their overlap; a merge decided later (by
  the model or by hand) is recorded as an alias, and the old id resolves to the new one.
- Some axes exist only under one value of another (a cooling schedule exists only if the acceptance rule is
  annealing): `parent` / `parent_value`.
- Pairs of values that proved impossible together are recorded (`incompatible`), the cross-consistency check of a
  morphological box.
- A coordinate is a dict {axis id: value id}. An axis missing from it is unknown for that program.

The codebook is problem-agnostic: the run fills it from its own programs.
"""
from __future__ import annotations

import copy
import json
import re

STOP = {"a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "is", "are", "be", "by", "with", "how", "what",
        "which", "its", "it", "this", "that", "used", "use", "uses", "using", "during", "into", "from", "as", "at",
        "does", "do", "program", "programs", "search", "each", "every", "all", "whether", "any"}
NEW = "new"                  # a drop may ask for "a new option of this axis": value id "<axis>.new"


def words(text):
    """The meaningful words of a name: lower case, no punctuation, no stop words, crude plural folding."""
    out = []
    for w in re.findall(r"[a-z0-9]+", str(text or "").lower()):
        if w in STOP:
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def similar(a, b):
    """Word overlap of two names (Jaccard on meaningful words), 1.0 for identical normalised names."""
    wa, wb = set(words(a)), set(words(b))
    if not wa or not wb:
        return 1.0 if str(a).strip().lower() == str(b).strip().lower() else 0.0
    return len(wa & wb) / len(wa | wb)


def axis_of(vid):
    return str(vid).rsplit(".", 1)[0]


def is_new(vid):
    return str(vid).endswith("." + NEW)


class Codebook:
    MATCH = 0.75             # names at least this similar are the same axis or value

    def __init__(self, data=None):
        data = copy.deepcopy(data) if data else {}
        self.axes = data.get("axes", {})
        self.next_axis = int(data.get("next_axis", 1))
        self.incompatible = [list(x) for x in data.get("incompatible", [])]
        self.log = data.get("log", [])

    # ---------------------------------------------------------------- serialisation
    def to_json(self):
        return {"axes": self.axes, "next_axis": self.next_axis, "incompatible": self.incompatible, "log": self.log[-200:]}

    def copy(self):
        return Codebook(self.to_json())

    @classmethod
    def load(cls, path):
        return cls(json.loads(open(path).read()))

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=1)

    # ---------------------------------------------------------------- lookups
    def resolve(self, aid):
        seen = set()
        while aid in self.axes and self.axes[aid].get("merged_into") and aid not in seen:
            seen.add(aid)
            aid = self.axes[aid]["merged_into"]
        return aid

    def resolve_value(self, vid):
        if vid is None:
            return None
        if is_new(vid):
            return f"{self.resolve(axis_of(vid))}.{NEW}"
        aid = self.resolve(axis_of(vid))
        ax = self.axes.get(axis_of(vid))
        seen = set()
        while ax is not None and vid in ax["values"] and ax["values"][vid].get("merged_into") and vid not in seen:
            seen.add(vid)
            vid = ax["values"][vid]["merged_into"]
            ax = self.axes.get(axis_of(vid))
        if axis_of(vid) != aid and aid in self.axes:          # the value's axis was merged: find it there by name
            name = self.value_name(vid)
            found = self.find_value(aid, name) if name else None
            return found or vid
        return vid

    def active_axes(self):
        return [a for a, x in self.axes.items() if not x.get("merged_into") and x.get("status", "active") != "dropped"]

    def reliable_axes(self, min_agreement=0.5):
        """Axes that may steer the search: active, and not measured unreliable."""
        out = []
        for a in self.active_axes():
            ag = self.axes[a].get("agreement")
            if ag is None or ag.get("n", 0) < 6 or ag.get("rate", 1.0) >= min_agreement:
                out.append(a)
        return out

    def values(self, aid):
        ax = self.axes.get(self.resolve(aid))
        return [v for v, x in ax["values"].items() if not x.get("merged_into")] if ax else []

    def name(self, aid):
        ax = self.axes.get(self.resolve(aid))
        return ax["name"] if ax else str(aid)

    def value_name(self, vid):
        if vid is None:
            return "?"
        if is_new(vid):
            return "a new option, unlike the listed ones"
        ax = self.axes.get(axis_of(vid))
        x = ax["values"].get(vid) if ax else None
        return x["name"] if x else str(vid)

    def find_axis(self, name, threshold=None):
        t = self.MATCH if threshold is None else threshold
        best, score = None, 0.0
        for a in self.active_axes():
            ax = self.axes[a]
            for n in [ax["name"]] + ax.get("aliases", []):
                s = similar(name, n)
                if s > score:
                    best, score = a, s
        return best if score >= t else None

    def find_value(self, aid, name, threshold=None):
        t = self.MATCH if threshold is None else threshold
        aid = self.resolve(aid)
        ax = self.axes.get(aid)
        if ax is None:
            return None
        best, score = None, 0.0
        for v in self.values(aid):
            x = ax["values"][v]
            for n in [x["name"]] + x.get("aliases", []):
                s = similar(name, n)
                if s > score:
                    best, score = v, s
        return best if score >= t else None

    # ---------------------------------------------------------------- growing
    def add_axis(self, name, gen=None, source="", values=(), parent=None, parent_value=None, question=None):
        """The id of the axis called `name`: an existing one if the name matches, else a new one."""
        name = " ".join(str(name).split())[:160]
        aid = self.find_axis(name)
        if aid is None:
            aid = f"A{self.next_axis}"
            self.next_axis += 1
            self.axes[aid] = {"id": aid, "name": name, "question": question or name, "born": gen, "source": source,
                              "aliases": [], "parent": parent, "parent_value": parent_value, "status": "active",
                              "values": {}, "next_value": 1, "agreement": None}
            self.log.append([gen, "axis", aid, name, source])
        elif name.lower() != self.axes[aid]["name"].lower() and name not in self.axes[aid]["aliases"]:
            self.axes[aid]["aliases"] = (self.axes[aid]["aliases"] + [name])[-8:]
        for v in values or ():
            self.add_value(aid, v, gen, source)
        return aid

    def add_value(self, aid, name, gen=None, source=""):
        aid = self.resolve(aid)
        ax = self.axes[aid]
        name = " ".join(str(name).split())[:160]
        vid = self.find_value(aid, name)
        if vid is None:
            vid = f"{aid}.v{ax['next_value']}"
            ax["next_value"] += 1
            ax["values"][vid] = {"id": vid, "name": name, "born": gen, "source": source, "aliases": []}
            self.log.append([gen, "value", vid, name, source])
        elif name.lower() != ax["values"][vid]["name"].lower() and name not in ax["values"][vid]["aliases"]:
            ax["values"][vid]["aliases"] = (ax["values"][vid]["aliases"] + [name])[-8:]
        return vid

    def merge_axis(self, src, dst, gen=None):
        """src becomes an alias of dst: its values move over (matched by name), its id resolves to dst."""
        src, dst = self.resolve(src), self.resolve(dst)
        if src == dst or src not in self.axes or dst not in self.axes:
            return dst
        a, b = self.axes[src], self.axes[dst]
        for v in list(self.values(src)):
            nv = self.add_value(dst, a["values"][v]["name"], gen, "merge")
            a["values"][v]["merged_into"] = nv
        a["merged_into"] = dst
        b["aliases"] = (b["aliases"] + [a["name"]] + a.get("aliases", []))[-8:]
        self.log.append([gen, "merge-axis", src, dst, ""])
        return dst

    def merge_value(self, src, dst, gen=None):
        src, dst = self.resolve_value(src), self.resolve_value(dst)
        if src == dst or axis_of(src) != axis_of(dst):
            return dst
        ax = self.axes[axis_of(src)]
        ax["values"][src]["merged_into"] = dst
        ax["values"][dst]["aliases"] = (ax["values"][dst]["aliases"] + [ax["values"][src]["name"]])[-8:]
        self.log.append([gen, "merge-value", src, dst, ""])
        return dst

    def mark_incompatible(self, v1, v2, gen=None):
        pair = sorted([self.resolve_value(v1), self.resolve_value(v2)])
        if axis_of(pair[0]) != axis_of(pair[1]) and pair not in self.incompatible:
            self.incompatible.append(pair)
            self.log.append([gen, "incompatible", pair[0], pair[1], ""])

    def compatible(self, coord):
        vals = {self.resolve_value(v) for v in coord.values() if v}
        return not any(a in vals and b in vals for a, b in self.incompatible)

    def set_agreement(self, aid, n, agree, kappa=None):
        self.axes[self.resolve(aid)]["agreement"] = {"n": int(n), "rate": round(agree / n, 4) if n else None,
                                                     "kappa": None if kappa is None else round(kappa, 4)}

    # ---------------------------------------------------------------- coordinates
    def canonical(self, coord):
        out = {}
        for a, v in (coord or {}).items():
            ra = self.resolve(a)
            if ra in self.axes and v:
                rv = self.resolve_value(v)
                if rv and axis_of(rv) == ra:
                    out[ra] = rv
        return out

    # ---------------------------------------------------------------- text for prompts
    def text(self, axes=None, max_values=8, stats=None):
        """The codebook as the annotator and planner see it: one block per axis with its values' ids."""
        rows = []
        for a in axes or self.active_axes():
            ax = self.axes[a]
            cond = ""
            if ax.get("parent") and ax.get("parent_value"):
                cond = f" (only when {ax['parent']} is {ax['parent_value']})"
            rows.append(f"{a}: {ax['question'] if ax.get('question') else ax['name']}{cond}")
            vs = self.values(a)
            for v in vs[:max_values]:
                st = (stats or {}).get(v, "")
                rows.append(f"   {v}: {ax['values'][v]['name']}{(' ' + st) if st else ''}")
            if len(vs) > max_values:
                rows.append(f"   (+{len(vs) - max_values} more values)")
        return "\n".join(rows)

    def describe(self, coord, axes=None):
        """A coordinate in words: one line per known axis."""
        out = []
        for a in axes or self.active_axes():
            v = (coord or {}).get(a)
            if v:
                out.append(f"- {a} ({self.name(a)}): {v} {self.value_name(v)}")
        return "\n".join(out)


def consolidate(cb, reply_json, gen=None):
    """Applies a consolidation reply {"merge": [[keep, dup, dup], ...]}: every dup becomes an alias of keep. Returns
    the merges made."""
    done = []
    for group in (reply_json or {}).get("merge") or []:
        if not isinstance(group, list) or len(group) < 2:
            continue
        keep = cb.resolve(str(group[0]).strip())
        if keep not in cb.axes:
            continue
        for dup in group[1:]:
            d = cb.resolve(str(dup).strip())
            if d in cb.axes and d != keep:
                cb.merge_axis(d, keep, gen)
                done.append((d, keep))
    return done


def hamming(c1, c2, axes=None):
    """Axes on which both coordinates are known and differ (unknowns don't count)."""
    keys = axes if axes is not None else set(c1) | set(c2)
    return sum(1 for a in keys if c1.get(a) and c2.get(a) and c1[a] != c2[a])


def known_overlap(c1, c2, axes=None):
    keys = axes if axes is not None else set(c1) | set(c2)
    return sum(1 for a in keys if c1.get(a) and c2.get(a))
