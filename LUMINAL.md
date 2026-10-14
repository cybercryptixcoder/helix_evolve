# Using Luminal with Helix

What works, what doesn't, and how we found out. Everything here was measured with Helix's real prompts between October 11 and 12, 2026. Luminal may change things after that; the checks at the end tell you whether it still holds.

## The short version

| Setting | Value |
|---|---|
| Endpoint | `https://flash.luminal.cloud/v1` (OpenAI-style: `POST /chat/completions`) |
| Model | `deepseek-ai/DeepSeek-V4.1-Flash` (the only model the endpoint listed) |
| Auth | `Authorization: Bearer <key>`; keys start `lum_live_` and come from the Luminal dashboard |
| **Hidden thinking** | **send `"reasoning_effort": "none"`**. Nothing else switches it off |
| Streaming | `"stream": true`. Non-streamed requests were cut off at about 20 s |
| Parallel calls | 12 at a time worked; halve on 503/429 and recover slowly |

Helix does all of this by default (`helix/llm.py`). With these settings, the last real run made 95 calls with **0 errors, 0 cut-off replies and no hidden reasoning**: median 2.2 s for a Coder call, 3.3 s for the Mutator, 9.1 s for the Researcher.

A minimal request that works:

```bash
curl -sN https://flash.luminal.cloud/v1/chat/completions \
  -H "Authorization: Bearer $LUMINAL_API_KEY" -H "Content-Type: application/json" \
  -d '{"model": "deepseek-ai/DeepSeek-V4.1-Flash", "stream": true, "max_tokens": 3000,
       "reasoning_effort": "none", "temperature": 0.8,
       "messages": [{"role": "system", "content": "You are terse."},
                    {"role": "user", "content": "Write a Python function that adds two numbers."}]}'
```

## Setting it up in Helix

- **Dashboard:** `python -m helix.ui`, then **Connect**: paste the key, keep the URL and model, press **Save** and **Test model**. The key is saved to `helix/.env`, which is gitignored.
- **By hand:** copy `helix/.env.example` to `helix/.env` and fill in `LUMINAL_API_KEY`. `helix/luminal.env` (committed, no key) already holds the endpoint and model.
- **Order of precedence:** real environment variables, then `helix/.env`, then `helix/luminal.env`.
- **Never commit a key.** None has ever been committed to this repo; keep it that way.

Environment variables Helix reads:

| Variable | Default | What it does |
|---|---|---|
| `LUMINAL_API_KEY` | none | Required |
| `LUMINAL_BASE_URL` | `https://flash.luminal.cloud/v1` | |
| `HELIX_FLASH_MODEL` | `deepseek-ai/DeepSeek-V4.1-Flash` | |
| `HELIX_PRO_MODEL` | empty | Optional second model, used every `--pro-every` calls. None was ever available to us |
| `HELIX_THINKING` | `none` | Sent as `reasoning_effort`. `low`, `medium` or `high` turn thinking back on (not recommended, see below) |
| `HELIX_STREAM` | on | Leave it on |
| `HELIX_MAX_CONCURRENT` | 12 | Most calls in flight |
| `HELIX_TIMEOUT` | 180 | Seconds of silence before a request is given up |
| `HELIX_MAX_TOKENS` | 8000 | Ceiling; each role also has its own, lower limit |
| `LUMINAL_EXTRA_BODY` | empty | JSON merged into every request. If it contains `reasoning_effort`, that value wins |
| `HELIX_PROVIDER` | `luminal` | `local` switches to an OpenAI-style server on your machine (Ollama, LM Studio) |

## The problem that cost us three runs: hidden thinking

DeepSeek-V4.1-Flash is a reasoning model. Unless told otherwise, it first "thinks" in a hidden channel (streamed as `reasoning_content`), and only then writes the answer. With Helix's real prompts it thought for about 11,000-12,000 characters. That used up the whole token budget, so the reply ended with `finish_reason: "length"` and **no answer at all**.

