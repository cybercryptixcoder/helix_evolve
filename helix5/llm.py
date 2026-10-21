"""The model client for v4.5/v5: v4's (helix4/llm.py), with one more option.

`chat(..., grow=False)` returns a reply cut off by the token limit as it is, instead of retrying with double the room.
In the October 21 tests a "low"-effort planner occasionally thought for 40,000+ tokens, hit the limit, and the
doubled retry thought for minutes more. With grow=False the caller falls back at once to an answer without thinking
(`helix5.run.Run.researcher`), which caps a planning call at about the budget it was given.
"""
from __future__ import annotations

import random
import time

from helix3.llm import CAP, EFFORTS, THINK_ROOM, THINK_SECONDS
from helix4.llm import LLM as _V4, LLMError


class LLM(_V4):
    supports_grow = True

    def chat(self, role, system, user, temperature=0.7, max_tokens=4000, effort="none", meta=None, tries=5, grow=True):
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
                if rep.finish == "length" and grow and not grown and payload["max_tokens"] < CAP:
                    self._record(role, system, user, rep, temperature, effort, meta, "cut off by max_tokens; retrying with double")
                    payload = {**payload, "max_tokens": min(CAP, payload["max_tokens"] * 2)}
                    grown = True
                    continue
                self._record(role, system, user, rep, temperature, effort, meta,
                             "cut off by max_tokens (returned as is)" if rep.finish == "length" else None)
                return rep
            except LLMError as exc:
                last = exc
                if not exc.retryable:
                    break
                penalty = 3.0 if "429" in str(exc) else 0.0
                if "longer than" in str(exc):
                    payload = {**payload, "reasoning_effort": "none",
                               "max_tokens": min(CAP, max_tokens + THINK_ROOM.get("none", 16000))}
                    effort = "none"
            finally:
                self._release(k, penalty)
            time.sleep(min(20, 1.5 * 2 ** attempt) + random.random())
        self._record(role, system, user, None, temperature, effort, meta, str(last))
        raise last or LLMError("model call failed")
