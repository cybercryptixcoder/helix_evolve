"""Duel (open suite): play an invented two-player territory game against a fixed pool of scripted opponents.

The game ("spore"): two players grow territories on a small graph of cells worth 1, 2 or 5 points. On a turn a
player claims an empty cell next to its territory; opponent cells next to the claimed cell that are now outnumbered
flip to the claimer. The game ends when the board is full; each player scores the points of the cells it owns.

Open ceiling (docs/OPEN_SUITE.md): an instance is 24 seeded games (6 against each opponent, half of them moving
first); cost = 100 x the opponents' share of all points scored; gap = 100 * cost / Code Zero's cost on the same
instance. Code Zero's costs are cached in suite/data/duel_cz.json (rebuild: `python -m suite.duel --cz`); an
instance missing from the cache is computed on the spot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from helix3.problem import Problem

ROOT = Path(__file__).resolve().parent.parent
CZ_FILE = ROOT / "suite" / "data" / "duel_cz.json"
SPLIT_SEED = {"train": 5171, "valid": 6282, "test": 7393}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
GAMES = 24
FAMILIES = {"grid": 1, "hex": 2, "web": 3, "islands": 4}
TRAIN_FAMILIES = ["grid", "hex", "web"]
HELD_OUT = ["islands"]
POINTS, POINT_P = (1, 2, 5), (0.6, 0.25, 0.15)


# ---------------------------------------------------------------------------------------------- boards
def _connect(A, xy):
    """Join components by their closest pair of cells until the graph is connected."""
    n = len(A)
    while True:
        comp = np.full(n, -1)
        c = 0
        for s in range(n):
            if comp[s] >= 0:
                continue
            comp[s] = c
            stack = [s]
            while stack:
                v = stack.pop()
                for u in np.flatnonzero(A[v] & (comp < 0)):
                    comp[u] = c
                    stack.append(u)
            c += 1
        if c == 1:
            return A
        a, b = np.flatnonzero(comp == 0), np.flatnonzero(comp != 0)
        d = ((xy[a][:, None, :] - xy[b][None, :, :]) ** 2).sum(-1)
        i, j = np.unravel_index(int(np.argmin(d)), d.shape)
        A[a[i], b[j]] = A[b[j], a[i]] = True


def _knn(xy, k):
    n = len(xy)
    d = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d, np.inf)
    A = np.zeros((n, n), dtype=bool)
    A[np.repeat(np.arange(n), k), np.argsort(d, 1)[:, :k].ravel()] = True
    return A | A.T


def make_board(family, rng):
    """(adjacency (N, N) bool, points (N,) int)."""
    if family == "grid":                                   # 6 x 6 square grid, 4 cells removed
        xy = np.array([(x, y) for y in range(6) for x in range(6)], dtype=float)
        A = np.abs(xy[:, None, :] - xy[None, :, :]).sum(-1) == 1
        drop = 4
    elif family == "hex":                                  # 6 x 5 hexagonal grid, 2 cells removed
        xy = np.array([(x + 0.5 * (y % 2), 0.866 * y) for y in range(5) for x in range(6)], dtype=float)
        d = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1))
        A = (d > 0.1) & (d < 1.1)
        drop = 2
    elif family == "web":                                  # 32 random points, each joined to its 3 nearest
        xy = rng.random((32, 2))
        A = _knn(xy, 3)
        drop = 0
    elif family == "islands":                              # three clumps of 11 cells, joined where closest
        centres = np.array([[0.0, 0.0], [3.0, 0.3], [1.4, 2.6]])
        xy = np.concatenate([c + rng.normal(0, 0.5, (11, 2)) for c in centres])
        A = _knn(xy, 3)
        drop = 0
    else:
        raise KeyError(family)
    keep = np.ones(len(xy), dtype=bool)
    if drop:
        keep[rng.choice(len(xy), drop, replace=False)] = False
    xy, A = xy[keep], A[np.ix_(keep, keep)]
    A = _connect(A, xy)
    perm = rng.permutation(len(A))                         # random numbering
    A = A[np.ix_(perm, perm)]
    return A, rng.choice(POINTS, len(A), p=POINT_P).astype(np.int64)


def _bfs(A, s):
    dist = np.full(len(A), -1)
    dist[s] = 0
    q = [s]
    for v in q:
        for u in np.flatnonzero(A[v] & (dist < 0)):
            dist[u] = dist[v] + 1
            q.append(u)
    return dist


# ---------------------------------------------------------------------------------------------- the game
class Board:
    """Rules. Owners are +1 / -1 (0 = empty); `home` cells never flip."""

    def __init__(self, A, pts, homes):
        self.A, self.Ai, self.pts = A, A.astype(np.int16), pts
        self.home = np.zeros(len(A), dtype=bool)
        self.home[list(homes)] = True

    def legal(self, owner, P):
        return np.flatnonzero((owner == 0) & (self.Ai @ (owner == P) > 0))

    def _vulnerable(self, owner, P):
        """Opponent cells that would flip if P claimed a cell next to them: (P's neighbours + 1) >= owner's."""
        return (owner == -P) & ~self.home & (self.Ai @ (owner == P) + 1 >= self.Ai @ (owner == -P))

    def gains(self, owner, P, M):
        """Immediate points for P of claiming each cell in M (the cell plus the cells it flips)."""
        F = self.A[M] & self._vulnerable(owner, P)[None, :]
        return self.pts[M] + F @ self.pts

    def claim(self, owner, P, c):
        """New owner array after P claims c, and the number of cells flipped."""
        flip = self._vulnerable(owner, P) & self.A[c]
        o = owner.copy()
        o[c] = P
        o[flip] = P
        return o, int(flip.sum())


def _pick(scores, M, rng):
    best = np.flatnonzero(scores == scores.max())
    return int(M[best[int(rng.integers(len(best)))]])


def opp_random(bd, owner, P, M, rng):
    return int(M[int(rng.integers(len(M)))])


def opp_greedy(bd, owner, P, M, rng):
    return _pick(bd.gains(owner, P, M), M, rng)


def opp_compact(bd, owner, P, M, rng):
    own_nb = bd.Ai[M] @ (owner == P)
    return _pick(10 * own_nb + bd.pts[M], M, rng)


def opp_lookahead(bd, owner, P, M, rng):
    g = bd.gains(owner, P, M)
    v = np.empty(len(M))
    for i, c in enumerate(M):
        o, _ = bd.claim(owner, P, c)
        M2 = bd.legal(o, -P)
        v[i] = g[i] - (bd.gains(o, -P, M2).max() if len(M2) else 0)
    return _pick(v, M, rng)


POOL = [opp_random, opp_greedy, opp_compact, opp_lookahead]


def play(game, priority, stats=None):
    """One game; the policy is +1. Returns (policy points, opponent points)."""
    A, pts = game["adj"], game["points"]
    bd = Board(A, pts, game["homes"])
    owner = np.zeros(len(A), dtype=np.int8)
    owner[game["homes"][0]], owner[game["homes"][1]] = 1, -1
    homes = np.array(game["homes"], dtype=np.int64)
    opp = POOL[game["opponent"]]
    shuffle = np.random.default_rng(game["seed"] + [1])
    orng = np.random.default_rng(game["seed"] + [2])
    P = 1 if game["first"] else -1
    turn = 0
    while (owner == 0).any():
        M = bd.legal(owner, P)
        if len(M) == 0:                                    # no empty cell next to this player: it passes
            P = -P
            continue
        if P == 1:
            k = len(M)
            M = M[shuffle.permutation(k)]
            if k == 1:
                i = 0
            else:
                s = np.asarray(priority(M, owner.copy(), homes, pts, A, turn), dtype=float)
                if s.shape != (k,):
                    raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
                i = int(np.argmax(np.round(s, 9)))
            c = int(M[i])
        else:
            c = opp(bd, owner, -1, M, orng)
        owner, nflip = bd.claim(owner, P, c)
        if stats is not None:
            if P == 1:
                stats["claims"] += 1
                stats["flips"] += nflip
                stats["claim_pts"] += int(pts[c])
            else:
                stats["lost"] += nflip
        turn += 1
        P = -P
    return int(pts[owner == 1].sum()), int(pts[owner == -1].sum())


# ---------------------------------------------------------------------------------------------- instances
def _fingerprint(inst):
    h = hashlib.sha1()
    for g in inst["games"]:
        h.update(np.packbits(g["adj"]).tobytes() + g["points"].tobytes())
        h.update(json.dumps([g["homes"], g["opponent"], g["first"], g["seed"]]).encode())
    return h.hexdigest()[:12]


def raw_instances(split):
    fams = TRAIN_FAMILIES + (HELD_OUT if split == "test" else [])
    out = []
    for fam in fams:
        code = FAMILIES[fam]
        for i in range(PER_FAMILY):
            games = []
            for g in range(GAMES):
                seed = [SPLIT_SEED[split], code, i, g]
                rng = np.random.default_rng(seed)
                A, pts = make_board(fam, rng)
                h0 = int(rng.integers(len(A)))
                dist = _bfs(A, h0)
                far = np.flatnonzero(dist == dist.max())
                h1 = int(far[int(rng.integers(len(far)))])
                pts[[h0, h1]] = 1
                homes = (h0, h1) if rng.random() < 0.5 else (h1, h0)
                games.append({"adj": A, "points": pts, "homes": homes, "opponent": g % len(POOL),
                              "first": (g // len(POOL)) % 2 == 0, "seed": seed})
            inst = {"id": f"{fam}-{SPLIT_BASE[split] + i:03d}", "family": fam, "split": split, "games": games}
            inst["fingerprint"] = _fingerprint(inst)
            out.append(inst)
    return out


def _zero(*args):
    return np.zeros(len(args[0]))


# ---------------------------------------------------------------------------------------------- the problem
class Duel(Problem):
    name = "duel"
    title = "Duel: play an invented territory game against a pool of scripted opponents"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(moves, owner, homes, points, adjacency, turn)"
    candidates_arg = 0
    description = f"""Play an invented two-player board game, "spore", against a fixed pool of scripted opponents. The policy is one player; it chooses its move each turn.

**The board.** A connected graph of about 30 cells. Each cell is worth 1, 2 or 5 points (about 60% are worth 1, 25% worth 2, 15% worth 5). Each player starts owning one *home* cell (worth 1); the two homes are far apart. All other cells start empty.

**A turn.** Players alternate. On your turn you must *claim* one empty cell that is adjacent to at least one cell you own; it becomes yours. Then *flips*: every opponent cell adjacent to the cell you just claimed (except the opponent's home, which never flips) becomes yours if, counting after your claim, you own at least as many of its neighbours as its owner does. Flips are decided all at once from the board right after the claim and do not chain: a flipped cell does not trigger further flips. A player with no legal claim (no empty cell next to its cells) passes and the other player continues.

**The end.** The game ends when no empty cell is left (about 30 claims in all, roughly half of them yours). Each player scores the points of the cells it owns at the end.

**One decision** = choosing which cell to claim. The **candidates** are your legal claims, in a random order (cells are also numbered at random). When there is only one legal claim it is taken automatically.

**Instances and cost.** An instance is {GAMES} games on freshly generated boards of one family: {GAMES // 4} against each of the 4 opponents in the pool, moving first in half of them. The opponents are scripted players with different, fixed behaviour; their logic and identity are hidden, and you never see their future moves. The instance's **cost** is 100 x the opponents' share of all points scored in its games (in [0, 100]; the board's points are always all claimed). The **gap** is 100 x cost / the cost of Code Zero (the policy that always takes the first candidate, i.e. a random legal claim) on the same instance: Code Zero scores 100, lower is better. An opponent always keeps at least its home, so 0 is impossible; there is no known best.

Three training families, differing in board shape: `grid` (a 6 x 6 square grid, 4 random cells removed, 4 neighbours per cell), `hex` (a 6 x 5 hexagonal grid, 2 cells removed, up to 6 neighbours) and `web` (32 random points, each joined to its 3 nearest). The test split adds a board shape that training never shows."""
    signature_doc = """- `moves`: shape (k,), int: the cells you may claim (the candidates), in random order. Index into the per-cell arrays below.
- `owner`: shape (N,), int8: for every cell on the board: 1 = yours, -1 = the opponent's, 0 = empty (N = number of cells).
- `homes`: shape (2,), int: your home cell and the opponent's home cell (homes never flip).
- `points`: shape (N,), int: what each cell is worth (1, 2 or 5).
- `adjacency`: shape (N, N), bool: which cells are neighbours (symmetric, False on the diagonal).
- `turn`: int: how many claims (by both players) have been made so far in this game; the game lasts N - 2 claims.
- Your current score is `points[owner == 1].sum()`, the opponent's `points[owner == -1].sum()`.
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is claimed."""
    metric_notes = {
        "cost": "100 x the opponents' share of all points in the instance's games (the instance's cost)",
        "win_pct": "% of the instance's games in which the policy scored more points than its opponent",
        "worst_share": "the opponents' share of points (%) against the opponent that did best against the policy",
        "flips_per_claim": "opponent cells flipped per claim the policy made",
        "lost_per_game": "policy cells flipped to the opponent per game",
        "claim_value": "mean points of the cells the policy claimed (not counting flips)",
    }
    example_features = [
        "import numpy as np\n\ndef feature(moves, owner, homes, points, adjacency, turn):\n"
        "    \"\"\"Points of the cell.\"\"\"\n"
        "    return points[moves].astype(float)\n",
        "import numpy as np\n\ndef feature(moves, owner, homes, points, adjacency, turn):\n"
        "    \"\"\"Neighbours of the cell that are mine.\"\"\"\n"
        "    return adjacency[moves][:, owner == 1].sum(axis=1).astype(float)\n",
        "import numpy as np\n\ndef feature(moves, owner, homes, points, adjacency, turn):\n"
        "    \"\"\"Empty neighbours of the cell.\"\"\"\n"
        "    return adjacency[moves][:, owner == 0].sum(axis=1).astype(float)\n",
    ]

    def __init__(self):
        self._cache = {}
        self._cz = None

    def instances(self, split):
        if split not in self._cache:
            if split not in SPLIT_SEED:
                raise KeyError(split)
            self._cache[split] = raw_instances(split)
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    @staticmethod
    def _cost(results):
        mine = sum(m for m, _ in results)
        theirs = sum(o for _, o in results)
        return 100.0 * theirs / (mine + theirs)

    # -------------------------------------------------------------- Code Zero's cost (cached)
    def cz_cost(self, inst):
        if self._cz is None:
            try:
                self._cz = json.loads(CZ_FILE.read_text())["instances"]
            except (OSError, ValueError, KeyError):
                self._cz = {}
        key = f"{inst['split']}/{inst['id']}"
        r = self._cz.get(key)
        if r is None or r.get("fingerprint") != inst["fingerprint"]:
            r = {"fingerprint": inst["fingerprint"], "cost": self._cost([play(g, _zero) for g in inst["games"]])}
            self._cz[key] = r
        return r["cost"]

    # -------------------------------------------------------------- scoring
    def run(self, instance, priority):
        cost = self._cost([play(g, priority) for g in instance["games"]])
        return {"gap": 100.0 * (cost / self.cz_cost(instance)), "cost": cost}

    def diagnose(self, instance, priority):
        st = {"claims": 0, "flips": 0, "claim_pts": 0, "lost": 0}
        res = [play(g, priority, st) for g in instance["games"]]
        cost = self._cost(res)
        by = {}
        for g, r in zip(instance["games"], res):
            by.setdefault(g["opponent"], []).append(r)
        return {
            "gap": round(100.0 * (cost / self.cz_cost(instance)), 3),
            "cost": round(cost, 3),
            "win_pct": round(100.0 * sum(m > o for m, o in res) / len(res), 1),
            "worst_share": round(max(self._cost(v) for v in by.values()), 2),
            "flips_per_claim": round(st["flips"] / max(1, st["claims"]), 3),
            "lost_per_game": round(st["lost"] / len(res), 2),
            "claim_value": round(st["claim_pts"] / max(1, st["claims"]), 3),
        }


# ---------------------------------------------------------------------------------------------- cache
def build_cz():
    p = Duel()
    p._cz = {}
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in p.instances(split):
            res = [play(g, _zero) for g in inst["games"]]
            cost = Duel._cost(res)
            moves = [len(g["adj"]) - 2 for g in inst["games"]]
            out[f"{split}/{inst['id']}"] = {"fingerprint": inst["fingerprint"], "cost": cost}
            print(f"  {split:5s} {inst['id']:12s} Code Zero cost {cost:6.2f}  ({np.mean(moves):.0f} claims per game)")
    CZ_FILE.parent.mkdir(parents=True, exist_ok=True)
    CZ_FILE.write_text(json.dumps({"method": "Code Zero (first candidate of the shuffled list): 100 x opponents' share "
                                             "of points over the instance's games", "instances": out}, indent=0))
    print(f"wrote {CZ_FILE} ({len(out)} instances, {time.time() - t0:.1f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cz", action="store_true", help="rebuild suite/data/duel_cz.json")
    a = ap.parse_args(argv)
    if a.cz:
        build_cz()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