How it showed up:

| Run | Thinking setting sent | Result |
|---|---|---|
| First runs (Oct 11, 17:00-18:15) | nothing at first; `chat_template_kwargs: {"thinking": false}` from 18:04 | Mutator calls of 40-60 s ending in "empty reply (finish_reason='length', ~23,000 characters of reasoning)" |
| Run 2 (Oct 11, evening) | `chat_template_kwargs: {"thinking": false}` | 100 of 186 Mutator calls cut off; cut-off replies used 73% of output tokens and 74% of LLM time |
| Run 3 (Oct 12, morning) | same | 100 of 108 Mutator calls cut off; 94% of output tokens and 91% of LLM time wasted. Stalled at generation 7 |
| Run 4 and later (Oct 12) | `reasoning_effort: "none"` | 0 cut off, 0 hidden reasoning |

Before we found the real switch, Helix worked around it in several ways, all still in `llm.py` and `run.py`:

- per-role output limits (program engine: Mutator and Coder 4,000 tokens, Researcher 6,000; feature engine: Mutator and Coder 3,000, Researcher 6,000), so a stuck call fails fast;
- `think_limit`: a streamed reply that has produced only hidden reasoning past a set length (8,000 characters for the Mutator) is closed early and retried;
- code-first and JSON-first prompts, a code-only retry, and salvaging a program or JSON that appears inside the reasoning.

They helped, but only the switch fixed it.

### The probe that found the fix

`luminal_probe` (not in the repo; the results are summarised here) sent the first real Mutator and Researcher prompts of run 3 under twelve request options, three times each. All requests were streamed, with `max_tokens` 3000.

| Option | Mutator answered | Mutator median | Researcher answered |
|---|---|---|---|
| `chat_template_kwargs: {"thinking": false}` (what runs 2 and 3 sent) | 0/3 | 23.1 s, all thinking | 1/3 |
| no extra fields | 0/3 | 22.2 s | 1/3 |
| `chat_template_kwargs: {"enable_thinking": false}` | 0/3 | 22.5 s | 3/3 |
| both template flags false | 0/3 | 23.1 s | 3/3 |
| **`reasoning_effort: "none"`** | **3/3** | **4.8 s, no thinking** | **3/3, 10.3 s** |
| `reasoning_effort: "low"` | 1/3 | 23.2 s | 3/3 |
| `chat_template_kwargs: {"thinking": true}` | 0/3 | 23.2 s | 3/3 |
| prefill the answer (`continue_final_message`) | 0/3 | 24.0 s | 3/3 |
| prefill with DeepSeek's `"prefix": true` | HTTP 400 | - | 3/3 |
| `/no_think` in the system prompt | 0/3 | 23.8 s | 3/3 |
| "Do not think, start with the code" in the user message | 0/3 | 23.7 s | 3/3 |
| temperature 0.2 | 0/3 | 23.6 s | 3/3 |

Conclusions:
- **`reasoning_effort: "none"` is the only option that reliably stops the thinking.** The chat-template flags (`thinking`, `enable_thinking`) are ignored, and so are prompt tricks.
- The Researcher's prompt is longer but invites less deliberation, so it often answered anyway. The Mutator's prompt ("write a better program") almost always triggered long thinking.
- The 400 for `"prefix": true` read: *"prefix is only available when using beta api (set base_url="https://api.deepseek.com/beta")"*. That suggests Luminal passes these requests through to DeepSeek's own API, which would explain why DeepSeek's parameter (`reasoning_effort`) works and vLLM-style template flags don't. This is an inference from the error, not something Luminal has told us.
- In the probe, `reasoning_effort: "none"` was sent together with `chat_template_kwargs: {"thinking": false}`. Helix now sends only `reasoning_effort`, and the next real run confirmed that alone is enough.

## Other things we learned the hard way

