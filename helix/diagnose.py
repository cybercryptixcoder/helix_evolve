"""Find out which kind of request the model rejects.

  python -m helix.diagnose

Sends a handful of single requests that differ in one thing at a time (prompt length,
temperature, max_tokens, then a few at once) and prints the outcome of each.
Paste the output when asking for help.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from . import roles
from .llm import LLM, Settings
from .sandbox import REPO_ROOT

TINY = "Reply with the single word: ready"


def probe(settings, label, system, user, temperature, max_tokens):
    llm = LLM(replace(settings, retries=0, timeout=180, max_tokens=max_tokens))
    started = time.time()
    try:
        r = llm.chat("diagnose", system, user, temperature=temperature, force_tier="flash")
        out = f"OK   {time.time() - started:5.1f}s  {r.tokens_in} in / {r.tokens_out} out"
    except Exception as exc:
        out = f"FAIL {time.time() - started:5.1f}s  {str(exc)[:300]}"
    print(f"{label:52s} {out}", flush=True)
    return out.startswith("OK")


def main():
    s = Settings.from_env()
    print(f"endpoint {s.base_url} | model {s.flash_model} | key ...{s.api_key[-4:]}\n", flush=True)
    real_system = roles.system_prompt("mutator")
    code = (REPO_ROOT / "programs" / "code_zero.py").read_text()
    real_user = roles.mutator_message(roles.Scored(code, -9.181), [])
    print(f"(the real Mutator prompt is {len(real_system) + len(real_user):,} characters)\n")
    probe(s, "1. tiny prompt, temp 0, max_tokens 8000 (= Test)", "You are terse.", TINY, 0, 8000)
    probe(s, "2. tiny prompt, temp 1.0", "You are terse.", TINY, 1.0, 8000)
    probe(s, "3. tiny prompt, max_tokens 2000", "You are terse.", TINY, 0, 2000)
    probe(s, "4. real Mutator prompt, temp 0, max_tokens 2000", real_system, real_user, 0, 2000)
    probe(s, "5. real Mutator prompt, temp 0, max_tokens 8000", real_system, real_user, 0, 8000)
    probe(s, "6. real Mutator prompt, temp 1.0, max_tokens 4000", real_system, real_user, 1.0, 4000)
    print("\n7. three tiny requests at once:", flush=True)
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(lambda i: probe(s, f"   request {i + 1}", "You are terse.", TINY, 0, 2000), range(3)))


if __name__ == "__main__":
    main()
