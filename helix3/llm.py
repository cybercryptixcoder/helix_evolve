"""The model client: Luminal (OpenAI-compatible), several keys, every rule from LUMINAL.md.

- Keys come from LUMINAL_API_KEYS (comma-separated) or LUMINAL_API_KEY, read from the environment or the
  repo's .env (gitignored). Each key gets its own limiter: at most `SURGE` calls starting together and a
  token bucket of `BUCKET` that refills at `REFILL` a second (Luminal allows ~13 at once and ~60 refilling
  at ~1/s; we stay under both). A call takes the key with the most room.
- Always streamed, always with reasoning_effort and max_tokens, retried on 429/5xx/socket errors.
- Every call is reported to `on_call` (the run's trace), with the prompt, reply, hidden reasoning, tokens
  and timing.
- `FakeLLM` answers from a function: for crash tests without spending anything.
"""
from __future__ import annotations

import json
import os
import random
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EFFORTS = ("none", "low", "medium", "high", "xhigh", "ultra", "max")
SURGE, BUCKET, REFILL = 6, 45.0, 0.85
# room for hidden reasoning on top of the answer's own max_tokens: a thinking model spends its budget on the
# reasoning first, so a fixed budget cuts the answer off at high effort (round 4: 27.7k reasoning tokens, answer cut)
THINK_ROOM = {"none": 0, "low": 12000, "medium": 20000, "high": 40000, "xhigh": 56000, "max": 80000, "ultra": 80000}
CAP = 393216
THINK_SECONDS = 600          # a thinking call that runs longer is cut and retried once without thinking
STEP_DOWN = {"max": "high", "ultra": "high", "xhigh": "high", "high": "medium", "medium": "low", "low": "none"}


def load_env():
    """Read KEY=VALUE lines from the repo's .env and helix/.env into os.environ (real env vars win)."""
    for p in (ROOT / ".env", ROOT / "helix" / ".env"):
        try:
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        except OSError:
            pass


def _ssl_context():
    for path in (os.environ.get("SSL_CERT_FILE"), "/root/.ccr/ca-bundle.crt"):
        if path and os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class LLMError(RuntimeError):
    def __init__(self, msg, retryable=False):
        super().__init__(msg)
        self.retryable = retryable


@dataclass
class Reply:
    text: str
    reasoning: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0
    seconds: float = 0.0
    finish: str = ""


class _Key:
    def __init__(self, key):
        self.key = key
        self.tokens = BUCKET
        self.stamp = time.time()
        self.active = 0

    def refill(self):
        now = time.time()
        self.tokens = min(BUCKET, self.tokens + (now - self.stamp) * REFILL)
        self.stamp = now


