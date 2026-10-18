"""Stacker (open suite): an invented falling-piece puzzle ("bloom"), scored in points over a fixed number of pieces.

Pieces of 3-5 cells, each one colour, drop into a well. After a piece lands, every full row AND every 2 x 2 square
of four cells of one colour is removed; cells above a removed cell fall by the number of removed cells below them in
their column (gaps under overhangs stay gaps), which can set off further rounds. A round that removes n cells scores
round x n^2 / 4; every piece placed scores 1. Some families push a garbage row up from the bottom every few pieces.
The game ends after a fixed number of pieces, or when a piece has nowhere to fit, or when garbage pushes a cell out.

Open ceiling (docs/OPEN_SUITE.md), maximised: an instance is a few seeded games; score = total points;
gap = 100 * Code Zero's score / score (Code Zero = 100 exactly, a score twice Code Zero's is 50). Code Zero's scores
are cached in suite/data/stacker_cz.json (rebuild: `python -m suite.stacker --cz`); an instance missing from the
cache (or whose fingerprint changed) is computed on the spot.
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
CZ_FILE = ROOT / "suite" / "data" / "stacker_cz.json"
SPLIT_SEED = {"train": 8111, "valid": 8222, "test": 8333}
SPLIT_BASE = {"train": 0, "valid": 100, "test": 200}
PER_FAMILY = 3
GAMES = 4
PIECES = 60
GREY = 9

# the shape catalogue (rotation 0, '#' = cell); ids are global, each family draws from a subset
SHAPES = [
    "###",                 # 0  bar3
    "#.|##",               # 1  hook3
    "###|.#.",             # 2  tee4
    ".##|##.",             # 3  step4
    "##.|.##",             # 4  step4 mirrored
    "###|#..",             # 5  bend4
    "###|..#",             # 6  bend4 mirrored
    "####",                # 7  bar4
    "#.#|###",             # 8  cup5
    "###|.#.|.#.",         # 9  tee5
    "#..|#..|###",         # 10 vee5
    "#..|##.|.##",         # 11 stair5
    "##.|.#.|.##",         # 12 zed5
    ".#.|###|.#.",         # 13 plus5
    "####|#...",           # 14 hook5
    "##..|.###",           # 15 snake5
    "####|.#..",           # 16 fork5
    "#.#|.#.",             # 17 chevron3 (corner-touching cells)
]
# family: piece set, width, height, colours, garbage every (0 = never)
FAMILIES = {
    "trio": {"code": 1, "set": [0, 1, 2, 3, 4, 5, 6, 7], "W": 10, "H": 16, "colours": 3, "garbage": 0},
    "penta": {"code": 2, "set": [3, 7, 8, 9, 10, 11, 12, 13, 14], "W": 9, "H": 18, "colours": 3, "garbage": 0},
    "rising": {"code": 3, "set": [0, 1, 2, 3, 4, 5, 6, 7], "W": 9, "H": 16, "colours": 3, "garbage": 6},
    "prism": {"code": 4, "set": [0, 1, 2, 8, 13, 15, 16, 17], "W": 8, "H": 15, "colours": 4, "garbage": 9},
}
TRAIN_FAMILIES = ["trio", "penta", "rising"]
HELD_OUT = ["prism"]


# ---------------------------------------------------------------------------------------------- pieces
def _grid(spec):
    rows = spec.split("|")
    return np.array([[ch == "#" for ch in r] for r in rows], dtype=bool)


def _rotations(spec):
    """Distinct clockwise rotations: list of (dy (n,), dx (n,), width, bottom profile (width,))."""
    g, out, seen = _grid(spec), [], set()
    for _ in range(4):
        key = (g.shape, g.tobytes())
        if key not in seen:
            seen.add(key)
            dy, dx = np.nonzero(g)
            bot = np.array([dy[dx == j].max() for j in range(g.shape[1])])
            out.append((dy.astype(np.int64), dx.astype(np.int64), g.shape[1], bot))
        g = np.rot90(g, -1)
    return out


ROT = [_rotations(s) for s in SHAPES]


def _piece_grid(sid, colour):
    out = np.zeros((5, 5), dtype=np.int8)
    if sid >= 0:
        g = _grid(SHAPES[sid])
        out[: g.shape[0], : g.shape[1]][g] = colour
    return out


PIECE_GRIDS = {}


def piece_grid(sid, colour):
    key = (sid, colour)
    if key not in PIECE_GRIDS:
        PIECE_GRIDS[key] = _piece_grid(sid, colour)
    return PIECE_GRIDS[key]


# ---------------------------------------------------------------------------------------------- rules
_TABLES = {}


def _table(sid, W):
    """Every (rotation, column) of shape `sid` in a well W wide: rot, col, column index (P, w), bottom profile
    (P, w) (padded columns repeat column 0 with a huge bottom so they never bind), cell offsets dy (P, n), cols (P, n)."""
    key = (sid, W)
    t = _TABLES.get(key)
    if t is None:
        rot, col, CI, BOT, DY, DX = [], [], [], [], [], []
        wmax = max(w for _, _, w, _ in ROT[sid])
        for r, (dy, dx, w, bot) in enumerate(ROT[sid]):
            for c in range(W - w + 1):
                rot.append(r)
                col.append(c)
                CI.append(list(range(c, c + w)) + [c] * (wmax - w))
                BOT.append(list(bot) + [-10 ** 6] * (wmax - w))
                DY.append(dy)
                DX.append(c + dx)
        t = _TABLES[key] = (np.array(rot), np.array(col), np.array(CI), np.array(BOT), np.array(DY), np.array(DX))
    return t


def placements(board, sid):
    """All legal placements of shape `sid`: (rot (k,), col (k,), top row (k,), cell rows (k, n), cell cols (k, n))."""
    H, W = board.shape
    filled = board > 0
    top = np.where(filled.any(0), filled.argmax(0), H)
    rot, col, CI, BOT, DY, DX = _table(sid, W)
    y = (top[CI] - 1 - BOT).min(1)
    ok = np.flatnonzero(y >= 0)
    if len(ok) == 0:
        return None
    y = y[ok]
    return rot[ok], col[ok], y, y[:, None] + DY[ok], DX[ok]


def _marks(b):
    """Full rows (a, h), single-colour 2 x 2 squares (a, h-1, W-1) and the cells they remove (a, h, W)."""
    W = b.shape[2]
    full = (b > 0).all(2)
    a00 = b[:, :-1, :-1]
    mono = (a00 > 0) & (a00 != GREY) & (a00 == b[:, 1:, :-1]) & (a00 == b[:, :-1, 1:]) & (a00 == b[:, 1:, 1:])
    rem = np.repeat(full[:, :, None], W, axis=2)
    rem[:, :-1, :-1] |= mono
    rem[:, 1:, :-1] |= mono
    rem[:, :-1, 1:] |= mono
    rem[:, 1:, 1:] |= mono
    return full, mono, rem


def resolve(B, lo=0, hi=None):
    """Resolve boards B (k, H, W) in place. Returns (points (k,), rows (k,), squares (k,), extra rounds (k,)).

    Before the landing the board had nothing to remove, so the first round only looks at rows lo..hi-1 (the rows
    the pieces landed in, one more on each side)."""
    k, H, W = B.shape
    hi = H if hi is None else hi
    pts = np.zeros(k)
    rows = np.zeros(k, dtype=np.int64)
    sq = np.zeros(k, dtype=np.int64)
    casc = np.zeros(k, dtype=np.int64)
    idx = np.arange(k)
    hidx = np.arange(H)[None, :, None]
    rnd = 1
    while len(idx):
        full, mono, rem = _marks(B[:, lo:hi] if rnd == 1 else B[idx])
        n = rem.sum((1, 2))
        hit = n > 0
        if not hit.any():
            break
        idx, rem, n = idx[hit], rem[hit], n[hit]
        pts[idx] += rnd * n * n / 4.0
        rows[idx] += full[hit].sum(1)
        sq[idx] += mono[hit].sum((1, 2))
        if rnd > 1:
            casc[idx] += 1
        elif lo > 0 or hi < H:
            r = np.zeros((len(idx), H, W), dtype=bool)
            r[:, lo:hi] = rem
            rem = r
        order = np.argsort(~rem, axis=1, kind="stable")                 # removed cells to the top, the rest keep order
        b = np.take_along_axis(B[idx], order, axis=1)
        b[hidx < rem.sum(1)[:, None, :]] = 0
        B[idx] = b
        rnd += 1
    return pts, rows, sq, casc


def play(game, fam, priority, stats=None):
    """One game; returns its points. priority None = Code Zero (the first shuffled candidate)."""
    H, W, colours, every = fam["H"], fam["W"], fam["colours"], fam["garbage"]
    shapes, cols_, gap_cols = game["shapes"], game["colours"], game["gaps"]
    n = len(shapes)
    board = np.zeros((H, W), dtype=np.int8)
    shuffle = np.random.default_rng(game["seed"] + [1])
    score, placed, topout = 0.0, 0, False
    for t in range(n):
        sid, col = int(shapes[t]), int(cols_[t])
        pl = placements(board, sid)
        if pl is None:
            topout = True
            break
        rot, cc, yy, R, C = pl
        k = len(rot)
        perm = shuffle.permutation(k)
        rot, cc, yy, R, C = rot[perm], cc[perm], yy[perm], R[perm], C[perm]
        B = np.repeat(board[None], k, axis=0)
        B[np.arange(k)[:, None], R, C] = col
        pts, rows, sq, casc = resolve(B, max(0, int(R.min()) - 1), min(H, int(R.max()) + 2))
        gains = pts + 1.0
        if priority is None or k == 1:
            i = 0
        else:
            nxt = (int(shapes[t + 1]), int(cols_[t + 1])) if t + 1 < n else (-1, 0)
            pieces = np.stack([piece_grid(sid, col), piece_grid(*nxt)])
            ids = np.array([[sid, col], [nxt[0], nxt[1] if nxt[0] >= 0 else 0]], dtype=np.int64)
            gin = (every - (t % every)) if every else 0
            s = np.asarray(priority(np.stack([rot, cc, yy], 1), B, gains, board.copy(), pieces, ids, float(score),
                                    n - t, gin, colours), dtype=float)
            if s.shape != (k,):
                raise ValueError(f"priority returned shape {s.shape} for {k} candidates; expected ({k},)")
            i = int(np.argmax(np.round(s, 9)))
        board = B[i]
        score += float(gains[i])
        placed += 1
        if stats is not None:
            stats["rows"] += int(rows[i])
            stats["squares"] += int(sq[i])
            stats["cascades"] += int(casc[i])
        if every and (t + 1) % every == 0:                                # a garbage row rises
            if board[0].any():
                topout = True
                break
            g = np.full(W, GREY, dtype=np.int8)
            g[int(gap_cols[t])] = 0
            board = np.concatenate([board[1:], g[None]])
    if stats is not None:
        stats["pieces"] += placed
        stats["topouts"] += int(topout)
    return score


# ---------------------------------------------------------------------------------------------- instances
def raw_instances(split):
    if split not in SPLIT_SEED:
        raise KeyError(split)
    out = []
    for name in TRAIN_FAMILIES + (HELD_OUT if split == "test" else []):
        fam = FAMILIES[name]
        for i in range(PER_FAMILY):
            games = []
            for g in range(GAMES):
                seed = [SPLIT_SEED[split], fam["code"], i, g]
                rng = np.random.default_rng(seed)
                games.append({"shapes": rng.choice(fam["set"], PIECES).astype(np.int64),
                              "colours": rng.integers(1, fam["colours"] + 1, PIECES).astype(np.int64),
                              "gaps": rng.integers(0, fam["W"], PIECES).astype(np.int64), "seed": seed})
            h = hashlib.sha1(json.dumps([SHAPES, {k: v for k, v in fam.items()}]).encode())
            for gm in games:
                h.update(gm["shapes"].tobytes() + gm["colours"].tobytes() + gm["gaps"].tobytes())
                h.update(json.dumps(gm["seed"]).encode())
            out.append({"id": f"{name}-{SPLIT_BASE[split] + i:03d}", "family": name, "split": split,
                        "games": games, "fingerprint": h.hexdigest()[:12]})
    return out


# ---------------------------------------------------------------------------------------------- the problem
class Stacker(Problem):
    name = "stacker"
    title = "Stacker: an invented falling-piece puzzle, points over a fixed number of pieces"
    families = TRAIN_FAMILIES
    held_out_families = HELD_OUT
    open_ceiling = True
    baseline = []
    signature = "feature(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours)"
    candidates_arg = 0
    description = f"""Play an invented falling-piece puzzle, "bloom". The policy chooses where each piece lands.

