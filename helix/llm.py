"""One client for every agent: Luminal through an OpenAI-style /chat/completions API.

Settings come from environment variables, or from helix/.env (see helix/.env.example):
  LUMINAL_BASE_URL    the endpoint, ending in /v1
  LUMINAL_API_KEY     sent as "Authorization: Bearer <key>"
  HELIX_FLASH_MODEL   the model used for most calls
  HELIX_PRO_MODEL     a stronger model used for every Nth call (optional)
  LUMINAL_EXTRA_BODY  optional JSON merged into every request body

Every call (role, model, prompts, reply, tokens, seconds) is appended to the
run's llm_calls.jsonl, so you can read exactly what each agent saw and said.

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
        extra = os.environ.get("LUMINAL_EXTRA_BODY", "").strip()
        s = cls(
            base_url=os.environ.get("LUMINAL_BASE_URL", "").rstrip("/"),
            api_key=os.environ.get("LUMINAL_API_KEY", ""),
            flash_model=os.environ.get("HELIX_FLASH_MODEL") or cls.flash_model,
            pro_model=os.environ.get("HELIX_PRO_MODEL", ""),
            extra_body=json.loads(extra) if extra else {},
        )
        for key, value in overrides.items():
            if value is not None:
                setattr(s, key, value)
        return s

    def problems(self):
        """What's missing before real calls can work."""
        missing = []
        if not self.base_url:
            missing.append("LUMINAL_BASE_URL")
        if not self.api_key:
            missing.append("LUMINAL_API_KEY")
        if not self.flash_model:
            missing.append("HELIX_FLASH_MODEL")
        return missing


@dataclass
class Reply:
    text: str
    model: str
    tier: str            # "flash" or "pro"
    tokens_in: int
    tokens_out: int
    seconds: float


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
            text, tokens_in, tokens_out = self._complete(model, system, user, temp, role)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            seconds = round(time.time() - started, 2)
            self._log({
                "role": role, "tier": tier, "model": model, "temperature": temp,
                "system": system, "user": user,
                "reply": None if error else text, "error": error,
                "tokens_in": None if error else tokens_in, "tokens_out": None if error else tokens_out,
                "seconds": seconds,
            })
        self._count(role, tier, tokens_in, tokens_out, seconds)
        return Reply(text, model, tier, tokens_in, tokens_out, seconds)

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
        if not text.strip():
            raise RuntimeError(f"empty reply (finish_reason={choice.get('finish_reason')!r})")
        usage = data.get("usage") or {}
        return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)

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
        return text, len(system + user) // 4, len(text) // 4

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


if __name__ == "__main__":
    settings = Settings.from_env()
    missing = settings.problems()
    if missing:
        raise SystemExit(f"Missing: {', '.join(missing)}. Copy helix/.env.example to helix/.env and fill it in.")
    llm = LLM(settings)
    tiers = ["flash"] + (["pro"] if settings.pro_model else [])
    for tier in tiers:
        r = llm.chat("check", "You are a terse assistant.", "Reply with the single word: ready", temperature=0, force_tier=tier)
        print(f"{tier:5s} {r.model}: {r.text.strip()[:60]!r}  ({r.seconds}s, {r.tokens_in} in / {r.tokens_out} out)")
