# Results

Each folder is one run of the two-loop search, published from `helix/runs/` by `python -m helix.publish`.
Scores are −(mean excess % over the lower bound): higher is better, 0 would be perfect. The held-out score uses the evaluator's `test` split, which the search never sees.

Gap closed = share of the gap between Code Zero and an offline packer that sees every job in advance (`python -m helix.reference`) that the best program has closed.

Progress to optimal: 0% = Code Zero, 100% = the optimal packing (`helix/bounds.py`).

| Run | Mode | Model | Generations | Code Zero | Best (train) | Gain | Gap closed | Progress to optimal | Best (held-out) | LLM calls | State |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [20261011-185558-full](20261011-185558-full/) | full | deepseek-ai/DeepSeek-V4.1-Flash | 30 | -9.181 | -6.793 | +2.388 | — | — | -6.755 | 423 | finished |
| [20261012-080715-full](20261012-080715-full/) | full | deepseek-ai/DeepSeek-V4.1-Flash | 17 | -9.181 | -7.511 | +1.670 | 47% | 19% | -7.161 | 273 | stopped |
| [20261012-124038-full](20261012-124038-full/) | full | deepseek-ai/DeepSeek-V4.1-Flash | 10 | -9.181 | -6.185 | +2.996 | 84% | 34% | -5.971 | 95 | finished |
| [20261012-134507-full](20261012-134507-full/) | full | deepseek-ai/DeepSeek-V4.1-Flash | 10 | -9.181 | -6.986 | +2.195 | 62% | 25% | -6.703 | 99 | finished |
| [20261014-042737-full](20261014-042737-full/) | full | deepseek-ai/DeepSeek-V4.1-Flash | 10 | -9.181 | -7.034 | +2.147 | 60% | 25% | -6.686 | 92 | finished |
| [20261014-051542-full](20261014-051542-full/) | full | deepseek-ai/DeepSeek-V4.1-Flash | 25 | -9.181 | -6.156 | +3.026 | 85% | 35% | -6.001 | 238 | finished |
| [20261017-014858-full](20261017-014858-full/) | full | deepseek-ai/DeepSeek-V4.1-Flash | 5 | -9.181 | -6.774 | +2.407 | 68% | 27% | -6.645 | 46 | finished |

In each folder: `report.md` (held-out check, where improvements came from, research log), `progress.png`, `best_program.py`, the full trace as JSONL, and every agent call in `llm_calls.jsonl.gz`.
