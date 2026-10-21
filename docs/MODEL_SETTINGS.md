# Model settings that work (and where they came from)

All Helix runs since v3 use one model through Luminal: **DeepSeek V4.1 Flash** (`deepseek-ai/DeepSeek-V4.1-Flash`,
`helix3/llm.py`, `helix4/llm.py`), with four API keys pooled.

| Role | Thinking (`reasoning_effort`) | Temperature | Why |
|---|---|---|---|
| Researcher / planner (v3, v4, v4.5, v5) | **low** | 0.7 | The v3 ablation (`docs/WORKLOG.md`, October 20: the open-suite job) compared none, low (with and without periodic high-effort generations) and high: low did best or tied, at a fraction of high's time. |
| Coder, Mutator | none | 0.5 / 0.8 | A low-thinking code call took 6.4 minutes in a probe (October 20); without thinking, 3-5 s. Many cheap samples beat a few slow ones. |
| Distiller, Navigator, Compactor (v4), lookups and reviews (v5) | none (reviews: low) | 0.3-0.4 | Bookkeeping, not invention. |

Other settings that matter:
- **Token room for thinking**: the client adds 12,000 tokens for "low" on top of the answer's budget, and doubles once
  if a reply is cut off (`helix4/llm.py` fixes v3's handling of "thought until the limit, wrote nothing"). The
  planner gets 12,000 answer tokens.
- **Thinking time cap**: a thinking call that runs past 600 s is retried without thinking.
- **Rate limits**: per key about 13 simultaneous and about 60 per minute; the client stays under both (6 at once, a
  bucket of 45 refilling at 0.85/s). Nine runs side by side on four keys produced no errors (October 20).
- **What "seed" means** (s1, s2, s3): only the random seed of the wide loop's parent sampling. Every run starts from
  the same Code Zero; model sampling is not seeded. Seeds are replicates, not head starts.
