"""The model client for v4: Helix v3's Luminal client (key pool, rate limits, retries, trace), with one fix.

v3 treated "the model thought until it hit max_tokens and wrote no answer" as an empty reply and retried with the
same budget, which fails the same way (the zero-shot probe of October 20 lost 3 of 4 calls to it). Here such a
reply comes back as finish="length", so v3's own logic retries once with double the room. `FakeLLM` answers from a
function, for tests without model calls.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request

from helix3.llm import LLM as _V3, LLMError, Reply  # noqa: F401  (re-exported)


class LLM(_V3):
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
        text = "".join(content)
        if not seen or (not text.strip() and finish != "length"):
            raise LLMError("empty answer", retryable=True)
        if not finish:
            raise LLMError("the stream ended without a finish reason (cut off)", retryable=True)
        det = usage.get("completion_tokens_details") or {}
        return Reply(text, "".join(reasoning), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                     det.get("reasoning_tokens") or 0, 0.0, finish)


class FakeLLM:
    """chat() answers with answer(role, system, user) -> str; records calls like the real client."""

    def __init__(self, answer, on_call=None, delay=0.0):
        self.answer, self.on_call, self.delay = answer, on_call, delay
        self.calls = self.tokens_in = self.tokens_out = 0

    def chat(self, role, system, user, temperature=0.7, max_tokens=4000, effort="none", meta=None, tries=5):
        if self.delay:
            time.sleep(self.delay)
        text = self.answer(role, system, user)
        self.calls += 1
        rep = Reply(text, "", len(system + user) // 4, len(text) // 4, 0, self.delay, "stop")
        if self.on_call:
            self.on_call({"role": role, "system": system, "user": user, "reply": text, "reasoning": "",
                          "tokens_in": rep.tokens_in, "tokens_out": rep.tokens_out, "reasoning_tokens": 0,
                          "seconds": self.delay, "finish": "stop", "temperature": temperature, "effort": effort,
                          "error": None, **(meta or {})})
        return rep
