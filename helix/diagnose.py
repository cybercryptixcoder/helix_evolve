"""Check that real-sized requests work, and how fast they are.

  python -m helix.diagnose

Sends the real Mutator prompt a few ways at once (streamed, non-streamed, and with two
common switches that make reasoning models think less) and prints the outcome, time and
amount of reasoning for each. Paste the output when asking for help.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from . import roles
from .llm import LLM, Settings
from .sandbox import REPO_ROOT


def probe(settings, label, system, user, **changes):
    s = replace(settings, retries=0, **{k: v for k, v in changes.items() if k != "extra"})
    if "extra" in changes:
        s = replace(s, extra_body={**settings.extra_body, **changes["extra"]})
    started = time.time()
    try:
        r = LLM(s).chat("diagnose", system, user, temperature=1.0, force_tier="flash")
        has_code = "def priority" in r.text
        return (f"{label:58s} OK   {time.time() - started:5.1f}s  {r.tokens_out:,} tokens out, "
                f"{len(r.reasoning):,} chars reasoning, code {'yes' if has_code else 'NO'}")
    except Exception as exc:
        return f"{label:58s} FAIL {time.time() - started:5.1f}s  {str(exc)[:260]}"


def main():
    s = Settings.from_env()
    print(f"endpoint {s.base_url} | model {s.flash_model} | key ...{s.api_key[-4:]} | "
          f"stream {s.stream} | max_tokens {s.max_tokens} | extra {s.extra_body or '-'}\n", flush=True)
    system = roles.system_prompt("mutator")
    code = (REPO_ROOT / "programs" / "code_zero.py").read_text()
    user = roles.mutator_message(roles.Scored(code, -9.181), [])
    tests = [
        ("1. real prompt, streamed (what runs use now)", {}),
        ("2. real prompt, NOT streamed (the old way)", {"stream": False}),
        ("3. streamed + reasoning_effort low", {"extra": {"reasoning_effort": "low"}}),
        ("4. streamed + thinking off (chat_template_kwargs)", {"extra": {"chat_template_kwargs": {"thinking": False}}}),
    ]
    print("Sending 4 real-sized requests at once (up to a few minutes)...\n", flush=True)
    with ThreadPoolExecutor(len(tests)) as ex:
        for line in ex.map(lambda t: probe(s, t[0], system, user, **t[1]), tests):
            print(line, flush=True)


if __name__ == "__main__":
    main()