**The well.** A grid W columns wide and H rows tall (row 0 is the top, row H - 1 the bottom). Each cell is empty (0), holds a coloured cell (colour 1 .. `colours`), or holds grey garbage ({GREY}).

**Pieces.** Each piece is a shape of 3 to 5 cells, all of one colour. Shape and colour are drawn uniformly at random from the family's shape set and colours, independently for every piece. You see the current piece and the next one. Shapes never contain a 2 x 2 block of their own cells; a few shapes have cells that touch only at a corner.

**A placement** = a rotation (0 to 3 quarter turns clockwise; rotations that give the same shape are listed once) and a column for the rotated piece's leftmost cell (the piece must lie within the well's width). The piece falls straight down from above the well and stops as soon as moving one row further down would overlap a filled cell or pass the floor (it cannot slide under an overhang). A placement is legal if every cell of the landed piece lies inside the well.

**Clearing.** After a piece lands, the board resolves in rounds. In each round, every cell that is in a full row (all W cells filled, any colours, garbage included) and every cell that is part of any 2 x 2 square of four cells of the same colour (garbage never counts as a colour) is removed, all at once. Then, in every column, everything above a removed cell moves down by the number of cells removed below it in that column (empty cells move too, so a gap under an overhang stays a gap). If that creates new full rows or single-colour 2 x 2 squares, another round follows, and so on until a round removes nothing.

