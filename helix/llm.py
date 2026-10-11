"""One client for every agent, over an OpenAI-style /chat/completions API.

Two providers, picked with HELIX_PROVIDER:
  luminal (default)   Luminal Cloud: LUMINAL_BASE_URL, LUMINAL_API_KEY,
                      HELIX_FLASH_MODEL, HELIX_PRO_MODEL (optional)
  local               a model on your own machine (Ollama, LM Studio, llama.cpp):
                      LOCAL_BASE_URL (default Ollama's http://localhost:11434/v1), LOCAL_MODEL
Also: LUMINAL_EXTRA_BODY (JSON merged into every request), HELIX_TIMEOUT (seconds per request).
Settings come from environment variables or helix/.env (the dashboard writes that file).

Every call (role, model, prompts, reply, the model's reasoning if it returns any,
tokens, seconds) is appended to the run's llm_calls.jsonl.

Check your settings:  python -m helix.llm
"""
import json
import os
import random
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


def _ssl_context():
    """Python from python.org on macOS ships without root certificates, so HTTPS fails with
    CERTIFICATE_VERIFY_FAILED. Use certifi's bundle when it's installed; otherwise the system default."""
    if os.environ.get("SSL_CERT_FILE"):
        return ssl.create_default_context()
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()

ENV_FILE = Path(__file__).resolve().parent / ".env"
# Committed team settings (Luminal endpoint, model, temporary key). helix/.env and real
# environment variables override anything in it.
TEAM_ENV_FILE = Path(__file__).resolve().parent / "luminal.env"
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
REASONING_KEPT = 20000      # characters of model reasoning saved per call
OLLAMA_URL = "http://localhost:11434/v1"
LUMINAL_URL = "https://flash.luminal.cloud/v1"
LUMINAL_FLASH = "deepseek-ai/DeepSeek-V4.1-Flash"


def load_env_file(path=ENV_FILE):
    """Read KEY=VALUE lines from helix/.env, then helix/luminal.env. Earlier sources win."""
    for p in (path, TEAM_ENV_FILE):
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                if value:
                    os.environ.setdefault(key.strip(), value)


@dataclass
class Settings:
    provider: str = "luminal"    # luminal | local
    base_url: str = LUMINAL_URL
    api_key: str = ""
    flash_model: str = LUMINAL_FLASH
    pro_model: str = ""
    pro_every: int = 10          # every Nth call goes to the pro model; 0 = never
    temperature: float = 0.8
    max_tokens: int = 8000       # room for written reasoning + a program, with hidden thinking off
    timeout: float = 180.0       # seconds of silence before giving up (streamed replies keep it alive)
    stream: bool = True          # Luminal cuts off non-streamed requests that run past ~20 s
    retries: int = 6             # 503s from a serverless model that's warming up are common
    extra_body: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, **overrides):
        load_env_file()
        env = os.environ.get
        extra = env("LUMINAL_EXTRA_BODY", "").strip()
        provider = (env("HELIX_PROVIDER") or "luminal").strip().lower()
        if provider == "local":
            s = cls(provider="local",
                    base_url=(env("LOCAL_BASE_URL") or OLLAMA_URL).rstrip("/"),
                    api_key=env("LOCAL_API_KEY") or "local",     # local servers ignore the key
                    flash_model=env("LOCAL_MODEL", ""),
                    pro_model="",
                    timeout=float(env("HELIX_TIMEOUT") or 600))  # local models are slower
        else:
            s = cls(provider="luminal",
                    base_url=(env("LUMINAL_BASE_URL") or LUMINAL_URL).rstrip("/"),
                    api_key=env("LUMINAL_API_KEY", ""),
                    flash_model=env("HELIX_FLASH_MODEL") or cls.flash_model,
                    pro_model=env("HELIX_PRO_MODEL", ""),
                    timeout=float(env("HELIX_TIMEOUT") or 180))
        try:
            s.extra_body = json.loads(extra) if extra else {}
        except json.JSONDecodeError:
            raise SystemExit(f"LUMINAL_EXTRA_BODY isn't valid JSON: {extra!r}")
        s.stream = (env("HELIX_STREAM") or "1").strip().lower() not in ("0", "false", "no", "off")
        # DeepSeek-V4.1-Flash on Luminal: with hidden thinking on it reasons for 16k+ tokens (~90 s) and
        # often never answers; with it off it answers in seconds. The agents still reason, in the reply
        # itself (every prompt asks for reasoning before the answer). HELIX_THINKING=on turns it back on.
        thinking_on = (env("HELIX_THINKING") or "off").strip().lower() in ("1", "on", "true", "yes")
        if s.provider == "luminal" and "chat_template_kwargs" not in s.extra_body:
            s.extra_body["chat_template_kwargs"] = {"thinking": thinking_on}
        if env("HELIX_MAX_TOKENS"):
            s.max_tokens = int(env("HELIX_MAX_TOKENS"))
        for key, value in overrides.items():
            if value is not None:
                setattr(s, key, value)
        return s

    def problems(self):
        """What's missing before real calls can work."""
        if self.provider == "local":
            return [name for name, value in (("LOCAL_BASE_URL", self.base_url), ("LOCAL_MODEL", self.flash_model))
                    if not value]
        return [name for name, value in (("LUMINAL_BASE_URL", self.base_url), ("LUMINAL_API_KEY", self.api_key),
                                         ("HELIX_FLASH_MODEL", self.flash_model)) if not value]


