"""The Scout: a web and paper search at the start of every generation (Shreyas, November 11, 2026), off by default.

Each generation the Scout reads where the run stands (the best program and its feedback, what the last generation tried
and what came of it, the Atlas's findings, the guidance's records) and its own search log (every query it has asked and
every page it has shown), and writes two sets of queries:
- deep, for the planner: about what is being worked on now: a problem the run is stuck on and how to get out of it,
  or how to implement an idea it is pursuing (code included);
- wide, one per mutator: approaches that are neither in the guidance nor tried in the Atlas, for diversity.
Web and code queries go to Exa (highlights: the passages of each page that answer the query's purpose); paper queries to
OpenAlex (semantic search, with abstracts). A page already shown is never shown again; a query already asked is not
asked again. Each result becomes an item W<generation>.<k>. The planner sees the deep items, each mutator its wide
items; an experiment or a mutation that draws on items cites them ("web": ["W6.2"], or a WEB: line), its coder gets
them in full, and each cited item's record (gained, no gain, failed) is computed from the archive, as for guidance, and
shown in later generations. Every search's cost (as the services report it) is logged in scout.jsonl, with the queries
and results, so a resumed run continues the log.

Keys: EXA_API_KEY and OPENALEX_API_KEY in the environment or the repo's .env.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lean.archive import short
from lean.llm import load_dotenv, _ssl_context
from lean.stores import outcome
from lean import prompts as P

SYSTEM = (
    "You are the research scout of an evolutionary search for better programs. Each generation you decide what to look "
    "up on the web, in code, and in the research literature, so that the people designing the next programs have "
    "material they don't already have. You ask precise, technical queries about the problem as it stands now, not "
    "about the topic in general: name the exact obstacle, constraint or technique. You never repeat a query that was "
    "already asked, and you look for what the run has not seen yet.")

ASK = """## Your task: the searches for generation {gen}

Write two sets of queries.

**deep** ({n_deep} queries), for the planner, about what this run is working on now:
- where it is stuck: a failure that keeps recurring, a change that keeps not helping, a plateau. Ask how others get out
  of exactly that ("how do <methods> escape <this situation> when <this constraint>");
- how to implement, well and fast, an idea the run is pursuing or about to pursue (prefer code and implementation
  details for these);
- facts the run needs to decide between two directions.

**wide** ({n_wide} queries, one per mutator), for diversity: approaches to this problem that are neither in the guidance
store nor tried in the Atlas, each different from the others.

For each query give:
- "query": what to search for, in natural language, specific to this problem as it stands (not a keyword list);
- "kind", which decides where it is searched and what comes back:
  - "web": the whole web, papers' full texts and technical reports included; returns the passages of each page that
    answer the purpose. Use it for how a method works, how to get out of a difficulty, and implementation details;
  - "code": repositories, gists and Q&A; returns the relevant part of a README or source file. Use it to see how
    others implement something;
  - "paper": a research index (titles and abstracts only, no method details). Use it to find which work exists on a
    question; at most one query of this kind in all (deep and wide together): "web" also finds papers, with their
    method details;
- "purpose": the one thing a result must contain to be useful (used to pick the relevant passage of each page).

Rules: never repeat or rephrase a query in the search log below; aim at what the run has not seen; at least one deep
query must be about a concrete difficulty the run has now (from the latest results), not a general topic.