@dataclass
class LLM:
    base_url: str = ""
    model: str = ""
    keys: list = field(default_factory=list)
    on_call: object = None             # callback(dict) for the trace
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

    def __post_init__(self):
        load_env()
        self.base_url = (self.base_url or os.environ.get("LUMINAL_BASE_URL", "https://flash.luminal.cloud/v1")).rstrip("/")
        self.model = self.model or os.environ.get("HELIX_FLASH_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash")
        raw = self.keys or [k for k in os.environ.get("LUMINAL_API_KEYS", "").split(",") if k.strip()] \
            or [os.environ.get("LUMINAL_API_KEY", "")]
        self._keys = [_Key(k.strip()) for k in raw if k and k.strip()]
        if not self._keys:
            raise LLMError("no Luminal key: set LUMINAL_API_KEYS (or LUMINAL_API_KEY) in .env")
        self._cv = threading.Condition()
        self._ctx = _ssl_context()
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- key pool
    def _acquire(self):
        with self._cv:
            while True:
                for k in self._keys:
                    k.refill()
                ok = [k for k in self._keys if k.tokens >= 1 and k.active < SURGE]
                if ok:
                    k = max(ok, key=lambda k: (k.tokens - 4 * k.active, random.random()))
                    k.tokens -= 1
                    k.active += 1
                    return k
                self._cv.wait(0.25)

    def _release(self, k, penalty=0.0):
        with self._cv:
            k.active -= 1
            k.tokens -= penalty
            self._cv.notify_all()

    # ---------------------------------------------------------------- one call
    def chat(self, role, system, user, temperature=0.7, max_tokens=4000, effort="none", meta=None, tries=5):
        effort = effort if effort in EFFORTS else "none"
        budget = max_tokens + THINK_ROOM.get(effort, 16000)
        payload = {"model": self.model, "stream": True, "stream_options": {"include_usage": True},
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "temperature": temperature, "max_tokens": min(CAP, budget), "reasoning_effort": effort}
        t0, last, grown = time.time(), None, False
        for attempt in range(tries):
            k = self._acquire()
            penalty = 0.0
            try:
                rep = self._stream(k.key, payload, THINK_SECONDS if payload["reasoning_effort"] != "none" else None)
                rep.seconds = round(time.time() - t0, 2)
                if rep.finish == "length" and not grown and payload["max_tokens"] < CAP:
                    # cut off by the token limit (usually the hidden reasoning ate it): once more, with double room
                    self._record(role, system, user, rep, temperature, effort, meta, "cut off by max_tokens; retrying with double")
                    payload = {**payload, "max_tokens": min(CAP, payload["max_tokens"] * 2)}
                    grown = True
                    continue
                self._record(role, system, user, rep, temperature, effort, meta, None)
                return rep
            except LLMError as exc:
                last = exc
                if not exc.retryable:
                    break
                penalty = 3.0 if "429" in str(exc) else 0.0
                if "longer than" in str(exc):          # bounded thinking: one timeout, then answer without thinking
                    lower = "none"
                    payload = {**payload, "reasoning_effort": lower,
                               "max_tokens": min(CAP, max_tokens + THINK_ROOM.get(lower, 16000))}
                    effort = lower
            finally:
                self._release(k, penalty)
            time.sleep(min(20, 1.5 * 2 ** attempt) + random.random())
        self._record(role, system, user, None, temperature, effort, meta, str(last))
        raise last or LLMError("model call failed")

    def _stream(self, key, payload, max_seconds=None):
        req = urllib.request.Request(self.base_url + "/chat/completions", data=json.dumps(payload).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=300, context=self._ctx)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            raise LLMError(f"{e.code}: {body or e.headers.get('x-reject-reason')}", retryable=e.code in (429, 500, 502, 503, 504))
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            raise LLMError(f"connection: {e}", retryable=True)
        content, reasoning, usage, finish, seen = [], [], {}, "", False
        t0 = time.time()
        try:
            with resp:
                for line in resp:
                    if max_seconds and time.time() - t0 > max_seconds:
                        raise LLMError(f"thinking took longer than {max_seconds}s", retryable=True)
                    line = line.decode(errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if chunk.get("error"):
                        raise LLMError(f"mid-stream error: {chunk['error']}", retryable=True)
                    seen = True
                    usage = chunk.get("usage") or usage
                    for ch in chunk.get("choices") or []:
                        finish = ch.get("finish_reason") or finish
                        d = ch.get("delta") or {}
                        content.append(d.get("content") or "")
                        reasoning.append(d.get("reasoning_content") or "")
        except (socket.timeout, ConnectionError, OSError, ValueError) as e:
            raise LLMError(f"stream broke: {e}", retryable=True)
        if not seen or not "".join(content).strip():
            raise LLMError("empty answer", retryable=True)
        if not finish:
            raise LLMError("the stream ended without a finish reason (cut off)", retryable=True)
        det = usage.get("completion_tokens_details") or {}
        return Reply("".join(content), "".join(reasoning), usage.get("prompt_tokens", 0),
                     usage.get("completion_tokens", 0), det.get("reasoning_tokens") or 0, 0.0, finish or "")

    def _record(self, role, system, user, rep, temperature, effort, meta, error):
        with self._lock:
            self.calls += 1
            if rep:
                self.tokens_in += rep.tokens_in
                self.tokens_out += rep.tokens_out
        if self.on_call:
            self.on_call({"role": role, "system": system, "user": user, "reply": rep.text if rep else None,
                          "reasoning": rep.reasoning if rep else "", "tokens_in": rep.tokens_in if rep else 0,
                          "tokens_out": rep.tokens_out if rep else 0,
                          "reasoning_tokens": rep.reasoning_tokens if rep else 0,
                          "seconds": rep.seconds if rep else None, "finish": rep.finish if rep else "",
                          "temperature": temperature, "effort": effort, "error": error, **(meta or {})})


class FakeLLM:
    """Answers with `answer(role, system, user) -> str`. Same interface and trace as LLM."""

    def __init__(self, answer, on_call=None):
        self.answer, self.on_call = answer, on_call
        self.calls = self.tokens_in = self.tokens_out = 0
        self._lock = threading.Lock()

    def chat(self, role, system, user, temperature=0.7, max_tokens=4000, effort="none", meta=None, tries=1):
        t = time.time()
        text = self.answer(role, system, user)
        with self._lock:
            self.calls += 1
        if self.on_call:
            self.on_call({"role": role, "system": system, "user": user, "reply": text, "reasoning": "",
                          "tokens_in": len(user) // 4, "tokens_out": len(text) // 4, "reasoning_tokens": 0,
                          "seconds": round(time.time() - t, 3), "finish": "stop", "temperature": temperature,
                          "effort": effort, "error": None, **(meta or {})})
        return Reply(text)