**Points.** Every piece placed scores 1. A round that removes n cells scores round x n x n / 4, where round is 1 for the first round after a landing, 2 for the next, and so on.

**Garbage.** In some families, after every K-th piece has landed and resolved, the whole contents of the well move up one row and a new bottom row of grey garbage appears, filled except for one random column. If a filled cell is pushed above the top, the game ends.

**The end.** A game ends after {PIECES} pieces, or as soon as the current piece has no legal placement (that piece scores nothing), or when garbage pushes a cell out of the top. Points scored so far count.

**One decision** = choosing the placement of the current piece. The **candidates** are all legal placements, in a random order (reshuffled at every decision). With one legal placement it is taken automatically.

**Instances and score.** An instance is {GAMES} games of one family with seeded piece sequences; its **score** is the total points of its games (higher is better). The **gap** is 100 x (Code Zero's score) / score, where Code Zero is the policy that always takes the first candidate (a random legal placement) on the same instance: Code Zero is 100, a score twice Code Zero's is 50, and lower is better; there is no known best.

Three training families: `trio` (10 wide, 16 tall, 8 shapes of 3-4 cells, 3 colours, no garbage), `penta` (9 wide, 18 tall, 9 shapes of 4-5 cells, 3 colours, no garbage) and `rising` (9 wide, 16 tall, the 3-4 cell shapes, 3 colours, a garbage row after every 6th piece). The test split adds a family that training never shows (other shapes, size, colours or garbage interval)."""
    signature_doc = f"""- `placements`: shape (k, 3), int: for each candidate [rotation (quarter turns clockwise), leftmost column, top row of the landed piece's bounding box], in random order.
- `boards`: shape (k, H, W), int8: the board after each candidate placement has landed and fully resolved (clears, falls, further rounds); before any garbage row rises. Cell codes: 0 empty, 1 .. `colours` a colour, {GREY} garbage. Row 0 is the top.
- `gains`: shape (k,), float: points each candidate scores (1 for the piece plus the clearing points of its rounds).
- `board`: shape (H, W), int8: the board now, before the current piece lands.
- `pieces`: shape (2, 5, 5), int8: the current piece and the next piece in rotation 0, drawn in the top-left corner of a 5 x 5 grid with their colour codes (0 elsewhere). The next piece is all zeros on the game's last piece.
- `ids`: shape (2, 2), int: [shape id, colour] of the current and the next piece (shape ids are the same in every family; [-1, 0] when there is no next piece).
- `score`: float: points scored so far in this game.
- `pieces_left`: int: pieces still to come in this game, including the current one (a game has at most {PIECES}).
- `garbage_in`: int: 0 if this game has no garbage; otherwise how many more pieces land (the current one included) before the next garbage row rises (1 = right after this piece resolves).
- `colours`: int: the number of colours in this game.
- Return one finite number per candidate (shape (k,)), or a few columns (shape (k, c)). The highest-scoring candidate is played."""
    metric_notes = {
        "score": "total points of the instance's games (what the gap measures, higher is better)",
        "pieces_per_game": f"pieces placed per game (at most {PIECES}; fewer means the game ended early)",
        "rows_per_game": "full rows removed per game",
        "squares_per_game": "single-colour 2 x 2 squares removed per game (overlapping squares count separately)",
        "cascades_per_game": "resolution rounds after the first (rounds set off by falling cells) per game",
        "topout_pct": "% of games that ended early (no legal placement, or garbage pushed a cell out)",
    }
    example_features = [
        "import numpy as np\n\ndef feature(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):\n"
        "    \"\"\"Points of the placement.\"\"\"\n"
        "    return gains.astype(float)\n",
        "import numpy as np\n\ndef feature(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):\n"
        "    \"\"\"Minus the number of filled cells after the placement.\"\"\"\n"
        "    return -(boards > 0).sum(axis=(1, 2)).astype(float)\n",
        "import numpy as np\n\ndef feature(placements, boards, gains, board, pieces, ids, score, pieces_left, garbage_in, colours):\n"
        "    \"\"\"Two columns: the landing row and the rotation.\"\"\"\n"
        "    return placements[:, [2, 0]].astype(float)\n",
    ]

    def __init__(self):
        self._cache = {}
        self._cz = None

    def instances(self, split):
        if split not in self._cache:
            self._cache[split] = raw_instances(split)
        return self._cache[split]

    def n_candidates(self, args):
        return len(args[0])

    @staticmethod
    def _score(inst, priority, stats=None):
        fam = FAMILIES[inst["family"]]
        return sum(play(g, fam, priority, stats) for g in inst["games"])

    def cz_score(self, inst):
        if self._cz is None:
            try:
                self._cz = json.loads(CZ_FILE.read_text())["instances"]
            except (OSError, ValueError, KeyError):
                self._cz = {}
        key = f"{inst['split']}/{inst['id']}"
        r = self._cz.get(key)
        if r is None or r.get("fingerprint") != inst["fingerprint"]:
            r = {"fingerprint": inst["fingerprint"], "score": self._score(inst, None)}
            self._cz[key] = r
        return r["score"]

    @staticmethod
    def _gap(score, cz):
        return 100.0 * (cz / max(score, 0.01 * cz))

    def run(self, instance, priority):
        s = self._score(instance, priority)
        return {"gap": self._gap(s, self.cz_score(instance)), "score": s}

    def diagnose(self, instance, priority):
        st = {"rows": 0, "squares": 0, "cascades": 0, "pieces": 0, "topouts": 0}
        s = self._score(instance, priority, st)
        g = len(instance["games"])
        return {
            "gap": round(self._gap(s, self.cz_score(instance)), 3),
            "score": round(s, 2),
            "pieces_per_game": round(st["pieces"] / g, 2),
            "rows_per_game": round(st["rows"] / g, 2),
            "squares_per_game": round(st["squares"] / g, 2),
            "cascades_per_game": round(st["cascades"] / g, 2),
            "topout_pct": round(100.0 * st["topouts"] / g, 1),
        }


# ---------------------------------------------------------------------------------------------- cache
def build_cz():
    p = Stacker()
    out = {}
    t0 = time.time()
    for split in SPLIT_SEED:
        for inst in p.instances(split):
            st = {"rows": 0, "squares": 0, "cascades": 0, "pieces": 0, "topouts": 0}
            s = Stacker._score(inst, None, st)
            out[f"{split}/{inst['id']}"] = {"fingerprint": inst["fingerprint"], "score": s}
            print(f"  {split:5s} {inst['id']:12s} Code Zero score {s:7.2f}  ({st['pieces'] / GAMES:.0f} pieces per game)")
    CZ_FILE.parent.mkdir(parents=True, exist_ok=True)
    CZ_FILE.write_text(json.dumps({"method": "Code Zero (first candidate of the shuffled list): total points over "
                                             "the instance's games", "instances": out}, indent=0))
    print(f"wrote {CZ_FILE} ({len(out)} instances, {time.time() - t0:.1f}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cz", action="store_true", help="rebuild suite/data/stacker_cz.json")
    a = ap.parse_args(argv)
    if a.cz:
        build_cz()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