@dataclass
class Reply:
    text: str
    model: str
    tier: str            # "flash" or "pro"
    tokens_in: int
    tokens_out: int
    seconds: float
    reasoning: str = ""  # the model's thinking, if the API returns it separately


class LLM:
    def __init__(self, settings, log_path=None):
        self.s = settings
        self.log_path = Path(log_path) if log_path else None
        self._lock = threading.Lock()
        self._calls = 0
        self.usage = {}   # (role, tier) -> {"calls", "tokens_in", "tokens_out", "seconds"}
        self.max_concurrent = max(1, int(os.environ.get("HELIX_MAX_CONCURRENT") or 12))
        self._slots = threading.Condition()
        self._limit = self.max_concurrent
        self._in_flight = 0
        self._retrying = 0
        self._ok_streak = 0
        self.note = None          # why we're currently sending fewer requests, if we are
        self._count_logged_calls()

    def _count_logged_calls(self):
        """On --resume the call log already holds this run's earlier calls: count them, so totals keep going."""
        if not self.log_path or not self.log_path.exists():
            return
        text = self.log_path.read_text()
        if text and not text.endswith("\n"):   # a killed run's half-written line: start new calls on a fresh line
            with self.log_path.open("a") as f:
                f.write("\n")
        for line in text.splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue   # a half-written last line from a killed run
            self._calls += 1
            if r.get("error") is None and r.get("role"):
                self._count(r["role"], r.get("tier") or "flash", r.get("tokens_in") or 0,
                            r.get("tokens_out") or 0, r.get("seconds") or 0.0)

    # ------------------------------------------------------------ routing
    def _pick_tier(self, force_tier):
        with self._lock:
            self._calls += 1
            n = self._calls
        if force_tier:
            return force_tier
        if self.s.pro_model and self.s.pro_every and n % self.s.pro_every == 0:
            return "pro"
        return "flash"

    # ------------------------------------------------------------ public
    def chat(self, role, system, user, temperature=None, force_tier=None):
        """Send one system + user message pair. Returns a Reply; raises after the last retry fails."""
        tier = self._pick_tier(force_tier)
        model = self.s.pro_model if tier == "pro" and self.s.pro_model else self.s.flash_model
        temp = self.s.temperature if temperature is None else temperature
        started = time.time()
        error = None
        try:
            text, tokens_in, tokens_out, reasoning = self._complete(model, system, user, temp, role)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            seconds = round(time.time() - started, 2)
            self._log({
                "role": role, "tier": tier, "model": model, "temperature": temp,
                "system": system, "user": user,
                "reply": None if error else text,
                "reasoning": None if error else (reasoning[:REASONING_KEPT] or None),
                "error": error,
                "tokens_in": None if error else tokens_in, "tokens_out": None if error else tokens_out,
                "seconds": seconds,
            })
        self._count(role, tier, tokens_in, tokens_out, seconds)
        return Reply(text, model, tier, tokens_in, tokens_out, seconds, reasoning)

    def wait_until_ready(self, max_wait=600.0, on_wait=None):
        """Send a tiny request until the model answers. Returns (ready, last_error).

        Serverless models answer 503 "temporarily unavailable" while they start up;
        waiting here stops a run from burning generations on a model that isn't there yet.
        A non-retryable error (bad key, unknown model) returns at once.
        """
        from dataclasses import replace
        probe = LLM(replace(self.s, retries=0, timeout=90))
        deadline, last = time.time() + max_wait, None
        while True:
            try:
                probe.chat("warmup", "You are a terse assistant.", "Reply with the single word: ready",
                           temperature=0, force_tier="flash")
                return True, None
            except Exception as exc:
                last = str(exc)
                retryable = any(f"HTTP {c} " in last for c in RETRY_STATUS) or "cannot reach" in last
                if not retryable or time.time() > deadline:
                    return False, last
                if on_wait:
                    on_wait(last, deadline - time.time())
                time.sleep(15)

    def summary(self):
        totals = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "pro_calls": 0}
        for (role, tier), u in self.usage.items():
            totals["calls"] += u["calls"]
            totals["tokens_in"] += u["tokens_in"]
            totals["tokens_out"] += u["tokens_out"]
            if tier == "pro":
                totals["pro_calls"] += u["calls"]
        totals.update(in_flight=self._in_flight, retrying=self._retrying, limit=self._limit, note=self.note)
        return totals

    # ------------------------------------------------------------ internals
    def _complete(self, model, system, user, temperature, role):
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": self.s.max_tokens,
            **({"stream": True} if self.s.stream else {}),
            **self.s.extra_body,
        }
        data = self._post(body)
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        # Reasoning models return their thinking in a separate field; the name varies by server.
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
        if not isinstance(reasoning, str):
            reasoning = json.dumps(reasoning)
        if not text.strip() and reasoning.strip():
            # The model slipped into hidden thinking and ran out of room before answering. The program or
            # JSON is often already written inside that thinking, so hand it on and let the parser look.
            text = reasoning
        if not text.strip():
            raise RuntimeError(f"empty reply (finish_reason={choice.get('finish_reason')!r})")
        usage = data.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or (len(system) + len(user)) // 4)
        tokens_out = int(usage.get("completion_tokens") or (len(text) + len(reasoning)) // 4)
        return text, tokens_in, tokens_out, reasoning

    def _post(self, body):
        missing = self.s.problems()
        if missing:
            raise RuntimeError(f"missing settings: {', '.join(missing)} (set them in helix/.env)")
        url = f"{self.s.base_url}/chat/completions"
        payload = json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.s.api_key}"}
        last_error = None
        for attempt in range(self.s.retries + 1):
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            self._acquire()
            try:
                with urllib.request.urlopen(req, timeout=self.s.timeout,
                                            context=SSL_CONTEXT if url.startswith("https") else None) as resp:
                    data = _read_stream(resp) if body.get("stream") else json.loads(resp.read().decode())
                self._speed_up()
                return data
            except urllib.error.HTTPError as err:
                detail = err.read().decode(errors="replace")[:500]
                # Luminal names the limit hit and the request id support asks for in these headers.
                extra = "".join(f" [{h}: {err.headers.get(h)}]" for h in ("x-reject-reason", "x-luminal-request-id")
                                if err.headers and err.headers.get(h))
                last_error = RuntimeError(f"HTTP {err.code} from {url}: {detail}{extra}")
                if err.code not in RETRY_STATUS:
                    raise last_error from None
                if err.code in (429, 503):
                    self._slow_down(f"HTTP {err.code}: {detail[:120]}")
                wait = _retry_after(err) or _backoff(attempt)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
                last_error = RuntimeError(f"cannot reach {url}: {getattr(err, 'reason', err)}")
                wait = _backoff(attempt)
            finally:
                self._release()
            if attempt < self.s.retries:
                with self._lock:
                    self._retrying += 1
                time.sleep(wait)          # waits outside the slot, so other calls can go
                with self._lock:
                    self._retrying -= 1
        raise last_error

    # ------------------------------------------------------------ adaptive concurrency
    # Fire everything at once, but if the server says it's overloaded (503/429), halve how
    # many requests are in flight; add one back after every 3 successes, up to the maximum.
    def _acquire(self):
        with self._slots:
            while self._in_flight >= self._limit:
                self._slots.wait()
            self._in_flight += 1

    def _release(self):
        with self._slots:
            self._in_flight -= 1
            self._slots.notify_all()

    def _slow_down(self, why):
        with self._slots:
            if self._limit > 1:
                self._limit = max(1, self._limit // 2)
            self._ok_streak = 0
            self.note = f"server said {why} - sending at most {self._limit} at a time"

    def _speed_up(self):
        with self._slots:
            self._ok_streak += 1
            if self._ok_streak >= 3 and self._limit < self.max_concurrent:
                self._limit += 1
                self._ok_streak = 0
                self._slots.notify_all()
                if self.note:
                    self.note = f"recovering from 503s - now up to {self._limit} at a time"
            if self._limit >= self.max_concurrent:
                self.note = None

    def _count(self, role, tier, tokens_in, tokens_out, seconds):
        with self._lock:
            u = self.usage.setdefault((role, tier), {"calls": 0, "tokens_in": 0, "tokens_out": 0, "seconds": 0.0})
            u["calls"] += 1
            u["tokens_in"] += tokens_in
            u["tokens_out"] += tokens_out
            u["seconds"] += seconds

    def _log(self, record):
        if not self.log_path:
            return
        record = {"time": time.strftime("%H:%M:%S"), **record}
        with self._lock, self.log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")


def _read_stream(resp):
    """Collect an OpenAI-style server-sent-event stream into the same shape as a normal reply."""
    content, reasoning, finish, usage, seen_events, raw_lines = [], [], None, {}, False, []
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        raw_lines.append(line)
        if not line.startswith("data:"):
            continue
        seen_events = True
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if chunk.get("error"):   # an error part-way through: treat like a dropped connection and retry
            raise ConnectionError(f"error in stream: {json.dumps(chunk['error'])[:300]}")
        if chunk.get("usage"):
            usage = chunk["usage"]
        for ch in chunk.get("choices") or []:
            delta = ch.get("delta") or ch.get("message") or {}
            if delta.get("content"):
                content.append(delta["content"])
            r = delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(r, str) and r:
                reasoning.append(r)
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
    if not seen_events:          # the server ignored "stream" and sent one normal JSON reply
        return json.loads("\n".join(raw_lines))
    return {"choices": [{"message": {"content": "".join(content), "reasoning_content": "".join(reasoning)},
                         "finish_reason": finish}], "usage": usage}


def _retry_after(err):
    try:
        return min(float(err.headers.get("Retry-After", "")), 60.0)
    except (TypeError, ValueError):
        return None


def _backoff(attempt):
    return min(3.0 * 2 ** attempt, 45.0) + random.uniform(0, 2)


# ---------------------------------------------------------------- offline test double
class FakeLLM(LLM):
    """Answers without any network, so the whole loop can be tested before keys exist.

    Mutator, Coder and zero-shot calls get a random weighted heuristic (sometimes a
    broken one, to exercise the repair path); the Researcher gets well-formed JSON
    hypotheses about the programs named in its prompt.
    """

    def __init__(self, settings=None, log_path=None, seed=0):
        super().__init__(settings or Settings(), log_path)
        self.rng = random.Random(seed)

    def _complete(self, model, system, user, temperature, role):
        with self._lock:
            if role == "researcher":
                text = self._hypotheses(user)
            elif role.endswith("repair") or self.rng.random() > 0.1:
                text = self._program()
            else:
                text = "Idea: return one score per resource.\n```python\nimport numpy as np\n\ndef priority(item, bins, capacity):\n    return np.zeros((len(bins), 2))\n```"
        time.sleep(0.05)
        thinking = f"(fake reasoning for the {role}: comparing the programs I was shown, then writing my answer)"
        return text, len(system + user) // 4, len(text) // 4, thinking

    def _program(self):
        a, b, c, d = (round(self.rng.uniform(0, 2), 3) for _ in range(4))
        return (
            f"Idea: weighted leftover with balance term (a={a}, b={b}, c={c}, new-bin penalty {d}).\n"
            "```python\nimport numpy as np\n\n\ndef priority(item, bins, capacity):\n"
            "    left = (bins - item) / capacity\n"
            f"    scores = -{a} * left.sum(axis=1) - {b} * np.abs(left[:, 0] - left[:, 1]) - {c} * left.max(axis=1)\n"
            f"    scores[-1] -= {d}\n"
            "    return scores\n```"
        )

    def _hypotheses(self, user):
        champ = (re.search(r"## The champion: (\S+),", user) or [0, "unknown"])[1]
        others = re.findall(r"^### Program (\S+):", user, re.M)
        n = int((re.search(r"exactly (\d+) hypotheses", user) or [0, 3])[1])
        n_cause = int((re.search(r"(\d+) \*\*cause\*\* tests", user) or [0, 0])[1])
        hyps = []
        for i in range(n):
            cause = i < n_cause
            hyps.append({
                "kind": "cause" if cause else "improve",
                "base": champ if cause or not others or i % 2 else self.rng.choice(others[:3]),
                "claim": f"Fake {'cause' if cause else 'improve'} claim {i}: the imbalance term is why the champion wins.",
                "change": "Remove the imbalance term." if cause else "Scale the imbalance weight by 1.3.",
                "prediction": "anticorr excess moves the most.",
                "builds_on": "",
            })
        return "```json\n" + json.dumps({"hypotheses": hyps}, indent=2) + "\n```\nAnalysis: fake."


def check(settings=None):
    """Send one tiny request to each configured model. Returns a list of result dicts (never raises)."""
    settings = settings or Settings.from_env()
    missing = settings.problems()
    if missing:
        return [{"ok": False, "tier": "-", "model": "-",
                 "detail": f"missing {', '.join(missing)}: fill them in on the dashboard or in helix/.env"}]
    llm = LLM(replace_retries(settings, 1, timeout=min(settings.timeout, 90)))
    results = []
    for tier in ["flash"] + (["pro"] if settings.pro_model else []):
        try:
            r = llm.chat("check", "You are a terse assistant.", "Reply with the single word: ready",
                         temperature=0, force_tier=tier)
            results.append({"ok": True, "tier": tier, "model": r.model,
                            "detail": f"replied {r.text.strip()[:40]!r} in {r.seconds}s"
                                      + (" (returns reasoning)" if r.reasoning else "")})
        except Exception as exc:
            model = settings.pro_model if tier == "pro" else settings.flash_model
            results.append({"ok": False, "tier": tier, "model": model, "detail": str(exc)[:400]})
    return results


def replace_retries(settings, retries, timeout=None):
    from dataclasses import replace
    return replace(settings, retries=retries, timeout=timeout or settings.timeout)


if __name__ == "__main__":
    s = Settings.from_env()
    print(f"provider: {s.provider} | endpoint: {s.base_url or '(not set)'}")
    for res in check(s):
        print(f"{'OK  ' if res['ok'] else 'FAIL'} {res['tier']:5s} {res['model']}: {res['detail']}")
