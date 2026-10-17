"""Strategy folders as candidates: reading, applying agent edits, validating, capping budgets."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path

ROLES = ("researcher", "mutator", "coder", "navigator", "prover")
CAPS = {("researcher", "experiments"): 6, ("mutator", "slots"): 6, ("fit", "trial_evals"): 48,
        ("fit", "champion_refit_evals"): 48, ("fit", "joint_refit_evals"): 48, ("combine", "max_pairs"): 3}
EDITABLE = re.compile(r"^(config\.json|hooks\.py|prompts/[a-z_]+\.md|prompts/features/[a-z_]+\.md)$")


def files(folder):
    folder = Path(folder)
    out = {}
    for p in sorted(folder.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            rel = p.relative_to(folder).as_posix()
            if EDITABLE.match(rel):
                out[rel] = p.read_text()
    return out


def digest_hash(folder):
    h = hashlib.sha1()
    for k, v in files(folder).items():
        h.update(k.encode() + b"\0" + v.encode() + b"\0")
    return h.hexdigest()[:12]


def as_text(folder, only=None, max_chars=60000):
    parts = []
    for k, v in files(folder).items():
        if only and k not in only:
            continue
        parts.append(f"<<<FILE {k}>>>\n{v.rstrip()}\n<<<END>>>")
    return "\n\n".join(parts)[:max_chars]


def parse_edits(text):
    """[(kind, path, payload)] from <<<FILE path>>>...<<<END>>> and <<<EDIT path>>><<<FIND>>>..<<<REPLACE>>>..<<<END>>>."""
    edits = []
    for m in re.finditer(r"<<<FILE\s+([^>\s]+)>>>\n(.*?)\n?<<<END>>>", text or "", re.S):
        edits.append(("file", m.group(1).strip(), m.group(2)))
    for m in re.finditer(r"<<<EDIT\s+([^>\s]+)>>>\s*<<<FIND>>>\n?(.*?)\n?<<<REPLACE>>>\n?(.*?)\n?<<<END>>>", text or "", re.S):
        edits.append(("edit", m.group(1).strip(), (m.group(2), m.group(3))))
    return edits


def apply_edits(parent, child, edits):
    """Copy the parent folder to child and apply the edits. Returns (changed paths, errors)."""
    parent, child = Path(parent), Path(child)
    if child.exists():
        shutil.rmtree(child)
    shutil.copytree(parent, child, ignore=shutil.ignore_patterns("__pycache__"))
    changed, errors = [], []
    for kind, path, payload in edits:
        if not EDITABLE.match(path):
            errors.append(f"{path}: not an editable strategy file")
            continue
        target = child / path
        if kind == "file":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload.rstrip() + "\n")
            changed.append(path)
        else:
            find, repl = payload
            if not target.exists():
                errors.append(f"{path}: no such file")
                continue
            s = target.read_text()
            n = s.count(find)
            if n != 1:
                errors.append(f"{path}: the find text appears {n} times (must be exactly once)")
                continue
            target.write_text(s.replace(find, repl))
            changed.append(path)
    return sorted(set(changed)), errors


def validate(folder):
    """Errors that would break the inner engine, plus budget caps (applied in place, reported)."""
    folder = Path(folder)
    errors, notes = [], []
    try:
        cfg = json.loads((folder / "config.json").read_text())
    except (OSError, ValueError) as e:
        return [f"config.json: {e}"], notes
    for (sec, key), cap in CAPS.items():
        v = (cfg.get(sec) or {}).get(key)
        if isinstance(v, (int, float)) and v > cap:
            cfg[sec][key] = cap
            notes.append(f"{sec}.{key} capped at {cap}")
    if notes:
        (folder / "config.json").write_text(json.dumps(cfg, indent=2))
    for role in ROLES:
        if not (folder / "prompts" / f"{role}.md").exists():
            errors.append(f"prompts/{role}.md is missing")
        if not (folder / "prompts" / "features" / f"{role}.md").exists():
            errors.append(f"prompts/features/{role}.md is missing")
    try:
        spec = importlib.util.spec_from_file_location("candidate_hooks", folder / "hooks.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        view = {"gen": 2, "nodes": [{"id": "a01", "title": "t", "description": "", "state": "promising", "tries": 1,
                                     "best_gain": 0.2, "last_gen": 1, "parent": ""},
                                    {"id": "a02", "title": "u", "description": "", "state": "untried", "tries": 0,
                                     "best_gain": None, "last_gen": None, "parent": ""}],
                "features": [{"id": "f001", "node": "a01", "origin": "deep", "status": "kept", "best_probe": 0.3,
                              "d_valid": 0.2, "gen": 1, "name": "x"}],
                "library": ["f001"], "backlog": [], "config": cfg}
        plan = mod.allocate(view)
        if not isinstance(plan, dict) or not isinstance(plan.get("research"), list) or not isinstance(plan.get("mutate"), dict):
            errors.append("hooks.allocate must return a dict with a 'research' list and a 'mutate' dict")
    except Exception as e:  # noqa: BLE001
        errors.append(f"hooks.py: {type(e).__name__}: {e}")
    return errors, notes


def diff_summary(parent, child, max_lines=40):
    import difflib
    a, b = files(parent), files(child)
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) == b.get(k):
            continue
        d = list(difflib.unified_diff((a.get(k) or "").splitlines(), (b.get(k) or "").splitlines(), lineterm="", n=0))
        out.append(f"--- {k}")
        out += [l for l in d[2:] if not l.startswith("@@")][:max_lines]
    return "\n".join(out)
