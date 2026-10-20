# Headroom reference for the runner problem (docs/WORKLOG.md, October 20): a beam-search planner over the
# game's own step() compared with the evolved champion.  python3 tools/runner_headroom.py . train 2000
"""How close is the evolved runner champion to the best possible? A beam-search planner over the game's own
step() function, compared with the champion and Code Zero on the same levels (same cost rules).
usage: python -I runner_planner.py <repo> <split> [beam]"""
import importlib.util, math, sys, time
repo, split = sys.argv[1], sys.argv[2]
BEAM = int(sys.argv[3]) if len(sys.argv) > 3 else 300
sys.path.insert(0, repo)
from suite import runner as R

spec = importlib.util.spec_from_file_location("champ", f"{repo}/results/open/runner/champion.py")
champ = importlib.util.module_from_spec(spec); spec.loader.exec_module(champ)


def plan(level):
    lv = level["_lv"]; saws = lv.saw_list; goal = lv.goal_x
    cx, cy = lv.flags[0]
    frontier = [(cx, cy, 0.0, 0.0, True, 0, 0, 1)]
    for clock in range(R.CAP):
        t1 = clock + 1
        nxt = {}
        for st in frontier:
            x = st[0]
            near = []
            for s in saws:
                if min(s[0], s[2]) - 2 < x < max(s[0], s[2]) + 2:
                    px, py, _, _ = R.saw_pos(s, t1)
                    near.append((px, py))
            for a in R.legal(st):
                st2, ok = R.step(lv, st, a, near)
                if not ok:
                    continue
                if st2[0] >= goal:
                    return t1, True
                key = (round(st2[0], 2), round(st2[1], 2), round(st2[2], 2), round(st2[3], 2), st2[4], st2[5] > 0, st2[6])
                if key not in nxt:
                    nxt[key] = st2
        if not nxt:
            return None, False
        # keep the states furthest right; break ties by speed, and keep some height diversity
        frontier = sorted(nxt.values(), key=lambda s: (s[0] + 2.0 * s[2], s[1]), reverse=True)[:BEAM]
    return None, False


P = R.Runner()
tot = {"cz": 0, "champ": 0, "plan": 0}
rows = []
t0 = time.time()
for inst in P.instances(split):
    for lv in inst["levels"]:
        cz = R.run_level(lv, lv["seed"], None)
        st = R._new_stats()
        ch = R.run_level(lv, lv["seed"], champ.priority, st)
        ticks, ok = plan(lv)
        pl = float(ticks) if ok else None
        rows.append((inst["family"], cz, ch, st["finished"], st["deaths"], pl))
        tot["cz"] += cz; tot["champ"] += ch; tot["plan"] += (pl if pl is not None else ch)
        print(f"{inst['id']:12} {inst['family']:8} codezero {cz:7.0f}  champion {ch:7.0f} (finished {st['finished']}, deaths {st['deaths']})"
              f"  planner {pl if pl is not None else 'none':>6}", flush=True)
print(f"\n{split}: progress = share of Code Zero's cost removed")
for k in ("champ", "plan"):
    print(f"  {k:6} total cost {tot[k]:8.0f}  progress {100 - 100 * tot[k] / tot['cz']:5.1f}%")
fin = [r for r in rows if r[3] and r[5]]
if fin:
    print(f"  on the {len(fin)} levels both finish: champion {sum(r[2] for r in fin) / len(fin):.0f} ticks, "
          f"planner {sum(r[5] for r in fin) / len(fin):.0f} ticks")
print(f"({time.time() - t0:.0f} s, beam {BEAM})")
