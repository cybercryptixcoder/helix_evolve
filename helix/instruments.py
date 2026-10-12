"""Instruments: what the champion's packings look like, next to near-optimal packings of the same jobs.

The Researcher used to see only scores. With these it can see *how* the champion loses: how many jobs
its bins hold, which combinations of job shapes it builds, how many bins it strands (one resource used
up while much of the other is left), compared with a near-optimal packing (helix/bounds.py --packings).

Jobs are put in classes by size, one letter per resource (CPU first, then memory):
S = under 20% of the bin, M = 20-40%, L = 40% or more. "LS" is a big-CPU, small-memory job.
"""
from collections import Counter

import numpy as np

from .bounds import diagnostic_instances, load_packings

STRANDED_LOW, STRANDED_HIGH = 0.05, 0.25


def job_class(item, cap):
    def size(v):
        return "S" if v < 0.2 else ("M" if v < 0.4 else "L")
    return size(item[0] / cap[0]) + size(item[1] / cap[1])


def pattern(classes):
    """A bin's make-up, e.g. "2LS+SL" for two big-CPU jobs and one big-memory job."""
    c = Counter(classes)
    return "+".join(f"{n if n > 1 else ''}{k}" for k, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def describe(inst, bins):
    items = np.asarray(inst["items"])
    cap = np.asarray(inst["capacity"], dtype=float)
    classes = [job_class(it, cap) for it in items]
    per_bin, patterns, stranded, left = Counter(), Counter(), 0, []
    for b in bins:
        per_bin[len(b)] += 1
        patterns[pattern(classes[i] for i in b)] += 1
        rest = 1 - items[b].sum(axis=0) / cap
        left.append(rest)
        if rest.min() < STRANDED_LOW and rest.max() > STRANDED_HIGH:
            stranded += 1
    left = np.asarray(left) if left else np.zeros((1, 2))
    return {"bins": len(bins), "simple_bound": inst["lower_bound"],
            "mean_jobs": round(len(items) / max(len(bins), 1), 2),
            "jobs_per_bin": {str(k): v for k, v in sorted(per_bin.items())},
            "patterns": dict(patterns.most_common(6)), "stranded": stranded,
            "left_cpu": round(float(left[:, 0].mean()), 3), "left_mem": round(float(left[:, 1].mean()), 3)}


def optimal_descriptions():
    """{family: description of the near-optimal packing} for the diagnostic instances that have one."""
    stored = load_packings()
    out = {}
    for inst in diagnostic_instances():
        p = stored.get(inst["id"])
        if p:
            out[inst["family"]] = {"instance": inst["id"], **describe(inst, p["bins"]), "optimum_at_least": p["lower"]}
    return out


def compare(champion_bins):
    """champion_bins: {instance id: bins} -> {family: {"champion": ..., "optimum": ...}}."""
    opt = optimal_descriptions()
    out = {}
    for inst in diagnostic_instances():
        if inst["id"] in champion_bins:
            out[inst["family"]] = {"instance": inst["id"], "champion": describe(inst, champion_bins[inst["id"]]),
                                   "optimum": opt.get(inst["family"])}
    return out


def text(comparison, families=None):
    """The comparison as text for the Researcher, the families with the biggest gap first."""
    if not comparison:
        return "(no packing comparison available)"
    rows = sorted(comparison.items(), key=lambda kv: -(kv[1]["champion"]["bins"] - (kv[1]["optimum"] or {}).get("bins", kv[1]["champion"]["bins"])))
    if families:
        rows = [r for r in rows if r[0] in families]
    lines = ["Job classes: one letter per resource (CPU, then memory): S < 20% of the bin, M 20-40%, L >= 40%. "
             f"A bin is stranded when one resource has < {STRANDED_LOW:.0%} left and the other > {STRANDED_HIGH:.0%}."]
    def fmt_counts(d):
        top = sorted(sorted(d.items(), key=lambda kv: -kv[1])[:5], key=lambda kv: int(kv[0]))
        return ", ".join(f"{k} jobs: {v}" for k, v in top)
    fmt_pat = lambda d: "; ".join(f"{k} x{v}" for k, v in list(d.items())[:5])
    for fam, c in rows:
        ch, op = c["champion"], c["optimum"]
        head = f"\n### {fam} ({c['instance']}): champion {ch['bins']} bins"
        if op:
            head += f", near-optimal packing {op['bins']} bins (no packing can use fewer than {op['optimum_at_least']})"
        lines.append(head + f"; simple bound {ch['simple_bound']}")
        lines.append(f"- jobs per bin: champion {ch['mean_jobs']} on average ({fmt_counts(ch['jobs_per_bin'])})"
                     + (f" | optimum {op['mean_jobs']} ({fmt_counts(op['jobs_per_bin'])})" if op else ""))
        lines.append(f"- stranded bins: champion {ch['stranded']}" + (f" | optimum {op['stranded']}" if op else "")
                     + f"; average room left per bin: champion CPU {ch['left_cpu']:.0%}, memory {ch['left_mem']:.0%}"
                     + (f" | optimum CPU {op['left_cpu']:.0%}, memory {op['left_mem']:.0%}" if op else ""))
        lines.append(f"- most common bins: champion {fmt_pat(ch['patterns'])}")
        if op:
            lines.append(f"  optimum: {fmt_pat(op['patterns'])}")
    return "\n".join(lines)