Reply with one JSON object and nothing else:
```json
{{"diagnosis": "where the run stands and what it needs, in 2-4 sentences",
 "deep": [{{"query": "...", "kind": "web", "purpose": "..."}}],
 "wide": [{{"query": "...", "kind": "paper", "purpose": "..."}}]}}
```"""

FIELD = '"web": ["<ids of web items it draws on, if any>"],\n    '
MUTATOR_LINE = "\nIf your change draws on web items, add one more line:\nWEB: <their ids, e.g. W6.2>"
INTRO = ("## From the web and the literature, found for this generation\n"
         "Material the scout found this generation (W items: web pages, code, and paper abstracts). It may or may not "
         "help: use what is relevant and say which items an experiment draws on; ignore the rest.\n\n")
MUT_INTRO = ("## From the web, for ideas: a direction found for you this generation\n"
             "Not a program to copy: material on an approach that may help. Use it if it gives you a good change.\n\n")
TRIED = "## Web items tried in earlier generations, and how they did\n"
CITED = "## From the web (the items this experiment draws on)\n"


def ids(value):
    if isinstance(value, str):
        value = re.findall(r"W\d+\.\d+", value)
    return [str(x).strip() for x in (value or []) if re.fullmatch(r"W\d+\.\d+", str(x).strip())]


class Searcher:
    """Exa (web, code) and OpenAlex (papers), with retries, a polite pace, and each call's reported cost."""

    def __init__(self):
        load_dotenv()
        self.exa = os.environ.get("EXA_API_KEY", "")
        self.openalex = os.environ.get("OPENALEX_API_KEY", "")
        if not self.exa or not self.openalex:
            raise RuntimeError("the scout needs EXA_API_KEY and OPENALEX_API_KEY (in .env)")
        self.ctx = _ssl_context()
        self.last = {"exa": 0.0, "openalex": 0.0}

    def _get(self, svc, req, pace):
        wait = self.last[svc] + pace - time.time()
        if wait > 0:
            time.sleep(wait)
        for attempt in range(5):
            self.last[svc] = time.time()
            try:
                with urllib.request.urlopen(req, timeout=90, context=self.ctx) as r:
                    return json.loads(r.read()), dict(r.headers)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(float(e.headers.get("Retry-After") or 2 ** (attempt + 1)))
                    continue
                raise RuntimeError(f"{svc} HTTP {e.code}: {e.read()[:200]!r}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < 4:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError(f"{svc}: {e}") from None

    def web(self, query, purpose, code=False, n=4):
        """Exa search (auto) with query-guided highlights; code: limited to code hosts."""
        body = {"query": query, "type": "auto", "numResults": n,
                "contents": {"highlights": {"query": purpose or query, "maxCharacters": 1800}}}
        if code:
            body["includeDomains"] = ["github.com", "gist.github.com", "stackoverflow.com", "gitlab.com"]
        req = urllib.request.Request("https://api.exa.ai/search", data=json.dumps(body).encode(),
                                     headers={"x-api-key": self.exa, "Content-Type": "application/json"})
        d, _ = self._get("exa", req, 0.25)                     # 10 requests a second is Exa's limit
        out = []
        for r in d.get("results") or []:
            text = "\n...\n".join(h.strip() for h in (r.get("highlights") or []) if h.strip())
            out.append({"title": r.get("title") or "", "url": r.get("url") or "", "date": (r.get("publishedDate") or "")[:10],
                        "text": text})
        return out, float((d.get("costDollars") or {}).get("total") or 0.0)

    def papers(self, query, n=4):
        """OpenAlex semantic search over titles and abstracts; each with its abstract."""
        q = urllib.parse.urlencode({"search.semantic": query[:2000], "per_page": n, "api_key": self.openalex,
                                    "select": "id,display_name,publication_year,cited_by_count,doi,"
                                              "primary_location,abstract_inverted_index"})
        req = urllib.request.Request(f"https://api.openalex.org/works?{q}")
        d, h = self._get("openalex", req, 1.05)                 # semantic search: 1 request a second
        out = []
        for w in d.get("results") or []:
            inv = w.get("abstract_inverted_index") or {}
            pos = sorted((i, word) for word, idx in inv.items() for i in idx)
            venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
            out.append({"title": w.get("display_name") or "", "url": w.get("doi") or w.get("id") or "",
                        "date": str(w.get("publication_year") or ""), "venue": venue,
                        "cited": w.get("cited_by_count"), "text": " ".join(word for _, word in pos)})
        cost = float(h.get("X-RateLimit-Cost-USD") or h.get("x-ratelimit-cost-usd") or 0.0)
        return out, cost


class Scout:
    def __init__(self, run, per_query=2, n_deep=4):
        self.run, self.per_query, self.n_deep = run, per_query, n_deep
        self.path = run.dir / "scout.jsonl"
        self.log = [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()] if self.path.exists() else []
        self.items = {}                                # W id -> its full text, for every generation so far
        for g in self.log:
            self.items.update(g.get("items_text", {}))
        self.searcher = Searcher()
        self.brief = {"deep": [], "wide": []}          # this generation's item ids

    def truncate(self, gen_done):
        self.log = [g for g in self.log if g["gen"] <= gen_done]
        self.path.write_text("".join(json.dumps(g) + "\n" for g in self.log))
        self.items = {}
        for g in self.log:
            self.items.update(g.get("items_text", {}))

    # ---- what the scout reads
    def state(self, gen):
        run, arch = self.run, self.run.archive
        best = arch.best()
        fb = "\n".join(f"  {l}" for l in best.feedback[:6])
        last = [p for p in arch.programs.values() if p.round == gen - 1 and gen > 1]
        lines = []
        for p in last:
            res = f"{p.delta:+.6f}" if p.valid and p.delta is not None else ("FAILED: " + short(p.error, 160))
            lines.append(f"- {p.id} ({p.role}, from {p.parent}): {short(p.idea, 220)} -> {res}")
        txt = (f"## The best program so far: {best.id} (generation {best.round}), score {best.score:.6f}\n"
               f"What it does: {short(best.idea, 400)}\nIts result:\n{fb}\n\n")
        if lines:
            txt += f"## What generation {gen - 1} tried, and what came of it\n" + "\n".join(lines) + "\n\n"
        if run.atlas and run.atlas.findings:
            fl = sorted(run.atlas.findings, key=lambda i: int(i[1:]))[-25:]
            txt += "## The Atlas's latest findings\n" + "\n".join(run.atlas.finding_line(f, 220) for f in fl) + "\n\n"
        if run.guidance:
            txt += "## The guidance store (titles and records)\n" + "\n".join(
                f"- {g}: {re.sub(r'^## G[0-9]+[:.] *', '', body.splitlines()[0])} | "
                f"{run.guidance.record(g, arch, gen, last=1).splitlines()[0]}"
                for g, body in run.guidance.entries.items()) + "\n\n"
        tried = self.tried_lines(gen)
        if tried:
            txt += tried + "\n"
        if self.log:
            qs = [f"- gen {g['gen']} ({q['set']}, {q['kind']}): {q['query']}" for g in self.log for q in g["queries"]]
            txt += "## Your search log: every query asked so far (don't repeat or rephrase these)\n" + "\n".join(qs[-80:]) + "\n\n"
        return txt

    def tried_lines(self, gen):
        """W items cited by earlier programs, with their records (one line each)."""
        arch = self.run.archive
        out = []
        for wid in sorted(self.items, key=lambda w: tuple(int(x) for x in w[1:].split("."))):
            progs = [p for p in arch.programs.values() if p.round < gen and wid in (p.plan or {}).get("web", [])]
            res = [(p, outcome(p)) for p in progs if outcome(p)]
            if not res:
                continue
            n = {o: sum(1 for _, x in res if x == o) for o in ("gained", "no gain", "failed")}
            out.append(f"- {short(self.items[wid].splitlines()[0], 160)} | tried {len(res)}: {n['gained']} gained, "
                       f"{n['no gain']} no gain, {n['failed']} failed ({', '.join(p.id for p, _ in res[-3:])})")
        return TRIED + "\n".join(out) + "\n" if out else ""

    # ---- one generation's search
    def scout(self, gen, n_wide):
        run = self.run
        user = (f"{run.statement}\n\n{self.state(gen)}"
                + ASK.format(gen=gen, n_deep=self.n_deep, n_wide=n_wide))
        js = P.extract_json(run.call("scout", SYSTEM, user, 0.6, 6000, "low"))
        js = js if isinstance(js, dict) else {}
        seen_q = {q["query"].strip().lower() for g in self.log for q in g["queries"]}
        seen_url = {r["url"] for g in self.log for r in g.get("results", [])}
        rec = {"gen": gen, "t": round(time.time(), 3), "diagnosis": str(js.get("diagnosis") or ""), "queries": [],
               "results": [], "items_text": {}, "cost_usd": {"exa": 0.0, "openalex": 0.0}, "errors": []}
        k = 0
        self.brief = {"deep": [], "wide": []}
        for set_name, limit in (("deep", self.n_deep), ("wide", n_wide)):
            qs = js.get(set_name) if isinstance(js.get(set_name), list) else []
            for qi, q in enumerate([q for q in qs if isinstance(q, dict) and q.get("query")][:limit]):
                query, kind = str(q["query"]).strip(), str(q.get("kind") or "web").strip().lower()
                purpose = str(q.get("purpose") or "").strip()
                entry = {"set": set_name, "slot": qi, "query": query, "kind": kind, "purpose": purpose, "items": []}
                rec["queries"].append(entry)
                if query.lower() in seen_q:
                    entry["skipped"] = "repeat"
                    continue
                try:
                    if kind == "paper":
                        res, cost = self.searcher.papers(query)
                        rec["cost_usd"]["openalex"] += cost
                    else:
                        res, cost = self.searcher.web(query, purpose, code=(kind == "code"))
                        rec["cost_usd"]["exa"] += cost
                except Exception as exc:                          # noqa: BLE001  (a failed search: none this time)
                    rec["errors"].append(f"{set_name} {kind}: {exc}"[:300])
                    continue
                kept = [r for r in res if r["url"] not in seen_url and len(r["text"]) >= 200][:self.per_query]
                for r in kept:
                    k += 1
                    wid = f"W{gen}.{k}"
                    src = r.get("venue") or urllib.parse.urlparse(r["url"]).netloc
                    head = f"{wid}: {r['title']} ({src}{', ' + r['date'] if r['date'] else ''}) {r['url']}"
                    text = f"{head}\nFound for: {purpose or query}\n{short(r['text'], 2400)}"
                    self.items[wid] = rec["items_text"][wid] = text
                    seen_url.add(r["url"])
                    entry["items"].append(wid)
                    rec["results"].append({"id": wid, "url": r["url"], "title": r["title"], "kind": kind, "set": set_name})
                    if set_name == "deep":
                        self.brief["deep"].append(wid)
        self.brief["wide"] = [e["items"] for e in rec["queries"] if e["set"] == "wide"]
        self.log.append(rec)
        with open(self.path, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        return rec

    # ---- what the agents see
    def for_planner(self, gen):
        items = [self.items[w] for w in self.brief["deep"]]
        diag = self.log[-1].get("diagnosis") if self.log and self.log[-1]["gen"] == gen else ""
        txt = (INTRO + (f"The scout's reading of where the run stands: {diag}\n\n" if diag else "")
               + "\n\n".join(items) + "\n\n") if items else ""
        return txt + self.tried_lines(gen)

    def for_mutator(self, slot):
        wide = self.brief["wide"]
        if not wide:
            return ""
        items = [self.items[w] for w in wide[slot % len(wide)]]
        return MUT_INTRO + "\n\n".join(items) + "\n\n" if items else ""

    def cited(self, wids):
        bodies = [self.items[w] for w in wids if w in self.items]
        return CITED + "\n\n".join(bodies) + "\n\n" if bodies else ""
