"""One client for an OpenAI-style chat endpoint (Luminal's DeepSeek V4.1 Flash by default).

Settings, from the environment or the repo's .env:
    LUMINAL_API_KEYS   comma-separated keys, used in turn, each paced at about one new call a second, with at most
                       LUMINAL_MAX_IN_FLIGHT (8) calls open on a key at once (every run in a process shares both)
    LUMINAL_BASE_URL   default https://flash.luminal.cloud/v1
    HELIX_MODEL        default deepseek-ai/DeepSeek-V4.1-Flash (HELIX_FLASH_MODEL is read too)

Replies are streamed with usage; 429, 5xx, dropped, empty or cut-off streams are retried with backoff (a rate limit
is waited out, however long). `on_call` receives every call (prompt, reply, tokens, seconds) for the run's log.
"""
from __future__ import annotations

import json
import os
import random
import ssl
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_PACE = threading.Lock()
_next_free = {}                      # key -> earliest start of its next call
_IN_FLIGHT = {}                      # key -> a semaphore: at most LUMINAL_MAX_IN_FLIGHT calls open on a key at once
_MAX_IN_FLIGHT = int(os.environ.get("LUMINAL_MAX_IN_FLIGHT", "8"))     # Luminal's limit per key


def load_dotenv():
    for p in (ROOT / ".env", Path(".env")):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _ssl_context():
    for path in (os.environ.get("SSL_CERT_FILE"), "/root/.ccr/ca-bundle.crt"):
        if path and Path(path).exists():
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


THINK_SECONDS = 600                  # a thinking call that runs longer is cut and retried without thinking (v4)


class LLMError(RuntimeError):
    pass


class ThinkingTooLong(LLMError):
    pass


class LLM:
    def __init__(self, on_call=None):
        load_dotenv()
        raw = os.environ.get("LUMINAL_API_KEYS") or os.environ.get("LUMINAL_API_KEY") or ""
        self.keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not self.keys:
            raise LLMError("no API key: set LUMINAL_API_KEYS in .env")
        self.base = os.environ.get("LUMINAL_BASE_URL", "https://flash.luminal.cloud/v1").rstrip("/")
        self.model = (os.environ.get("HELIX_MODEL") or os.environ.get("HELIX_FLASH_MODEL")
                      or "deepseek-ai/DeepSeek-V4.1-Flash")
        self.ctx = _ssl_context()
        self.on_call = on_call
        self.calls = self.tokens_in = self.tokens_out = 0
        self._lock = threading.Lock()

    def chat(self, role, system, user, temperature=0.7, max_tokens=8000, effort="none", meta=None):
        """The reply's text ("" if every attempt failed; the failure is logged)."""
        body = {"model": self.model, "stream": True, "stream_options": {"include_usage": True},
                "temperature": temperature, "reasoning_effort": effort,
                "max_tokens": max_tokens + (24000 if effort != "none" else 0),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        t0, last, attempt, limited, grown = time.time(), None, 0, 0, False
        text, think, finish, usage = "", "", None, {}
        tin = tout = cached = reasoning = 0  # summed over every attempt that streamed (a cut-off one costs tokens too)
        tag = json.dumps({"role": role, **(meta or {})})      # sent as X-Trace-Tag, for a logging relay (if any)
        while True:
            retry_after = None
            with _PACE:
                key = min(self.keys, key=lambda k: _next_free.get(k, 0.0))
                start = max(time.time(), _next_free.get(key, 0.0))
                _next_free[key] = start + 1.0
            time.sleep(max(0.0, start - time.time()))
            with _PACE:
                gate = _IN_FLIGHT.setdefault(key, threading.BoundedSemaphore(_MAX_IN_FLIGHT))
            try:
                with gate:
                    text, think, finish, usage = self._stream(key, body, THINK_SECONDS
                                                              if body["reasoning_effort"] != "none" else None, tag)
                tin += int(usage.get("prompt_tokens") or 0)
                tout += int(usage.get("completion_tokens") or 0)
                cached += int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
                reasoning += int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
                if finish == "length" and not grown:
                    # cut off by the token limit (v4's rule): once more, with double the room
                    body = {**body, "max_tokens": body["max_tokens"] * 2}
                    grown = True
                    raise LLMError("cut off by max_tokens; retrying once with double the room")
                if not text.strip():
                    raise LLMError(f"empty answer (finish={finish})")
                if not finish:
                    raise LLMError("the stream ended without a finish reason")
                last = None
                break
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read()[:200]!r}"
                if e.code not in (408, 409, 429, 500, 502, 503, 504):
                    break
                if e.code == 429:
                    retry_after = float(e.headers.get("Retry-After") or 1)
                    with _PACE:
                        _next_free[key] = max(_next_free.get(key, 0.0), time.time() + retry_after)
            except ThinkingTooLong as e:          # v4's rule: a thinking call that runs too long is retried without thinking
                last = f"{e}"
                body = {**body, "reasoning_effort": "none", "max_tokens": max_tokens}
            except Exception as e:                                   # noqa: BLE001  (drops, timeouts: retry)
                last = f"{type(e).__name__}: {e}"
            if retry_after is not None:
                limited += 1
                pause = min(600, retry_after + min(60, 2 ** min(limited, 6))) + random.random()
            else:
                attempt += 1
                if attempt >= 5:
                    break
                pause = min(30, 2 * 2 ** attempt) + random.random()
            time.sleep(pause)
        with self._lock:
            self.calls += 1
            self.tokens_in += tin
            self.tokens_out += tout
        if self.on_call:
            self.on_call({"role": role, "system": system, "user": user, "reply": text if last is None else "",
                          "reasoning": think, "tokens_in": tin, "tokens_out": tout, "tokens_cached": cached,
                          "tokens_reasoning": reasoning, "finish": finish, "key": key[-4:], "t_start": round(t0, 3),
                          "seconds": round(time.time() - t0, 1), "temperature": temperature, "effort": effort,
                          "error": last, **(meta or {})})
        return "" if last is not None else text

    def _stream(self, key, body, max_seconds=None, tag=None):
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        if tag:
            headers["X-Trace-Tag"] = tag
        req = urllib.request.Request(self.base + "/chat/completions", data=json.dumps(body).encode(), headers=headers)
        text, think, finish, usage = [], [], None, {}
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=600, context=self.ctx) as r:
            for raw in r:
                if max_seconds and time.time() - t0 > max_seconds:
                    raise ThinkingTooLong(f"thinking took longer than {max_seconds} s")
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                ev = json.loads(data)
                if ev.get("error"):
                    raise LLMError(f"mid-stream error: {ev['error']}")
                usage = ev.get("usage") or usage
                for ch in ev.get("choices") or []:
                    d = ch.get("delta") or {}
                    text.append(d.get("content") or "")
                    think.append(d.get("reasoning_content") or "")
                    finish = ch.get("finish_reason") or finish
        return "".join(text), "".join(think), finish, usage


class FakeLLM:
    """Answers from a function answer(role, system, user) -> str. For crash tests only, never for results."""

    def __init__(self, answer, on_call=None):
        self.answer, self.on_call = answer, on_call
        self.calls = self.tokens_in = self.tokens_out = 0

    def chat(self, role, system, user, temperature=0.7, max_tokens=8000, effort="none", meta=None):
        text = self.answer(role, system, user)
        self.calls += 1
        if self.on_call:
            self.on_call({"role": role, "system": system, "user": user, "reply": text, "reasoning": "",
                          "tokens_in": 0, "tokens_out": 0, "finish": "stop", "seconds": 0.0,
                          "temperature": temperature, "effort": effort, "error": None, **(meta or {})})
        return text
