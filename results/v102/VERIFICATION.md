# Verification of the Helix v10.2 jobs' constructions

Every best construction re-scored independently (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), EinsteinArena's verifier (as its API publishes it) and exact rational arithmetic. Digits are truncated, not rounded. The best published value with n <= 50,000 steps is 0.961021 (AlphaEvolve V2); the published LLM-driven systems' values: results/v102/COMPARISON.md.

| Construction | Steps | Helix | DeepMind's code | Arena's code | Exact | All agree | Against AlphaEvolve V2 |
|---|---|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True | -6.474e-02 |
| v102-helix | 50000 | 0.948610408760 | 0.948610408760 | 0.948610408760 | 0.948610407407 | True | -1.241e-02 |
| v102-helix-s2 | 49998 | 0.941244146241 | 0.941244146241 | 0.941244146241 | 0.941244144332 | True | -1.978e-02 |