- **Stream.** Non-streamed requests that ran past about 20 seconds were cut off on the server side (Oct 11). Streaming keeps the connection alive. `llm.py` handles both and falls back if the server ignores `stream`.
- **503 and 429.** Overload and warm-up came back as 503 ("temporarily unavailable"). Helix retries with backoff (honouring `Retry-After`) and halves the number of calls in flight on each 503/429, adding one back after every 3 successes. Before a run starts, it sends a tiny request until the model answers (up to 15 minutes), so a run doesn't burn generations on a model that isn't up yet.
- **Error details.** Rejections carry `x-reject-reason` and `x-luminal-request-id` headers. Helix puts both in the error message; quote the request id if you contact Luminal support.
- **macOS SSL.** Python from python.org on macOS ships without root certificates, so HTTPS fails with `CERTIFICATE_VERIFY_FAILED`. Helix uses the `certifi` bundle (it's in `helix/requirements.txt`).
- **`max_tokens` includes hidden thinking.** With thinking on, a 3,000-token budget was spent entirely on thinking.
- **Usage numbers.** Streamed replies don't always include `usage`; Helix then estimates tokens as characters ÷ 4.
- **Errors mid-stream.** An `error` object inside the stream is treated like a dropped connection and retried.

## Checking that it still works

| Command | What it tells you |
|---|---|
| `python -m helix.llm` | One tiny request: does the key work, how fast, does it return reasoning |
| `python -m helix.diagnose` | The real Mutator prompt sent four ways at once (streamed, not streamed, `reasoning_effort` low and none), with time, reasoning length and whether code came back |
| dashboard, **Connect → Test model** | Same as `python -m helix.llm` |
| `python -m helix.analyze helix/runs/<run>` | Per role: calls, errors, median seconds, cut-off replies, and how many returned hidden reasoning. If "cut off" or "thinking" is not 0, the switch has stopped working |

Every call is logged in the run's `llm_calls.jsonl`: the prompt, the reply, any hidden reasoning, tokens, seconds, `finish` (`stop`, `length`, or `thinking` when Helix closed it early) and the request settings.

## What we don't know

- ~~**Whether thinking would make the agents better.**~~ *Probed 2026-10-14:* `reasoning_effort` `low` and `medium` (with a large `max_tokens`, streamed and not) both come back as `service_unavailable` after ≈20 s — the thinking tier is not servable on this deployment right now, so `none` is the only usable mode. The question above stays open until that changes; `HELIX_THINKING=on` is how to retry it.
- ~~**Rate limits, quotas and prices.**~~ *Probed 2026-10-14:* 8 parallel calls fine; at 16 parallel small calls, 6 of 16 returned `rate limit exceeded` at ≈1.6 s. So the free ceiling sits between 8 and 16 concurrent; Helix's adaptive backoff in `llm.py` (halve in-flight on 429/5xx) covers bursts. Prices still unknown.
- **Official documentation for the text API.** We didn't find any. The GitHub repository `luminal-ai/luminal` documents Luminal's inference compiler, not the hosted API. The one Luminal document we had covers the Images API (`https://images.luminal.cloud`, Ideogram 4.5), which uses the same keys and prepaid wallet.
- ~~**Other models.**~~ *Probed 2026-10-14:* `/v1/models` lists only `deepseek-ai/DeepSeek-V4.1-Flash`. A "Pro" model is still not available, so `--pro-every` has never actually been used.
- **Parameter edges** *probed 2026-10-14:* `temperature` ∈ [0, 2] (2.5 → 400); `max_tokens` ∈ [1, 393216] (0 and −5 → 400); unknown extra fields are ignored, not rejected; a 10,000-character system prompt is fine; an empty user message is fine.
- **Whether the ~20 s non-streaming cutoff still exists.** Helix streams, so we never re-checked.
- **The LLM Gateway route** in `helix/.env.example` (`https://api.llmgateway.io/v1`, model `luminal/deepseek-v4.1-flash`) came from the hackathon setup notes and was never tested.
