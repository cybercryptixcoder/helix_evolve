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

import gzip
import html
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
store nor tried in the Atlas, each different from the others. Phrase them openly (the kind of method or the difficulty,
not the one method you would pick first), so that the range of what the search finds, not your own first idea, decides
what the mutators see.

For each query give:
- "query": what to search for, in natural language, specific to this problem as it stands (not a keyword list);
- "kind", which decides where it is searched and what comes back:
  - "web": the whole web, papers' full texts and technical reports included; returns the passages of each page that
    answer the purpose. Use it for how a method works, how to get out of a difficulty, and implementation details;
  - "code": real source code, as written: finds repositories, files, gists and Stack Overflow answers, then reads the
    relevant source files themselves. Describe the code you want to see (its language and what it does, e.g. "Python
    function that ..."). Ask for code that is likely to exist: a known move, model, algorithm or data structure, or a
    library's usage, not this problem's exact variant (nobody has published that; the coders adapt what is found).
    Use it to see how others implement something, and for any programming difficulty the run has (an error that keeps
    coming back, a step that is too slow, a library's API), not only for methods;
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
         "Material the scout found this generation (W items: web pages, source code, and paper abstracts). It may or may not "
         "help: use what is relevant and say which items an experiment draws on; ignore the rest.\n\n")
MUT_INTRO = ("## From the web, for ideas: a direction found for you this generation\n"
             "Not a program to copy: material on an approach that may help. Use it if it gives you a good change.\n\n")
TRIED = "## Web items tried in earlier generations, and how they did\n"
CITED = "## From the web (the items this experiment draws on)\n"


PICK = """## Choose the source files to read

A search for code found these sources. Query: {query}
What a result must contain: {purpose}

{sources}

Choose up to {n} files (in all) most likely to hold code that serves that purpose: from a repository's file list, or a
file already given. For each, give 3-8 identifiers or words likely to appear in the relevant part (function, class,
method or variable names), used to cut the part of the file to read. Reply with one JSON object and nothing else:
```json
{{"files": [{{"repo": "owner/name", "path": "the/path.ext", "terms": ["..."]}}]}}
```"""

CODE_EXT = (".py", ".pyx", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".java", ".kt", ".scala", ".rs", ".go",
            ".jl", ".js", ".ts", ".cs", ".r", ".m", ".f90", ".ml", ".hs", ".rb", ".swift", ".lua", ".zig", ".nim", ".d")
NOT_REPO = {"topics", "orgs", "search", "marketplace", "features", "collections", "sponsors", "settings", "login",
            "about", "pricing", "enterprise", "apps"}
CODE_CHARS = 6000                                       # a code item: up to this much of a file


def is_code(path):
    return path.lower().endswith(CODE_EXT)


def html_text(h):
    """Stack Exchange HTML to text, code blocks kept as written."""
    h = re.sub(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", lambda m: "\n```\n" + m.group(1) + "\n```\n", h, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def source(url):
    """What a code-search result points at: a GitHub file or repository, a gist, a Stack Overflow question, or None.
    A GitHub pull request, issue, release or doc page points at its repository, whose code may hold the answer."""
    p = urllib.parse.urlparse(url)
    parts = [x for x in p.path.split("/") if x]
    if p.netloc in ("github.com", "www.github.com") and len(parts) >= 2 and parts[0] not in NOT_REPO:
        repo = f"{parts[0]}/{parts[1]}"
        if len(parts) >= 5 and parts[2] == "blob" and is_code(parts[-1]):
            return {"type": "file", "repo": repo, "ref": parts[3], "path": "/".join(parts[4:])}
        return {"type": "repo", "repo": repo}
    if p.netloc == "gist.github.com" and parts:
        return {"type": "gist", "id": parts[-1]}
    m = re.match(r"/questions/(\d+)", p.path)
    if p.netloc.endswith("stackoverflow.com") and m:
        return {"type": "qa", "id": m.group(1)}
    return None


def window(text, terms, size=CODE_CHARS):
    """The part of a file (whole lines, at most `size` characters) where the terms are densest."""
    if len(text) <= size:
        return text
    lines = [l[:size] for l in text.splitlines(keepends=True)]
    terms = [t.lower() for t in terms if len(t) >= 3]
    hits = [sum(l.lower().count(t) for t in terms) for l in lines]
    best, span, j, h, c = -1, (0, 0), 0, 0, 0
    for i in range(len(lines)):
        while j < len(lines) and c + len(lines[j]) <= size:
            c, h, j = c + len(lines[j]), h + hits[j], j + 1
        if h > best:
            best, span = h, (i, j)
        c, h = c - len(lines[i]), h - hits[i]
    fi = next((k for k in range(*span) if hits[k]), span[0])  # start at the definition the first hit is in, if it
    i, back = fi, 0                                             # is near (code reads down from a definition); else a
    while i > 0 and not re.match(r"\S", lines[i]) and back + len(lines[i - 1]) <= size // 3:   # little before it
        i, back = i - 1, back + len(lines[i - 1])
    if not re.match(r"\S", lines[i]):
        i, back = fi, 0
        while i > 0 and back + len(lines[i - 1]) <= size // 6:
            i, back = i - 1, back + len(lines[i - 1])
    c, j = 0, i
    while j < len(lines) and c + len(lines[j]) <= size:
        c, j = c + len(lines[j]), j + 1
    return "".join(lines[i:j])


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
        self.github = os.environ.get("GITHUB_TOKEN", "")      # optional: GitHub's API allows 60 calls an hour without
        self.ctx = _ssl_context()
        self.last = {}

    def _get(self, svc, req, pace, raw=False):
        wait = self.last.get(svc, 0.0) + pace - time.time()
        if wait > 0:
            time.sleep(wait)
        for attempt in range(5):
            self.last[svc] = time.time()
            try:
                with urllib.request.urlopen(req, timeout=90, context=self.ctx) as r:
                    data = r.read()
                    if raw:
                        return data.decode("utf-8", "replace"), dict(r.headers)
                    if r.headers.get("Content-Encoding") == "gzip":          # Stack Exchange always gzips
                        data = gzip.decompress(data)
                    return json.loads(data), dict(r.headers)
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
            body["includeDomains"] = ["github.com", "gist.github.com", "stackoverflow.com"]
        req = urllib.request.Request("https://api.exa.ai/search", data=json.dumps(body).encode(),
                                     headers={"x-api-key": self.exa, "Content-Type": "application/json"})
        d, _ = self._get("exa", req, 0.25)                     # 10 requests a second is Exa's limit
        out = []
        for r in d.get("results") or []:
            text = "\n...\n".join(h.strip() for h in (r.get("highlights") or []) if h.strip())
            out.append({"title": r.get("title") or "", "url": r.get("url") or "", "date": (r.get("publishedDate") or "")[:10],
                        "text": text})
        return out, float((d.get("costDollars") or {}).get("total") or 0.0)

    # ---- real code: GitHub files (raw, as written), gists, Stack Overflow answers
    def _github(self, url, raw=False):
        h = {"User-Agent": "helix-scout"}
        if self.github and not raw:
            h["Authorization"] = f"Bearer {self.github}"
        return self._get("github", urllib.request.Request(url, headers=h), 0.2, raw=raw)[0]

    def tree(self, repo):
        """A repository's source files (paths), from GitHub's tree of its default branch."""
        d = self._github(f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1")
        return [t["path"] for t in d.get("tree") or [] if t.get("type") == "blob" and is_code(t["path"])
                and t.get("size", 0) < 400_000]

    def file(self, repo, ref, path):
        return self._github(f"https://raw.githubusercontent.com/{repo}/{ref}/{urllib.parse.quote(path)}", raw=True)

    def gist(self, gid):
        d = self._github(f"https://api.github.com/gists/{gid}")
        return "\n\n".join(f"# {name}\n{f.get('content') or ''}" for name, f in (d.get("files") or {}).items()
                           if is_code(name))

    def answers(self, qid):
        """A Stack Overflow question's top answers, code blocks as written."""
        q = urllib.parse.urlencode({"site": "stackoverflow", "filter": "withbody", "sort": "votes", "order": "desc",
                                    "pagesize": 3})
        d, _ = self._get("stackexchange", urllib.request.Request(
            f"https://api.stackexchange.com/2.3/questions/{qid}/answers?{q}"), 0.2)
        return "\n\n".join(f"### Answer (score {a.get('score')})\n{html_text(a.get('body') or '')}"
                           for a in d.get("items") or [])

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

    # ---- a code query: real source code, not pages about it
    def code(self, query, purpose, seen_url, n_sources=4):
        """Exa finds repositories, files, gists and Stack Overflow questions; the model picks the files to read from the
        repositories' file lists; each file is read as written (raw) and the part where its terms are densest kept.
        Returns (results, Exa cost, the files picked)."""
        res, cost = self.searcher.web(query, purpose, code=True, n=10)
        srcs, keys = [], set()
        for r in res:
            s = source(r["url"])
            key = s and (s.get("repo") or s.get("id"))
            if not s or key in keys:
                continue
            keys.add(key)
            srcs.append(dict(s, title=r["title"], url=r["url"]))
            if len(srcs) == n_sources:
                break
        listing, trees = [], {}
        for s in srcs:
            if s["type"] == "repo":
                try:
                    paths = self.searcher.tree(s["repo"])
                except Exception:                                 # noqa: BLE001  (an unreadable repository: skip it)
                    continue
                if len(paths) > 300:                              # large repositories: paths that share a word with
                    words = set(re.findall(r"[a-z]{4,}", (query + " " + purpose).lower()))   # the query first
                    paths = sorted(paths, key=lambda p: (-len(words & set(re.findall(r"[a-z]{4,}", p.lower()))),
                                                          len(p)))[:300]
                trees[s["repo"]] = set(paths)
                listing.append(f"### Repository {s['repo']} ({short(s['title'], 100)}): its source files\n"
                               + "\n".join(paths))
            elif s["type"] == "file":
                trees.setdefault(s["repo"], set()).add(s["path"])
                listing.append(f"### File {s['repo']}: {s['path']}")
        picked = []
        if listing:
            js = P.extract_json(self.run.call("scout", SYSTEM, PICK.format(
                query=query, purpose=purpose or query, sources="\n\n".join(listing), n=self.per_query + 1), 0.2, 3000))
            for f in (js.get("files") if isinstance(js, dict) else None) or []:
                if isinstance(f, dict) and f.get("path") in trees.get(f.get("repo"), ()):
                    picked.append(f)
        out = []
        for s in srcs:                                            # in the search's order
            try:
                if s["type"] in ("repo", "file"):
                    for f in [f for f in picked if f["repo"] == s["repo"]]:
                        ref = s["ref"] if s["type"] == "file" and f["path"] == s["path"] else "HEAD"
                        url = f"https://github.com/{s['repo']}/blob/{ref}/{f['path']}"
                        if url in seen_url:
                            continue
                        text = window(self.searcher.file(s["repo"], ref, f["path"]),
                                      [str(t) for t in f.get("terms") or []])
                        out.append({"title": f"{s['repo']}: {f['path']}", "url": url, "date": "", "text": text})
                elif s["type"] == "gist":
                    out.append({"title": s["title"], "url": s["url"], "date": "",
                                "text": window(self.searcher.gist(s["id"]), re.findall(r"\w{4,}", purpose))})
                elif s["type"] == "qa":
                    out.append({"title": s["title"], "url": s["url"], "date": "",
                                "text": self.searcher.answers(s["id"])[:CODE_CHARS]})
            except Exception:                                     # noqa: BLE001  (an unreadable source: the next one)
                continue
        return out, cost, picked

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
                    elif kind == "code":
                        res, cost, entry["picked"] = self.code(query, purpose, seen_url)
                        rec["cost_usd"]["exa"] += cost
                    else:
                        res, cost = self.searcher.web(query, purpose)
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
                    body = r["text"] if kind == "code" else short(r["text"], 2400)
                    text = f"{head}\nFound for: {purpose or query}\n{body}"
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
