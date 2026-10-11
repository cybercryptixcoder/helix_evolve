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
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / ".env"
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
REASONING_KEPT = 20000      # characters of model reasoning saved per call
OLLAMA_URL = "http://localhost:11434/v1"


def load_env_file(path=ENV_FILE):
    """Read KEY=VALUE lines from helix/.env. Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    provider: str = "luminal"    # luminal | local
    base_url: str = ""
    api_key: str = ""
    flash_model: str = "deepseek-v4.1-flash"
    pro_model: str = ""
    pro_every: int = 10          # every Nth call goes to the pro model; 0 = never
    temperature: float = 0.8
    max_tokens: int = 8000
    timeout: float = 180.0       # seconds per request
    retries: int = 4
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
                    base_url=env("LUMINAL_BASE_URL", "").rstrip("/"),
                    api_key=env("LUMINAL_API_KEY", ""),
                    flash_model=env("HELIX_FLASH_MODEL") or cls.flash_model,
                    pro_model=env("HELIX_PRO_MODEL", ""),
                    timeout=float(env("HELIX_TIMEOUT") or 180))
        try:
            s.extra_body = json.loads(extra) if extra else {}
        except json.JSONDecodeError:
            raise SystemExit(f"LUMINAL_EXTRA_BODY isn't valid JSON: {extra!r}")
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

    def summary(self):
        totals = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "pro_calls": 0}
        for (role, tier), u in self.usage.items():
            totals["calls"] += u["calls"]
            totals["tokens_in"] += u["tokens_in"]
            totals["tokens_out"] += u["tokens_out"]
            if tier == "pro":
                totals["pro_calls"] += u["calls"]
        return totals

    # ------------------------------------------------------------ internals
    def _complete(self, model, system, user, temperature, role):
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": self.s.max_tokens,
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
        if not text.strip():
            raise RuntimeError(f"empty reply (finish_reason={choice.get('finish_reason')!r})")
        usage = data.get("usage") or {}
        return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0), reasoning

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
            try:
                with urllib.request.urlopen(req, timeout=self.s.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as err:
                detail = err.read().decode(errors="replace")[:500]
                last_error = RuntimeError(f"HTTP {err.code} from {url}: {detail}")
                if err.code not in RETRY_STATUS:
                    raise last_error from None
                wait = _retry_after(err) or _backoff(attempt)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
                last_error = RuntimeError(f"cannot reach {url}: {getattr(err, 'reason', err)}")
                wait = _backoff(attempt)
            if attempt < self.s.retries:
                time.sleep(wait)
        raise last_error

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


def _retry_after(err):
    try:
        return min(float(err.headers.get("Retry-After", "")), 60.0)
    except (TypeError, ValueError):
        return None


def _backoff(attempt):
    return min(2.0 * 2 ** attempt, 60.0) + random.uniform(0, 1)


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
        ids = re.findall(r"^### Program (\S+)", user, re.M) or ["unknown"]
        n = int((re.search(r"exactly (\d+) hypotheses", user) or [0, 3])[1])
        hyps = [{
            "base": self.rng.choice(ids[:3]),
            "claim": f"Fake claim {i}: penalising imbalance between leftover CPU and memory matters most on anticorr.",
            "change": "Double the weight on the CPU/memory imbalance term.",
            "prediction": "anticorr excess drops; other families roughly unchanged.",
        } for i in range(n)]
        return "```json\n" + json.dumps({"hypotheses": hyps}, indent=2) + "\n```"


def check(settings=None):
    """Send one tiny request to each configured model. Returns a list of result dicts (never raises)."""
    settings = settings or Settings.from_env()
    missing = settings.problems()
    if missing:
        return [{"ok": False, "tier": "-", "model": "-",
                 "detail": f"missing {', '.join(missing)}: fill them in on the dashboard or in helix/.env"}]
    llm = LLM(replace_retries(settings, 1))
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


def replace_retries(settings, retries):
    from dataclasses import replace
    return replace(settings, retries=retries)


if __name__ == "__main__":
    s = Settings.from_env()
    print(f"provider: {s.provider} | endpoint: {s.base_url or '(not set)'}")
    for res in check(s):
        print(f"{'OK  ' if res['ok'] else 'FAIL'} {res['tier']:5s} {res['model']}: {res['detail']}")
