"""A model of the landscape over design coordinates (docs/V9_DESIGN.md, docs/SEARCH_SPACE_MODEL.md section 4).

    height(x, effort) = mu + sum_i g_i(x_i) + sum_(i,j selected) g_ij(x_i, x_j) + beta * log(1 + effort) + noise

- x is a coordinate: one value per axis (or "?" when unknown). Each axis's values are one-hot features; their
  effects g_i share one prior variance per axis, learned from the data (empirical Bayes, by EM on the evidence), so an
  axis whose values matter gets loose effects and one that doesn't is shrunk to nothing. That is the effect-sparsity
  bet: a few main effects and a few interactions explain most of the variation.
- Pairwise interactions are screened from the main-effects residuals (an F-like ratio per pair of axes) and only the
  strongest few are modelled: interactions are what make several hills, but most pairs don't interact.
- Effort (how many experiments have been spent at, or next to, a design) is a covariate, so a young design is not
  compared with a mature one at face value. Climbs saturate, so effort enters through a few saturating features,
  exp(-effort / s) for s in EFFORT_SCALES, shared by all designs. Rankings of designs don't depend on it.
- An axis seen with fewer than two values (a decision nobody has varied: a frozen axis) has no data on how much its
  values matter, so its prior variance is the pooled one of the axes that have been varied, not shrunk to zero: the
  decisions every program shares are where the most is unknown (docs/SEARCH_SPACE.md), and the model must say so.
  Varied axes are pulled gently towards the pooled variance too (a hyperprior worth `pool_weight` levels).
- Values never observed keep the prior: mean zero, the axis's variance. Sampling a model from the posterior (Thompson
  sampling) therefore sometimes rates an untried value high: exploration of new values and new axes comes from the
  same loop as exploitation, with no extra rule. Unseen cells of a modelled pair get the pair's prior variance too.
- Rows can be weighted (each distinct design counts about once, so a lineage of a thousand polishes doesn't drown the
  rest).

Outputs: predictions with uncertainty, posterior samples, each axis's (and pair's) share of the explained variance
(a functional-ANOVA importance: "what is helping and what is hurting"), each value's effect, and standardised
residuals (where the coordinates fail to explain a score: the trigger for discovering a missing axis).

numpy only. The fit is a few small linear solves: milliseconds for thousands of rows.
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np

UNKNOWN = "?"
EFFORT_SCALES = (1.0, 4.0, 16.0, 64.0, 256.0)


class LandscapeModel:
    def __init__(self, levels, pairs_max=8, pair_f=4.0, pair_min_rows=2, effort=True, iters=60, pool_weight=2.0):
        """levels: {axis id: [value ids]} (the "?" level is added). Axes are modelled in this order."""
        self.axes = list(levels)
        self.levels = {a: list(dict.fromkeys(list(levels[a]) + [UNKNOWN])) for a in self.axes}
        self.pairs_max, self.pair_f, self.pair_min_rows = pairs_max, pair_f, pair_min_rows
        self.use_effort, self.iters, self.pool_weight = effort, iters, pool_weight
        self.ready = False
        self.pairs = []                    # [(a, b)]
        self.pair_cells = {}               # (a, b) -> [(va, vb)] modelled cells
        self.n = 0

    # ---------------------------------------------------------------- features
    def _layout(self):
        cols, groups = ["mu"], ["mu"]
        if self.use_effort:
            for k in range(len(EFFORT_SCALES)):
                cols.append(("effort", k))
                groups.append("effort")
        for a in self.axes:
            for v in self.levels[a]:
                cols.append((a, v))
                groups.append(a)
        for ab in self.pairs:
            for cell in self.pair_cells[ab]:
                cols.append((ab, cell))
                groups.append(ab)
        self.cols, self.groups = cols, groups
        self.index = {c: i for i, c in enumerate(cols)}
        self.group_names = list(dict.fromkeys(groups))
        self.group_idx = {g: np.array([i for i, x in enumerate(groups) if x == g]) for g in self.group_names}

    def _value(self, coord, a):
        v = (coord or {}).get(a) or UNKNOWN
        return v if v in self.levels[a] else UNKNOWN

    def features(self, coords, efforts=None):
        X = np.zeros((len(coords), len(self.cols)))
        X[:, 0] = 1.0
        for r, c in enumerate(coords):
            if self.use_effort:
                e = max(0.0, 0.0 if efforts is None else float(efforts[r] or 0.0))
                for k, sc in enumerate(EFFORT_SCALES):
                    X[r, 1 + k] = math.exp(-e / sc)
            vals = {a: self._value(c, a) for a in self.axes}
            for a in self.axes:
                X[r, self.index[(a, vals[a])]] = 1.0
            for ab in self.pairs:
                j = self.index.get((ab, (vals[ab[0]], vals[ab[1]])))
                if j is not None:
                    X[r, j] = 1.0
        return X

    # ---------------------------------------------------------------- fitting
    def fit(self, rows, min_rows=5):
        """rows: [{"coord": {axis: value}, "y": float, "effort": float, "w": weight}]. Returns self."""
        rows = [r for r in rows if r.get("y") is not None and np.isfinite(r["y"])]
        self.n = len(rows)
        if self.n < min_rows:
            self.ready = False
            return self
        y = np.array([float(r["y"]) for r in rows])
        w = np.array([float(r.get("w", 1.0)) for r in rows])
        w = w * (len(w) / w.sum())
        self.y_mean = float(np.average(y, weights=w))
        self.y_sd = float(math.sqrt(np.average((y - self.y_mean) ** 2, weights=w))) or 1.0
        ys = (y - self.y_mean) / self.y_sd
        coords = [r.get("coord") or {} for r in rows]
        efforts = [r.get("effort") for r in rows]
        self.pairs, self.pair_cells = [], {}
        self.varied = {}
        for a in self.axes:
            seen = {self._value(c, a) for c in coords} - {UNKNOWN}
            self.varied[a] = len(seen) >= 2
        self._layout()
        X = self.features(coords, efforts)
        self._em(X, ys, w)
        if self.pairs_max > 0 and len(self.axes) >= 2:
            self._screen_pairs(coords, X, ys, w)
            if self.pairs:
                self._layout()
                X = self.features(coords, efforts)
                self._em(X, ys, w)
        self.X, self.ys, self.w, self.coords, self.efforts = X, ys, w, coords, efforts
        ef = sorted(float(e or 0.0) for e in efforts)
        self.effort_ref = ef[len(ef) // 2] if ef else 1.0
        self.observed = {a: {} for a in self.axes}
        for c in coords:
            for a in self.axes:
                v = self._value(c, a)
                self.observed[a][v] = self.observed[a].get(v, 0) + 1
        self.ready = True
        return self

    def _em(self, X, ys, w):
        n, p = X.shape
        sw = np.sqrt(w)
        Xw, yw = X * sw[:, None], ys * sw
        tau = {g: (100.0 if g == "mu" else 10.0 if g == "effort" else 0.3) for g in self.group_names}
        sigma2 = 0.5
        XtX, Xty = Xw.T @ Xw, Xw.T @ yw
        for _ in range(self.iters):
            prec = np.zeros(p)
            for g, idx in self.group_idx.items():
                prec[idx] = 1.0 / tau[g]
            A = XtX / sigma2 + np.diag(prec)
            S = np.linalg.inv(A)
            S = 0.5 * (S + S.T)
            m = S @ Xty / sigma2
            old = dict(tau)
            raw = {}
            for g, idx in self.group_idx.items():
                if g in ("mu", "effort"):
                    continue
                raw[g] = (float(np.sum(m[idx] ** 2) + np.trace(S[np.ix_(idx, idx)])), len(idx))
            varied = [raw[g][0] / raw[g][1] for g in raw if isinstance(g, str) and self.varied.get(g)]
            pooled = float(np.median(varied)) if varied else 0.3
            for g, (ss, k) in raw.items():
                if isinstance(g, str) and not self.varied.get(g):
                    tau[g] = float(np.clip(pooled, 1e-4, 25.0))        # a frozen axis: no data, the pooled prior
                else:
                    nu = self.pool_weight
                    tau[g] = float(np.clip((ss + nu * pooled) / (k + nu), 1e-6, 25.0))
            resid = yw - Xw @ m
            sigma2 = float(np.clip((resid @ resid + np.sum((Xw @ S) * Xw)) / max(w.sum(), 1.0), 1e-6, 25.0))
            if max(abs(math.log(tau[g] / old[g])) for g in tau) < 1e-4:
                break
        self.m, self.S, self.tau, self.sigma2 = m, S, tau, sigma2
        try:
            self.L = np.linalg.cholesky(S + 1e-12 * np.eye(p))
        except np.linalg.LinAlgError:
            vals, vecs = np.linalg.eigh(S)
            self.L = vecs @ np.diag(np.sqrt(np.clip(vals, 0, None)))

    def _screen_pairs(self, coords, X, ys, w):
        """Pairs of axes whose cells' mean residuals vary more than noise explains (an F-like ratio)."""
        resid = ys - X @ self.m
        scores = []
        for a, b in combinations(self.axes, 2):
            cells = {}
            for r, c in enumerate(coords):
                k = (self._value(c, a), self._value(c, b))
                if UNKNOWN in k:
                    continue
                cells.setdefault(k, []).append(r)
            use = {k: v for k, v in cells.items() if len(v) >= self.pair_min_rows}
            if len(use) < 3:
                continue
            ss, df = 0.0, 0
            for k, idx in use.items():
                ww = w[idx]
                mu = float(np.average(resid[idx], weights=ww))
                ss += ww.sum() * mu * mu
                df += 1
            f = ss / max(df, 1) / self.sigma2
            if f >= self.pair_f:
                scores.append((f, (a, b), sorted(use)))
        scores.sort(key=lambda x: -x[0])
        for f, ab, cells in scores[: self.pairs_max]:
            self.pairs.append(ab)
            self.pair_cells[ab] = cells
        self.pair_scores = {ab: round(f, 2) for f, ab, _ in scores[: self.pairs_max]}

    # ---------------------------------------------------------------- using it
    def _unseen_pair_count(self, coords):
        """How many modelled pairs each coordinate hits in a cell that has no feature (prior-only interaction)."""
        out = []
        for c in coords:
            k = []
            for ab in self.pairs:
                va, vb = self._value(c, ab[0]), self._value(c, ab[1])
                if (ab, (va, vb)) not in self.index and UNKNOWN not in (va, vb):
                    k.append(ab)
            out.append(k)
        return out

    def predict(self, coords, effort=None):
        """(mean, sd) on the original scale, for coordinates at a common effort (default: the rows' median effort,
        where the effort terms are well determined)."""
        if not self.ready:
            raise RuntimeError("the model is not fitted")
        effort = self.effort_ref if effort is None else effort
        X = self.features(coords, [effort] * len(coords))
        mean = X @ self.m
        var = np.sum((X @ self.S) * X, axis=1)
        for r, ks in enumerate(self._unseen_pair_count(coords)):
            var[r] += sum(self.tau[ab] for ab in ks)
        return mean * self.y_sd + self.y_mean, np.sqrt(np.maximum(var, 0)) * self.y_sd

    def sample(self, rng):
        """One model drawn from the posterior: a function coords -> predicted heights (original scale)."""
        z = rng.standard_normal(self.L.shape[0])
        wv = self.m + self.L @ z
        extra = {}

        def f(coords, effort=None):
            X = self.features(coords, [self.effort_ref if effort is None else effort] * len(coords))
            out = X @ wv
            for r, ks in enumerate(self._unseen_pair_count(coords)):
                for ab in ks:
                    key = (ab, (self._value(coords[r], ab[0]), self._value(coords[r], ab[1])))
                    if key not in extra:
                        extra[key] = rng.standard_normal() * math.sqrt(self.tau[ab])
                    out[r] += extra[key]
            return out * self.y_sd + self.y_mean
        return f

    def effects(self, a):
        """{value: (effect, sd, rows)} for one axis, on the original scale (centred on the observed values)."""
        idx = [self.index[(a, v)] for v in self.levels[a]]
        obs = [v for v in self.levels[a] if self.observed[a].get(v)]
        centre = float(np.mean([self.m[self.index[(a, v)]] for v in obs])) if obs else 0.0
        out = {}
        for v, i in zip(self.levels[a], idx):
            out[v] = ((float(self.m[i]) - centre) * self.y_sd, math.sqrt(max(self.S[i, i], 0.0)) * self.y_sd,
                      self.observed[a].get(v, 0))
        return out

    def importance(self):
        """Each axis's and modelled pair's share of the variance its fitted effects explain over the programs
        (functional ANOVA on the fitted model, weighted by how many programs make each choice), and the effort term's.
        A decision read on only a few programs explains little of the whole, however far apart those few scored."""
        var = {}
        n_all = max(self.n, 1)
        for a in self.axes:
            obs = [v for v in self.levels[a] if self.observed[a].get(v) and v != UNKNOWN]
            if len(obs) >= 2:
                e = np.array([self.m[self.index[(a, v)]] for v in obs])
                w = np.array([self.observed[a][v] for v in obs], dtype=float)
                mean = float((w * e).sum() / w.sum())
                var[a] = float((w * (e - mean) ** 2).sum() / n_all)      # programs with the decision unread add 0
            else:
                var[a] = 0.0
        for ab in self.pairs:
            e = np.array([self.m[self.index[(ab, c)]] for c in self.pair_cells[ab]])
            var[ab] = float(e.var()) if len(e) >= 2 else 0.0
        if self.use_effort:
            idx = self.group_idx["effort"]
            ef = np.array([[math.exp(-e / sc) for sc in EFFORT_SCALES] for e in (self.efforts or [])
                           if e is not None]) if self.efforts else np.zeros((0, len(idx)))
            var["effort"] = float((ef @ self.m[idx]).var()) if len(ef) > 1 else 0.0
        tot = sum(var.values()) or 1.0
        return {k: v / tot for k, v in sorted(var.items(), key=lambda x: -x[1])}

    def residuals(self):
        """Standardised residuals of the fitted rows: (row index, residual / noise sd)."""
        r = (self.ys - self.X @ self.m) / math.sqrt(self.sigma2)
        return list(enumerate(r.tolist()))

    def noise_sd(self):
        return math.sqrt(self.sigma2) * self.y_sd

    def summary(self):
        return {"rows": self.n, "axes": len(self.axes), "pairs": [list(p) for p in self.pairs],
                "noise_sd": round(self.noise_sd(), 8) if self.ready else None,
                "importance": {str(k): round(v, 4) for k, v in self.importance().items()} if self.ready else {}}
